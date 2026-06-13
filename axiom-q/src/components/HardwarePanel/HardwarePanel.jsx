import { Atom, Cpu, SlidersHorizontal, ThermometerSun, Waves } from "lucide-react";
import useQuantumStore from "../../store/useQuantumStore";
import { SkeletonRow } from "../ui/Skeleton";

function QubitGrid() {
  const selectedQubit = useQuantumStore((s) => s.selectedQubit);
  const selectQubit = useQuantumStore((s) => s.selectQubit);
  const systemStatus = useQuantumStore((s) => s.system_status);
  const qubits = useQuantumStore((s) => s.qubits);
  const loaded = useQuantumStore((s) => s.qubits_loaded);
  const qubitsError = useQuantumStore((s) => s.qubits_error);

  if (!loaded) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-neon-cyan/70">
          <Cpu size={14} />
          <span>Qubit Register</span>
       </div>
        <div className="grid grid-cols-4 gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonRow key={i} />
          ))}
       </div>
     </div>
    );
  }

  if (qubitsError) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-red-400/70">
          <Cpu size={14} />
          <span>Qubit Register</span>
       </div>
        <p className="text-[10px] font-mono text-red-400 bg-red-500/5 border border-red-500/20 rounded p-2">
          {qubitsError}
       </p>
     </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-neon-cyan/70">
        <Cpu size={14} />
        <span>Qubit Register</span>
     </div>
      <div className="grid grid-cols-4 gap-2">
        {qubits.map((q, i) => {
          const active = i === selectedQubit;
          return (
            <button
              key={q._id || q.label}
              onClick={() => selectQubit(i)}
              disabled={systemStatus === "CALIBRATING"}
              className={`
                relative flex flex-col items-center justify-center rounded-lg p-2
                border text-xs font-mono font-bold transition-all duration-200
                ${active
                  ? "bg-neon-cyan/10 border-neon-cyan/50 text-neon-cyan glow-cyan"
                  : "bg-surface-sunken/60 border-border-subtle text-slate-400 hover:border-slate-500 hover:text-slate-200"
                }
                disabled:opacity-40 disabled:cursor-not-allowed
              `}
            >
              <Atom size={16} className={active ? "text-neon-cyan" : "text-slate-500"} />
              <span className="mt-1">{q.label}</span>
              {active && (
                <span className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-neon-cyan animate-pulse" />
              )}
           </button>
          );
        })}
     </div>
   </div>
  );
}

function NoiseSlider({ icon: Icon, label, value, onChange, disabled, color = "cyan" }) {
  const colorMap = {
    cyan: "accent-[#00f0ff]",
    green: "accent-[#39ff14]",
    amber: "accent-[#f59e0b]",
    purple: "accent-[#a855f7]",
  };
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 text-slate-300">
          <Icon size={13} className="text-slate-500" />
          {label}
       </span>
        <span className="font-mono text-neon-cyan">{value.toFixed(2)}</span>
     </div>
      <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className={`w-full h-1.5 rounded-full cursor-pointer appearance-none bg-surface-sunken
          [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:w-3.5
          [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-0
          [&::-webkit-slider-thumb]:bg-neon-cyan [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(0,240,255,0.5)]
          disabled:opacity-50 disabled:cursor-not-allowed
          ${colorMap[color]}`}
      />
   </div>
  );
}

function CalibrateButton() {
  const systemStatus = useQuantumStore((s) => s.system_status);
  const startCalibration = useQuantumStore((s) => s.startCalibration);
  const qubits = useQuantumStore((s) => s.qubits);

  const isCalibrating = systemStatus === "CALIBRATING";
  const isCalibrated = systemStatus === "CALIBRATED";
  const noQubits = qubits.length === 0;

  return (
    <button
      onClick={startCalibration}
      disabled={isCalibrating || noQubits}
      title={noQubits ? "Waiting for qubits to load from backend..." : ""}
      className={`
        w-full relative flex items-center justify-center gap-2 py-3 px-4
        rounded-xl font-bold text-sm uppercase tracking-widest
        border transition-all duration-300
        ${isCalibrating
          ? "bg-neon-amber/10 border-neon-amber/40 text-neon-amber glow-amber cursor-wait"
          : isCalibrated
            ? "bg-neon-green/10 border-neon-green/40 text-neon-green glow-green"
            : noQubits
              ? "bg-surface-sunken border-border-subtle text-slate-500 cursor-not-allowed"
              : "bg-neon-cyan/10 border-neon-cyan/40 text-neon-cyan animate-pulse-glow hover:brightness-125"
        }
      `}
    >
      {isCalibrating && (
        <span className="inline-block h-4 w-4 rounded-full border-2 border-neon-amber border-t-transparent animate-spin" />
      )}
      {isCalibrated && <Atom size={16} className="text-neon-green" />}
      {!isCalibrating && !isCalibrated && <Waves size={16} />}
      <span>
        {isCalibrating
          ? "Autonomous Calibration Running…"
          : isCalibrated
            ? "Calibration Complete — Re-run?"
            : noQubits
              ? "Loading Qubits..."
              : "Run Autonomous Calibration"}
     </span>
   </button>
  );
}

export default function HardwarePanel() {
  const noise = useQuantumStore((s) => s.noise);
  const setNoise = useQuantumStore((s) => s.setNoise);
  const qubitState = useQuantumStore((s) => s.qubit_state);
  const systemStatus = useQuantumStore((s) => s.system_status);

  return (
    <div className="flex flex-col gap-5 h-full">
      <div className="flex items-center gap-2">
        <SlidersHorizontal size={18} className="text-neon-cyan" />
        <h2 className="text-base font-bold tracking-tight text-slate-100">
          Hardware Controls
       </h2>
     </div>

      <QubitGrid />

      <div className="rounded-lg border border-border-subtle bg-surface-sunken/60 p-3 space-y-1.5">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          Active Qubit Parameters
       </p>
        <div className="grid grid-cols-3 gap-2 text-xs font-mono">
          <div className="flex flex-col">
            <span className="text-slate-500 text-[10px]">Freq</span>
            <span className="text-neon-cyan">{qubitState.frequency.toFixed(2)} GHz</span>
         </div>
          <div className="flex flex-col">
            <span className="text-slate-500 text-[10px]">Amp</span>
            <span className="text-neon-cyan">{qubitState.amplitude.toFixed(3)}</span>
         </div>
          <div className="flex flex-col">
            <span className="text-slate-500 text-[10px]">T₁</span>
            <span className="text-neon-cyan">{qubitState.t1_decay_value} µs</span>
         </div>
       </div>
     </div>

      <div className="space-y-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          Noise Channel Injection
       </p>
        <NoiseSlider
          icon={ThermometerSun}
          label="T1 Thermal Relaxation"
          value={noise.t1_thermal}
          onChange={(v) => setNoise("t1_thermal", v)}
          disabled={systemStatus === "CALIBRATING"}
          color="cyan"
        />
        <NoiseSlider
          icon={Waves}
          label="Phase Damping"
          value={noise.phase_damping}
          onChange={(v) => setNoise("phase_damping", v)}
          disabled={systemStatus === "CALIBRATING"}
          color="cyan"
        />
     </div>

      <div className="mt-auto">
        <CalibrateButton />
     </div>
   </div>
  );
}
