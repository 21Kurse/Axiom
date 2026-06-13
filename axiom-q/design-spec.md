# Axiom.Q — UI/UX Refactoring Design Specification
**Version:** 0.3.0  
**Date:** 2026-06-13  
**Theme:** Deep-Space Cyberpunk / Instrument-Grade Dashboard

---

## 1. Global Design System

### 1.1 Color Palette
```
BACKGROUND_PRIMARY:   #0B0F19  /* Deep space blue/black */
BACKGROUND_SECONDARY: #111827  /* Slightly elevated cards/panels */
BACKGROUND_TERTIARY:  #1F2937  /* Inputs, hover states */

NEON_CYAN:            #00F0FF  /* Primary interactive, data primary */
NEON_GREEN:           #00FF41  /* Success, calibrated, live */
NEON_PURPLE:          #A855F7  /* Dashed lines, secondary data */
NEON_RED:             #FF4444  /* Error, degraded */

TEXT_PRIMARY:         #F9FAFB  /* Headlines, primary data */
TEXT_SECONDARY:       #9CA3AF  /* Labels, secondary data */
TEXT_MUTED:           rgba(255,255,255,0.40)  /* Footer, timestamps */

BORDER_COLOR:         rgba(255,255,255,0.08)   /* 1px crisp panel borders */
BORDER_ACTIVE:        rgba(0,240,255,0.30)     /* Cyan glow on focus/active */

GRID_MAJOR:           rgba(255,255,255,0.06)   /* Oscilloscope grid lines */
GRID_MINOR:           rgba(255,255,255,0.03)   /* Subtle tick marks */
```

### 1.2 Typography
```css
--font-mono: "JetBrains Mono", "SF Mono", "Fira Code", Consolas, monospace;
--font-sans: "Inter", system-ui, -apple-system, sans-serif;

/* Usage rules */
ALL numerical data, terminal text, JSON: var(--font-mono)
Headers, labels, UI chrome:               var(--font-sans)

Hierarchy:
  H1/Panel titles:  13px, uppercase, tracking-wide, --font-sans, TEXT_SECONDARY
  Data values:      11px, --font-mono, TEXT_PRIMARY
  Secondary metric: 9px, --font-mono, TEXT_SECONDARY
  Labels:           10px, uppercase, --font-sans, TEXT_SECONDARY
```

### 1.3 Animation Tokens
```css
--pulse-duration: 2s;
--pulse-ease: cubic-bezier(0.4, 0, 0.6, 1);
--transition-fast: 0.12s ease-out;
```

---

## 2. Global Layout & Header

### 2.1 Top-Right Status Indicators
*Requirement: Add subtle pinging pulse animations to status dots.*

```css
.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  position: relative;
  display: inline-block;
}

/* Active state: green ping */
.status-indicator.active::after {
  content: '';
  position: absolute;
  top: -4px;
  left: -4px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid var(--neon-green);
  animation: statusPing 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes statusPing {
  0% { transform: scale(0.8); opacity: 0.8; }
  100% { transform: scale(2.0); opacity: 0; }
}

/* Warning state: cyan pulse */
.status-indicator.warning::after {
  border-color: var(--neon-cyan);
}
```

### 2.2 Footer
*Requirement: Reduce opacity of version and environment tag to 40%.*

```jsx
<footer className="text-[rgba(255,255,255,0.40)] text-[10px] font-mono uppercase tracking-widest">
  <span>AXIOM.Q V0.2.8</span>
  <span className="mx-2">|</span>
  <span>JAMHACKS 2026</span>
</footer>
```

---

## 3. Hardware Controls Panel (Left Column)

### 3.1 Qubit Register Grid
*Requirement: Add secondary metric inside or below each qubit square.*

```jsx
// Component: QubitButton
<div className="relative w-[72px] h-[72px] rounded-sm border border-[rgba(255,255,255,0.08)] 
                bg-[#111827] flex flex-col items-center justify-center
                transition-all duration-150 hover:border-[rgba(0,240,255,0.30)]">
  {/* Active state glow */}
  {isActive && (
    <div className="absolute inset-0 rounded-sm border-2 border-[#00F0FF] 
                    shadow-[0_0_12px_rgba(0,240,255,0.40)] pointer-events-none" />
  )}
  
  {/* Primary label */}
  <span className="font-mono text-[11px] text-[#F9FAFB] tracking-wider">Q{index}</span>
  
  {/* Secondary metric — appears for all qubits */}
  <span className="font-mono text-[9px] text-[#9CA3AF] mt-0.5">
    T₁:{t1Value}μs
  </span>
  {/* Alternative: Scrap value: fidelity percentage */}
  <span className="font-mono text-[9px] text-[#9CA3AF] mt-0.5">
    {(fidelity * 100).toFixed(1)}%
  </span>
</div>
```

### 3.2 Noise Channel Injection Sliders
*Requirement: Thinner tracks, precise alignment, matching neon color, tick marks.*

```css
.noise-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 2px; /* Thinner track */
  background: linear-gradient(to right, 
    var(--neon-cyan) 0%, 
    var(--neon-cyan) var(--value-percent), 
    rgba(255,255,255,0.08) var(--value-percent)
  );
  border-radius: 1px;
  position: relative;
}

.noise-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 10px;
  height: 10px;
  background: var(--neon-cyan);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 0 6px rgba(0,240,255,0.50);
  margin-top: -4px; /* Center on 2px track */
}

/* Tick marks */
.slider-ticks {
  display: flex;
  justify-content: space-between;
  width: 100%;
  margin-top: 4px;
}

.slider-tick {
  width: 1px;
  height: 4px;
  background: rgba(255,255,255,0.15);
}

/* Numeric value */
.slider-value {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--neon-cyan); /* Matches active fill */
  min-width: 32px;
  text-align: right;
}
```

### 3.3 Calibration Button
*Requirement: Sharp border, tactile, dark green background.*

```jsx
<button className="w-full py-3 px-4 
                    bg-[#064E3B] hover:bg-[#065F46] active:bg-[#047857]
                    border border-[#10B981] rounded-sm
                    transition-colors duration-150
                    flex items-center justify-center gap-2">
  <span className="w-2 h-2 rounded-full bg-[#00FF41]" />
  <span className="font-mono text-[11px] text-white uppercase tracking-wider">
    CALIBRATION COMPLETE — RE-RUN?
  </span>
</button>
```

---

## 4. Live Telemetry Panel (Center Column)

### 4.1 Rabi Oscillation Telemetry
*Requirement: Faint grid overlay, legend/hover indicator.*

```jsx
// Chart configuration (Recharts/Chart.js)
const chartOptions = {
  grid: {
    strokeDasharray: "0", 
    stroke: "rgba(255,255,255,0.06)",
    horizontal: true,
    vertical: true,
  },
  xAxis: { 
    stroke: "rgba(255,255,255,0.10)",
    tick: { fontSize: 10, fill: "#9CA3AF", fontFamily: "var(--font-mono)" }
  },
  yAxis: {
    stroke: "rgba(255,255,255,0.10)",
    tick: { fontSize: 10, fill: "#9CA3AF", fontFamily: "var(--font-mono)" }
  }
};

// Legend
const Legend = () => (
  <div className="flex gap-4 text-[10px] font-mono">
    <div className="flex items-center gap-1.5">
      <span className="w-4 h-[2px] bg-[#00F0FF] inline-block" />
      <span className="text-[#9CA3AF]">LIVE_READOUT</span>
    </div>
    <div className="flex items-center gap-1.5">
      <span className="w-4 border-t-[2px] border-dashed border-[#A855F7] inline-block" />
      <span className="text-[#9CA3AF]">TARGET_WAVE</span>
    </div>
  </div>
);
```

### 4.2 Bloch Sphere (WebGL)
*Requirement: Coordinate axis labels, faint grid, depth anchoring.*

```jsx
// Three.js / React Three Fiber augmentations

// Axis labels at vector endpoints
const AxisLabels = () => (
  <>
    <Html position={[0, 0, 1.15]} center>
      <span className="text-[10px] font-mono text-[#9CA3AF]">Z</span>
    </Html>
    <Html position={[1.15, 0, 0]} center>
      <span className="text-[10px] font-mono text-[#9CA3AF]">X</span>
    </Html>
    <Html position={[0, 1.15, 0]} center>
      <span className="text-[10px] font-mono text-[#9CA3AF]">Y</span>
    </Html>
  </>
);

// Background grid plane for depth
<gridHelper 
  args={[2.4, 12, "rgba(255,255,255,0.03)", "rgba(255,255,255,0.02)"]} 
  position={[0, 0, -0.5]}
/>

// Sphere bounding box
<mesh>
  <boxGeometry args={[2.2, 2.2, 2.2]} />
  <meshBasicMaterial 
    color="#0B0F19" 
    transparent 
    opacity={0.3} 
    wireframe 
  />
</mesh>
```

---

## 5. NVIDIA Ising Agent & Payload Inspector (Right Column)

### 5.1 Bash Terminal
*Requirement: Scanline overlay, terminal cursor pulse.*

```jsx
<div className="relative bg-[#0B0F19] border border-[rgba(255,255,255,0.08)] rounded-sm overflow-hidden">
  {/* Scanline overlay */}
  <div className="absolute inset-0 pointer-events-none z-10 opacity-[0.03]"
       style={{
         backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.03) 2px, rgba(255,255,255,0.03) 4px)"
       }}
  />
  
  {/* Terminal content */}
  <div className="font-mono text-[11px] p-3 text-[#9CA3AF]">
    <span className="text-[#00FF41]">➜</span> <span className="text-[#00F0FF]">axiom-q</span> 
    <span className="animate-pulse">_</span>
  </div>
</div>
```

### 5.2 Agent Payload Inspector
*Requirement: Enhanced JSON contrast, dynamic status badges.*

```jsx
// Syntax highlighting with enhanced contrast
const jsonTheme = {
  key: "text-[#00F0FF]",           // Cyan keys
  string: "text-[#A855F7]",        // Purple strings
  number: "text-[#00FF41]",        // Green numbers
  boolean: "text-[#F59E0B]",       // Amber booleans
  null: "text-[#9CA3AF]",          // Gray nulls
  punctuation: "text-[#6B7280]",   // Darker punctuation
};

// Dynamic status badge
const StatusBadge = ({ status }) => {
  const variants = {
    IDLE: "bg-[rgba(255,255,255,0.08)] text-[#9CA3AF] border-[rgba(255,255,255,0.12)]",
    STREAMING: "bg-[rgba(0,240,255,0.10)] text-[#00F0FF] border-[#00F0FF]/30 animate-pulse",
    PROCESSING: "bg-[rgba(245,158,11,0.10)] text-[#F59E0B] border-[#F59E0B]/30",
  };
  
  return (
    <span className={`px-2 py-0.5 rounded-sm border text-[9px] font-mono uppercase tracking-wider ${variants[status]}`}>
      {status}
    </span>
  );
};
```

---

## 6. Overall Polish Checklist

| Element | Specification |
|---------|---------------|
| Borders | `1px solid rgba(255,255,255,0.08)` |
| Active borders | `1px solid rgba(0,240,255,0.30)` |
| Border radius | `2px` (sharp, not rounded) |
| Font — All data | JetBrains Mono 9–11px |
| Font — UI labels | Inter 10px uppercase |
| Focus state | `ring-1 ring-[#00F0FF]/30` |
| Transitions | `all 0.12s ease-out` |

---

## 7. Implementation Priorities

1. **Phase 1**: Global CSS variables, typography, base theme
2. **Phase 2**: Header status dots + footer
3. **Phase 3**: Hardware grid (secondary metrics + active glow)
4. **Phase 4**: Sliders (thin tracks + ticks)
5. **Phase 5**: Chart grid overlay + legend
6. **Phase 6**: Bloch sphere axis labels + depth grid
7. **Phase 7**: Terminal + JSON enhancements
8. **Phase 8**: Scanline overlays + final polish pass
