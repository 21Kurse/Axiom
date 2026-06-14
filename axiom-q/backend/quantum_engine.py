"""
Axiom.Q Closed-Loop Quantum Simulation Engine

Implements the physically correct Rabi oscillation model:
  P1(t) = A * sin((Ω_drive) * t) * exp(-t / T1) + Noise_Floor

where:
  Ω_drive = Ω_0 - (Δω_hardware - Δω_corrected)   (closed-loop drive)
  A        = pulse_amp_mod                       (calibration pulse parameter)
  T1       = longitudinal relaxation time        (environmental, constant)
  T2       = transverse dephasing time           (environmental, constant)

Calibration modifies Ω_drive and A, NOT T1/T2.
"""

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, thermal_relaxation_error, depolarizing_error
import asyncio

# Simulation constants
THETA_STEPS = 50
SHOTS = 1024

# Physics defaults
OMEGA_0_GHZ = 4.8          # baseline resonance (GHz, same as qubit frequency)
DRIFT_SCALE = 0.02          # rad/µs per MHz of drift


def get_rabi_circuits(drift_mhz: float = 0.0, pulse_amp_mod: float = 1.0):
    """
    Programmatically compiles Qiskit quantum circuits executing a Rabi
    oscillation experiment with closed-loop physics:

    The drive frequency is shifted by the residual drift:
      Ω_drive = Ω_0 + Δω
    The pulse amplitude scales the Rx rotation:
      theta_eff = pulse_amp_mod * theta_sweep

    This means calibration (pulse_amp_mod, drift_compensation) directly
    modifies the control pulse, NOT the noise environment.
    """
    circuits = []
    thetas = np.linspace(0, 4 * np.pi, THETA_STEPS)

    # Effective drive: baseline - residual drift
    # Ω_drive = Ω_0 - Δω
    omega_drive = OMEGA_0_GHZ - (drift_mhz * DRIFT_SCALE)

    # Detuned drive reduces effective Rabi rotation rate proportionally
    rabi_ratio = omega_drive / OMEGA_0_GHZ

    for idx, theta_base in enumerate(thetas):
        qc = QuantumCircuit(1, 1, name=f"rabi_{idx}")
        effective_theta = pulse_amp_mod * theta_base * rabi_ratio
        qc.rx(effective_theta, 0)
        qc.measure(0, 0)
        circuits.append(qc)
    return circuits


def build_noise_model(t1_relaxation: float, phase_damping: float) -> NoiseModel:
    """
    Construct a realistic quantum noise model using thermal relaxation and
    depolarizing errors, dynamically configured from the WebSocket parameters.

    T1 and T2 are PURELY ENVIRONMENTAL — they are NEVER modified by calibration.
    Calibration adjusts the control pulse (amplitude + drift correction), not
    the physical decoherence channels.
    """
    noise_model = NoiseModel()

    # Base physical hardware assumptions
    t_gate = 50.0  # ns (single-qubit gate time)

    # Interpolate input sliders (0.0 to 1.0) into physical error rates
    # If t1_relaxation is 0.0, T1 is virtually infinite (100,000 ns). If 1.0, it's very short (100 ns).
    t1 = max(100.0, 100000.0 * (1.0 - t1_relaxation))

    # T2 must physically satisfy T2 <= 2*T1
    t2 = max(50.0, (2.0 * t1) * (1.0 - phase_damping))
    t2 = min(t2, 2.0 * t1)

    # Add thermal relaxation error to 'rx' (which acts as our drive pulse)
    error_1q = thermal_relaxation_error(t1, t2, t_gate)
    noise_model.add_all_qubit_quantum_error(error_1q, ['rx'])

    # Additional depolarizing error to simulate intense phase_damping
    if phase_damping > 0.0:
        depol_error = depolarizing_error(phase_damping * 0.1, 1)
        noise_model.add_all_qubit_quantum_error(depol_error, ['rx'])

    return noise_model


async def run_rabi_simulation(
    t1_relaxation: float,
    phase_damping: float,
    drift_mhz: float = 0.0,
    pulse_amp_mod: float = 1.0,
):
    """
    Executes the noisy Rabi circuit using AerSimulator.

    The noise model (T1, T2) is driven ONLY by t1_relaxation and phase_damping
    (environmental / hardware parameters that the user controls via sliders).
    Calibration does NOT touch these — instead it adjusts:
      - drift_mhz: residual hardware drift (after calibration correction)
      - pulse_amp_mod: microwave pulse amplitude modifier

    Returns the raw Qiskit simulation probabilities (noisy telemetry).
    """
    loop = asyncio.get_running_loop()

    def _simulate():
        circuits = get_rabi_circuits(drift_mhz=drift_mhz, pulse_amp_mod=pulse_amp_mod)
        simulator = AerSimulator()

        noise_model = build_noise_model(t1_relaxation, phase_damping)

        # Transpile and execute
        transpiled_circuits = transpile(circuits, simulator)
        result = simulator.run(transpiled_circuits, noise_model=noise_model, shots=SHOTS).result()

        # Extract final measurement count dictionaries and raw float probabilities
        raw_counts = []
        probabilities = []

        for i in range(THETA_STEPS):
            counts = result.get_counts(i)
            raw_counts.append(counts)

            # Probability of measuring the excited state |1>
            p1 = counts.get('1', 0) / SHOTS
            probabilities.append(p1)

        return {
            "probabilities": probabilities,
            "raw_counts": raw_counts
        }

    return await loop.run_in_executor(None, _simulate)


def compute_analytical_rabi(
    t1_relaxation: float,
    phase_damping: float = 0.0,
    drift_mhz: float = 0.0,
    pulse_amp_mod: float = 1.0,
    duration_us: float = 200.0,
    points: int = 150,
) -> list[float]:
    """
    Compute the closed-loop analytical Rabi oscillation probability series.

    P1(t) = A * sin((Ω_0 - Δω) * t) * e^(-t / T1) + Noise_Floor

    This function is used by the backend to render the Rabi chart when
    real Qiskit telemetry isn't flowing (or as a visual comparison).
    """
    t_arr = np.linspace(0, duration_us, points)

    omega_drive = OMEGA_0_GHZ - (drift_mhz * DRIFT_SCALE)
    T1_us = max(0.1, (1.0 - t1_relaxation) * 100)
    noise_floor = phase_damping * 0.15

    theta_base = (t_arr / duration_us) * 4 * np.pi
    rabi_ratio = omega_drive / OMEGA_0_GHZ
    effective_theta = pulse_amp_mod * theta_base * rabi_ratio

    p_e = (np.sin(effective_theta / 2) ** 2) * envelope + noise_floor

    return p_e.tolist()
