import numpy as np

from digcalc_project.src.models.project import PolylineData, Project
from digcalc_project.src.models.strata_models import Material, StrataStack
from digcalc_project.src.models.surface import Surface
from digcalc_project.src.services.interpolation_service import IDWInterpolator


def _dummy_surface():
    # 0-100 bounds placeholder; create surface with bounds property via points
    pts = [(0, 0, 0), (100, 0, 0), (0, 100, 0)]
    return Surface.from_point_list("base", pts)


def test_contour_grid_simple():
    try:
        import shapely  # noqa: F401
    except ImportError:
        import pytest

        pytest.skip("Shapely not installed")

    proj = Project(name="Test")
    # Add square contour with z=10, material 1
    square = [(0, 0, 10), (50, 0, 10), (50, 50, 10), (0, 50, 10), (0, 0, 10)]
    poly: PolylineData = {"points": square, "elevation": None, "is_strata": True, "material_id": 1}
    proj.add_traced_polyline(poly, layer_name="Contours")

    material = Material(id=1, name="Mat")
    stack = StrataStack(id=1, materials=[material], boreholes=[])

    interp = IDWInterpolator()
    surf = _dummy_surface()
    surfaces, _ = interp.generate_surfaces(proj, stack, surf)
    assert surfaces, "Expected one surface"
    grid = surfaces[0].grid_data
    assert np.nanmin(grid) == 10
