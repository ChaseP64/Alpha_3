import importlib
import sys

import pytest
from PySide6.QtCore import QPointF

# Import module under test
from digcalc_project.src.tools import spline


def _square_points(closed: bool = True):
    pts = [
        QPointF(0, 0),
        QPointF(10, 0),
        QPointF(10, 10),
        QPointF(0, 10),
    ]
    if closed:
        pts.append(QPointF(0, 0))
    return pts


@pytest.mark.parametrize("density,expected_len_range", [(1.0, (38, 42)), (0.5, (78, 82))])
def test_sample_basic_lengths(density, expected_len_range):
    """Sampling a 10×10 closed square should yield ~perimeter/density points."""
    pts = _square_points()
    out = spline.sample(pts, density_ft=density)
    assert expected_len_range[0] <= len(out) <= expected_len_range[1]


def test_degenerate_returns_input():
    """Providing fewer than two points returns the points unchanged."""
    input_pts = [QPointF(1, 2)]
    out = spline.sample(input_pts, density_ft=1.0)
    assert out == [(1.0, 2.0, 0.0)]


def test_fallback_without_scipy(monkeypatch):
    """When SciPy is not available, the function falls back to linear densify."""
    # Remove scipy from sys.modules & make import raise
    monkeypatch.setitem(sys.modules, "scipy", None)

    def _raise(*args, **kwargs):
        raise ImportError("forced for test")

    monkeypatch.setitem(sys.modules, "scipy.interpolate", _raise)

    importlib.reload(spline)  # reload to clear cached science stuff

    pts = _square_points()
    out = spline.sample(pts, density_ft=1.0)
    assert 30 <= len(out) <= 42  # Linear densify gives 41 expected

    # Restore original state
    sys.modules.pop("scipy", None)
    importlib.reload(spline)
