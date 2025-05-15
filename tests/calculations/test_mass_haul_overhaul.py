from shapely.geometry import LineString

from digcalc_project.src.core.calculations.mass_haul import build_mass_haul
from digcalc_project.src.core.geometry.surface_builder import flat_surface


def test_overhaul_positive():
    """Uniform 5-ft fill over large grid should yield positive overhaul (>0)."""
    ref = flat_surface(z=0, size=50, name="OG")
    diff = flat_surface(z=5, size=50, name="Design")  # uniform fill

    align = LineString([(0, 0), (500, 0)])

    # Station interval set per prompt
    stations = build_mass_haul(ref, diff, align, station_interval=25, free_haul_ft=0)

    assert stations.overhaul_yd_station is not None
    assert stations.overhaul_yd_station > 0
