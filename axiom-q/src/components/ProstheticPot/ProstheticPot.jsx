import { useCallback, useEffect, useRef, useState } from "react";
import useQuantumStore from "../../store/useQuantumStore";
import { Sliders, Target, RotateCcw } from "lucide-react";

/**
 * Vertical knob track — reusable for both the limb-shift pot and the
 * comfort-target pot. Both are draggable; limb-shift emits pot events
 * back to the WS, comfort-target updates the local target range.
 */
function KnobTrack({ value, threshold, label, icon: Icon, draggable, accentColor = "#b0b8c0", onUpdate }) {
  const trackRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const updateValueFromPointer = useCallback(
    (clientY) => {
      if (!draggable || !onUpdate) return;
      const el = trackRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const yFromTop = clientY - rect.top;
      const v = 1 - Math.max(0, Math.min(1, yFromTop / rect.height));
      onUpdate(v);
    },
    [draggable, onUpdate]
  );

  const onPointerDown = (e) => {
    if (!draggable) return;
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
  const thresholdPct = threshold != null ? (threshold * 100).toFixed(0) : null;
  const aboveThreshold = threshold != null && value >= threshold;

  return (
    <div className="flex flex-col items-center gap-1 select-none">
      <div className="flex items-center gap-1 text-[8px] font-mono text-slate-400 uppercase tracking-widest">
        <Icon size={10} className="text-slate-400" />
        <span>{label}</span>
        <span className="text-slate-300 font-bold">{fillPct}%</span>
     </div>

      <div className="relative flex items-end gap-2 h-[220px]">
        <div
          ref={trackRef}
          onPointerDown={onPointerDown}
          className={`relative w-7 h-full rounded-sm
                      bg-[#121212] border border-[rgba(255,255,255,0.10)]
                      shadow-[inset_0_0_8px_rgba(0,0,0,0.6)] overflow-hidden
                      ${draggable ? "cursor-pointer" : "cursor-default"}`}
          style={{ touchAction: draggable ? "none" : "auto" }}
        >
          {/* Filled portion */}
          <div
            className="absolute inset-x-0 bottom-0 transition-[height] duration-75 ease-out"
            style={{
              height: `${value * 100}%`,
              background: aboveThreshold
                ? "linear-gradient(to top, rgba(176,168,160,0.20), rgba(184,197,209,0.08))"
                : "linear-gradient(to top, rgba(176,184,168,0.20), rgba(184,197,209,0.08))",
              borderTop: `1px solid ${aboveThreshold ? "#b0a8a0" : "rgba(176,168,192,0.6)"}`,
            }}
          />

          {/* Threshold line — only on the limb-shift knob */}
          {threshold != null && (
            <div
              className="absolute inset-x-0 h-px bg-[rgba(176,168,192,0.30)] pointer-events-none"
              style={{ bottom: `${threshold * 100}%` }}
            >
              <span
                className="absolute -right-[2px] -translate-x-full -top-2
                           text-[7px] font-mono text-slate-400 tracking-wider whitespace-nowrap"
              >
                F {thresholdPct}%
             </span>
           </div>
          )}

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
            className="absolute inset-x-[-5px] h-[3px] pointer-events-none
                       shadow-[0_0_10px_rgba(176,168,192,0.85)]"
            style={{
              bottom: `calc(${value * 100}% - 1.5px)`,
              background: aboveThreshold ? "#b0a8a0" : accentColor,
              boxShadow: aboveThreshold
                ? "0 0 12px rgba(245,158,11,0.80)"
                : `0 0 12px ${accentColor}99`,
            }}
          />

          {/* Cap pegs at 0% and 100% */}
          <div className="absolute inset-x-[-3px] bottom-0 h-1 bg-[rgba(255,255,255,0.20)] pointer-events-none" />
          <div className="absolute inset-x-[-3px] top-0 h-1 bg-[rgba(255,255,255,0.20)] pointer-events-none" />
       </div>

        {/* Ticks + numeric axis on the right */}
        <div className="relative h-full flex flex-col justify-between text-[7px] font-mono text-slate-500 pr-1">
          {[100, 75, 50, 25, 0].map((pct) => (
            <span key={pct} className="leading-none">
              {pct.toString().padStart(3, " ")}
           </span>
          ))}
       </div>
     </div>
   </div>
  );
}

/**
 * Twin-knob panel: limb-shift (drag, drives WS pot) + comfort-target
 * (drag, sets the local target pressure range).
 */
export default function ProstheticPot() {
  const prosthetic = useQuantumStore((s) => s.prosthetic);
  const sendPotValue = useQuantumStore((s) => s.sendPotValue);
  const sendPot2Value = useQuantumStore((s) => s.sendPot2Value);
  const resetProstheticCycle = useQuantumStore((s) => s.resetProstheticCycle);

  const potValue = Number(prosthetic.pot_value || 0);
  const threshold = Number(prosthetic.threshold || 0.30);
  const pot2Value = Number(prosthetic.pot2_value ?? 0.5);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-3">
        <KnobTrack
          value={potValue}
          threshold={threshold}
          label="Limb-Shift"
          icon={Sliders}
          draggable={true}
          accentColor="#b0b8c0"
          onUpdate={sendPotValue}
        />

        <KnobTrack
          value={pot2Value}
          threshold={null}
          label="Comfort Target"
          icon={Target}
          draggable={true}
          accentColor="#00F0FF"
          onUpdate={sendPot2Value}
        />
     </div>

      <button
        onClick={resetProstheticCycle}
        className="flex items-center gap-1 px-2 py-0.5 rounded-sm text-[8px] font-mono
                   text-slate-400 hover:text-slate-300 border border-[rgba(255,255,255,0.08)]
                   hover:border-[rgba(176,168,192,0.30)] transition-all duration-150"
        title="Send reset to backend so a new cycle can be fired by another drag."
      >
        <RotateCcw size={9} />
        <span className="uppercase tracking-widest">Reset</span>
     </button>
   </div>
  );
}
