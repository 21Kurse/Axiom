"""
Prosthetics VLM Agent
======================
Placeholder for Phase 2.  This module will send the ``heatmap_noisy.png``
image to the NVIDIA VLM (via the existing LiteLLM proxy in
:pymod:`backend.nvidia_client`) for diagnosis and correction instructions.

For now it exposes a stub ``analyze()`` function so that ``main.py``
can call the full pipeline without errors.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("axiom-q.prosthetics.agent")


async def analyze(heatmap_path: str, drift_cells: list[tuple[int, int]]) -> dict[str, Any]:
    """
    Send the heatmap image to the VLM for analysis.

    Parameters
    ----------
    heatmap_path : str
        Path to the rendered ``heatmap_noisy.png``.
    drift_cells : list[tuple[int, int]]
        (row, col) pairs where drift was detected.

    Returns
    -------
    dict
        VLM analysis payload (stub returns a placeholder until Phase 2).
    """
    log.info("Agent stub — would send %s with %d drift cells to VLM.",
             heatmap_path, len(drift_cells))

    return {
        "status": "STUB",
        "heatmap_path": heatmap_path,
        "drift_cells": drift_cells,
        "diagnosis": "Phase 2 — VLM analysis not yet implemented.",
        "corrections": [],
    }
