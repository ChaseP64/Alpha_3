from digcalc_project.src.models.project_scale import ProjectScale


def test_roundtrip() -> None:
    """Ensure ProjectScale serialises and deserialises losslessly."""
    scale1 = ProjectScale(px_per_in=96.0, world_units="ft", world_per_in=20.0)
    data = scale1.to_dict()
    scale2 = ProjectScale.from_dict(data)

    assert scale1 == scale2, "Round-tripped ProjectScale should be identical"
    assert abs(scale1.world_per_px - (20.0 / 96.0)) < 1e-9 