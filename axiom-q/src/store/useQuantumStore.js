import { create } from "zustand";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/telemetry";
const PROSTHETIC_WS_URL =
  import.meta.env.VITE_PROSTHETIC_WS_URL || "ws://localhost:8000/ws/prosthetic";

let ws = null;
let prostheticWs = null;

const sendWebSocketMessage = (state, nextNoise = null, nextQubitIndex = null, nextStatus = null, nextCorrections = null) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const noise = nextNoise || state.noise;
    const qubitId = `Q${nextQubitIndex !== null ? nextQubitIndex : state.selectedQubit}`;
    
    const sysStatus = nextStatus !== null ? nextStatus : state.system_status;
    const isCalibrated = sysStatus === "CALIBRATED";
    const corrections = nextCorrections !== null ? nextCorrections : state.agent_payload.correction_variables;
    
    let effective_drift = state.hardware_drift;
    let effective_amp = state.pulse_amp_mod;
    
    if (isCalibrated && corrections) {
      effective_drift -= (corrections.drift_compensation_mhz || 0.0);
      effective_amp += (corrections.pi_pulse_amp_offset || 0.0);
    }

    ws.send(
      JSON.stringify({
        qubit_id: qubitId,
        t1_relaxation: noise.t1_thermal,
        phase_damping: noise.phase_damping,
        hardware_drift: effective_drift,
        pulse_amp_mod: effective_amp,
      })
    );
  }
};

const useQuantumStore = create((set, get) => ({
  /* ── Qubit State ── */
  qubit_state: {
    frequency: 0,
    amplitude: 0,
    t1_decay_value: 0,
  },
  qubits: [],
  qubits_loaded: false,
  qubits_error: null,

  selectedQubit: 0,

  /* ── Noise Channel Parameters ── */
  noise: {
    t1_thermal: 0.25,
    phase_damping: 0.15,
  },

  /* ── Hardware Physics ── */
  hardware_drift: 0.05,         // MHz environmental/hardware drift
  pulse_amp_mod: 1.0,          // unitless pulse amplitude modifier

  /* ── Telemetry Data ── */
  telemetry_data: {
    noisy: [],
    clean: [],
  },

  /* ── System Status ── */
  system_status: "UNCALIBRATED",

  /* ── Backend / Mongo readiness ── */
  backend_health: null,
  backend_health_error: null,

  /* ── AI Console Logs ── */
  ai_console_logs: [],

  /* ── Prosthetic live demo ── */
  prosthetic: {
    pot_value: 0.0,            // current knob position [0, 1]
    threshold: 0.30,           // server-side threshold that fires a cycle
    status: "READY",           // READY | DRIFT_INJECTING | DIAGNOSING | HEALING | ERROR
    cycle_running: false,
    connected: false,
    cells: null,               // last {row, col, kpa, zone}[] payload from server
    cells_phase: null,         // "drifted" | "healing" | "healed"
    cells_frame: 0,
    diagnosis: null,           // { confidence, explanation, affected_cells, cell_corrections, n_corrections }
    last_pot_ts: 0,
  },

  /* ── JSON Payload Inspector ── */
  agent_payload: {
    status: "IDLE",
    correction_variables: {
      drift_compensation_mhz: 0.0,
      pi_pulse_amp_offset: 0.0,
    },
    confidence: null,
    model: "ising-calibration",
  },

  /* ── Actions ── */

  fetchHealth: async () => {
    try {
      const resp = await fetch(`${API_BASE}/`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      set({ backend_health: data, backend_health_error: null });
    } catch (e) {
      set({ backend_health: null, backend_health_error: e.message });
    }
  },

  fetchQubits: async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/qubits`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      if (data.status === "SUCCESS" && data.qubits?.length) {
        const qubits = data.qubits;
        
        set((state) => {
          const isInitialLoad = !state.qubits_loaded;
          const newSelected = isInitialLoad ? 0 : state.selectedQubit;
          const q = qubits[newSelected] || qubits[0];
          
          return {
            qubits,
            qubits_loaded: true,
            qubits_error: null,
            selectedQubit: newSelected,
            qubit_state: {
              frequency: q.frequency,
              amplitude: q.amplitude,
              t1_decay_value: q.t1_decay,
            },
            ...(isInitialLoad && { ai_console_logs: [{ ts: Date.now(), msg: "> System online. Qubit register loaded from backend." }] })
          };
        });
      } else {
        set({
          qubits_error: data.detail || data.reason || "Unknown error fetching qubits",
          qubits_loaded: true,
        });
      }
    } catch (e) {
      set({
        qubits_error: `Failed to fetch qubits: ${e.message}`,
        qubits_loaded: true,
        ai_console_logs: [{ ts: Date.now(), msg: `> Backend connection failed: ${e.message}` }],
      });
    }
  },

  initWebSocket: () => {
    if (ws) return;
    const addLog = (msg) =>
      set((s) => ({ ai_console_logs: [...s.ai_console_logs, { ts: Date.now(), msg }] }));

    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        addLog("> WebSocket connected to backend.");
        sendWebSocketMessage(get());
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "telemetry_update") {
            set((state) => ({
              telemetry_data: {
                ...state.telemetry_data,
                noisy: data.probabilities,
              },
            }));
          } else if (data.event === "error" || data.error) {
            addLog(`> WebSocket error from backend: ${data.error || data.detail || JSON.stringify(data)}`);
          }
        } catch (e) {
          addLog(`> WebSocket parse error: ${e.message}`);
        }
      };
      ws.onerror = () => {
        addLog("> WebSocket connection error.");
      };
      ws.onclose = () => {
        addLog("> WebSocket disconnected. Reconnecting in 3s...");
        ws = null;
        setTimeout(connect, 3000);
      };
    };
    connect();
  },

  selectQubit: async (index) => {
    const state = get();
    const q = state.qubits[index];
    if (!q) return;

    // Send immediate uncalibrated WS update
    sendWebSocketMessage(state, null, index, "UNCALIBRATED", null);

    set({
      selectedQubit: index,
      qubit_state: {
        frequency: q.frequency,
        amplitude: q.amplitude,
        t1_decay_value: q.t1_decay,
      },
      system_status: "UNCALIBRATED",
      telemetry_data: { noisy: [], clean: [] },
      agent_payload: {
        status: "IDLE",
        correction_variables: { drift_compensation_mhz: 0.0, pi_pulse_amp_offset: 0.0 },
        confidence: null,
        model: "ising-calibration",
      },
    });

    try {
      const resp = await fetch(`${API_BASE}/api/v1/telemetry/Q${index}`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.status === "OK" && data.telemetry) {
          const t = data.telemetry;
          if (t.status === "CALIBRATED" && t.corrections) {
            const corrVars = t.corrections.corrections || {};
            const payload = {
              status: "COMPLETE",
              correction_variables: {
                drift_compensation_mhz: corrVars.drift_compensation_mhz ?? 0.0,
                pi_pulse_amp_offset: corrVars.pi_pulse_amp_offset ?? 0.0,
              },
              confidence: t.corrections.confidence ?? null,
              model: "ising-calibration",
            };
            set({
              system_status: "CALIBRATED",
              agent_payload: payload,
            });
            // Update websocket with correct calibrated stream
            sendWebSocketMessage(get());
          }
        }
      }
    } catch (e) {
      // ignore
    }
  },

  setNoise: (key, value) =>
    set((state) => {
      const nextNoise = { ...state.noise, [key]: value };
      sendWebSocketMessage(state, nextNoise);
      return { noise: nextNoise };
    }),

  setHardwareDrift: (value) =>
    set((state) => {
      const next = { ...state, hardware_drift: value };
      sendWebSocketMessage(next);
      return { hardware_drift: value };
    }),

  startCalibration: async () => {
    const state = get();
    if (state.system_status === "CALIBRATING") return;

    set({ system_status: "CALIBRATING" });
    const addLog = (msg) =>
      set((s) => ({
        ai_console_logs: [...s.ai_console_logs, { ts: Date.now(), msg }],
      }));

    const qubitId = `Q${state.selectedQubit}`;
    addLog(`> Initiating calibration for ${qubitId}...`);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000);

      const response = await fetch(`${API_BASE}/api/v1/calibrate/${qubitId}`, {
        method: "POST",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const data = await response.json();

      if (data.status === "SUCCESS") {
        const corrections = data.corrections || {};
        addLog(`> Calibration succeeded. Corrections received.`);
        set({
          system_status: "CALIBRATED",
          agent_payload: {
            status: "COMPLETE",
            correction_variables: {
              drift_compensation_mhz: corrections.drift_compensation_mhz ?? 0.0,
              pi_pulse_amp_offset: corrections.pi_pulse_amp_offset ?? 0.0,
            },
            confidence: data.confidence ?? null,
            model: "ising-calibration",
          },
        });
        sendWebSocketMessage(get());

        addLog("> Calibration complete. Corrections applied.");
        addLog(`> Δf = ${corrections.drift_compensation_mhz ?? 0} MHz | ΔA = ${corrections.pi_pulse_amp_offset ?? 0}`);
      } else {
        const errMsg = data.detail || data.reason || data.message || JSON.stringify(data);
        addLog(`> Calibration error: ${errMsg}`);
        set({
          system_status: "UNCALIBRATED",
          agent_payload: {
            status: "ERROR",
            correction_variables: { drift_compensation_mhz: 0.0, pi_pulse_amp_offset: 0.0 },
            confidence: null,
            model: "ising-calibration",
          },
        });
      }
    } catch (e) {
      const msg = e.name === "AbortError" ? "Request timed out (120s)" : e.message;
      addLog(`> Calibration error: ${msg}`);
      set({
        system_status: "UNCALIBRATED",
        agent_payload: {
          status: "ERROR",
          correction_variables: { drift_compensation_mhz: 0.0, pi_pulse_amp_offset: 0.0 },
          confidence: null,
          model: "ising-calibration",
        },
      });
    }
  },

  resetCalibration: () =>
    set((state) => ({
      system_status: "UNCALIBRATED",
      telemetry_data: { noisy: [], clean: [] },
      ai_console_logs: [
        { ts: Date.now(), msg: "> System reset. Awaiting calibration command..." },
      ],
      agent_payload: {
        status: "IDLE",
        correction_variables: {
          drift_compensation_mhz: 0.0,
          pi_pulse_amp_offset: 0.0,
        },
        confidence: null,
        model: "ising-calibration",
      },
      // NOTE: noise (t1_thermal, phase_damping) and hardware_drift are
      // preserved across reset — they represent real physical environment.
    })),

  /* ── Prosthetic WebSocket + actions ── */

  initProstheticWebSocket: () => {
    if (prostheticWs) return;
    const log = (msg) =>
      set((s) => ({ ai_console_logs: [...s.ai_console_logs, { ts: Date.now(), msg }] }));

    const connect = () => {
      prostheticWs = new WebSocket(PROSTHETIC_WS_URL);
      prostheticWs.onopen = () => {
        log("> Prosthetic WebSocket connected to /ws/prosthetic.");
        set((s) => ({ prosthetic: { ...s.prosthetic, connected: true } }));
      };
      prostheticWs.onmessage = (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch (e) {
          log(`> Prosthetic WS parse error: ${e.message}`);
          return;
        }
        const handle = get()._handleProstheticEvent;
        if (typeof handle === "function") handle(data);
      };
      prostheticWs.onerror = () => {
        log("> Prosthetic WebSocket error.");
      };
      prostheticWs.onclose = () => {
        log("> Prosthetic WebSocket disconnected. Reconnecting in 3s...");
        prostheticWs = null;
        set((s) => ({ prosthetic: { ...s.prosthetic, connected: false } }));
        setTimeout(connect, 3000);
      };
    };
    connect();
  },

  _handleProstheticEvent: (data) => {
    if (!data || data.service !== "prosthetic" && data.type === undefined) return;
    const t = data.type;
    if (t === "status") {
      set((s) => ({
        prosthetic: {
          ...s.prosthetic,
          status: data.phase || s.prosthetic.status,
          cycle_running:
            data.phase === "READY" ? false : s.prosthetic.cycle_running,
          pot_value:
            typeof data.pot_value === "number"
              ? data.pot_value
              : s.prosthetic.pot_value,
          threshold:
            typeof data.threshold === "number"
              ? data.threshold
              : s.prosthetic.threshold,
        },
      }));
    } else if (t === "pot") {
      set((s) => ({
        prosthetic: {
          ...s.prosthetic,
          pot_value: typeof data.value === "number" ? data.value : s.prosthetic.pot_value,
          last_pot_ts: typeof data.ts === "number" ? data.ts : s.prosthetic.last_pot_ts,
        },
      }));
    } else if (t === "cell_state") {
      set((s) => ({
        prosthetic: {
          ...s.prosthetic,
          cells: data.cells || s.prosthetic.cells,
          cells_phase: data.phase || s.prosthetic.cells_phase,
          cells_frame: typeof data.frame === "number" ? data.frame : s.prosthetic.cells_frame,
        },
      }));
    } else if (t === "diagnosis") {
      set((s) => ({
        prosthetic: { ...s.prosthetic, diagnosis: data.data || s.prosthetic.diagnosis },
      }));
    } else if (t === "heatmap") {
      // Just log so the agent panel can show it later if desired.
      const log = (msg) => set((curr) => ({
        ai_console_logs: [...curr.ai_console_logs, { ts: Date.now(), msg }],
      }));
      log(`> Heatmap rendered → ${data.path}`);
    } else if (t === "error") {
      const log = (msg) => set((curr) => ({
        ai_console_logs: [...curr.ai_console_logs, { ts: Date.now(), msg }],
      }));
      log(`> Prosthetic WS error: ${data.error || "unknown"}`);
    }
  },

  sendPotValue: (value) => {
    if (prostheticWs && prostheticWs.readyState === WebSocket.OPEN) {
      const clamped = Math.max(0, Math.min(1, Number(value) || 0));
      prostheticWs.send(
        JSON.stringify({
          type: "pot",
          value: clamped,
          ts: Date.now() / 1000,
        })
      );
      set((s) => ({ prosthetic: { ...s.prosthetic, pot_value: clamped } }));
    }
  },

  resetProstheticCycle: () => {
    if (prostheticWs && prostheticWs.readyState === WebSocket.OPEN) {
      prostheticWs.send(JSON.stringify({ type: "reset" }));
    }
  },
}));

export default useQuantumStore;
