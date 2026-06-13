import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, thermal_relaxation_error, depolarizing_error
import asyncio

# Simulation constants
THETA_STEPS = 50
SHOTS = 1024

def get_rabi_circuits():
    """
    Programmatically compiles a Qiskit quantum circuit executing a standard Rabi Oscillation experiment
    via a parameterized Rx-gate pulse sweep.
    """
    circuits = []
    # Sweep from 0 to 4*pi to see multiple oscillations (Rabi drive)
    thetas = np.linspace(0, 4 * np.pi, THETA_STEPS)
    for idx, theta in enumerate(thetas):
        qc = QuantumCircuit(1, 1, name=f"rabi_{idx}")
        qc.rx(theta, 0)
        qc.measure(0, 0)
        circuits.append(qc)
    return circuits

def build_noise_model(t1_relaxation: float, phase_damping: float) -> NoiseModel:
    """
    Construct a realistic quantum noise model using thermal relaxation and depolarizing errors
    dynamically configured by the inbound parameters from the WebSocket stream.
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

async def run_rabi_simulation(t1_relaxation: float, phase_damping: float):
    """
    Executes the noisy Rabi circuit utilizing AerSimulator and extracts the final measurement counts.
    Runs in an executor to avoid blocking the asyncio event loop.
    """
    loop = asyncio.get_running_loop()
    
    def _simulate():
        circuits = get_rabi_circuits()
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
