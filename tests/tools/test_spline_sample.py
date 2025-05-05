import sys

import pytest
from PySide6.QtCore import QPointF

from digcalc_project.src.tools.spline import sample


def _square(z: float = 0.0):
    """Return 5-point closed square polyline (10×10)."""
    pts = [
        QPointF(0, 0),
        QPointF(10, 0),
        QPointF(10, 10),
        QPointF(0, 10),
        QPointF(0, 0),
    ]
    if z:
        for p in pts:
            # Monkey-patch z attribute for 3-D path
            setattr(p, "z", lambda v=z: v)  # type: ignore[attr-defined]
    return pts


def test_density_1ft():
    """Perimeter 40 ft at 1 ft density → ~40 samples (±2)."""
    pts = sample(_square(), density_ft=1.0)
    assert 38 <= len(pts) <= 42
    # Endpoints preserved
    assert pts[0][:2] == (0.0, 0.0)
    assert pts[-1][:2] == (0.0, 0.0)


def test_fallback_linear(monkeypatch):
    """Force SciPy absence to exercise linear fallback."""
    monkeypatch.setitem(sys.modules, "scipy", None)

    pts = sample(_square(), density_ft=1.0)
    assert 38 <= len(pts) <= 42

    # Clean up
    sys.modules.pop("scipy", None)