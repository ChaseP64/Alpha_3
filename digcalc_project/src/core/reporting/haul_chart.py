"""digcalc_project.src.core.reporting.haul_chart

Utility to generate a mass-haul chart (cumulative earth-moving curve) as a
PNG image suitable for embedding into PDF reports or displaying in the UI.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib

# Use a non-interactive backend to allow rendering in headless environments
# (CI pipelines, servers, etc.).
matplotlib.use("Agg")

import matplotlib.pyplot as plt

__all__ = ["make_mass_haul_chart"]


def make_mass_haul_chart(
    stations: Sequence[float],
    cumulatives: Sequence[float],
    free_band: float,
    png_path: str | Path,
) -> None:
    """Create and save a mass-haul chart.

    The function plots the cumulative mass curve together with a *free-haul
    band* – a horizontal band representing ± ``free_band`` about zero that
    visualises the distance within which hauling material is considered
    cost-free.

    Args:
        stations (Sequence[float]): Station positions (ft) along the alignment.
        cumulatives (Sequence[float]): Cumulative volumes (ft³) at each station
            – typically the ``cumulative`` attribute from
            :class:`core.calculations.mass_haul.HaulStation`.
        free_band (float): Free-haul distance (ft). A shaded band of this half-
            height is drawn above and below the zero line.
        png_path (str | Path): Output path for the PNG file. Parent
            directories will be created if they do not exist.

    Returns:
        None. The PNG is written to *png_path*.

    """
    if len(stations) != len(cumulatives):
        raise ValueError("'stations' and 'cumulatives' must be the same length")

    # Ensure target directory exists.
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Plot.
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(stations, cumulatives, label="Mass curve", color="tab:blue")
    ax.fill_between(
        stations,
        [free_band] * len(stations),
        [-free_band] * len(stations),
        color="lightgrey",
        alpha=0.3,
        label="Free-haul band",
    )

    ax.set_xlabel("Station (ft)")
    ax.set_ylabel("Cumulative volume (ft³)")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.legend()
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)

    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
