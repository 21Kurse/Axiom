import { Zap } from "lucide-react";
import useQuantumStore from "../../store/useQuantumStore";
import StatusBar from "../ui/StatusBar";

export default function Header() {
  const systemStatus = useQuantumStore((s) => s.system_status);

  const statusColor = {
    UNCALIBRATED: "bg-neon-amber",
    CALIBRATING: "bg-neon-purple animate-pulse",
    CALIBRATED: "bg-neon-green",
  };

  return (
    <header className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-border-subtle bg-surface-card/60 backdrop-blur-sm">
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-neon-cyan/10 border border-neon-cyan/20 glow-cyan">
          <Zap size={16} className="text-neon-cyan" />
       </div>
        <div className="flex flex-col">
          <span className="text-sm font-bold tracking-tight text-slate-100">
            Axiom<span className="text-neon-cyan">.Q</span>
         </span>
          <span className="text-[9px] text-slate-500 uppercase tracking-widest">
            Autonomous Quantum Control
         </span>
       </div>
     </div>

      {/* Status indicators */}
      <div className="flex items-center gap-4">
        <StatusBar />

        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${statusColor[systemStatus]}`} />
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">
            {systemStatus.replace("_", " ")}
         </span>
       </div>
     </div>
   </header>
  );
}
