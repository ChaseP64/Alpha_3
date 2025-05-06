from __future__ import annotations

"""Test spline.sample density for a simple 10×10-ft square."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF  # noqa: E402

# Import sample and catmull_rom helpers
from digcalc_project.src.tools.spline import catmull_rom, sample  # noqa: E402


def test_square_density_default():
    """A 40-ft perimeter square sampled at 1-ft density should yield ~40 points."""

    square = [
        QPointF(0, 0),
        QPointF(10, 0),
        QPointF(10, 10),
        QPointF(0, 10),
        QPointF(0, 0),
    ]

    # Ensure catmull_rom runs without exceptions (path not used further here)
    _ = catmull_rom(square)

    pts = sample(square, 1.0)  # 1-ft sampling density

    # Perimeter is 40 ft so expect around 40 ± 4 points (allow minor variation)
    assert 36 <= len(pts) <= 44

    # Endpoints should match original start/end (x,y only; sample returns (x,y,z))
    assert pts[0][0] == 0 and pts[0][1] == 0
    assert pts[-1][0] == 0 and pts[-1][1] == 0 