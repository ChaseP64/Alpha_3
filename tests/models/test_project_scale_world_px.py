
from digcalc_project.src.models.project_scale import ProjectScale

DPI = 150.0
EXPECTED_WPPX = 50.0 / DPI  # 0.333333… ft per pixel


def test_world_per_px_direct():
    """50 ft / in at 150 dpi ⇒ 50 / 150 = 0.333 ft/px."""
    sc = ProjectScale.from_direct(50.0, "ft", render_dpi=DPI)
    assert abs(sc.world_per_px - EXPECTED_WPPX) < 1e-6


def test_world_per_px_ratio():
    """Scale 1 : 600 with project units 'ft' matches the direct-entry path."""
    sc = ProjectScale.from_ratio(1.0, 600.0, "ft", render_dpi=DPI)
    assert abs(sc.world_per_px - EXPECTED_WPPX) < 1e-6
