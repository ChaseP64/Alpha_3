from __future__ import annotations

"""Golden-file helper utilities for Smart-Clean validation.

The module serialises :class:`~digcalc_project.src.core.geom.polyline.Polyline`
objects to a compact JSON representation and provides diff helpers used by
GUI/CLI tests.

Usage
-----
>>> from tests.golden import save_golden, load_golden, diff_percentage
>>> save_golden("sample.json", polylines)
>>> ref = load_golden("sample.json")
>>> diff = diff_percentage(polylines, ref)
"""

import json
from pathlib import Path
from typing import List

import numpy as np

from digcalc_project.src.core.geom.polyline import Polyline

__all__ = [
    "to_jsonable",
    "from_jsonable",
    "save_golden",
    "load_golden",
    "diff_percentage",
]


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def to_jsonable(polylines: List[Polyline]):  # noqa: D401 – helper
    """Convert *polylines* to a JSON-serialisable structure."""
    out = []
    for pl in polylines:
        out.append(
            {
                "vertices": np.round(pl.vertices, 6).tolist(),  # 6-dp precision
                "stroke_rgb": pl.stroke_rgb,
                "dash": pl.dash,
            }
        )
    return out


def from_jsonable(data) -> List[Polyline]:  # noqa: D401 – helper
    """Recreate list of :class:`Polyline` from *data* (dict list)."""
    pls: list[Polyline] = []
    for item in data:
        pls.append(
            Polyline(
                vertices=np.asarray(item["vertices"], dtype=float),
                stroke_rgb=tuple(item["stroke_rgb"]) if item["stroke_rgb"] else None,
                dash=tuple(item["dash"]) if item["dash"] else None,
            )
        )
    return pls


def save_golden(path: str | Path, polylines: List[Polyline]) -> None:  # noqa: D401
    """Write *polylines* to *path* as JSON (pretty-printed)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(to_jsonable(polylines), fp, indent=2)


def load_golden(path: str | Path) -> List[Polyline]:  # noqa: D401
    """Return polylines from golden JSON file at *path*."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    return from_jsonable(data)


# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------


def diff_percentage(a: List[Polyline], b: List[Polyline]) -> float:  # noqa: D401
    """Return percentage difference between two polyline lists.

    Heuristic: counts unmatched vertices after aligning by index.
    Result is (#unmatched / total_ref_vertices) × 100.
    """
    import math

    verts_a = np.concatenate([pl.vertices for pl in a]) if a else np.empty((0, 2))
    verts_b = np.concatenate([pl.vertices for pl in b]) if b else np.empty((0, 2))

    if len(verts_b) == 0:
        return 100.0 if len(verts_a) else 0.0

    n_compare = min(len(verts_a), len(verts_b))
    if n_compare == 0:
        return 100.0

    max_dist = np.linalg.norm(verts_a[:n_compare] - verts_b[:n_compare], axis=1).max()

    # Treat discrepancy proportional to max_dist (ft).  Assuming map scale
    pct = min(100.0, (max_dist / 1.0) * 100)  # 1 ft reference scale
    return pct
