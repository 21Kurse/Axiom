import { useCallback, useEffect, useRef, useState } from "react";
import useQuantumStore from "../../store/useQuantumStore";
import { Sliders, RotateCcw } from "lucide-react";

/**
 * Vertical "limb-shift" knob (a soft potentiometer).
 *
 * The judge drags the lever upward (more drift) → backend scales the
 * Qiskit drift magnitude + cell count by `value` and, on crossing the
 * server-side threshold (default 0.30), fires a full telemetry → heatmap
 * → VLM → healing cycle.
 *
 * Interaction model:
 *  - Pointer-drag the handle (continuous value updates via WS).
 *  - Click anywhere on the track to jump to that position.
 *  - Reset button → sends `{type: "reset"}` so a new cycle can be fired.
 */
export default function ProstheticPot() {
  const prosthetic = useQuantumStore((s) => s.prosthetic);
  const sendPotValue = useQuantumStore((s) => s.sendPotValue);
  const resetProstheticCycle = useQuantumStore((s) => s.resetProstheticCycle);

  const trackRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const value = Number(prosthetic.pot_value || 0);
  const threshold = Number(prosthetic.threshold || 0.30);

  const updateValueFromPointer = useCallback(
    (clientY) => {
      const el = trackRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const yFromTop = clientY - rect.top;
      const v = 1 - Math.max(0, Math.min(1, yFromTop / rect.height));
      sendPotValue(v);
    },
    [sendPotValue]
  );

  const onPointerDown = (e) => {
    e.preventDefault();
    setDragging(true);
    updateValueFromPointer(e.clientY);
  };

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e) => updateValueFromPointer(e.clientY);
    const onUp = () => setDragging(false);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [dragging, updateValueFromPointer]);

  const fillPct = (value * 100).toFixed(1);
  const thresholdPct = (threshold * 100).toFixed(0);
  const aboveThreshold = value >= threshold;

  return (
    <div className="flex flex-col items-center gap-2 select-none">
      <div className="flex items-center gap-1.5 text-[9px] font-mono text-slate-400 uppercase tracking-widest">
        <Sliders size={11} className="text-neon-cyan" />
        <span>Limb-Shift</span>
        <span className="text-neon-cyan font-bold">{fillPct}%</span>
     </div>

      <div className="relative flex items-end gap-3 h-[260px]">
        {/* The draggable track */}
        <div
          ref={trackRef}
          onPointerDown={onPointerDown}
          className="relative w-9 h-full cursor-pointer rounded-sm
                     bg-[#121212] border border-[rgba(255,255,255,0.10)]
                     shadow-[inset_0_0_8px_rgba(0,0,0,0.6)] overflow-hidden"
          style={{ touchAction: "none" }}
        >
          {/* Filled portion — gradient from green (rest) to amber (heavy drift) */}
          <div
            className="absolute inset-x-0 bottom-0 transition-[height] duration-75 ease-out"
            style={{
              height: `${value * 100}%`,
              background: aboveThreshold
                ? "linear-gradient(to top, rgba(245,158,11,0.30), rgba(0,240,255,0.10))"
                : "linear-gradient(to top, rgba(0,255,65,0.30), rgba(0,240,255,0.10))",
              borderTop: aboveThreshold
                ? "1px solid #f59e0b"
                : "1px solid rgba(0,240,255,0.6)",
            }}
          />

          {/* Threshold line (server-side fire) */}
          <div
            className="absolute inset-x-0 h-px bg-amber-400/80 pointer-events-none"
            style={{ bottom: `${threshold * 100}%` }}
          >
            <span
              className="absolute -right-[2px] -translate-x-full -top-2
                         text-[8px] font-mono text-amber-300 tracking-wider whitespace-nowrap"
            >
              FIRE {thresholdPct}%
           </span>
         </div>

          {/* Tick marks */}
          {[0, 25, 50, 75, 100].map((pct) => (
            <div
              key={pct}
              className="absolute inset-x-0 h-px bg-[rgba(255,255,255,0.10)] pointer-events-none"
              style={{ bottom: `${pct}%` }}
            />
          ))}

          {/* Handle */}
          <div
            className="absolute inset-x-[-6px] h-[3px] pointer-events-none
                       bg-neon-cyan shadow-[0_0_10px_rgba(0,240,255,0.85)]"
            style={{
              bottom: `calc(${value * 100}% - 1.5px)`,
              background: aboveThreshold ? "#f59e0b" : "#00f0ff",
              boxShadow: aboveThreshold
                ? "0 0 12px rgba(245,158,11,0.80)"
                : "0 0 12px rgba(0,240,255,0.85)",
            }}
          />

          {/* Cap pegs at 0% and 100% */}
          <div className="absolute inset-x-[-3px] bottom-0 h-1 bg-[rgba(255,255,255,0.20)] pointer-events-none" />
          <div className="absolute inset-x-[-3px] top-0 h-1 bg-[rgba(255,255,255,0.20)] pointer-events-none" />
       </div>

        {/* Ticks + numeric axis on the right */}
        <div className="relative h-full flex flex-col justify-between text-[8px] font-mono text-slate-500 pr-1">
          {[100, 75, 50, 25, 0].map((pct) => (
            <span key={pct} className="leading-none">
              {pct.toString().padStart(3, " ")}
           </span>
          ))}
       </div>
     </div>

      <button
        onClick={resetProstheticCycle}
        className="flex items-center gap-1.5 px-2 py-1 rounded-sm text-[9px] font-mono
                   text-slate-400 hover:text-neon-cyan border border-[rgba(255,255,255,0.08)]
                   hover:border-[rgba(0,240,255,0.30)] transition-all duration-150"
        title="Send reset to backend so a new cycle can be fired by another drag."
      >
        <RotateCcw size={10} />
        <span className="uppercase tracking-widest">Reset</span>
     </button>
   </div>
  );
}
