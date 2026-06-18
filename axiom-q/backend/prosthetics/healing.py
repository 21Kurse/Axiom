"""
Prosthetics Self-Healing Engine
================================
Applies the VLM-recommended corrections from the agent to the drifted
pressure grid, simulating autonomous socket re-calibration.

The agent returns a ``cell_corrections`` dict mapping cell IDs (e.g. "2,3")
to target kPa values.  This module applies those corrections and returns the
healed grid.

Phase 2 (v2 slice — all-virtual): ``send_to_arduino`` is replaced by an
async-friendly :func:`heal_animated` that yields per-frame cell states.
A frontend client subscribes via WebSocket and tweens its Three.js mesh.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Awaitable, Callable, Optional

import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
import matplotlib.pyplot as plt

from backend.prosthetics.heatmap import RYG_CMAP, VMIN, VMAX

log = logging.getLogger("axiom-q.prosthetics.healing")

GRID_ROWS = 6
GRID_COLS = 6

# Optional broadcast hook signature: async (payload: dict) -> None
BroadcastFn = Optional[Callable[[dict], Awaitable[None]]]


def zone_for(row: int, col: int) -> int:
    """
    3-zone dispatch used by the Three.js mesh to group cells into
    proximal / mid / distal band animations.

    Concept preserved from the original 3-servo plan; the output
    target is now a mesh group, not a servo.
    """
    return (row + col) % 3


def cells_state_payload(
    grid: np.ndarray,
    phase: str,
    frame: int = 0,
    final: bool = False,
) -> dict:
    """
    JSON-safe representation of a 6×6 pressure grid for transmission
    over the WebSocket.

    The frontend consumes ``cells`` as a flat list indexed by
    ``row * 6 + col`` and uses ``zones`` to dispatch cells into
    the appropriate Three.js mesh group.

    Parameters
    ----------
    grid : np.ndarray
        6×6 pressure grid (kPa).
    phase : str
        One of: ``"drifted"``, ``"healing"``, ``"healed"``.
    frame : int
        Frame index during animation (0..N-1).
    final : bool
        If True this is the last frame of the heal sequence.
    """
    cells: list[dict[str, Any]] = []
    matrix = np.asarray(grid, dtype=float)
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cells.append({
                "row": r,
                "col": c,
                "kpa": float(matrix[r, c]),
                "zone": zone_for(r, c),
            })
    return {
        "type": "cell_state",
        "phase": phase,
        "frame": int(frame),
        "final": bool(final),
        "cells": cells,
    }


def heal(
    drifted: np.ndarray,
    diagnosis: dict[str, Any],
) -> np.ndarray:
    """
    Apply VLM-diagnosed corrections to the drifted pressure grid.

    Parameters
    ----------
    drifted : np.ndarray
        The current 6×6 pressure grid with drift.
    diagnosis : dict
        VLM agent response containing at least:
        - ``cell_corrections``: dict mapping ``"row,col"`` → target kPa (float)
        - ``affected_cells``: list of ``[row, col]`` pairs
        - ``confidence``: float 0–1

    Returns
    -------
    np.ndarray
        Corrected pressure grid.
    """
    healed = drifted.copy()
    cell_corrections = diagnosis.get("cell_corrections", {})
    confidence = float(diagnosis.get("confidence", 0.0))

    if not cell_corrections:
        log.info("No cell_corrections in VLM response — returning drifted grid as-is.")
        return healed

    applied = 0
    for cell_id, target_kpa in cell_corrections.items():
        try:
            # cell_id can be "2,3" or "2_3" or "[2,3]"
            cleaned = str(cell_id).strip("[]() ")
            parts = cleaned.replace("_", ",").split(",")
            row, col = int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, IndexError):
            log.warning("Skipping unparseable cell_id: %s", cell_id)
            continue

        if not (0 <= row < healed.shape[0] and 0 <= col < healed.shape[1]):
            log.warning("Cell (%d, %d) out of bounds — skipping.", row, col)
            continue

        try:
            target_val = float(target_kpa)
        except (ValueError, TypeError):
            log.warning("Non-numeric target kPa for cell %s: %s", cell_id, target_kpa)
            continue

        old_val = healed[row, col]
        # Blend correction by VLM confidence: full confidence → snap to target
        healed[row, col] = old_val + confidence * (target_val - old_val)
        applied += 1
        log.info(
            "  Cell (%d,%d): %.2f kPa → %.2f kPa (target=%.2f, conf=%.2f)",
            row, col, old_val, healed[row, col], target_val, confidence,
        )

    log.info("Applied %d / %d corrections (confidence=%.2f).",
             applied, len(cell_corrections), confidence)
    return healed


async def heal_animated(
    drifted: np.ndarray,
    healed: np.ndarray,
    broadcast: BroadcastFn = None,
    frames: int = 20,
    frame_interval_s: float = 0.05,
    save_gif_path: Optional[str] = None,
) -> np.ndarray:
    """
    Smoothly interpolate from ``drifted`` to ``healed`` over ``frames``
    steps, optionally broadcasting each frame's cell state via ``broadcast``.

    If ``save_gif_path`` is given, a healing GIF is also written for the
    README / insurance video.

    Returns the final healed grid.
    """
    import asyncio

    final = healed
    if broadcast is not None:
        # Emit the started-d frame so the UI can swap from drifted→healing.
        await broadcast(cells_state_payload(drifted, phase="healing", frame=0))

    for f in range(1, frames + 1):
        progress = f / float(frames)
        current_grid = drifted + (healed - drifted) * progress
        if broadcast is not None:
            is_final = f == frames
            await broadcast(
                cells_state_payload(current_grid, phase="healing", frame=f, final=is_final)
            )
            if is_final:
                await broadcast(
                    cells_state_payload(healed, phase="healed", frame=frames, final=True)
                )
        await asyncio.sleep(frame_interval_s)

    if save_gif_path:
        try:
            create_healing_gif(drifted, healed, save_gif_path)
        except Exception as exc:  # pragma: no cover - cosmetic
            log.warning("GIF save skipped: %s", exc)

    return final


def create_healing_gif(
    drifted: np.ndarray,
    healed: np.ndarray,
    out_path: str = "healing.gif",
) -> str:
    """
    Create an animated GIF showing the 6×6 pressure grid updating cell-by-cell
    from the drifted state back to the target/healed state over 20 frames.

    Used for the static insurance video / README screenshot only.
    The live UI uses :func:`heal_animated` + WebSocket broadcast instead.
    """
    fig, ax = plt.subplots(figsize=(6, 6))
    fig.patch.set_facecolor("#0a0e14")
    ax.set_facecolor("#0f1923")
    ax.set_title("Autonomous Socket Healing", color="white", fontsize=14, pad=15)
    ax.set_xlabel("Column", fontsize=9, color="#94a3b8")
    ax.set_ylabel("Row", fontsize=9, color="#94a3b8")
    ax.tick_params(colors="#64748b", labelsize=8)

    im = ax.imshow(drifted, cmap=RYG_CMAP.reversed(), vmin=VMIN, vmax=VMAX)

    # Store text objects to update them
    texts = []
    rows, cols = drifted.shape
    for r in range(rows):
        row_texts = []
        for c in range(cols):
            val = drifted[r, c]
            text_color = "#0f172a" if val < 14.0 else "#ffffff"
            t = ax.text(
                c, r, f"{val:.1f}",
                ha="center", va="center",
                color=text_color, fontsize=10, fontweight="bold",
            )
            row_texts.append(t)
        texts.append(row_texts)

    frames = 20

    def update(frame):
        progress = frame / float(frames - 1)
        current_grid = drifted + (healed - drifted) * progress

        im.set_array(current_grid)

        for r in range(rows):
            for c in range(cols):
                val = current_grid[r, c]
                text_color = "#0f172a" if val < 14.0 else "#ffffff"
                texts[r][c].set_text(f"{val:.1f}")
                texts[r][c].set_color(text_color)

        return [im]

    anim = FuncAnimation(fig, update, frames=frames, interval=100, blit=False)

    try:
        anim.save(out_path, writer=PillowWriter(fps=10))
        log.info("Saved healing animation -> %s", os.path.abspath(out_path))
    except Exception as e:
        log.error("Failed to save GIF: %s", e)
    finally:
        plt.close(fig)

    return os.path.abspath(out_path)


def diagnosis_summary(diagnosis: dict[str, Any]) -> dict:
    """
    JSON-safe summary of a VLM diagnosis for the inspector panel.
    """
    cell_corrections = diagnosis.get("cell_corrections", {})
    affected = diagnosis.get("affected_cells", [])
    return {
        "confidence": float(diagnosis.get("confidence", 0.0)),
        "explanation": diagnosis.get("explanation", ""),
        "affected_cells": affected,
        "cell_corrections": cell_corrections,
        "n_corrections": len(cell_corrections),
    }
