"""Unit tests for VolumeCalculator.compute_slice_volumes."""

from digcalc_project.src.core.calculations.volume_calculator import VolumeCalculator
from digcalc_project.src.core.geometry.surface_builder import flat_surface


def test_two_slice():
    """Uniform 2-ft fill across 10×10 ft grid should yield two equal slices."""
    ref = flat_surface(z=0, size=10, name="Ref")
    diff = flat_surface(z=2, size=10, name="Diff")

    # Instantiate calculator without project context for this unit test
    calc = VolumeCalculator(project=None)  # type: ignore[arg-type]

    slices = calc.compute_slice_volumes(ref, diff, slice_thickness_ft=1.0)

    # Expect exactly two slices: 0-1 and 1-2 ft
    assert len(slices) == 2

    # Both slices should be pure fill (no cut) with positive volume
    assert slices[0].fill > 0 and slices[0].cut == 0
    assert slices[1].fill > 0 and slices[1].cut == 0
