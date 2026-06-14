"""
Prosthetics Heatmap Renderer
==============================
Renders side-by-side Matplotlib heatmaps for the prosthetic pressure grid:
    Left  → Target State  (clean, ideal kPa values)
    Right → Drifted State (post quantum-noise perturbation)

Uses a red-yellow-green colormap, annotates each cell with its kPa value,
and saves the figure as ``heatmap_noisy.png`` for downstream VLM analysis.
"""

from __future__ import annotations

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")                       # headless rendering
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ── Custom red → yellow → green colormap ───────────────────────────────
_RYG_COLORS = [
    (0.85, 0.15, 0.15),   # red   (high deviation / danger)
    (0.95, 0.85, 0.15),   # yellow (caution)
    (0.15, 0.78, 0.30),   # green  (nominal)
]
RYG_CMAP = LinearSegmentedColormap.from_list("ryg", _RYG_COLORS, N=256)

# Value range for the colorbar (kPa)
VMIN = 6.0
VMAX = 20.0

# Output directory — defaults to the prosthetics package folder
_DEFAULT_OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def render_heatmap(
    target: np.ndarray,
    drifted: np.ndarray,
    out_path: str | None = None,
    title: str = "Prosthetic Socket — Pressure Telemetry",
) -> str:
    """
    Render a side-by-side heatmap figure.

    Parameters
    ----------
    target : np.ndarray
        Clean 6×6 pressure grid (kPa).
    drifted : np.ndarray
        Drifted 6×6 pressure grid (kPa).
    out_path : str, optional
        Full file path for the saved PNG.  Defaults to
        ``<module_dir>/heatmap_noisy.png``.
    title : str
        Figure super-title.

    Returns
    -------
    str
        Absolute path to the saved PNG file.
    """
    if out_path is None:
        out_path = os.path.join(_DEFAULT_OUT_DIR, "heatmap_noisy.png")

    fig, (ax_target, ax_drifted) = plt.subplots(
        1, 2, figsize=(14, 6), constrained_layout=True
    )
    fig.patch.set_facecolor("#0a0e14")
    fig.suptitle(title, fontsize=15, fontweight="bold", color="white", y=1.02)

    for ax, data, subtitle in [
        (ax_target, target, "Target State (Ideal)"),
        (ax_drifted, drifted, "Drifted State (Noisy)"),
    ]:
        # Reverse the colormap so green = nominal (low), red = high (danger)
        im = ax.imshow(
            data,
            cmap=RYG_CMAP.reversed(),
            vmin=VMIN,
            vmax=VMAX,
            aspect="equal",
        )

        ax.set_title(subtitle, fontsize=12, color="white", pad=10)
        ax.set_xlabel("Column", fontsize=9, color="#94a3b8")
        ax.set_ylabel("Row", fontsize=9, color="#94a3b8")
        ax.tick_params(colors="#64748b", labelsize=8)
        ax.set_facecolor("#0f1923")

        # Annotate cells with kPa values
        rows, cols = data.shape
        for r in range(rows):
            for c in range(cols):
                val = data[r, c]
                # Contrast: dark text on light cells, white on dark cells
                text_color = "#0f172a" if val < 14.0 else "#ffffff"
                ax.text(
                    c, r, f"{val:.1f}",
                    ha="center", va="center",
                    fontsize=8, fontweight="bold",
                    color=text_color,
                )

    # Shared colorbar
    cbar = fig.colorbar(im, ax=[ax_target, ax_drifted], shrink=0.8, pad=0.03)
    cbar.set_label("Pressure (kPa)", fontsize=10, color="white")
    cbar.ax.tick_params(colors="#94a3b8", labelsize=8)

    plt.savefig(
        out_path,
        dpi=150,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)

    return os.path.abspath(out_path)
