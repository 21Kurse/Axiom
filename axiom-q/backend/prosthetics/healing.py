"""
Prosthetics Self-Healing Engine
================================
Applies the VLM-recommended corrections from the agent to the drifted
pressure grid, simulating autonomous socket re-calibration.

The agent returns a ``cell_corrections`` dict mapping cell IDs (e.g. "2,3")
to target kPa values.  This module applies those corrections and returns the
healed grid.
"""

from __future__ import annotations

import logging
import numpy as np
from typing import Any

log = logging.getLogger("axiom-q.prosthetics.healing")


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
