import numpy as np
from digcalc_project.src.models.strata_models import StrataSurface, StrataStack, Material
from digcalc_project.src.core.calculators.volume_calculator import build_cumulative_arrays


def _make_flat_surface(mat_id: int, z: float, grid_shape=(5, 5)):
    grid = np.full(grid_shape, z, dtype=float)
    meta = {"cell_size": 1.0, "x_min": 0.0, "y_min": 0.0, "crs": None}
    return StrataSurface(id=mat_id, material_id=mat_id, grid_data=grid, grid_metadata=meta)


def test_build_cumulative_arrays_flat_layers():
    material1 = Material(id=1, name="Layer1", colour="#111111")
    material2 = Material(id=2, name="Layer2", colour="#222222")
    material3 = Material(id=3, name="Layer3", colour="#333333")

    surfaces = [
        _make_flat_surface(1, 0.0),
        _make_flat_surface(2, 10.0),
        _make_flat_surface(3, 20.0),
    ]

    stack = StrataStack(id=1, materials=[material1, material2, material3], boreholes=[])
    stack.surfaces = surfaces  # Attach generated surfaces

    top_z, bottom_z = build_cumulative_arrays(stack, base_grid=np.zeros((5,5)))

    # For stacked flat layers: top_z should equal the shallowest surface (0.0)
    # and bottom_z the deepest (20.0)
    assert np.allclose(top_z, 0.0)
    assert np.allclose(bottom_z, 20.0) 