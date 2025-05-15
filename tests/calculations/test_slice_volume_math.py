from digcalc_project.src.core.calculations.volume_calculator import VolumeCalculator
from digcalc_project.src.core.geometry.surface_builder import flat_surface


def test_two_equal_slices():
    """Uniform 2-ft fill across 10×10 ft grid should yield two equal slices."""
    ref = flat_surface(z=0, size=10, name="OG")
    diff = flat_surface(z=2, size=10, name="Design")

    vc = VolumeCalculator(project=None)  # type: ignore[arg-type]
    slices = vc.compute_slice_volumes(ref, diff, 1.0)

    # Expect exactly two slices
    assert len(slices) == 2

    # All slices are fill only; none should contain cut
    assert all(s.cut == 0 for s in slices)
    assert all(s.fill > 0 for s in slices)

    # Each slice should have the same fill volume
    assert sum(s.fill for s in slices) == slices[0].fill * 2
