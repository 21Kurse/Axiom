import { Atom, Cpu, SlidersHorizontal, ThermometerSun, Waves } from "lucide-react";
import useQuantumStore from "../../store/useQuantumStore";
import { SkeletonRow } from "../ui/Skeleton";

const MOCK_METRICS = [
  "T1: 102µs",
  "99.2%",
  "T1: 98µs",
  "99.1%",
  "T1: 110µs",
  "98.8%",
  "T1: 85µs",
  "99.5%",
];

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
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-neon-cyan/70 font-mono">
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
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-red-400/70 font-mono">
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
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-neon-cyan/70 font-mono">
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
                relative flex flex-col items-center justify-center rounded-sm p-2 pt-3
                border text-xs font-mono font-bold transition-all duration-200
                ${
                  active
                    ? "bg-[#111827] border-2 border-[#00F0FF] text-[#00F0FF] shadow-[0_0_10px_rgba(0,240,255,0.4)]"
                    : "bg-surface-sunken/60 border-border-subtle text-slate-400 hover:border-slate-500 hover:text-slate-200"
                }
                disabled:opacity-40 disabled:cursor-not-allowed
              `}
            >
              <Atom size={16} className={active ? "text-[#00F0FF]" : "text-slate-500"} />
              <span className="mt-1">Q{i}</span>
              <span className="text-[9px] font-mono text-slate-500 mt-0.5 leading-none">
                {MOCK_METRICS[i]}
             </span>
           </button>
          );
        })}
     </div>
   </div>
  );
}

function NoiseSlider({ icon: Icon, label, value, onChange, disabled }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 text-slate-300 font-mono">
          <Icon size={13} className="text-slate-500" />
          {label}
       </span>
        <span className="font-mono text-[#b8c5d1]">{value.toFixed(2)}</span>
     </div>
      <div className="relative h-3 flex items-center">
        <div className="absolute w-full h-[2px] bg-[rgba(255,255,255,0.08)] rounded-full pointer-events-none" />
        <div
          className="absolute h-[2px] bg-[#b8c5d1] rounded-full pointer-events-none"
          style={{ width: `${value * 100}%` }}
        />
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="absolute w-full h-full opacity-0 cursor-pointer z-10"
        />
     </div>
   </div>
  );
}

export default function HardwarePanel() {
  const noise = useQuantumStore((s) => s.noise);
  const setNoise = useQuantumStore((s) => s.setNoise);
  const qubitState = useQuantumStore((s) => s.qubit_state);
  const systemStatus = useQuantumStore((s) => s.system_status);
  const hardwareDrift = useQuantumStore((s) => s.hardware_drift);
  const setHardwareDrift = useQuantumStore((s) => s.setHardwareDrift);

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center gap-2">
        <SlidersHorizontal size={18} className="text-neon-cyan" />
        <h2 className="text-base font-bold tracking-tight text-slate-100 font-sans">
          Hardware Controls
       </h2>
     </div>

      <QubitGrid />

      <div className="rounded-lg border border-border-subtle bg-surface-sunken/60 p-2.5 space-y-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 font-mono">
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

      <div className="space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 font-mono">
          Noise Channel Injection
       </p>
        <NoiseSlider
          icon={ThermometerSun}
          label="T1 Thermal Relaxation"
          value={noise.t1_thermal}
          onChange={(v) => setNoise("t1_thermal", v)}
          disabled={systemStatus === "CALIBRATING"}
        />
        <NoiseSlider
          icon={Waves}
          label="Phase Damping"
          value={noise.phase_damping}
          onChange={(v) => setNoise("phase_damping", v)}
          disabled={systemStatus === "CALIBRATING"}
        />
        <NoiseSlider
          icon={Waves}
          label="Hardware Drift (Δω MHz)"
          value={hardwareDrift}
          onChange={(v) => setHardwareDrift(v)}
          disabled={systemStatus === "CALIBRATING"}
        />
     </div>
   </div>
  );
}
