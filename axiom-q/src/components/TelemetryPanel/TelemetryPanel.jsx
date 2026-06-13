import { Activity, Box } from "lucide-react";
import { useMemo, useEffect, useRef } from "react";
import * as THREE from "three";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import useQuantumStore from "../../store/useQuantumStore";
import { SkeletonChart } from "../ui/Skeleton";

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
        className={`h-1.5 w-1.5 rounded-full ${status === "CALIBRATING" ? "animate-pulse" : ""}`}
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

  const hasTelemetry = telemetry.noisy && telemetry.noisy.length > 0;

  const chartData = useMemo(() => {
    const POINTS = 150;
    const DURATION = 200;
    const amplitude = qubitState.amplitude || 1;
    const omega = (4 * 2 * Math.PI) / DURATION;

    const data = [];
    for (let i = 0; i < POINTS; i++) {
      const t = (i / POINTS) * DURATION;
      const ideal = amplitude * Math.sin(omega * t);
      data.push({ time: t.toFixed(1), Ideal: parseFloat(ideal.toFixed(3)) });
    }
    if (hasTelemetry) {
      for (let i = 0; i < telemetry.noisy.length && i < POINTS; i++) {
        const prob = telemetry.noisy[i];
        data[i].Real = parseFloat(((prob - 0.5) * 2 * amplitude).toFixed(3));
      }
    }
    return data;
  }, [qubitState.amplitude, hasTelemetry, telemetry.noisy]);

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-card/80 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-200">
          <Activity size={14} className="text-neon-cyan" />
          Rabi Oscillation Telemetry
       </span>
        <StatusBadge />
     </div>

      <div className="relative w-full h-[220px] bg-surface-sunken/40 pt-4 pb-1 overflow-hidden">
        {systemStatus === "CALIBRATING" && (
          <div className="absolute inset-x-0 h-32 pointer-events-none z-50 animate-scan">
            <div className="w-full h-full bg-gradient-to-b from-transparent to-neon-cyan/20 border-b-2 border-neon-cyan glow-cyan" />
         </div>
        )}
        {hasTelemetry ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="time" hide />
              <YAxis domain={[-1.2, 1.2]} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px", fontSize: "10px" }}
                itemStyle={{ color: "#e2e8f0" }}
              />
              <Line type="monotone" dataKey="Ideal" stroke="#a855f7" strokeWidth={1} dot={false} opacity={0.5} strokeDasharray="4 4" isAnimationActive={false} />
              <Line type="monotone" dataKey="Real" stroke="#00f0ff" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
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

      <div className="flex justify-between px-4 py-1.5 text-[9px] font-mono text-slate-600 border-t border-border-subtle">
        <span>t = 0 µs</span>
        <span className="text-slate-500">P(e) vs Drive Duration</span>
        <span>t = 200 µs</span>
     </div>
   </div>
  );
}

function BlochSphereCard() {
  const qubitState = useQuantumStore((s) => s.qubit_state);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
    camera.position.set(2, 1.5, 2.5);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const sphereGeo = new THREE.SphereGeometry(1, 32, 16);
    const sphereMat = new THREE.MeshBasicMaterial({ color: 0xa855f7, wireframe: true, transparent: true, opacity: 0.15 });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
    scene.add(sphere);

    const equatorGeo = new THREE.RingGeometry(0.98, 1.02, 64);
    const equatorMat = new THREE.MeshBasicMaterial({ color: 0xa855f7, side: THREE.DoubleSide, transparent: true, opacity: 0.3 });
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
    const arrowHelper = new THREE.ArrowHelper(arrowDir, arrowOrigin, 1, 0x00f0ff, 0.2, 0.1);
    scene.add(arrowHelper);

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

      const theta0 = qState.amplitude * Math.PI;
      const phi0 = (qState.frequency - 4.8) * 10 * Math.PI;
      const t1Factor = noise.t1_thermal;

      let y_p = Math.cos(theta0);
      let x_p = Math.sin(theta0) * Math.cos(phi0);
      let z_p = Math.sin(theta0) * Math.sin(phi0);

      y_p = y_p + (1 - y_p) * t1Factor;
      x_p = x_p * (1 - t1Factor);
      z_p = z_p * (1 - t1Factor);

      const pd = noise.phase_damping;
      if (pd > 0) {
        const wobble = (Math.random() - 0.5) * pd * 0.8;
        const currentPhi = Math.atan2(z_p, x_p) + wobble;
        const r_xz = Math.sqrt(x_p * x_p + z_p * z_p);
        x_p = r_xz * Math.cos(currentPhi);
        z_p = r_xz * Math.sin(currentPhi);
      }

      const vector = new THREE.Vector3(x_p, y_p, z_p);
      const length = Math.max(vector.length(), 0.001);
      vector.normalize();

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
    };
  }, []);

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-card/80 overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-200">
          <Box size={14} className="text-neon-purple" />
          Bloch Sphere
       </span>
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">WebGL</span>
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
          φ <span className="text-neon-purple">{((qubitState.frequency - 4.8) * 100).toFixed(1)}°</span>
       </span>
        <span className="text-slate-500">
          |ψ⟩ <span className="text-neon-green">≡ |0⟩</span>
       </span>
     </div>
   </div>
  );
}

export default function TelemetryPanel() {
  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center gap-2">
        <Activity size={18} className="text-neon-cyan" />
        <h2 className="text-base font-bold tracking-tight text-slate-100">Live Telemetry</h2>
     </div>

      <TelemetryCard />
      <BlochSphereCard />
   </div>
  );
}
