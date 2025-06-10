"""CSV exporter helper for per-material cut volumes."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

from digcalc_project.src.models.strata_models import StrataStack


def save_material_cut_csv(path: str | Path, volumes: Dict[int, float], strata_stack: StrataStack, unit: str = "cuyd") -> None:
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
