import { Zap, Play, RotateCw } from "lucide-react";
import useQuantumStore from "../../store/useQuantumStore";

function StatusIndicator({ label, color = "green" }) {
  const isGreen = color === "green";
  return (
    <div className="flex items-center gap-1.5">
      <span className="relative flex h-2 w-2">
        {isGreen && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00FF41] opacity-75"></span>
        )}
        <span
          className={`relative inline-flex rounded-full h-2 w-2 ${
            isGreen ? "bg-[#00FF41]" : "bg-[#9CA3AF]"
          }`}
        ></span>
      </span>
      <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">
        {label}
      </span>
    </div>
  );
}

function MinimalCalibrateToggle() {
  const systemStatus = useQuantumStore((s) => s.system_status);
  const startCalibration = useQuantumStore((s) => s.startCalibration);
  const qubits = useQuantumStore((s) => s.qubits);

  const isCalibrating = systemStatus === "CALIBRATING";
  const isCalibrated = systemStatus === "CALIBRATED";
  const noQubits = qubits.length === 0;

  if (isCalibrating) {
    return (
      <button disabled className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-neon-amber/40 bg-neon-amber/10 text-neon-amber text-[10px] font-mono font-bold uppercase tracking-widest cursor-wait">
        <span className="inline-block h-2.5 w-2.5 rounded-full border border-neon-amber border-t-transparent animate-spin" />
        Calibrating...
      </button>
    );
  }

  if (isCalibrated) {
    return (
      <button
        onClick={startCalibration}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-500/40 bg-surface-sunken/60 text-slate-400 hover:text-neon-cyan hover:border-neon-cyan/40 hover:bg-neon-cyan/10 transition-colors text-[10px] font-mono font-bold uppercase tracking-widest"
      >
        <RotateCw size={11} />
        Re-run
      </button>
    );
  }

  return (
    <button
      onClick={startCalibration}
      disabled={noQubits}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-neon-cyan/40 bg-neon-cyan/10 text-neon-cyan hover:bg-neon-cyan/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-[10px] font-mono font-bold uppercase tracking-widest glow-cyan"
    >
      <Play size={11} />
      Run Auto-Calibrate
    </button>
  );
}

export default function Header() {
  const systemStatus = useQuantumStore((s) => s.system_status);

  return (
    <header className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-border-subtle bg-surface-card/60 backdrop-blur-sm">
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-neon-cyan/10 border border-neon-cyan/20 glow-cyan">
          <Zap size={16} className="text-neon-cyan" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-bold tracking-tight text-slate-100 font-mono">
            Axiom<span className="text-neon-cyan">.Q</span>
          </span>
          <span className="text-[9px] text-slate-500 uppercase tracking-widest font-mono">
            Autonomous Quantum Control
          </span>
        </div>
      </div>

      {/* Status indicators */}
      <div className="flex items-center gap-6">
        <StatusIndicator label="MONGODB" color="green" />
        <StatusIndicator label="LITELLM" color="green" />
        <StatusIndicator label={systemStatus.replace("_", " ")} color={systemStatus === "CALIBRATED" ? "green" : "gray"} />

        {/* Minimalistic Calibration Toggle */}
        <div className="pl-4 ml-4 border-l border-border-subtle">
          <MinimalCalibrateToggle />
        </div>
      </div>
    </header>
  );
}
