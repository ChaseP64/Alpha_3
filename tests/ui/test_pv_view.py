import importlib

import pytest

# Skip entire module if PyVista is not installed
pytest.importorskip("pyvista")

from digcalc_project.src.core.geometry.surface_builder import flat_surface

# Dynamic import because the package segment name "3d" is not a valid identifier
pv_view_mod = importlib.import_module("digcalc_project.src.ui.3d.pv_view")
surface_to_polydata = pv_view_mod.surface_to_polydata


def test_polydata_conversion():
    """Simple smoke‐test ensuring conversion produces points and cells."""
    # Build a tiny flat surface (grid)
    surf = flat_surface(z=1.0, size=2, name="Test")

    # Convert to PyVista PolyData
    mesh = surface_to_polydata(surf)

    # Ensure the mesh has geometry
    assert mesh.n_points > 0, "Converted mesh has no points"
    assert mesh.n_cells > 0, "Converted mesh has no cells"
