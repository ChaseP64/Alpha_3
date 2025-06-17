import numpy as np
import pytest

from digcalc_project.src.core.geometry.tin_generator import generate_tin
from digcalc_project.src.models.surface import Surface

try:
    from scipy.spatial import Delaunay
except ImportError:
    Delaunay = None  # Skip tests if SciPy missing


@pytest.mark.skipif(Delaunay is None, reason="SciPy required for TIN tests")
def test_random_points_delaunay():
    """Generate a TIN for 100 random points and compare triangle count with SciPy's Delaunay."""
    rng = np.random.default_rng(seed=123)
    pts = rng.random((100, 3), dtype=float)
    pts[:, 0] *= 100.0  # scale x
    pts[:, 1] *= 100.0  # scale y
    pts[:, 2] *= 50.0   # scale z

    surface = generate_tin(pts, name="random-cloud")
    assert isinstance(surface, Surface)
    assert len(surface.points) == 100

    xy = pts[:, :2]
    delaunay = Delaunay(xy)
    assert len(surface.triangles) == len(delaunay.simplices)


@pytest.mark.skipif(Delaunay is None, reason="SciPy required for TIN tests")
def test_square_with_center():
    """Square with center point should yield 4 triangles in a Delaunay TIN."""
    pts = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.5, 0.5, 0.0],  # centre
    ], dtype=float)

    surface = generate_tin(pts, name="square-centre")
    assert isinstance(surface, Surface)
    assert len(surface.points) == 5

    # For a square plus center, Delaunay should output exactly 4 triangles.
    assert len(surface.triangles) == 4

    # Validate that all triangle vertices are part of the surface's point set.
    all_ids = set(surface.points.keys())
    for tri in surface.triangles.values():
        ids = {tri.p1.id, tri.p2.id, tri.p3.id}
        assert ids.issubset(all_ids) 