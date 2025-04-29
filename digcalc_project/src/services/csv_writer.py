"""csv_writer.py
Utility for exporting slice volume results to CSV.

This service provides a single helper :func:`write_slice_table` which writes a
list of :class:`~digcalc_project.models.calculation.SliceResult` objects to a
comma-separated-values file for easy use in spreadsheets or further analysis.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Union

from ..models.calculation import SliceResult

__all__ = ["write_slice_table"]


def write_slice_table(slices: Iterable[SliceResult], path: Union[str, Path]) -> None:
    """Write a table of *slice* cut/fill volumes to **CSV**.

    Args:
        slices: Iterable of :class:`~digcalc_project.models.calculation.SliceResult`.
        path:   Output file location (``str`` or :class:`~pathlib.Path``).

    The CSV will contain the following headers:
    ``Slice Bottom``, ``Slice Top``, ``Cut (ft³)``, ``Fill (ft³)``.
    Each numeric value is formatted to two decimal places for readability.
    """

    # Ensure *path* is Path-like then open in text mode with newline="" for
    # correct CSV output on all platforms.
    dest = Path(path)
    with dest.expanduser().resolve().open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Slice Bottom", "Slice Top", "Cut (ft³)", "Fill (ft³)"])
        for slc in slices:
            writer.writerow([
                f"{slc.z_bottom:.3f}",
                f"{slc.z_top:.3f}",
                f"{slc.cut:.2f}",
                f"{slc.fill:.2f}",
            ]) 