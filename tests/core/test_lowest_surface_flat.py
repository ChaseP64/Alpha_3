from digcalc_project.src.core.geometry.surface_builder import flat_surface, lowest_surface


def test_lowest_is_min():
    """lowest_surface should pick the minimum Z at every point (flat grid case)."""
    design = flat_surface(z=3, size=10, name="Design")
    existing = flat_surface(z=5, size=10, name="Existing")

    low = lowest_surface(design, existing)

    # All resulting points should have Z = 3 (the lower of 3 and 5)
    assert all(p.z == 3 for p in low.points.values()) 