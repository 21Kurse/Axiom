import { useEffect, useRef } from "react";
import { Terminal, FileJson, RefreshCw } from "lucide-react";
import useQuantumStore from "../../store/useQuantumStore";

function TerminalStream() {
  const logs = useQuantumStore((s) => s.ai_console_logs);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const hasError = logs.some((l) =>
    l.msg.toLowerCase().includes("error") || l.msg.includes("FAIL")
  );

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-card/80 overflow-hidden flex flex-col">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border-subtle bg-surface-sunken/60">
        <span className="h-2.5 w-2.5 rounded-full bg-red-500/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-neon-amber/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-neon-green/70" />
        <span className="ml-2 text-[10px] font-mono text-slate-500">
          nvidia-ising-agent — bash
       </span>
        {hasError && (
          <span className="ml-auto text-[9px] font-mono text-red-400 uppercase tracking-wider">
            ⚠ errors present
         </span>
        )}
     </div>

      <div
        ref={scrollRef}
        className="flex-1 min-h-[240px] max-h-[340px] overflow-y-auto p-3 space-y-1 font-mono text-xs bg-surface-sunken/80"
      >
        {logs.length === 0 && (
          <div className="text-slate-600 italic">No console output yet…</div>
        )}
        {logs.map((entry, i) => {
          const ts = new Date(entry.ts).toLocaleTimeString("en-US", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          });

          const isError = entry.msg.toLowerCase().includes("error") || entry.msg.includes("FAIL");
          const isCmd = entry.msg.startsWith(">");
          const colorClass = isError
            ? "text-red-400"
            : isCmd
              ? "text-neon-cyan"
              : "text-slate-300";

          return (
            <div key={i} className="flex gap-2">
              <span className="text-slate-600 shrink-0 select-none">{ts}</span>
              <span className={colorClass}>{entry.msg}</span>
           </div>
          );
        })}
        <div className="flex items-center gap-1 text-neon-cyan">
          <span>❯</span>
          <span className="animate-blink-cursor inline-block w-1.5 h-4 bg-neon-cyan/70" />
       </div>
     </div>
   </div>
  );
}

function JsonInspector() {
  const payload = useQuantumStore((s) => s.agent_payload);
  const isComplete = payload.status === "COMPLETE";
  const isError = payload.status === "ERROR";

  return (
    <div
      className={`rounded-xl border overflow-hidden flex flex-col ${
        isError
          ? "border-red-500/40 bg-red-500/5"
          : "border-border-subtle bg-surface-card/80"
      }`}
    >
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-200">
          <FileJson size={14} className={isError ? "text-red-400" : "text-neon-amber"} />
          Agent Payload Inspector
       </span>
        <span
          className={`text-[9px] font-mono font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border ${
            isError
              ? "bg-red-400/10 border-red-400/40 text-red-400"
              : isComplete
                ? "bg-neon-green/10 border-neon-green/40 text-neon-green"
                : "bg-surface-sunken border-border-subtle text-slate-500"
          }`}
        >
          {payload.status}
       </span>
     </div>

      <div className="p-3 font-mono text-[11px] leading-relaxed bg-surface-sunken/80 overflow-x-auto max-h-48">
        {isError ? (
          <pre className="text-red-400 whitespace-pre-wrap break-words">
            {JSON.stringify(payload, null, 2)}
         </pre>
        ) : (
          <pre className="text-slate-400">
            <span className="text-slate-600">{'{'}</span>
            {"\n"}
            <span className="ml-3 text-slate-500">"model</span>
            <span className="text-slate-600">:</span>
            <span className="text-neon-amber">"{payload.model}"</span>
            <span className="text-slate-600">,</span>
            {"\n"}
            <span className="ml-3 text-slate-500">"confidence</span>
            <span className="text-slate-600">:</span>
            <span className={isComplete ? "text-neon-green" : "text-slate-600"}>
              {payload.confidence ?? "null"}
           </span>
            <span className="text-slate-600">,</span>
            {"\n"}
            <span className="ml-3 text-slate-500">"correction_variables</span>
            <span className="text-slate-600">: {'{'}</span>
            {"\n"}
            {Object.entries(payload.correction_variables).map(([key, val], i, arr) => (
              <span key={key}>
                <span className="ml-6 text-neon-cyan">{key}</span>
                <span className="text-slate-600">:</span>
                <span className={isComplete ? "text-neon-green" : "text-slate-600"}>
                  {val}
               </span>
                {i < arr.length - 1 && <span className="text-slate-600">,</span>}
                {"\n"}
             </span>
            ))}
            <span className="ml-3 text-slate-600">{`}`}</span>
            {"\n"}
            <span className="text-slate-600">{`}`}</span>
         </pre>
        )}
     </div>
   </div>
  );
}

export default function AgentPanel() {
  const resetCalibration = useQuantumStore((s) => s.resetCalibration);
  const systemStatus = useQuantumStore((s) => s.system_status);

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal size={18} className="text-neon-amber" />
          <h2 className="text-base font-bold tracking-tight text-slate-100">
            NVIDIA Ising Agent
         </h2>
       </div>
        {systemStatus !== "CALIBRATING" && (
          <button
            onClick={resetCalibration}
            className="flex items-center gap-1 text-[10px] font-mono text-slate-500 hover:text-slate-300 transition-colors"
          >
            <RefreshCw size={11} />
            Reset
         </button>
        )}
     </div>

      <TerminalStream />
      <JsonInspector />
   </div>
  );
}
