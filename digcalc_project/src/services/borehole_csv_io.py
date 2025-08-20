"""CSV I/O helpers for Borehole logs (Phase 1-4).

Public API
==========
load_csv(path, stack, *, eps=0.01) -> tuple[int,int]
    Import rows from *path* into *stack*.  Returns ``(added, skipped)``.

save_csv(path, stack)
    Write the current boreholes to *path* (overwrites).

CSV schema (one row per layer)
-----------------------------
``x,y,material_name,top_z,thickness[,material_color]``

* ``material_name`` – matched case-sensitively when upserting.
* Optional ``material_color`` column honoured when creating a **new** material.  If the name already exists and colours differ we log a warning.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Tuple

from ..models.strata_models import (
    BoreholeLog,
    LayerDepth,
    Material,
    StrataStack,
)

logger = logging.getLogger(__name__)

__all__ = [
    "load_csv",
    "save_csv",
]

MERGE_EPS_FT = 0.01  # tolerance for XY merge (≈ 1/8")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _upsert_material(stack: StrataStack, name: str, colour: str | None) -> int:
    """Return material_id, creating new ``Material`` if needed."""
    for mat in stack.materials:
        if mat.name == name:
            if colour and mat.colour.lower() != colour.lower():
                logger.warning(
                    "Material '%s' already exists with colour %s; CSV had %s",
                    name,
                    mat.colour,
                    colour,
                )
            return mat.id
    # create
    new_id = stack.next_material_id()
    stack.materials.append(Material(id=new_id, name=name, colour=colour or "#CCCCCC"))
    return new_id


def _find_borehole(stack: StrataStack, x: float, y: float, eps: float) -> BoreholeLog | None:
    for bh in stack.boreholes:
        if abs(bh.x - x) <= eps and abs(bh.y - y) <= eps:
            return bh
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_csv(
    file_path: str | Path, stack: StrataStack, *, eps: float = MERGE_EPS_FT
) -> Tuple[int, int]:
    """Import borehole layers from *file_path* into *stack*.

    Returns (added_rows, skipped_rows).
    """
    added = 0
    skipped = 0

    with Path(file_path).open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            try:
                x = float(row["x"])
                y = float(row["y"])
                mat_name = row["material_name"].strip()
                top_z = float(row["top_z"])
                thickness = float(row["thickness"])
                if thickness <= 0:
                    raise ValueError("thickness<=0")
                colour = row.get("material_color") or None
            except Exception as exc:  # noqa: BLE001 broad but logs
                logger.warning("Row %d skipped (%s)", i, exc)
                skipped += 1
                continue

            mat_id = _upsert_material(stack, mat_name, colour)
            layer = LayerDepth(material_id=mat_id, top_z=top_z, bottom_z=top_z - thickness)

            bh = _find_borehole(stack, x, y, eps)
            if bh is None:
                bh = BoreholeLog(id=stack.next_borehole_id(), x=x, y=y)
                stack.boreholes.append(bh)
            try:
                bh.add_layer(layer)
                added += 1
            except ValueError as exc:
                logger.warning("Row %d skipped (layer validation failed: %s)", i, exc)
                skipped += 1

    return added, skipped


def save_csv(file_path: str | Path, stack: StrataStack) -> None:
    """Export *stack* boreholes to CSV at *file_path*."""
    with Path(file_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["x", "y", "material_name", "top_z", "thickness", "material_color"])
        mat_lookup = {m.id: m for m in stack.materials}
        for bh in stack.boreholes:
            for ld in bh.layers:
                mat = mat_lookup.get(ld.material_id)
                writer.writerow(
                    [
                        f"{bh.x:.3f}",
                        f"{bh.y:.3f}",
                        mat.name if mat else "?",
                        f"{ld.top_z:.3f}",
                        f"{ld.top_z - ld.bottom_z:.3f}",
                        (mat.colour if mat else "") if mat else "",
                    ]
                )
