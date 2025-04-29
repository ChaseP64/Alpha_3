"""csv_writer.py
Utility for exporting slice volume results to CSV.

This service provides a single helper :func:`write_slice_table` which writes a
list of :class:`~digcalc_project.models.calculation.SliceResult` objects to a
comma-separated-values file for easy use in spreadsheets or further analysis.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Union, TYPE_CHECKING

from ..models.calculation import SliceResult

if TYPE_CHECKING:  # pragma: no cover
    from ..core.calculations.mass_haul import HaulStation

__all__ = ["write_slice_table", "write_mass_haul", "write_region_table"]


def write_slice_table(slices: Iterable[SliceResult], path: Union[str, Path]) -> None:
    """Write *slice* volume results to **CSV** with minimal formatting.

    This helper adheres to the Phase-8 prompt specification – headers are
    exactly ``Bottom, Top, Cut, Fill`` and numeric values are written as raw
    floats (no formatting) so downstream tools can parse without string
    parsing.
    """

    dest = Path(path)
    with dest.expanduser().resolve().open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Bottom", "Top", "Cut", "Fill"])
        for s in slices:
            writer.writerow([s.z_bottom, s.z_top, s.cut, s.fill])


def write_mass_haul(stations: Iterable["HaulStation"], path: Union[str, Path]) -> None:
    """Write mass-haul station data to **CSV**.

    Args:
        stations: Iterable of :class:`~digcalc_project.src.core.calculations.mass_haul.HaulStation`.
        path: Output file location.
    """

    from ..core.calculations.mass_haul import HaulStation  # local import to avoid heavy import cost

    dest = Path(path)
    with dest.expanduser().resolve().open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Station", "Cut", "Fill", "Cumulative"])
        for s in stations:
            # Type guard – tolerate duck-typed objects that expose the required attributes.
            if not all(hasattr(s, attr) for attr in ("station", "cut", "fill", "cumulative")):
                raise ValueError("Each station object must have station, cut, fill, cumulative attributes")
            writer.writerow([
                f"{s.station:.2f}",
                f"{s.cut:.1f}",
                f"{s.fill:.1f}",
                f"{s.cumulative:.1f}",
            ])


def write_region_table(rows, path):  # type: ignore[typing-arg-name]
    """Write *region* volume rows to **CSV**.

    The *rows* objects are expected to expose the following attributes:
    ``name``, ``area``, ``depth``, ``cut``, ``fill``.
    Net volume (``fill - cut``) is computed on the fly per prompt.
    """

    dest = Path(path)
    with dest.expanduser().resolve().open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Region", "Area", "Depth", "Cut", "Fill", "Net"])
        for r in rows:
            writer.writerow([r.name, r.area, r.depth or "Def", r.cut, r.fill, r.fill - r.cut]) 