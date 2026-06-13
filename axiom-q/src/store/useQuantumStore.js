import { create } from "zustand";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/telemetry";

let ws = null;

const sendWebSocketMessage = (state, nextNoise = null, nextQubitIndex = null) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const noise = nextNoise || state.noise;
    const qubitId = `Q${nextQubitIndex !== null ? nextQubitIndex : state.selectedQubit}`;
    ws.send(
      JSON.stringify({
        qubit_id: qubitId,
        t1_relaxation: noise.t1_thermal,
        phase_damping: noise.phase_damping,
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
        const q = qubits[0];
        set({
          qubits,
          qubits_loaded: true,
          qubits_error: null,
          selectedQubit: 0,
          qubit_state: {
            frequency: q.frequency,
            amplitude: q.amplitude,
            t1_decay_value: q.t1_decay,
          },
          ai_console_logs: [{ ts: Date.now(), msg: "> System online. Qubit register loaded from backend." }],
        });
      } else {
        set({
          qubits_error: data.detail || data.reason || "Unknown error fetching qubits",
          qubits_loaded: true,
          ai_console_logs: [{ ts: Date.now(), msg: `> Error loading qubits: ${data.detail || data.reason || "Unknown"}` }],
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

  selectQubit: (index) =>
    set((state) => {
      const q = state.qubits[index];
      if (!q) return {};
      sendWebSocketMessage(state, null, index);
      return {
        selectedQubit: index,
        qubit_state: {
          frequency: q.frequency,
          amplitude: q.amplitude,
          t1_decay_value: q.t1_decay,
        },
      };
    }),

  setNoise: (key, value) =>
    set((state) => {
      const nextNoise = { ...state.noise, [key]: value };
      sendWebSocketMessage(state, nextNoise);
      return { noise: nextNoise };
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

        // Smoothly reset noise sliders to zero
        const s = get();
        const startT1 = s.noise.t1_thermal;
        const startPd = s.noise.phase_damping;

        let step = 0;
        const steps = 30;
        const resetInterval = setInterval(() => {
          step++;
          const factor = 1 - (step / steps);

          set((state) => ({
            noise: {
              ...state.noise,
              t1_thermal: startT1 * factor,
              phase_damping: startPd * factor,
            }
          }));

          if (step >= steps) {
            clearInterval(resetInterval);
            set((state) => ({
              noise: { ...state.noise, t1_thermal: 0.0, phase_damping: 0.0 }
            }));
            sendWebSocketMessage(get(), { t1_thermal: 0.0, phase_damping: 0.0 });
          }
        }, 16);

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
    set({
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
    }),
}));

export default useQuantumStore;
