from __future__ import annotations

"""Tests for PvDock._validate_polydata helper."""

import numpy as np
import pyvista as pv
import pytest

from digcalc_project.src.ui.docks.pv_dock import PvDock


def test_empty_mesh_raises() -> None:
    with pytest.raises(ValueError):
        PvDock._validate_polydata(pv.PolyData())


def test_flat_mesh_raises() -> None:
    pts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0]])
    faces = np.hstack([[3, 0, 1, 2]])  # single triangle (PolyData expects a flat array)
    flat = pv.PolyData(pts, faces)
    with pytest.raises(ValueError):
        PvDock._validate_polydata(flat)


def test_good_mesh_passes() -> None:
    cube = pv.Cube()
    # Should not raise
    PvDock._validate_polydata(cube) 