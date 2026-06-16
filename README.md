# Axiom

Axiom is a closed-loop hardware calibration system designed to treat real-world physical variances and environmental degradation as biological and hardware noise. By leveraging the **NVIDIA Ising-Calibration-1-35B VLM**, the system bridges biomedical engineering and quantum computing, deploying real-time corrective actions for both prosthetic socket shifts and qubit pulse schedules.

## 🚀 Core Functionality

Throughout the day, prosthetic users experience limb volume shifts, leading to discomfort, blisters, and loss of limb control. Axiom treats these physical volume shifts as **biological hardware noise**.

* **Biomedical Feedback Loop:** The system monitors a 36-cell Force-Sensitive Resistor (FSR) pressure heatmap inside a prosthetic socket. The NVIDIA Ising VLM diagnoses fit degradation and drives physical servos to autonomously re-tension an internal conforming mesh.
* **Quantum Architecture Generalization:** The exact same closed-loop control plane applies to quantum environments. The system captures noisy Rabi oscillation plots caused by thermal relaxation. The Ising VLM diagnoses this geometric drift and returns a structured JSON payload to dynamically update the qubit's pulse schedule.

---

## 🛠️ Tech Stack & Architecture

| Layer | Technologies Used |
| :--- | :--- |
| **AI / Inference** | NVIDIA Ising-Calibration-1-35B VLM (via secure WebSocket tunneling) |
| **Hardware / Firmware** | Raspberry Pi (Production Target), Arduino (Prototyping), KiCad (Schematics), FSR Matrix |
| **Software / Engine** | Python, Google Antigravity, VS Code, Git |
| **Database** | MongoDB (Telemetry, Qubit State, and Heatmap Storage) |

---

## ⚡ Engineering Triumphs & Challenges Overcome

* **94% Latency Reduction:** Successfully optimized the quantum calibration cycle, bringing latency down from **90 seconds → 64 seconds → 5.4 seconds** for real-time viability.
* **Heterogeneous Telemetry Pipelines:** Architected and debugged multi-port WebSocket connections to handle parallel streams of MongoDB data, image inputs, and 36-cell heatmap vectors.
* **Full Hardware Mapping:** Designed complete circuit schematics in KiCad mapping out the full Raspberry Pi control plane alongside the Arduino sensory prototype.
