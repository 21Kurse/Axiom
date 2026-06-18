"""
Prosthetics Pipeline Runner
=============================
Orchestrates the full Phase 1 pipeline in sequence:

    1. telemetry  → generate target grid + inject quantum-noise drift
    2. heatmap    → render side-by-side PNG (saved as heatmap_noisy.png)
    3. agent      → send heatmap to NVIDIA VLM for diagnosis
    4. healing    → apply VLM-recommended corrections
    5. ledger     → record the full cycle

Phase 2 (v2 slice — all-virtual):

* ``pot_value`` ∈ [0, 1] drives the Qiskit drift magnitude and cell count.
* Each cycle's cell states are emitted via an async ``broadcast`` hook that
  forwards to a WebSocket (live mode) — the Three.js frontend tweens its mesh
  in lockstep with the heal animation.

Run directly:

    python -m backend.prosthetics.main --mode oneshot [--seed N] [--save-gif]
    python -m backend.prosthetics.main --mode replay --n-cycles 5
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import sys
from typing import Awaitable, Callable, Optional

# Ensure the project root is on the path so `backend.*` imports work
# when running this file directly.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.prosthetics.telemetry import run_telemetry
from backend.prosthetics.heatmap import render_heatmap
from backend.prosthetics.agent import analyze
from backend.prosthetics.healing import (
    cells_state_payload,
    create_healing_gif,
    diagnosis_summary,
    heal,
    heal_animated,
)
from backend.prosthetics.ledger import record, print_timeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("axiom-q.prosthetics")

# Async-safe broadcast hook used by the live WebSocket path.
BroadcastFn = Callable[[dict], Awaitable[None]]

# Shared output directory for /assets artifacts the frontend may serve.
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── One cycle ─────────────────────────────────────────────────────────
async def run_one_cycle(
    pot_value: float = 0.0,
    t1_factor: float = 0.5,
    phase_factor: float = 0.3,
    seed: int | None = None,
    broadcast: Optional[BroadcastFn] = None,
    save_gif: bool = False,
    frame_interval_s: float = 0.05,
) -> dict:
    """
    Execute the full prosthetics telemetry → healing pipeline once.

    Parameters
    ----------
    pot_value : float
        Limb-shift knob value in ``[0, 1]``. Controls drift magnitude and
        cell count via :func:`telemetry.inject_drift`.
    t1_factor, phase_factor : float
        Noise-model severities (passed through transparently).
    seed : int, optional
        Random seed (used for both the drift generator and the demo
        reproducibility — pass ``42`` for judges).
    broadcast : async callable, optional
        Awaited with typed event dicts (``status``, ``cell_state``,
        ``diagnosis``). Frontend WebSocket client consumes these.
    save_gif : bool
        Also persist a ``healing.gif`` for the README / insurance video.
    frame_interval_s : float
        Per-frame sleep during the heal animation (≈ 20 fps at 0.05).
    """
    pot_value = max(0.0, min(1.0, float(pot_value)))
    if broadcast is not None:
        await broadcast({
            "type": "status",
            "phase": "DRIFT_INJECTING",
            "pot_value": pot_value,
        })

    # ── Step 1: Quantum Telemetry ──────────────────────────────────────
    log.info("═══ Step 1/5 — Quantum Telemetry Simulation (pot=%.2f) ═══", pot_value)
    telemetry = run_telemetry(t1_factor, phase_factor, seed, pot_value=pot_value)
    target = telemetry["target"]
    drifted = telemetry["drifted"]
    drift_cells = telemetry["drift_cells"]

    log.info("  Target grid  : mean=%.2f kPa", target.mean())
    log.info("  Drifted grid : mean=%.2f kPa", drifted.mean())
    log.info("  Drift cells  : %d cells shifted", len(drift_cells))

    if broadcast is not None:
        await broadcast(cells_state_payload(drifted, phase="drifted", frame=0))

    # ── Step 2: Heatmap Rendering ──────────────────────────────────────
    log.info("═══ Step 2/5 — Heatmap Rendering ═══")
    heatmap_path = render_heatmap(
        target,
        drifted,
        out_path=os.path.join(OUT_DIR, "heatmap_noisy.png"),
    )
    log.info("  Saved heatmap → %s", heatmap_path)

    if broadcast is not None:
        await broadcast({"type": "heatmap", "path": heatmap_path})

    # ── Step 3: VLM Agent Analysis ─────────────────────────────────────
    log.info("═══ Step 3/5 — VLM Agent Analysis ═══")
    if broadcast is not None:
        await broadcast({"type": "status", "phase": "DIAGNOSING"})
    diagnosis = await analyze(heatmap_path, drift_cells)
    log.info("  Drift zone     : %s", diagnosis.get("drift_zone", "n/a"))
    log.info("  Affected cells : %s", diagnosis.get("affected_cells", []))
    log.info("  Confidence     : %.2f", float(diagnosis.get("confidence", 0.0)))

    if broadcast is not None:
        await broadcast({
            "type": "diagnosis",
            "data": diagnosis_summary(diagnosis),
        })

    # ── Step 4: Self-Healing ───────────────────────────────────────────
    log.info("═══ Step 4/5 — Self-Healing ═══")
    if broadcast is not None:
        await broadcast({"type": "status", "phase": "HEALING"})

    target_healed = heal(drifted, diagnosis)

    gif_path = None
    if save_gif:
        gif_path = os.path.join(OUT_DIR, "healing.gif")

    healed = await heal_animated(
        drifted,
        target_healed,
        broadcast=broadcast,
        frames=20,
        frame_interval_s=frame_interval_s,
        save_gif_path=gif_path,
    )
    log.info("  Healed grid mean: %.2f kPa", healed.mean())

    # ── Step 5: Audit Ledger ───────────────────────────────────────────
    log.info("═══ Step 5/5 — Audit Ledger ═══")
    entry = record(target, drifted, drift_cells, diagnosis, healed)
    log.info("  Ledger entry timestamp: %s", entry.get("timestamp"))

    if broadcast is not None:
        await broadcast({
            "type": "status",
            "phase": "READY",
            "cycle_complete": True,
        })

    return {
        "pot_value": pot_value,
        "heatmap_path": heatmap_path,
        "healing_gif_path": gif_path,
        "drift_cells": drift_cells,
        "diagnosis": diagnosis,
        "ledger_entry": entry,
        "target_mean": float(target.mean()),
        "drifted_mean": float(drifted.mean()),
        "healed_mean": float(healed.mean()),
    }


# ── CLI modes ─────────────────────────────────────────────────────────
async def run_oneshot(
    pot_value: float = 0.45,
    seed: int | None = None,
    save_gif: bool = False,
    broadcast: Optional[BroadcastFn] = None,
) -> dict:
    """Run a single cycle (judge demo)."""
    log.info("Running ONESHOT cycle (pot=%.2f, seed=%s)", pot_value, seed)
    return await run_one_cycle(
        pot_value=pot_value,
        seed=seed,
        broadcast=broadcast,
        save_gif=save_gif,
    )


async def run_replay(
    n_cycles: int = 5,
    base_seed: int = 42,
    save_gif: bool = False,
    pot_min: float = 0.30,
    pot_max: float = 0.85,
    broadcast: Optional[BroadcastFn] = None,
) -> list[dict]:
    """Run N cycles with varying pot values (README demo)."""
    log.info("Running REPLAY of %d cycles", n_cycles)
    results = []
    for i in range(n_cycles):
        pot = pot_min + (pot_max - pot_min) * (i + 1) / n_cycles
        seed = base_seed + i
        result = await run_one_cycle(
            pot_value=pot,
            seed=seed,
            broadcast=broadcast,
            save_gif=save_gif and i == n_cycles - 1,
        )
        results.append(result)
        print_timeline()
    return results


def _build_argparse() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="QVis prosthetics pipeline runner")
    p.add_argument(
        "--mode",
        choices=["oneshot", "replay", "live-stub"],
        default="oneshot",
        help=(
            "oneshot: single demo cycle. "
            "replay: N randomized cycles for the README. "
            "live-stub: assert the live ws bridge is wired (no-op). "
            "Live mode itself runs from the FastAPI app."
        ),
    )
    p.add_argument("--seed", type=int, default=None, help="RNG seed (use 42 for demo)")
    p.add_argument("--pot", type=float, default=0.45, help="pot_value ∈ [0,1] for oneshot")
    p.add_argument("--n-cycles", type=int, default=5, help="cycles for replay mode")
    p.add_argument("--save-gif", action="store_true", help="write healing.gif artifact")
    return p


def main():
    args = _build_argparse().parse_args()

    if args.mode == "oneshot":
        result = asyncio.run(run_oneshot(args.pot, args.seed, args.save_gif))
        print(f"\n✅ Heatmap: {result['heatmap_path']}")
        print(f"✅ Healing GIF: {result['healing_gif_path'] or '(none — pass --save-gif)'}")
        print(f"   Drift cells affected: {len(result['drift_cells'])}")

    elif args.mode == "replay":
        asyncio.run(run_replay(args.n_cycles, args.seed or 42, args.save_gif))

    elif args.mode == "live-stub":
        print("'live' mode is driven by /ws/prosthetic on the FastAPI app.")
        print("Start it with:")
        print("    cd axiom-q")
        print("    uvicorn backend.main:app --reload")
        print("Then drag the soft pot slider in the HUD past 0.30.")


if __name__ == "__main__":
    main()
