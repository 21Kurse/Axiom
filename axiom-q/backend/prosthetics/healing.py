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
import json
import serial
import time
import os
import numpy as np
from typing import Any
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from backend.prosthetics.heatmap import RYG_CMAP, VMIN, VMAX

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


def send_to_arduino(diagnosis: dict[str, Any], port: str = "/dev/cu.usbmodem101", baudrate: int = 9600):
    """
    Send VLM cell corrections down the USB serial port to the Arduino.
    """
    cell_corrections = diagnosis.get("cell_corrections", {})
    if not cell_corrections:
        return
        
    try:
        log.info("Opening serial port %s at %d baud...", port, baudrate)
        ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2) # Wait for Arduino to reset
        
        for cell_id, target_kpa in cell_corrections.items():
            # Standardize cell_id format for Arduino (e.g., "03" or "23")
            cleaned = str(cell_id).strip("[]() ")
            parts = cleaned.replace("_", ",").split(",")
            if len(parts) == 2:
                r, c = parts[0].strip(), parts[1].strip()
                formatted_id = f"{r}{c}"
            else:
                formatted_id = cleaned
                
            cmd = json.dumps({"cell_id": formatted_id, "target_kpa": float(target_kpa)})
            ser.write((cmd + "\n").encode("utf-8"))
            log.info("Sent to Arduino: %s", cmd)
            time.sleep(0.2) # 200ms delay between commands
            
        ser.close()
    except Exception as e:
        log.warning("Could not send to Arduino on %s: %s", port, e)


def create_healing_gif(drifted: np.ndarray, healed: np.ndarray, out_path: str = "healing.gif") -> str:
    """
    Create an animated GIF showing the 6x6 pressure grid updating cell-by-cell
    from the drifted state back to the target/healed state over 20 frames.
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
            t = ax.text(c, r, f"{val:.1f}", ha="center", va="center", color=text_color, fontsize=10, fontweight="bold")
            row_texts.append(t)
        texts.append(row_texts)
        
    frames = 20
    
    def update(frame):
        # Progress from 0.0 to 1.0
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
