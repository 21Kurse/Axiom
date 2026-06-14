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
PRESSURE_MIN_KPA = 8.0
PRESSURE_MAX_KPA = 12.0
DRIFT_FACTOR_MIN = 1.30                     # 30 % increase
DRIFT_FACTOR_MAX = 1.60                     # 60 % increase
DRIFT_CELL_COUNT_MIN = 3
DRIFT_CELL_COUNT_MAX = 5
SHOTS = 1024

# Noise-model hardware assumptions (consistent with quantum_engine.py)
T_GATE_NS = 50.0


def generate_target_array(seed: int | None = None) -> np.ndarray:
    """
    Create a 6×6 target pressure array with values uniformly sampled
    from [PRESSURE_MIN_KPA, PRESSURE_MAX_KPA].
    """
    rng = np.random.default_rng(seed)
    return rng.uniform(PRESSURE_MIN_KPA, PRESSURE_MAX_KPA,
                       size=(GRID_ROWS, GRID_COLS))


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


def _run_drift_circuit(noise_model: NoiseModel) -> str:
    """
    Run NUM_CELLS independent single-qubit H+measure circuits through the
    noisy simulator and concatenate the dominant bit from each into a bitstring.

    Running one qubit at a time is memory-efficient (avoids the 2^36 statevector)
    while still injecting identical thermal-relaxation noise on every qubit.
    """
    # Build all single-qubit circuits in one list for a single simulator.run() call
    circuits = []
    for _ in range(NUM_CELLS):
        qc = QuantumCircuit(1, 1)
        qc.h(0)
        qc.measure(0, 0)
        circuits.append(qc)

    simulator = AerSimulator()
    transpiled = transpile(circuits, simulator)
    result = simulator.run(
        transpiled, noise_model=noise_model, shots=SHOTS
    ).result()

    # For each qubit, pick the dominant measured bit
    bitstring = ""
    for i in range(NUM_CELLS):
        counts = result.get_counts(i)
        dominant_bit = max(counts, key=counts.get)
        bitstring += dominant_bit

    return bitstring


def inject_drift(
    target: np.ndarray,
    t1_factor: float = 0.5,
    phase_factor: float = 0.3,
    seed: int | None = None,
) -> np.ndarray:
    """
    Apply quantum-noise-driven drift to *target*.

    1. Build the thermal-relaxation noise model.
    2. Run the 36-qubit Hadamard circuit through Aer.
    3. Use the resulting bitstring to select 3–5 cells.
    4. Increase each selected cell's pressure by 30–60 %.

    Returns
    -------
    np.ndarray
        A copy of *target* with drift applied.
    """
    rng = np.random.default_rng(seed)
    noise_model = _build_thermal_noise_model(t1_factor, phase_factor)
    bitstring = _run_drift_circuit(noise_model)

    # Pad / trim the bitstring to exactly NUM_CELLS
    bitstring = bitstring.ljust(NUM_CELLS, "0")[:NUM_CELLS]

    # Indices where the noisy circuit measured |1⟩
    candidate_indices = [i for i, bit in enumerate(bitstring) if bit == "1"]

    # If too few candidates, fall back to random selection
    if len(candidate_indices) < DRIFT_CELL_COUNT_MIN:
        candidate_indices = rng.choice(
            NUM_CELLS, size=DRIFT_CELL_COUNT_MIN, replace=False
        ).tolist()

    # Sub-sample to 3–5 cells
    n_drift = rng.integers(DRIFT_CELL_COUNT_MIN, DRIFT_CELL_COUNT_MAX + 1)
    if len(candidate_indices) > n_drift:
        chosen = rng.choice(candidate_indices, size=n_drift, replace=False).tolist()
    else:
        chosen = candidate_indices[:n_drift]

    drifted = target.copy()
    for idx in chosen:
        row, col = divmod(idx, GRID_COLS)
        factor = rng.uniform(DRIFT_FACTOR_MIN, DRIFT_FACTOR_MAX)
        drifted[row, col] *= factor

    return drifted


def run_telemetry(
    t1_factor: float = 0.5,
    phase_factor: float = 0.3,
    seed: int | None = None,
) -> dict:
    """
    Top-level entry point for Phase 1 – Step 2.

    Returns
    -------
    dict with keys:
        target  : np.ndarray  – clean 6×6 pressure grid (kPa)
        drifted : np.ndarray  – drifted 6×6 pressure grid (kPa)
        drift_cells : list[tuple[int,int]] – (row, col) pairs that were shifted
    """
    target = generate_target_array(seed)
    drifted = inject_drift(target, t1_factor, phase_factor, seed)

    # Identify which cells actually changed
    diff = np.abs(drifted - target) > 0.01
    drift_cells = list(zip(*np.where(diff)))

    return {
        "target": target,
        "drifted": drifted,
        "drift_cells": drift_cells,
    }
