"""CSV exporter helper for per-material cut volumes."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

from digcalc_project.src.models.strata_models import StrataStack


def save_material_cut_csv(
    path: str | Path, volumes: Dict[int, float], strata_stack: StrataStack, unit: str = "cuyd"
) -> None:
    """Write per-material cut volumes to CSV.

    Args:
        path: Output CSV path.
        volumes: Dict mapping material_id → volume (ft³ or m³).
        strata_stack: Provides material metadata.
        unit: Output unit label (default cubic yards).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = [("Material", "Volume ({}³)".format(unit))]
    for mat in strata_stack.materials:
        vol = volumes.get(mat.id, 0.0)
        rows.append((mat.name, f"{vol:.2f}"))

    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerows(rows)


def export_volume_report(path: str | Path, params: dict, dz_cache: tuple) -> None:
    """Write a volume calculation report to a CSV file.

    Args:
        path (str | Path): The path to the output CSV file.
        params (dict): A dictionary of parameters for the volume calculation.
        dz_cache (tuple): A tuple containing the cut/fill depths and grid points.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    header = ["Parameter", "Value", "", "Grid Point X", "Grid Point Y", "Cut/Fill Depth"]

    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(header)

        # Write parameters
        writer.writerow(["Existing Surface", params.get("existing_surface", "")])
        writer.writerow(["Proposed Surface", params.get("proposed_surface", "")])
        writer.writerow(["Grid Resolution", params.get("grid_resolution", "")])
        writer.writerow([])

        # Write grid data
        dz, grid_points = dz_cache
        for i, (x, y) in enumerate(grid_points):
            writer.writerow(["", "", "", x, y, dz[i]])
