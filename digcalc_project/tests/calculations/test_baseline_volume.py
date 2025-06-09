"""Tests for baseline grid-based volume calculator (Phase 0-2).

Scenario: *Existing* surface slopes linearly from z=0 ft at y=0 ft to z=10 ft at
          y=100 ft over a 100 ft × 100 ft square.  *Proposed* surface is a flat
          pad at z=5 ft across the same footprint.

Analytical answer (continuous integration):
    • *Fill*: 12 500 ft³ (area under pad where existing is below pad)
    • *Cut*: 12 500 ft³ (area above pad where existing is above pad)
    • *Net*:  0 ft³

The grid-based algorithm should converge exactly for a linear plane when the
input points lie on that plane, therefore we expect results within ≤ 1 ft³.
"""

import numpy as np
import pytest

pytest.importorskip("scipy", reason="SciPy required for VolumeCalculator tests")

from digcalc_project.src.core.calculators.volume_calculator import VolumeCalculator
from digcalc_project.src.models.surface import Surface
from digcalc_project.src.models.project import Project


def _build_slope_surface(name: str, spacing: float = 10.0) -> Surface:
    """Create a planar *sloped* Surface over 0–100 ft in X and Y.

    Elevation follows z = 0.1 × y (ft).
    """
    xs = np.arange(0.0, 100.0 + spacing * 0.5, spacing)
    ys = np.arange(0.0, 100.0 + spacing * 0.5, spacing)
    pts = [(x, y, 0.1 * y) for y in ys for x in xs]
    return Surface.from_point_list(name, pts, spacing=spacing)


def _build_flat_pad(name: str, elev: float = 5.0, spacing: float = 10.0) -> Surface:
    """Create a flat Surface at constant *elev* over 0–100 ft in X and Y."""
    xs = np.arange(0.0, 100.0 + spacing * 0.5, spacing)
    ys = np.arange(0.0, 100.0 + spacing * 0.5, spacing)
    pts = [(x, y, elev) for y in ys for x in xs]
    return Surface.from_point_list(name, pts, spacing=spacing)


def test_baseline_cut_fill_accuracy():
    project = Project("baseline-volume-test")
    calc = VolumeCalculator(project)

    existing = _build_slope_surface("existing")
    proposed = _build_flat_pad("pad")

    # Use 1-ft grid spacing to ensure high accuracy for comparison against
    # analytical solution.
    res = calc.calculate_grid_method(existing, proposed, grid_resolution=1.0)

    assert res["net"] == pytest.approx(0.0, abs=1.0)
    assert res["cut"] == pytest.approx(12_500.0, rel=0.001)  # ±0.1 %
    assert res["fill"] == pytest.approx(12_500.0, rel=0.001) 