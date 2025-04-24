"""Unit tests for digcalc_project.src.tools.daylight_offset_tool.

This module validates the behaviour of the geometry helper functions that
perform polygon offsetting and daylight slope projection.
"""

from math import isclose

import pytest
from shapely.geometry import Polygon

from digcalc_project.src.tools.daylight_offset_tool import (
    offset_polygon,
    project_to_slope,
)


# -----------------------------------------------------------------------------
# Tests for `offset_polygon`
# -----------------------------------------------------------------------------


def test_offset_polygon_outward_square():
    """Offsetting a 10×10 square outward by 1 ft should yield a 12×12 square."""
    # Arrange
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

    # Act
    result = offset_polygon(square, dist=1.0)

    # Assert - resulting polygon area should be approx 144 (12×12)
    area = Polygon(result).area
    assert isclose(area, 144.0, rel_tol=0.0, abs_tol=1e-6)


def test_offset_polygon_negative_too_large():
    """Shrinking a polygon by more than half its size should raise ValueError."""
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

    # When the inward buffer collapses geometry Shapely returns an empty or
    # multi-polygon; our helper should raise ValueError in that case.
    with pytest.raises(ValueError):
        offset_polygon(square, dist=-6.0)


# -----------------------------------------------------------------------------
# Tests for `project_to_slope`
# -----------------------------------------------------------------------------


def test_project_to_slope_basic():
    """Ensure Z drop calculation is correct (4 ft horizontal at 2H:1V ↦ -2 ft)."""
    base_pts = [(0.0, 0.0), (4.0, 0.0)]
    horiz_off = 4.0
    slope_ratio = 2.0

    projected = project_to_slope(base_pts, horiz_off, slope_ratio)

    # Z should be -2.0 for all points.
    for x, y, z in projected:
        assert x in (0.0, 4.0)
        assert y == 0.0
        assert isclose(z, -2.0, abs_tol=1e-9)


def test_project_to_slope_zero_ratio():
    """Passing slope_ratio=0 should raise ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        project_to_slope([(0.0, 0.0)], horiz_off=1.0, slope_ratio=0.0) 