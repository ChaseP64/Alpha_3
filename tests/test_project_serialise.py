from digcalc_project.src.models.project import Project
from digcalc_project.src.models.project_scale import ProjectScale
from digcalc_project.src.models.serializers import from_dict, to_dict


def test_project_scale_round_trip():
    """Ensure ProjectScale survives to_dict → from_dict cycle without loss."""
    pscale = ProjectScale.from_direct(50.0, "ft", render_dpi=150.0)
    original = Project(name="RT", scale=pscale)

    blob = to_dict(original)
    clone = from_dict(blob)

    assert clone.scale is not None, "Scale missing after round-trip"

    # Compare dict representations to avoid datetime mismatch formatting
    assert clone.scale.dict(exclude_none=True) == pscale.dict(exclude_none=True)
