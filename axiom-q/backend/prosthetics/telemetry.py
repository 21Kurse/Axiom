"""
Prosthetics Quantum Telemetry Simulator
========================================
Generates a 6×6 pressure-sensor grid representing bladder-cell pressures
in a prosthetic limb socket (target ~8–12 kPa).

Uses the existing Qiskit Aer thermal-relaxation noise model from the Axiom.Q
quantum engine to inject physically-motivated 'drift' — simulating autonomous
limb swelling, shifting, or temperature-driven material expansion.

Each cell maps to one qubit; a short Hadamard + measurement circuit is run
through the noise model and the resulting bitstring selects which cells
experience drift (pressure increase of 30–60%).
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, thermal_relaxation_error

# ── Constants ──────────────────────────────────────────────────────────
GRID_ROWS = 6
GRID_COLS = 6
NUM_CELLS = GRID_ROWS * GRID_COLS          # 36 cells → 36 qubits

# Fallback pressure range (used when the Arduino is not connected).
DEFAULT_PRESSURE_MIN_KPA = 8.0
DEFAULT_PRESSURE_MAX_KPA = 12.0

# At pot_value == 0 the drift is gentle (the patient is at rest);
# at pot_value == 1 the drift is severe (compartment-syndrome style).
DRIFT_FACTOR_MIN_REST = 1.05
DRIFT_FACTOR_MAX_REST = 1.20
DRIFT_FACTOR_MIN_FULL = 1.30
DRIFT_FACTOR_MAX_FULL = 1.60

DRIFT_CELL_COUNT_MIN = 2
DRIFT_CELL_COUNT_MAX = 18

# Pot → drift parameters (linear ramps, clamped)
POT_THRESHOLD_FIRE = 0.30   # above this, fire the live demo
POT_TARGET_KPA_PEAK = 30.0  # worst-case peak pressure at pot_value == 1

SHOTS = 1024

# Noise-model hardware assumptions (consistent with quantum_engine.py)
T_GATE_NS = 50.0


def generate_target_array(seed: int | None = None) -> np.ndarray:
    """Create a 6×6 target pressure array with values uniformly sampled from [8, 12] kPa."""
    pmin, pmax = DEFAULT_PRESSURE_MIN_KPA, DEFAULT_PRESSURE_MAX_KPA
    rng = np.random.default_rng(seed)
    return rng.uniform(pmin, pmax, size=(GRID_ROWS, GRID_COLS))


def _build_thermal_noise_model(t1_factor: float = 0.5,
                                phase_factor: float = 0.3) -> NoiseModel:
    """
    Build a thermal-relaxation noise model identical in structure to the one
    in :pymod:`backend.quantum_engine` but tuned for the prosthetics use-case.

    Parameters
    ----------
    t1_factor : float
        Controls T1 decay severity (0 = no decay, 1 = extreme decay).
    phase_factor : float
        Controls T2 dephasing severity (0 = none, 1 = extreme).
    """
    noise_model = NoiseModel()

    t1 = max(100.0, 100_000.0 * (1.0 - t1_factor))
    t2 = max(50.0, (2.0 * t1) * (1.0 - phase_factor))
    t2 = min(t2, 2.0 * t1)

    error = thermal_relaxation_error(t1, t2, T_GATE_NS)
    noise_model.add_all_qubit_quantum_error(error, ["h"])  # applied to Hadamard

    return noise_model


def inject_drift(
    target: np.ndarray,
    t1_factor: float = 0.5,
    phase_factor: float = 0.3,
    seed: int | None = None,
    pot_value: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply quantum-noise-driven drift to *target* using a memory-efficient
    patchwork approach.

    ``pot_value`` (the limb-shift knob, ``[0, 1]``) scales:

    - The per-cell pressure *magnitude* (``drift_factor``)
    - The *number* of cells that drift
    - Optional peak-ceiling when pressure exceeds ``POT_TARGET_KPA_PEAK``

    At ``pot_value == 0`` the system is at rest: tiny drifts (5–20 %).
    At ``pot_value == 1`` the limb has shifted aggressively: 30–60 %
    drifts across up to 18 of the 36 cells.
    """
    pot = max(0.0, min(1.0, float(pot_value)))

    drift_min = DRIFT_FACTOR_MIN_REST + (DRIFT_FACTOR_MIN_FULL - DRIFT_FACTOR_MIN_REST) * pot
    drift_max = DRIFT_FACTOR_MAX_REST + (DRIFT_FACTOR_MAX_FULL - DRIFT_FACTOR_MAX_REST) * pot
    n_drift = int(round(DRIFT_CELL_COUNT_MIN +
                        (DRIFT_CELL_COUNT_MAX - DRIFT_CELL_COUNT_MIN) * pot))

    rng = np.random.default_rng(seed)
    noise_model = _build_thermal_noise_model(t1_factor, phase_factor)
    simulator = AerSimulator()

    total_drift_pattern = ""
    target_n_qubits = max(1, (n_drift + 0) // 1)  # 36 cells = 36 bits
    n_circuits = max(1, target_n_qubits // 6)

    # Memory-efficient 'patchwork' approach: 6-qubit circuits, run repeatedly
    # until we have at least ``n_drift`` drifty bits to apply.
    while len(total_drift_pattern) < 36:
        for _ in range(n_circuits):
            qc = QuantumCircuit(6, 6)
            qc.h(range(6))
            qc.measure(range(6), range(6))

            transpiled = transpile(qc, simulator)
            result = simulator.run(transpiled, noise_model=noise_model, shots=SHOTS).result()
            counts = result.get_counts(qc)
            most_frequent = max(counts, key=counts.get)
            total_drift_pattern += most_frequent
            if len(total_drift_pattern) >= 36:
                break

    drifted = target.copy()

    # Apply pressure increases where bits are '1', capped at the first
    # ``n_drift`` cells we encounter (in row-major order).
    drifted_count = 0
    for idx, bit in enumerate(total_drift_pattern):
        if drifted_count >= n_drift:
            break
        if bit == "1":
            row, col = divmod(idx, GRID_COLS)
            factor = rng.uniform(drift_min, drift_max)
            drifted[row, col] = target[row, col] * factor
            # Soft-cap at peak to keep the heatmap's red range meaningful
            drifted[row, col] = min(drifted[row, col], POT_TARGET_KPA_PEAK)
            drifted_count += 1

    return target, drifted


def run_telemetry(
    t1_factor: float = 0.5,
    phase_factor: float = 0.3,
    seed: int | None = None,
    pot_value: float = 0.0,
) -> dict:
    """
    Top-level entry point for Phase 1 – Step 2.

    ``pot_value`` propagates into :func:`inject_drift` and scales the
    magnitude and the number of drift cells for the limb-shift simulation.

    Returns
    -------
    dict with keys:
        target    : np.ndarray  – clean 6×6 pressure grid (kPa)
        drifted   : np.ndarray  – drifted 6×6 pressure grid (kPa)
        drift_cells : list[tuple[int,int]] – (row, col) pairs that were shifted
        pot_value : float       – the input knob value (echoed for downstream)
        telemetry_mode : str    – "simulated" (Qiskit) for this slice
    """
    target_original = generate_target_array(seed)
    target, drifted = inject_drift(
        target_original,
        t1_factor=t1_factor,
        phase_factor=phase_factor,
        seed=seed,
        pot_value=pot_value,
    )

    # Identify which cells actually changed
    diff = np.abs(drifted - target) > 0.01
    drift_cells = list(zip(*np.where(diff)))

    return {
        "target": target,
        "drifted": drifted,
        "drift_cells": drift_cells,
        "pot_value": float(pot_value),
        "telemetry_mode": "simulated",
    }
