import { Activity, Box, HeartPulse } from "lucide-react";
import { useMemo, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import useQuantumStore from "../../store/useQuantumStore";
import { SkeletonChart } from "../ui/Skeleton";
import ProstheticPot from "../ProstheticPot/ProstheticPot";
import ProstheticMesh from "../ProstheticMesh/ProstheticMesh";

// Must match backend quantum_engine.py DRIFT_SCALE
const DRIFT_SCALE = 0.02; // rad/µs per MHz of drift
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function StatusBadge() {
  const status = useQuantumStore((s) => s.system_status);

  const map = {
    UNCALIBRATED: {
      bg: "bg-neon-amber/10",
      border: "border-neon-amber/40",
      text: "text-neon-amber",
      glow: "glow-amber",
      label: "UNCALIBRATED",
    },
    CALIBRATING: {
      bg: "bg-neon-purple/10",
      border: "border-neon-purple/40",
      text: "text-neon-purple",
      glow: "glow-purple",
      label: "CALIBRATING",
    },
    CALIBRATED: {
      bg: "bg-neon-green/10",
      border: "border-neon-green/40",
      text: "text-neon-green",
      glow: "glow-green",
      label: "CALIBRATED",
    },
  };

  const s = map[status] || map.UNCALIBRATED;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${s.bg} ${s.border} ${s.text} ${s.glow}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === "CALIBRATING" ? "animate-pulse" : ""
        }`}
        style={{ backgroundColor: "currentColor" }}
      />
      {s.label}
   </span>
  );
}

function ProstheticStatusBadge() {
  const status = useQuantumStore((s) => s.prosthetic.status);
  const phase = (status || "READY").toUpperCase();

  const map = {
    READY: {
      bg: "bg-neon-green/10",
      border: "border-neon-green/40",
      text: "text-neon-green",
      glow: "glow-green",
      label: "READY",
    },
    DRIFT_INJECTING: {
      bg: "bg-neon-amber/10",
      border: "border-neon-amber/40",
      text: "text-neon-amber",
      glow: "glow-amber",
      label: "DRIFT_INJECTING",
    },
    DIAGNOSING: {
      bg: "bg-neon-purple/10",
      border: "border-neon-purple/40",
      text: "text-neon-purple",
      glow: "glow-purple",
      label: "DIAGNOSING",
    },
    HEALING: {
      bg: "bg-neon-cyan/10",
      border: "border-neon-cyan/40",
      text: "text-neon-cyan",
      glow: "glow-cyan",
      label: "HEALING",
    },
    ERROR: {
      bg: "bg-neon-red/10",
      border: "border-neon-red/40",
      text: "text-neon-red",
      glow: "glow-red",
      label: "ERROR",
    },
  };

  const s = map[phase] || map.READY;
  const isPulsing = phase === "DRIFT_INJECTING" || phase === "DIAGNOSING";
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${s.bg} ${s.border} ${s.text} ${s.glow}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          isPulsing ? "animate-pulse" : ""
        }`}
        style={{ backgroundColor: "currentColor" }}
      />
      {s.label}
   </span>
  );
}

function ProstheticDiagnosisPanel() {
  const diagnosis = useQuantumStore((s) => s.prosthetic.diagnosis);
  const cellsPhase = useQuantumStore((s) => s.prosthetic.cells_phase);
  const cells = useQuantumStore((s) => s.prosthetic.cells);
  const status = useQuantumStore((s) => s.prosthetic.status);
  const targetMin = useQuantumStore((s) => s.prosthetic.target_pressure_min_kpa);
  const targetMax = useQuantumStore((s) => s.prosthetic.target_pressure_max_kpa);
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    if (!zoomed) return;
    const onKey = (e) => {
      if (e.key === "Escape") setZoomed(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zoomed]);

  if (!diagnosis || !cells) {
    return (
      <div className="text-[9px] font-mono text-slate-600 uppercase tracking-widest leading-snug">
        Drag the lever past the FIRE line to issue a live calibration pulse.
      </div>
    );
  }

  const confidence = (diagnosis.confidence ?? 0) * 100;
  const corrections = diagnosis.cell_corrections || {};
  const n = diagnosis.n_corrections ?? Object.keys(corrections).length;
  const meanKpa = (() => {
    const vals = cells.map((c) => c.kpa);
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  })();

  const heatmapSrc = `${API_BASE}/api/v1/prosthetics/heatmap?t=${status}-${cellsPhase}-${cells[0]?.kpa.toFixed(
    1
  )}`;

  return (
    <div className="flex flex-col gap-1.5 font-mono text-[10px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-slate-400">PHASE</span>
        <span className="text-neon-cyan uppercase">
          {cellsPhase || "—"}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-slate-400">CORRECTIONS</span>
        <span className="text-neon-cyan">{n}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-slate-400">CONFIDENCE</span>
        <span className="text-neon-green">{confidence.toFixed(0)}%</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-slate-400">MEAN kPa</span>
        <span className="text-neon-amber">{meanKpa.toFixed(1)}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-slate-400">TARGET kPa</span>
        <span className="text-neon-cyan">
          {targetMin.toFixed(1)}–{targetMax.toFixed(1)}
        </span>
      </div>
      {diagnosis.explanation && (
        <div className="mt-1 text-slate-500 leading-snug">
          <span className="text-neon-purple">›</span> {diagnosis.explanation}
        </div>
      )}

      {/* Show the actual generated heatmap image in real-time */}
      <button
        type="button"
        onClick={() => setZoomed(true)}
        className="mt-3 block w-full text-left border border-[rgba(255,255,255,0.08)] rounded overflow-hidden bg-slate-950/60 cursor-zoom-in group hover:border-neon-cyan/40 transition-colors"
        aria-label="Expand VLM scan heatmap"
      >
        <div className="bg-[rgba(255,255,255,0.03)] px-2 py-1.5 border-b border-[rgba(255,255,255,0.06)] text-[8px] font-bold text-slate-400 tracking-wider flex items-center justify-between">
          <span>LIVE VLM SCAN HEATMAP</span>
          <span className="text-neon-cyan/70 normal-case font-normal">
            click to expand ⤢
          </span>
        </div>
        <img
          src={heatmapSrc}
          className="w-full h-auto object-cover block transition-opacity group-hover:opacity-80"
          alt="Limb Shift Heatmap"
          onError={(e) => {
            e.target.style.display = "none";
          }}
        />
      </button>

      {zoomed && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 backdrop-blur-sm p-6"
          onClick={() => setZoomed(false)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="relative max-w-[95vw] max-h-[95vh] rounded-lg border border-[rgba(255,255,255,0.12)] bg-[#0a0e14] shadow-2xl overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-[rgba(255,255,255,0.08)]">
              <span className="text-[10px] font-bold font-mono text-slate-300 tracking-wider uppercase">
                VLM Scan Heatmap — Pressure Grid (kPa)
              </span>
              <button
                type="button"
                onClick={() => setZoomed(false)}
                className="text-slate-400 hover:text-neon-red text-sm font-mono px-2 leading-none"
                aria-label="Close heatmap"
              >
                ✕
              </button>
            </div>
            <img
              src={heatmapSrc}
              className="max-w-full max-h-[85vh] object-contain block"
              alt="Limb Shift Heatmap (expanded)"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function ProstheticLiveCard() {
  const connected = useQuantumStore((s) => s.prosthetic.connected);

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-card/80 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-200 font-mono">
          <HeartPulse size={14} className="text-neon-green" />
          Prosthetic Live Demo
       </span>
        <div className="flex items-center gap-2">
          {!connected && (
            <span className="text-[9px] font-mono text-neon-amber uppercase tracking-widest">
              ws_offline
           </span>
          )}
          <ProstheticStatusBadge />
       </div>
     </div>

      <div className="grid grid-cols-[160px_1fr_220px] gap-3 p-3">
        {/* The vertical pot knob */}
        <div className="flex flex-col items-center justify-start pt-2">
          <ProstheticPot />
       </div>

        {/* The 36-cell Three.js mesh */}
        <div className="relative min-h-[280px] bg-surface-sunken/40 rounded-sm overflow-hidden">
          <div
            className="absolute inset-0 opacity-[0.05] pointer-events-none"
            style={{
              backgroundImage:
                "radial-gradient(circle at 50% 50%, rgba(0,240,255,0.6) 0%, transparent 70%)",
            }}
          />
          <ProstheticMesh />
          <div className="absolute top-2 left-2 text-[9px] font-mono text-slate-500 uppercase tracking-widest pointer-events-none">
            36-cell socket mesh
         </div>
          <div className="absolute bottom-2 left-2 flex items-center gap-2 text-[9px] font-mono text-slate-500 pointer-events-none">
            <span className="flex items-center gap-1">
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: "#00ff41" }}
              />
              8 kPa
           </span>
            <span className="flex items-center gap-1">
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: "#ff2e2e" }}
              />
              30 kPa
           </span>
         </div>
       </div>

        {/* Live diagnosis / inspector */}
        <div className="bg-[#121212] rounded-sm border border-[rgba(255,255,255,0.06)] p-3 overflow-auto">
          <div className="text-[9px] font-mono text-slate-500 uppercase tracking-widest mb-2">
            Diagnosis inspector
         </div>
          <ProstheticDiagnosisPanel />
       </div>
     </div>
   </div>
  );
}

function TelemetryCard() {
  const qubitState = useQuantumStore((s) => s.qubit_state);
  const telemetry = useQuantumStore((s) => s.telemetry_data);
  const systemStatus = useQuantumStore((s) => s.system_status);
  const noise = useQuantumStore((s) => s.noise);
  const hardwareDrift = useQuantumStore((s) => s.hardware_drift);
  const corrections = useQuantumStore((s) => s.agent_payload.correction_variables);

  const hasTelemetry = telemetry.noisy && telemetry.noisy.length > 0;

  const chartData = useMemo(() => {
    const POINTS = 150;
    const DURATION = 200;
    const omega_0 = qubitState.frequency || 4.8;
    const pulse_amp_mod_base = 1.0;

    const t1_thermal = noise.t1_thermal;
    const phase_damping = noise.phase_damping;

    const drift_mhz = hardwareDrift;
    const drift_compensation_mhz = corrections.drift_compensation_mhz || 0.0;
    const pi_pulse_amp_offset = corrections.pi_pulse_amp_offset || 0.0;

    const delta_omega = (drift_mhz - drift_compensation_mhz) * DRIFT_SCALE;
    const omega_drive = omega_0 - delta_omega;
    const A = pulse_amp_mod_base + pi_pulse_amp_offset;
    const T1_us = Math.max(0.1, (1 - t1_thermal) * 100);
    const noise_floor = phase_damping * 0.15;

    const qiskitData = telemetry.noisy || [];
    const qiskitLen = qiskitData.length;

    const data = [];
    for (let i = 0; i < POINTS; i++) {
      const t = (i / POINTS) * DURATION;
      
      const theta_base = (t / DURATION) * 4 * Math.PI;
      const ideal_theta = pulse_amp_mod_base * theta_base;
      const ideal = Math.pow(Math.sin(ideal_theta / 2), 2);

      const rabi_ratio = omega_drive / omega_0;
      const effective_theta = A * theta_base * rabi_ratio;
      const envelope = Math.exp(-t / T1_us);
      let real = Math.pow(Math.sin(effective_theta / 2), 2) * envelope + noise_floor;

      let Qiskit;
      if (systemStatus === "CALIBRATED") {
        Qiskit = parseFloat(real.toFixed(3));
      } else {
        const qiskitIdx = Math.round((i / POINTS) * (qiskitLen - 1));
        Qiskit =
          qiskitLen > 0 && qiskitIdx < qiskitLen && qiskitIdx >= 0
            ? parseFloat(qiskitData[qiskitIdx].toFixed(3))
            : undefined;
      }

      data.push({
        time: t.toFixed(1),
        Ideal: parseFloat(ideal.toFixed(3)),
        Real: parseFloat(real.toFixed(3)),
        ...(Qiskit !== undefined && { Qiskit }),
      });
    }
    return data;
  }, [
    qubitState.frequency,
    telemetry.noisy,
    noise.t1_thermal,
    noise.phase_damping,
    hardwareDrift,
    corrections.drift_compensation_mhz,
    corrections.pi_pulse_amp_offset,
    systemStatus,
  ]);

  const hasQiskitData =
    (telemetry.noisy && telemetry.noisy.length > 0) ||
    systemStatus === "CALIBRATED";

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-card/80 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-200 font-mono">
          <Activity size={14} className="text-neon-cyan" />
          Rabi Oscillation Telemetry
       </span>
        <StatusBadge />
     </div>

      <div className="relative w-full h-[280px] bg-surface-sunken/40 pt-2 pb-1 overflow-hidden">
        {systemStatus === "CALIBRATING" && (
          <div className="absolute inset-x-0 h-32 pointer-events-none z-50 animate-scan">
            <div className="w-full h-full bg-gradient-to-b from-transparent to-neon-cyan/20 border-b-2 border-neon-cyan glow-cyan" />
         </div>
        )}
        {hasTelemetry ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="0"
                stroke="rgba(255,255,255,0.06)"
                vertical={true}
                horizontal={true}
              />
              <XAxis
                dataKey="time"
                interval="preserveStartEnd"
                minTickGap={40}
                tick={{
                  fill: "#9CA3AF",
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                }}
                axisLine={{ stroke: "rgba(255,255,255,0.10)" }}
                tickLine={false}
              />
              <YAxis
                domain={[-0.1, 1.1]}
                tick={{
                  fill: "#64748b",
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                }}
                axisLine={{ stroke: "rgba(255,255,255,0.10)" }}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1c1c1c",
                  border: "1px solid #262626",
                  borderRadius: "8px",
                  fontSize: "10px",
                }}
                itemStyle={{ color: "#e2e8f0" }}
              />
              <Line
                type="monotone"
                dataKey="Ideal"
                stroke="#a855f7"
                strokeWidth={1}
                dot={false}
                opacity={0.5}
                strokeDasharray="4 4"
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="Real"
                stroke="#00f0ff"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
              {hasQiskitData && (
                <Line
                  type="monotone"
                  dataKey="Qiskit"
                  stroke="#39ff14"
                  strokeWidth={1.5}
                  dot={{ fill: "#39ff14", r: 1.5 }}
                  isAnimationActive={false}
                  connectNulls
                />
              )}
           </LineChart>
         </ResponsiveContainer>
        ) : (
          <div className="flex flex-col items-center justify-center h-full px-4">
            <SkeletonChart />
            <p className="text-[10px] font-mono text-slate-500 mt-2">
              Awaiting telemetry stream from backend…
           </p>
         </div>
        )}
     </div>

      <div className="flex items-center justify-between px-4 py-1.5 border-t border-border-subtle">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-[2px] bg-[#00F0FF] inline-block" />
            <span className="text-[10px] font-mono text-slate-400">
              LIVE_READOUT
           </span>
         </div>
          <div className="flex items-center gap-1.5">
            <span className="w-4 border-t-[2px] border-dashed border-[#A855F7] inline-block" />
            <span className="text-[10px] font-mono text-slate-400">
              TARGET_WAVE
           </span>
         </div>
          {hasQiskitData && (
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-[2px] bg-[#39ff14] inline-block" />
              <span className="text-[10px] font-mono text-slate-400">
                QISKIT_SIM
             </span>
           </div>
          )}
       </div>
        <span className="text-[9px] font-mono text-slate-600">
          P(e) vs Drive Duration
       </span>
     </div>
   </div>
  );
}

function createTextSprite(text) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = 256;
  canvas.height = 256;
  ctx.font = "bold 60px JetBrains Mono, monospace";
  ctx.fillStyle = "#9CA3AF";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    opacity: 0.8,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.5, 0.5, 1);
  return sprite;
}

function BlochSphereCard() {
  const qubitState = useQuantumStore((s) => s.qubit_state);
  const canvasRef = useRef(null);
  const stateLabelRef = useRef("|0⟩");

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      45,
      canvas.clientWidth / canvas.clientHeight,
      0.1,
      100
    );
    camera.position.set(2, 1.5, 2.5);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
    });
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const sphereGeo = new THREE.SphereGeometry(1, 32, 16);
    const sphereMat = new THREE.MeshBasicMaterial({
      color: 0xa855f7,
      wireframe: true,
      transparent: true,
      opacity: 0.15,
    });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
    scene.add(sphere);

    const equatorGeo = new THREE.RingGeometry(0.98, 1.02, 64);
    const equatorMat = new THREE.MeshBasicMaterial({
      color: 0xa855f7,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.3,
    });
    const equator = new THREE.Mesh(equatorGeo, equatorMat);
    equator.rotation.x = Math.PI / 2;
    scene.add(equator);

    const axesHelper = new THREE.AxesHelper(1.2);
    const colors = axesHelper.geometry.attributes.color;
    colors.setXYZ(0, 1, 0.2, 0.6);
    colors.setXYZ(1, 1, 0.2, 0.6);
    colors.setXYZ(2, 0, 0.9, 1);
    colors.setXYZ(3, 0, 0.9, 1);
    colors.setXYZ(4, 0.6, 0.2, 1);
    colors.setXYZ(5, 0.6, 0.2, 1);
    scene.add(axesHelper);

    const arrowDir = new THREE.Vector3(0, 1, 0);
    const arrowOrigin = new THREE.Vector3(0, 0, 0);
    const arrowHelper = new THREE.ArrowHelper(
      arrowDir,
      arrowOrigin,
      1,
      0x00f0ff,
      0.2,
      0.1
    );
    scene.add(arrowHelper);

    const xLabel = createTextSprite("X");
    xLabel.position.set(1.4, 0, 0);
    scene.add(xLabel);
    const yLabel = createTextSprite("Y");
    yLabel.position.set(0, 1.4, 0);
    scene.add(yLabel);
    const zLabel = createTextSprite("Z");
    zLabel.position.set(0, 0, 1.4);
    scene.add(zLabel);

    const gridHelper = new THREE.GridHelper(2.4, 12, 0xffffff, 0xffffff);
    gridHelper.material.opacity = 0.04;
    gridHelper.material.transparent = true;
    gridHelper.position.y = -0.5;
    scene.add(gridHelper);

    const boxGeo = new THREE.BoxGeometry(2.2, 2.2, 2.2);
    const boxMat = new THREE.MeshBasicMaterial({
      color: 0x111111,
      transparent: true,
      opacity: 0.3,
      wireframe: true,
    });
    const box = new THREE.Mesh(boxGeo, boxMat);
    scene.add(box);

    const glowGeo = new THREE.SphereGeometry(0.06, 16, 16);
    const glowMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
    const glowMesh = new THREE.Mesh(glowGeo, glowMat);
    scene.add(glowMesh);

    let reqId;
    const animate = () => {
      reqId = requestAnimationFrame(animate);
      const state = useQuantumStore.getState();
      const qState = state.qubit_state;
      const noise = state.noise;
      const isCalibrated = state.system_status === "CALIBRATED";

      const corrections = state.agent_payload.correction_variables;
      const driftCompensation = isCalibrated
        ? corrections.drift_compensation_mhz || 0
        : 0;
      const piPulseOffset = isCalibrated
        ? corrections.pi_pulse_amp_offset || 0
        : 0;

      const theta0 = (qState.amplitude + piPulseOffset) * Math.PI;
      const currentDrift = state.hardware_drift || 0.0;
      const residualDrift =
        (currentDrift - driftCompensation) * DRIFT_SCALE;
      const phi0 = ((qState.frequency - residualDrift) - 4.8) * 10 * Math.PI;

      const t1Factor = noise.t1_thermal;
      const pd = noise.phase_damping;

      let y_p = Math.cos(theta0);
      let x_p = Math.sin(theta0) * Math.cos(phi0);
      let z_p = Math.sin(theta0) * Math.sin(phi0);

      const t1DecayRate = 3.0 * t1Factor;
      const t1Decay = 1 - Math.exp(-t1DecayRate);
      y_p = 1 - (1 - y_p) * (1 - t1Decay);
      x_p = x_p * Math.exp(-t1DecayRate);
      z_p = z_p * Math.exp(-t1DecayRate);

      const driftMagnitude = Math.abs(
        (currentDrift - driftCompensation) * DRIFT_SCALE
      );
      const wobbleMag = driftMagnitude * 2 + pd * 0.3;

      const time = Date.now() * 0.002;
      x_p += Math.sin(time) * wobbleMag;
      z_p += Math.cos(time * 1.5) * wobbleMag;

      const vector = new THREE.Vector3(x_p, y_p, z_p);
      const length = Math.max(vector.length(), 0.001);
      vector.normalize();

      if (y_p > 0.5) {
        stateLabelRef.current = "≡ |0⟩";
      } else if (y_p < -0.5) {
        stateLabelRef.current = "≡ |1⟩";
      } else {
        stateLabelRef.current = "≡ |ψ⟩";
      }

      arrowHelper.setDirection(vector);
      arrowHelper.setLength(length, 0.2 * length, 0.1 * length);
      glowMesh.position.copy(vector.clone().multiplyScalar(length));

      scene.rotation.y += 0.001;
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!canvas) return;
      camera.aspect = canvas.clientWidth / canvas.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(reqId);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      sphereGeo.dispose();
      sphereMat.dispose();
      equatorGeo.dispose();
      equatorMat.dispose();
      glowGeo.dispose();
      glowMat.dispose();
      boxGeo.dispose();
      boxMat.dispose();
      gridHelper.dispose();
    };
  }, []);

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-card/80 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-200 font-mono">
          <Box size={14} className="text-neon-purple" />
          Bloch Sphere
       </span>
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
          WebGL
       </span>
     </div>

      <div className="relative flex-1 min-h-[220px] flex items-center justify-center bg-surface-sunken/40">
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 50% 50%, rgba(168, 85, 247, 0.25) 0%, transparent 70%)",
          }}
        />
        <canvas
          ref={canvasRef}
          className="w-full h-full z-10"
          style={{ display: "block" }}
        />
     </div>

      <div className="flex justify-around px-4 py-1.5 text-[10px] font-mono border-t border-border-subtle">
        <span className="text-slate-500">
          θ{" "}
          <span className="text-neon-cyan">
            {(qubitState.amplitude * 180).toFixed(1)}°
         </span>
       </span>
        <span className="text-slate-500">
          φ{" "}
          <span className="text-neon-purple">
            {((qubitState.frequency - 4.8) * 100).toFixed(1)}°
         </span>
       </span>
        <span className="text-slate-500">
          |ψ⟩ <span className="text-neon-green">{stateLabelRef.current}</span>
       </span>
     </div>
   </div>
  );
}

export default function TelemetryPanel() {
  return (
    <div className="flex flex-col gap-3 h-full">
      <TelemetryCard />
      <BlochSphereCard />
      <ProstheticLiveCard />
   </div>
  );
}
