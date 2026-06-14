"""
Prosthetics Pipeline Runner
=============================
Orchestrates the full Phase 1 pipeline in sequence:

    1. telemetry  → generate target grid + inject quantum-noise drift
    2. heatmap    → render side-by-side PNG (saved as heatmap_noisy.png)
    3. agent      → (stub) send heatmap to VLM for diagnosis
    4. healing    → (stub) apply VLM corrections
    5. ledger     → (stub) record the full cycle

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
from backend.prosthetics.healing import heal
from backend.prosthetics.ledger import record

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
    log.info("  Diagnosis status: %s", diagnosis.get("status"))

    # ── Step 4: Self-Healing ───────────────────────────────────────────
    log.info("═══ Step 4/5 — Self-Healing ═══")
    corrections = diagnosis.get("corrections", [])
    healed = heal(drifted, corrections)
    log.info("  Healed grid mean: %.2f kPa", healed.mean())

    # ── Step 5: Audit Ledger ───────────────────────────────────────────
    log.info("═══ Step 5/5 — Audit Ledger ═══")
    entry = record(target, drifted, drift_cells, diagnosis, healed)
    log.info("  Ledger entry: %s", entry)

    log.info("═══ Pipeline complete ═══")

    return {
        "heatmap_path": heatmap_path,
        "drift_cells": drift_cells,
        "diagnosis": diagnosis,
        "ledger_entry": entry,
    }


def main():
    """CLI entry point."""
    result = asyncio.run(run_pipeline())
    print(f"\n✅ Heatmap saved to: {result['heatmap_path']}")
    print(f"   Drift cells affected: {len(result['drift_cells'])}")


if __name__ == "__main__":
    main()
