# Axiom.Q Physics Validation Audit Report

**Auditor:** Physics Validation Engine
**Date:** 2026-06-13
**Scope:** Full calibration pipeline — quantum state, noise models, drift, circuits, VLM inference, correction application, visualization, metric consistency

---

## Subsystem 1: Quantum State Representation (Bloch Sphere)

### What the system currently does

[TelemetryPanel.jsx:335–371](../axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx#L335-L371) renders a Three.js Bloch sphere with:
- **Y-axis as quantization axis** (non-standard; standard is Z)
- `theta0 = (amplitude + piPulseOffset) * π` — polar angle from Y-north
- `phi0 = ((frequency − currentDrift + driftCorrected) − 4.8) × 10π`
- T1 relaxation: linear interpolation toward Y = +1 (north pole = |0⟩)
- T2 dephasing: contributes to stochastic wobble magnitude only
- Corrections gated behind `system_status === "CALIBRATED"`

### Assumptions
1. The Y-axis is the quantization axis (north = |0⟩, south = |1⟩)
2. `qubitState.amplitude` (DB default: Q0 = 0.95) maps directly to θ in radians via `θ = amplitude × π`
3. The `(freq − 4.8) × 10π` scaling law converts frequency offset to azimuthal angle

### What is physically valid
- Direction of T1 relaxation (toward |0⟩ at north pole) is correct
- Wobble from residual drift is conceptually sound
- Corrections applied only post-calibration matches the state-machine design

### What is questionable
1. **Y-axis quantization convention** — internally consistent but violates standard Bloch sphere convention (Z = quantization axis). Could confuse users familiar with quantum textbooks.
2. **T1 relaxation is linear interpolation, not exponential** — `y_p = y_p + (1 − y_p) × t1Factor` blends toward |0⟩ linearly. Real T1 decay is exponential: ⟨σ_z⟩(t) = 1 − 2(1−⟨σ_z⟩₀) × e^(−t/T1). The linear approximation is only exact at a single time point.
3. **phi0 scaling (`× 10π`) is arbitrary** — no physical law maps a GHz frequency offset to an azimuthal angle via this factor. It exists solely to produce visible rotation.
4. **T2 dephasing lacks Bloch-sphere representation** — phase damping only adds wobble, it doesn't produce the correct T2 decoherence (exponential decay of off-diagonal density-matrix elements, which would shrink the transverse components of the Bloch vector toward the Z-axis).

### What is incorrect
1. **θ = 171° contradicts `≡ |0⟩` label** ([TelemetryPanel.jsx:334](../axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx#L334) line 443 in full file). The UI displays `≡ |0⟩` but Q0's amplitude = 0.95 → θ = 0.95 × 180 = **171°**, which is near the **|1⟩** pole (south). Either the label or the amplitude→θ mapping is wrong.

---

## Subsystem 2: Noise Model Application (T1 / T2)

### What the system currently does

**Backend** ([quantum_engine.py:60–91](../axiom-q/backend/quantum_engine.py#L60-L91)):
- T1 = max(100, 100000 × (1 − t1_relaxation)) **ns**
- T2 = max(50, 2T1 × (1 − phase_damping)), constrained T2 ≤ 2T1
- t_gate = 50 ns; noise applied to `rx` gate via `thermal_relaxation_error(t1, t2, t_gate)` + `depolarizing_error(phase_damping × 0.1, 1)`

**Frontend** ([TelemetryPanel.jsx:88–89](../axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx#L88-L89)):
- T1 = max(0.1, (1 − t1_thermal) × 100) **µs**
- noise_floor = phase_damping × 0.15 (ad-hoc constant)

### What is physically valid
- **T2 ≤ 2T1 constraint** is correct (thermal relaxation physics)
- **T1/T2 range mapping**: slider → physical units is internally consistent (frontend 0.1–100 µs = backend 100–100,000 ns)
- **thermal_relaxation_error** at gate time `t_gate` is the standard Qiskit noise channel
- **Depolarizing error** for phase damping is a reasonable additional error channel

### What is questionable
1. **T1 floor of 100 ns (0.1 µs)** is extremely aggressive — real superconducting qubits are 10–300 µs. At t1_relaxation → 1.0, the system enters an unrealistic regime with T1 = 0.1 µs, but this is a slider design choice, not a physics error.
2. **Depolarizing error scaled by `phase_damping × 0.1`** — coupling phase damping to depolarizing error is ad-hoc. Depolarizing error is not the same as phase damping (dephasing). Depolarizing includes both T1 and T2 processes.
3. **Frontend noise_floor = 0.15 × phase_damping** — this adds a constant P(|1⟩) offset, which would make the Rabi oscillation asymptote to a non-zero probability even at infinite time. Physically, the steady-state of a Rabi oscillation under T1 decay should approach P(|0⟩) = 1 (ground state), not a non-zero noise floor.

---

## Subsystem 3: Hardware Drift Modeling (Δω)

### What the system currently does

**Backend** ([quantum_engine.py:49](../axiom-q/backend/quantum_engine.py#L49)):
- Ω_drive = OMEGA_0 − (drift_mhz × DRIFT_SCALE), where DRIFT_SCALE = 0.02 rad/µs per MHz

**Frontend** ([TelemetryPanel.jsx:85–86](../axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx#L85-L86)):
- `delta_omega = drift_mhz − drift_corrected_mhz`
- `omega_drive = omega_0 − delta_omega` → expands to `omega_0 − drift_mhz + drift_corrected_mhz`

### What is physically valid
- The concept that calibration compensates for frequency drift by adjusting the effective drive is sound
- The closed-loop form `Ω_drive = Ω_0 − Δω_residual` is correct

### What is incorrect
1. **Backend `omega_drive` is dead code** — computed at [quantum_engine.py:49](../axiom-q/backend/quantum_engine.py#L49) but **never used** in the circuit generation. `get_rabi_circuits` creates `Rx(pulse_amp_mod × theta_base)` circuits that don't depend on `omega_drive` at all. The Rabi experiment sweeps the rotation angle; the drive frequency enters only in the analytical model.
2. **Drift has zero effect on the Qiskit simulation** — `drift_mhz` is passed through the entire call chain (`run_rabi_simulation → get_rabi_circuits → omega_drive = ...`) but never affects the `Rx(theta)` circuits or the noise model. Moving the "Hardware Drift" slider changes the frontend analytical chart but does NOT change the actual backend telemetry probabilities.
3. **Frontend-backend drift scaling mismatch** — the backend applies DRIFT_SCALE = 0.02 to convert MHz → angular frequency shift, the frontend uses drift_mhz directly with no scaling. For hardware_drift = 0.05 MHz:
   - Backend effective shift: 0.05 × 0.02 = 0.001
   - Frontend effective shift: 0.05
   - These differ by **50×**

---

## Subsystem 4: Calibration Experiment Generation (Rabi Circuits)

### What the system currently does

[quantum_engine.py:31–57](../axiom-q/backend/quantum_engine.py#L31-L57) generates 50 Rabi circuits:
- `theta` sweeps from 0 to 4π in 50 steps
- `Rx(pulse_amp_mod × theta)` for each step
- Noise applied via thermal_relaxation + depolarizing errors on `rx` gate

[main.py:87–146](../axiom-q/backend/main.py#L87-L146) WebSocket endpoint:
- Receives `{t1_relaxation, phase_damping, hardware_drift, pulse_amp_mod}`
- Runs Qiskit simulation
- Sends `{event: "telemetry_update", probabilities: [...]}`

### What is physically valid
- The Rabi experiment structure (sweeping Rx angle) is standard
- 1024 shots per circuit point is reasonable
- The 4π sweep covers two full Rabi oscillation cycles

### What is questionable
1. **50 data points across 4π** — Nyquist sampling requires at least 2 points per oscillation, so 4 points minimum for 2 cycles. 50 points is sufficient but coarse for VLM analysis of fine features.
2. **pulse_amp_mod defaults to 1.0 with no UI slider** — the user can't adjust it from the frontend. Only the calibration model can change it, but the correction (`pi_pulse_amp_offset`) isn't fed back to the backend simulation.

---

## Subsystem 5: Ising Model Interpretation (VLM Calibration)

### What the system currently does

[nvidia_client.py:231–266](../axiom-q/backend/nvidia_client.py#L231-L266):
- Sends text + base64 plot to LiteLLM
- Model prompt: "quantum hardware calibration engine" returning `{drift_corrected_mhz, pi_pulse_amp_mod, confidence}`
- 6-layer JSON parser with fallback keyword extraction

### What is physically valid
- Using observed waveform to infer corrections is how real calibration works
- The separation of "environmental noise" (T1/T2, uncorrectable) vs "control errors" (drift/amplitude, correctable) in the system prompt is physically correct
- The model receives the raw P(|1⟩) probabilities so it can observe waveform distortion

### What is questionable
1. **Model is not told the current `hardware_drift` value** — [nvidia_client.py:66–67](../axiom-q/backend/nvidia_client.py#L66-L67) only sends `t1_relaxation` and `phase_damping`. The model must infer drift entirely from waveform shape, which limits accuracy. In a real calibration system, the known detuning would be provided.
2. **No verification of correction plausibility** — the model's output is accepted as-is without physical bounds checking (e.g., `drift_corrected_mhz` could exceed the actual drift, `pi_pulse_amp_mod` could be negative).
3. **"Ising" label is nominal** — the model performs waveform-to-correction inference, not Ising Hamiltonian solving. The physics connection is via the model's training, not explicit computation.

### What is incorrect
1. **outcome_fidelity = float(confidence)** ([main.py:263](../axiom-q/backend/main.py#L263)) — this equates the model's self-reported confidence with actual calibration fidelity, which is circular reasoning. Fidelity should measure how well the corrected waveform matches the ideal, not how confident the model claims to be.

---

## Subsystem 6: Correction Application Pipeline

### What the system currently does

1. Model returns: `{drift_corrected_mhz, pi_pulse_amp_mod, confidence}`
2. [main.py:256–258](../axiom-q/backend/main.py#L256-L258): renames → `{pi_pulse_amp_offset, drift_compensation_mhz}`
3. Frontend stores as `agent_payload.correction_variables.{drift_compensation_mhz, pi_pulse_amp_offset}`

### What is physically valid
- Key renaming preserves values accurately
- Corrections are applied additively in the frontend (drift_compensation subtracted from drift, amplitude offset added to base)
- Reset clears corrections while preserving physical noise parameters

### What is questionable
1. **Corrections don't feed back to the backend** — the backend simulation always runs with raw parameters. The frontend only adjusts its analytical visualization. This creates a divergence: the WS telemetry stream shows uncorrected physics, but the chart shows corrected analytical curves.

### What is incorrect
1. **Naming semantics: `drift_corrected_mhz` vs `drift_compensation_mhz`** — "corrected" implies the drift is already compensated (i.e., this is the residual after correction), while "compensation" implies this is the amount TO subtract. The frontend code at [TelemetryPanel.jsx:85](../axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx#L85) uses `delta_omega = drift_mhz − drift_compensation_mhz`, treating it as the amount to subtract. If the model outputs the residual (already-corrected drift), this formula would double-compensate. The semantics are ambiguous and could lead to sign errors depending on model interpretation.

---

## Subsystem 7: Visualization Generation

### What the system currently does

**Rabi chart** ([TelemetryPanel.jsx:69–107](../axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx#L69-L107)):
- Analytical formula: `P₁(t) = A × sin(ω_drive × t) × e^(−t/T1) + noise_floor`
- "Real" line uses corrected parameters; "Ideal" line uses ω₀ with no decay

**Bloch sphere** — covered in Subsystem 1.

### What is physically valid
- The Rabi formula P₁(t) = A sin(Ωt) e^(−t/T1) + noise_floor is the textbook damped Rabi oscillation
- The "Ideal" line (pure sine, no decay) correctly represents the lossless limit

### What is questionable
1. **Chart is purely analytical, not Qiskit output** — the frontend computes the Rabi curve from a formula rather than plotting the actual simulation probabilities from the backend. The WS telemetry is received but not rendered. This is a design choice (smooth curve vs noisy data points) but means the chart is a visualization, not a measurement display.
2. **Severe aliasing at ω₀ = 4.8** — with 150 points over 200 µs and ω₀ = 4.8 rad/µs, the Rabi frequency produces ~153 full cycles. The Nyquist limit is 0.375 cycles/µs, so the chart aliases the true oscillation into a lower-frequency pattern. This produces a seemingly smooth wave that doesn't represent the actual 4.8 rad/µs oscillation.

### What is incorrect
1. **`compute_analytical_rabi` noise_floor is always 0** ([quantum_engine.py:162](../axiom-q/backend/quantum_engine.py#L162)):
   ```python
   noise_floor = phase_damping * 0.15 if 'phase_damping' in locals() else 0.0
   ```
   `phase_damping` is **not a parameter** of `compute_analytical_rabi()`. The `locals()` check always fails, so `noise_floor = 0.0` unconditionally. This makes the backend analytical function ignore phase damping entirely.

---

## Subsystem 8: Metric Consistency

### Cross-subsystem parameter flow

| Parameter | Frontend | Backend | Consistent? |
|-----------|----------|---------|-------------|
| T1 | max(0.1, (1−t1)×100) µs | max(100, 100000×(1−t1)) ns | ✅ (same formula, units match) |
| T2 | not displayed analytically | max(50, 2T1×(1−pd)) ns | N/A (frontend uses noise_floor) |
| Drift scale | direct (×1) | DRIFT_SCALE (×0.02) | ❌ **50× mismatch** |
| ω₀ source | DB qubit frequency (4.8+) | OMEGA_0_GHZ = 4.8 | ⚠️ partial (hardcoded vs DB) |
| Pulse amp | `qubitState.amplitude` (0.95) | `pulse_amp_mod` param (1.0) | ❌ **different semantics** |

### What is physically valid
- T1 mapping is consistent between frontend and backend
- Correction key chain is intact (model → API → store)

### What is incorrect
1. **Frontend `pulse_amp_mod_base` = `qubitState.amplitude`**, but the backend receives `pulse_amp_mod` from the store (default 1.0). The frontend's "amplitude" from the DB (Q0 = 0.95) is the qubit's calibrated pulse amplitude, a different concept from the `pulse_amp_mod` parameter (unitless scaling factor). They're being conflated in the Rabi chart formula:
   ```javascript
   const A = pulse_amp_mod_base + pi_pulse_amp_offset;  // = 0.95 + offset
   ```
   But the backend simulation uses `pulse_amp_mod = 1.0` (from the store), not 0.95.

---

## Summary of Findings

### CONFIRMED BUGS (Incorrect)

| # | Subsystem | Location | Issue |
|---|-----------|----------|-------|
| B1 | Visualization | [quantum_engine.py:162](../axiom-q/backend/quantum_engine.py#L162) | `noise_floor` in `compute_analytical_rabi()` always 0.0 because `phase_damping` is not a function parameter |
| B2 | Drift Model | [quantum_engine.py:49](../axiom-q/backend/quantum_engine.py#L49) | `omega_drive` is dead code; hardware drift has **zero effect** on the Qiskit simulation |
| B3 | Drift Model | Frontend vs Backend | Drift scaling mismatch: backend uses DRIFT_SCALE=0.02, frontend applies drift directly (50× difference) |
| B4 | Bloch Sphere | [TelemetryPanel.jsx:443](../axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx#L443) | `≡ \|0⟩` label contradicts θ = 171° (near \|1⟩) |
| B5 | Corrections | Frontend ↔ Backend | `drift_corrected_mhz` (model) vs `drift_compensation_mhz` (frontend) semantics ambiguous — is it the residual or the amount to subtract? |
| B6 | Metrics | [TelemetryPanel.jsx:73,87](../axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx#L73) | Frontend Rabi A = `qubitState.amplitude` (0.95) ≠ backend `pulse_amp_mod` (1.0) |

### QUESTIONABLE (Not Clearly Wrong, But Concerning)

| # | Subsystem | Location | Issue |
|---|-----------|----------|-------|
| Q1 | Bloch Sphere | TelemetryPanel.jsx:360 | T1 relaxation uses linear interpolation instead of exponential decay |
| Q2 | Bloch Sphere | TelemetryPanel.jsx:348 | phi0 × 10π scaling has no physical justification |
| Q3 | VLM | nvidia_client.py:66 | Model not told current `hardware_drift` value, limiting inference accuracy |
| Q4 | VLM | main.py:263 | `outcome_fidelity = confidence` is circular reasoning |
| Q5 | Noise | TelemetryPanel.jsx:89 | `noise_floor = 0.15 × phase_damping` is ad-hoc; creates non-zero steady-state |
| Q6 | Charts | TelemetryPanel.jsx:69-107 | Chart is purely analytical; actual Qiskit data is received but not rendered |
| Q7 | Convention | TelemetryPanel.jsx | Y-axis as quantization axis is non-standard |

---

## Overall Confidence Score

**5.2 / 10**

### Rationale

| Dimension | Score | Justification |
|-----------|-------|---------------|
| Noise Model (T1/T2) | 8/10 | Correct Qiskit noise model, proper T2 ≤ 2T1 constraint; only docked for ad-hoc depolarizing coupling and frontend noise_floor |
| Rabi Circuit Design | 7/10 | Physically valid Rx sweep with proper noise injection; docked for drift having no effect |
| Drift Physics | 2/10 | Dead code in backend, 50× scaling mismatch, zero simulation sensitivity — the most severe subsystem failure |
| Bloch Sphere | 4/10 | Internally consistent convention but θ=171° vs \|0⟩ label is wrong, linear T1, arbitrary φ scaling |
| VLM Calibration | 5/10 | Conceptually valid approach but missing drift input, circular fidelity, no bounds checking |
| Correction Pipeline | 5/10 | Values preserved correctly but semantic ambiguity in `corrected` vs `compensation` naming |
| Visualization | 4/10 | Aliased by undersampling, backend data not rendered, pure analytical display rather than simulated data |
| Metric Consistency | 3/10 | T1 units match; everything else (drift scale, amplitude semantics, ω₀ source) diverges |

### Weighted assessment

The system correctly implements the **noise physics** and **circuit generation** at the Qiskit level. The Rabi experiment with thermal relaxation + depolarizing errors is a legitimate noisy simulation. However, the **drift model is non-functional** (dead code, no effect on simulation), the **visualization is divergent** from simulation output, and several **semantic mismatches** between frontend and backend create inconsistencies in what the user sees vs what the physics engine computes.

The critical path from user input → Qiskit simulation → model inference → correction display is broken at the drift node: the user's drift slider does nothing to the backend simulation, yet the calibration model is asked to infer drift corrections from that simulation's output. The Bloch sphere and Rabi chart render analytical approximations that don't reflect the actual Qiskit probabilities.

---

## Suggested Fixes (Only Where Necessary)

### Fix B1 — `compute_analytical_rabi` noise_floor
```python
# ADD phase_damping as a function parameter
def compute_analytical_rabi(
    t1_relaxation: float,
    phase_damping: float = 0.0,  # <-- ADD THIS
    drift_mhz: float = 0.0,
    ...
) -> list[float]:
    ...
    noise_floor = phase_damping * 0.15  # Now in scope
```

### Fix B2 — Make drift affect the simulation
The simplest fix: apply drift as a detuning offset to the theta sweep rather than computing an unused omega_drive. In `get_rabi_circuits`, the drift should modify the rotation angles:
```python
# Replace dead-code omega_drive with actual theta modulation
omega_drive = OMEGA_0_GHZ - (drift_mhz * DRIFT_SCALE)
# Use ratio to scale theta: if drive is off-resonance, the effective Rabi rate changes
effective_omega_ratio = omega_drive / OMEGA_0_GHZ
effective_theta = pulse_amp_mod * theta_base * effective_omega_ratio
```

### Fix B3 — Align frontend drift scaling
In TelemetryPanel.jsx, apply the same DRIFT_SCALE:
```javascript
const DRIFT_SCALE = 0.02; // must match backend
const delta_omega = (drift_mhz - drift_corrected_mhz) * DRIFT_SCALE;
const omega_drive = omega_0 - delta_omega;
```

### Fix B4 — Fix the |0⟩ label or the amplitude mapping
Either:
- Fix the label to `≡ |1⟩` when amplitude ≈ 0.95, OR
- Change theta mapping to `theta0 = (1 - amplitude) * π` so amplitude=0.95 → θ=9° ≈ |0⟩

### Fix B6 — Use consistent pulse amplitude
In the frontend Rabi chart, use the `pulse_amp_mod` from the store (1.0) instead of `qubitState.amplitude` (0.95):
```javascript
const pulse_amp_mod_base = 1.0; // matches backend default
const A = pulse_amp_mod_base + pi_pulse_amp_offset;
```

---

*End of audit.*
