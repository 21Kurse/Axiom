import { Activity, Box } from "lucide-react";
import { useMemo, useEffect, useRef } from "react";
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

// Must match backend quantum_engine.py DRIFT_SCALE
const DRIFT_SCALE = 0.02; // rad/µs per MHz of drift

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
    const pulse_amp_mod_base = 1.0; // matches backend default, not qubitState.amplitude

    // Environmental Noise (Must NOT be zeroed out)
    const t1_thermal = noise.t1_thermal;
    const phase_damping = noise.phase_damping;

    // Sliders & Corrections
    const drift_mhz = hardwareDrift;
    const drift_compensation_mhz = corrections.drift_compensation_mhz || 0.0;
    const pi_pulse_amp_offset = corrections.pi_pulse_amp_offset || 0.0;

    // Calculate effective physical variables
    // Apply DRIFT_SCALE to convert MHz → angular frequency (matches backend)
    const delta_omega = (drift_mhz - drift_compensation_mhz) * DRIFT_SCALE;
    const omega_drive = omega_0 - delta_omega;
    const A = pulse_amp_mod_base + pi_pulse_amp_offset;
    const T1_us = Math.max(0.1, (1 - t1_thermal) * 100);
    const noise_floor = phase_damping * 0.15;

    // Qiskit telemetry data (50 points from backend simulation)
    const qiskitData = telemetry.noisy || [];
    const qiskitLen = qiskitData.length;

    const data = [];
    for (let i = 0; i < POINTS; i++) {
      const t = (i / POINTS) * DURATION;

      // Target/Ideal analytical wave
      const ideal = pulse_amp_mod_base * Math.sin(omega_0 * t);

      // P1(t) = A * sin((Ω_0 - Δω) * t) * e^(-t / T1) + Noise_Floor
      const envelope = Math.exp(-t / T1_us);
      let real = A * Math.sin(omega_drive * t) * envelope + noise_floor;

      // Map Qiskit data point to this time index
      const qiskitIdx = Math.round((i / POINTS) * qiskitLen);
      const Qiskit = qiskitLen > 0 && qiskitIdx < qiskitLen
        ? parseFloat(qiskitData[qiskitIdx].toFixed(3))
        : undefined;

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
  ]);

  const hasQiskitData = telemetry.noisy && telemetry.noisy.length > 0;

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
                tick={{ fill: "#9CA3AF", fontSize: 10, fontFamily: "var(--font-mono)" }}
                axisLine={{ stroke: "rgba(255,255,255,0.10)" }}
                tickLine={false}
              />
              <YAxis
                domain={[-1.2, 1.2]}
                tick={{ fill: "#64748b", fontSize: 10, fontFamily: "var(--font-mono)" }}
                axisLine={{ stroke: "rgba(255,255,255,0.10)" }}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  border: "1px solid #1e293b",
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
            <span className="text-[10px] font-mono text-slate-400">LIVE_READOUT</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-4 border-t-[2px] border-dashed border-[#A855F7] inline-block" />
            <span className="text-[10px] font-mono text-slate-400">TARGET_WAVE</span>
          </div>
          {hasQiskitData && (
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-[2px] bg-[#39ff14] inline-block" />
              <span className="text-[10px] font-mono text-slate-400">QISKIT_SIM</span>
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
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0.8 });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.5, 0.5, 1);
  return sprite;
}

function BlochSphereCard() {
  const qubitState = useQuantumStore((s) => s.qubit_state);
  const canvasRef = useRef(null);
  // Store computed state label for display
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

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
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

    // Axis labels
    const xLabel = createTextSprite("X");
    xLabel.position.set(1.4, 0, 0);
    scene.add(xLabel);
    const yLabel = createTextSprite("Y");
    yLabel.position.set(0, 1.4, 0);
    scene.add(yLabel);
    const zLabel = createTextSprite("Z");
    zLabel.position.set(0, 0, 1.4);
    scene.add(zLabel);

    // Depth grid / bounding box
    const gridHelper = new THREE.GridHelper(2.4, 12, 0xffffff, 0xffffff);
    gridHelper.material.opacity = 0.04;
    gridHelper.material.transparent = true;
    gridHelper.position.y = -0.5;
    scene.add(gridHelper);

    const boxGeo = new THREE.BoxGeometry(2.2, 2.2, 2.2);
    const boxMat = new THREE.MeshBasicMaterial({
      color: 0x111827,
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
      const driftCompensation = isCalibrated ? corrections.drift_compensation_mhz || 0 : 0;
      const piPulseOffset = isCalibrated ? corrections.pi_pulse_amp_offset || 0 : 0;

      const theta0 = (qState.amplitude + piPulseOffset) * Math.PI;
      const currentDrift = state.hardware_drift || 0.0;
      // phi0 incorporates drift with DRIFT_SCALE (matches backend)
      const residualDrift = (currentDrift - driftCompensation) * DRIFT_SCALE;
      const phi0 = ((qState.frequency - residualDrift) - 4.8) * 10 * Math.PI;

      // Environmental Noise parameters
      const t1Factor = noise.t1_thermal;
      const pd = noise.phase_damping;

      // Bloch vector before noise
      let y_p = Math.cos(theta0);
      let x_p = Math.sin(theta0) * Math.cos(phi0);
      let z_p = Math.sin(theta0) * Math.sin(phi0);

      // T1 Relaxation: exponential decay toward ground state |0> (Y-axis north pole)
      // Physical: ⟨σ⟩(t) = 1 - (1 - ⟨σ⟩₀) * e^(-t/T1)
      // Using t1Factor as the relaxation rate constant
      const t1DecayRate = 3.0 * t1Factor; // scale factor for visible effect
      const t1Decay = 1 - Math.exp(-t1DecayRate);
      y_p = 1 - (1 - y_p) * (1 - t1Decay); // relax toward y=+1
      x_p = x_p * Math.exp(-t1DecayRate);
      z_p = z_p * Math.exp(-t1DecayRate);

      // Calculate wobble magnitude proportionately to the error terms
      const driftMagnitude = Math.abs((currentDrift - driftCompensation) * DRIFT_SCALE);
      const wobbleMag = (driftMagnitude * 2) + (pd * 0.3);

      const time = Date.now() * 0.002;
      x_p += Math.sin(time) * wobbleMag;
      z_p += Math.cos(time * 1.5) * wobbleMag;

      const vector = new THREE.Vector3(x_p, y_p, z_p);
      const length = Math.max(vector.length(), 0.001);
      vector.normalize();

      // Derive dynamic state label from the Bloch vector's quantization-axis projection
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
        <canvas ref={canvasRef} className="w-full h-full z-10" style={{ display: "block" }} />
      </div>

      <div className="flex justify-around px-4 py-1.5 text-[10px] font-mono border-t border-border-subtle">
        <span className="text-slate-500">
          θ <span className="text-neon-cyan">{(qubitState.amplitude * 180).toFixed(1)}°</span>
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
    </div>
  );
}
