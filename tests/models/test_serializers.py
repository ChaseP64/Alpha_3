from digcalc_project.src.models.serializers import to_dict, from_dict
from digcalc_project.src.models.project import Project
from digcalc_project.src.models.project_scale import ProjectScale


def test_serializer_roundtrip_with_scale():
    """Project → dict → Project roundtrip should preserve scale."""

    scale = ProjectScale(px_per_in=96.0, world_units="ft", world_per_in=20.0)
    proj = Project(name="Foo", scale=scale)

    data = to_dict(proj)
    proj2 = from_dict(data)

    assert proj2.scale == scale


def test_serializer_scale_none():
    """Serialising a project without scale should roundtrip with None."""

    proj = Project(name="Bar")
    data = to_dict(proj)
    assert data["scale"] is None

    proj2 = from_dict(data)
    assert proj2.scale is None


def test_serializer_invalid_scale_fallback():
    """Malformed scale data should not raise and should result in scale None."""

    data = {
        "name": "BadScale",
        "scale": {"px_per_in": "abc", "world_units": "ft"},  # missing world_per_in
    }

    proj = from_dict(data)
    assert proj.scale is None 