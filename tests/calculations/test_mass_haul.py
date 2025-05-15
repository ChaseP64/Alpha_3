"""Unit tests for mass-haul calculations."""

from shapely.geometry import LineString

from digcalc_project.src.core.calculations.mass_haul import build_mass_haul
from digcalc_project.src.core.geometry.surface_builder import flat_surface


def test_simple_fill_job() -> None:
    """Uniform 2-ft fill over a 10×10 ft grid should yield net positive cumulative."""
    ref = flat_surface(z=0, size=10, name="Ref")
    diff = flat_surface(z=2, size=10, name="Diff")

    alignment = LineString([(0, 0), (100, 0)])

    stations = build_mass_haul(ref, diff, alignment, station_interval=10, free_haul_ft=0)

    # The final cumulative should be positive (net fill)
    assert stations[-1].cumulative > 0

    # Ensure the number of stations matches expectation (~100/10 + 1 = 11)
    assert len(stations) == 11
