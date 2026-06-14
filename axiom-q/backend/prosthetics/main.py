"""
Prosthetics Pipeline Runner
=============================
Orchestrates the full Phase 1 pipeline in sequence:

    1. telemetry  → generate target grid + inject quantum-noise drift
    2. heatmap    → render side-by-side PNG (saved as heatmap_noisy.png)
    3. agent      → send heatmap to NVIDIA VLM for diagnosis
    4. healing    → apply VLM-recommended corrections
    5. ledger     → record the full cycle

Run directly:
    python -m backend.prosthetics.main
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os

# Ensure the project root is on the path so `backend.*` imports work
# when running this file directly.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.prosthetics.telemetry import run_telemetry
from backend.prosthetics.heatmap import render_heatmap
from backend.prosthetics.agent import analyze
from backend.prosthetics.healing import heal, send_to_arduino, create_healing_gif
from backend.prosthetics.ledger import record, print_timeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("axiom-q.prosthetics")


async def run_pipeline(
    t1_factor: float = 0.5,
    phase_factor: float = 0.3,
    seed: int | None = None,
) -> dict:
    """
    Execute the full prosthetics telemetry → healing pipeline.

    Parameters
    ----------
    t1_factor : float
        T1 relaxation severity for the drift noise model (0–1).
    phase_factor : float
        Phase-damping severity for the drift noise model (0–1).
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    dict
        Summary of the pipeline run including paths and status.
    """
    # ── Step 1: Quantum Telemetry ──────────────────────────────────────
    log.info("═══ Step 1/5 — Quantum Telemetry Simulation ═══")
    telemetry = run_telemetry(t1_factor, phase_factor, seed)
    target = telemetry["target"]
    drifted = telemetry["drifted"]
    drift_cells = telemetry["drift_cells"]

    log.info("  Target grid  : mean=%.2f kPa", target.mean())
    log.info("  Drifted grid : mean=%.2f kPa", drifted.mean())
    log.info("  Drift cells  : %d cells shifted %s", len(drift_cells), drift_cells)

    # ── Step 2: Heatmap Rendering ──────────────────────────────────────
    log.info("═══ Step 2/5 — Heatmap Rendering ═══")
    out_dir = os.path.dirname(os.path.abspath(__file__))
    heatmap_path = render_heatmap(
        target,
        drifted,
        out_path=os.path.join(out_dir, "heatmap_noisy.png"),
    )
    log.info("  Saved heatmap → %s", heatmap_path)

    # ── Step 3: VLM Agent Analysis ─────────────────────────────────────
    log.info("═══ Step 3/5 — VLM Agent Analysis ═══")
    diagnosis = await analyze(heatmap_path, drift_cells)
    log.info("  Drift zone     : %s", diagnosis.get("drift_zone", "n/a"))
    log.info("  Affected cells : %s", diagnosis.get("affected_cells", []))
    log.info("  Confidence     : %.2f", float(diagnosis.get("confidence", 0.0)))

    # ── Step 4: Self-Healing ───────────────────────────────────────────
    log.info("═══ Step 4/5 — Self-Healing ═══")
    healed = heal(drifted, diagnosis)
    log.info("  Healed grid mean: %.2f kPa", healed.mean())
    
    log.info("  [Hero Demo] Sending cell corrections to Arduino via serial...")
    send_to_arduino(diagnosis)
    
    log.info("  [Hero Demo] Generating healing animation GIF...")
    gif_path = create_healing_gif(drifted, healed, out_path=os.path.join(out_dir, "healing.gif"))

    # ── Step 5: Audit Ledger ───────────────────────────────────────────
    log.info("═══ Step 5/5 — Audit Ledger ═══")
    entry = record(target, drifted, drift_cells, diagnosis, healed)
    log.info("  Ledger entry timestamp: %s", entry.get("timestamp"))

    log.info("═══ Pipeline complete ═══")
    
    print_timeline()

    return {
        "heatmap_path": heatmap_path,
        "healing_gif_path": gif_path,
        "drift_cells": drift_cells,
        "diagnosis": diagnosis,
        "ledger_entry": entry,
    }


def main():
    """CLI entry point."""
    result = asyncio.run(run_pipeline())
    print(f"\n✅ Heatmap saved to: {result['heatmap_path']}")
    print(f"✅ Healing animation saved to: {result['healing_gif_path']}")
    print(f"   Drift cells affected: {len(result['drift_cells'])}\n")
    
    print("🎥 **INSURANCE POLICY VIDEO INSTRUCTIONS** 🎥")
    print("Please record the screen and the physical servo moving simultaneously")
    print("using your phone or a screen recording tool with your webcam.")
    print("This serves as proof of autonomous adjustment for the patient's insurance ledger.")


if __name__ == "__main__":
    main()
