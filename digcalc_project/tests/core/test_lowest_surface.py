from digcalc_project.src.core.geometry.surface_builder import flat_surface, lowest_surface


def test_lowest_simple():
    design = flat_surface(z=5, size=10, name="Design")
    existing = flat_surface(z=8, size=10, name="Existing")

    low = lowest_surface(design, existing)

    assert len(low.points) == len(design.points)
    # All z-values should equal the design (lower) elevation of 5
    assert all(abs(p.z - 5) < 1e-6 for p in low.points.values()) 