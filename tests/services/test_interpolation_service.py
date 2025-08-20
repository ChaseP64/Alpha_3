"""Unit tests for the Strata Surface Interpolation service."""

import numpy as np
import pytest

# Import paths aligned with existing tests – no Alpha_3 package prefix
from digcalc_project.src.models.strata_models import (
    BoreholeLog,
    LayerDepth,
    Material,
    StrataStack,
)
from digcalc_project.src.services.interpolation_service import IDWInterpolator

# Use a lightweight stub for Surface bounds during interpolation


class MockProject:
    """A mock project class for testing purposes."""

    def __init__(self, base_grid=0.0, min_thickness=0.0):
        self.base_grid = base_grid
        self.min_thickness = min_thickness


@pytest.fixture
def simple_planar_stack():
    """Creates a StrataStack with three boreholes defining a simple plane."""
    material = Material(id=1, name="Silt", colour="#C0C0C0")

    # Plane: Z = 0.1*X + 0.2*Y + 5
    boreholes = [
        BoreholeLog(
            id=1,
            x=10,
            y=20,
            layers=[LayerDepth(material_id=1, top_z=0.1 * 10 + 0.2 * 20 + 5, bottom_z=0.0)],
        ),  # Z≈10
        BoreholeLog(
            id=2,
            x=50,
            y=20,
            layers=[LayerDepth(material_id=1, top_z=0.1 * 50 + 0.2 * 20 + 5, bottom_z=0.0)],
        ),  # Z≈14
        BoreholeLog(
            id=3,
            x=30,
            y=60,
            layers=[LayerDepth(material_id=1, top_z=0.1 * 30 + 0.2 * 60 + 5, bottom_z=0.0)],
        ),  # Z≈20
    ]

    stack = StrataStack(id=1, materials=[material], boreholes=boreholes)
    return stack


@pytest.fixture
def existing_surface():
    """Lightweight mock surface object providing .bounds and .crs attributes."""
    from types import SimpleNamespace

    # bounds = (x_min, y_min, z_min, x_max, y_max, z_max)
    bounds = (0.0, 0.0, 0.0, 100.0, 100.0, 0.0)
    return SimpleNamespace(bounds=bounds, crs=None)


def test_idw_plane(simple_planar_stack, existing_surface):
    """
    Tests that the IDWInterpolator can accurately reproduce a planar surface
    from three borehole points.
    """
    interpolator = IDWInterpolator()
    project = MockProject(base_grid=1.0)  # Use a 1m grid

    surfaces = interpolator.generate_surfaces(project, simple_planar_stack, existing_surface)

    # 1. Check that one surface was generated
    assert len(surfaces) == 1
    strata_surface = surfaces[0]

    # 2. Check metadata
    assert strata_surface.material_id == 1
    assert strata_surface.grid_metadata["cell_size"] == 1.0

    # 3. Calculate RMSE at borehole locations
    grid = strata_surface.grid_data
    known_points = np.array([(b.x, b.y) for b in simple_planar_stack.boreholes])
    known_values = np.array([b.layers[0].top_z for b in simple_planar_stack.boreholes])

    interpolated_values = []
    for x, y in known_points:
        # Convert world coords to grid indices
        ix = int(round(x / strata_surface.grid_metadata["cell_size"]))
        iy = int(round(y / strata_surface.grid_metadata["cell_size"]))
        interpolated_values.append(grid[iy, ix])

    interpolated_values = np.array(interpolated_values)

    rmse = np.sqrt(np.mean((known_values - interpolated_values) ** 2))

    # 4. Assert that the error is negligible
    assert rmse < 1e-6
