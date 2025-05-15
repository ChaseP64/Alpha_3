import math

import pytest

from digcalc_project.src.models.project_scale import ProjectScale


def test_roundtrip() -> None:
    """Ensure ProjectScale serialises and deserialises losslessly."""
    scale1 = ProjectScale(px_per_in=96.0, world_units="ft", world_per_in=20.0)
    data = scale1.to_dict()
    scale2 = ProjectScale.from_dict(data)

    assert scale1 == scale2, "Round-tripped ProjectScale should be identical"
    assert abs(scale1.world_per_px - (20.0 / 96.0)) < 1e-9


# ---------------------------------------------------------------------------
# New behaviour – alias property
# ---------------------------------------------------------------------------


def test_ft_per_px_alias() -> None:
    """``ft_per_px`` must return the same value as ``world_per_px``."""
    scale = ProjectScale(px_per_in=96.0, world_units="ft", world_per_in=20.0)
    assert scale.ft_per_px == scale.world_per_px


def test_world_per_px_zero_division() -> None:
    """A zero ``px_per_in`` should raise ``ZeroDivisionError``."""
    scale = ProjectScale(px_per_in=0.0, world_units="ft", world_per_in=20.0)

    with pytest.raises(ZeroDivisionError):
        _ = scale.world_per_px


# ---------------------------------------------------------------------------
# Integration test – Project <-> serializers roundtrip
# ---------------------------------------------------------------------------


from digcalc_project.src.models.project import Project
from digcalc_project.src.models.serializers import from_dict, to_dict


def test_scale_roundtrip() -> None:
    """Ensure Project.scale survives in-memory serializer roundtrip."""
    proj = Project(
        name="Demo",
        scale=ProjectScale(px_per_in=96, world_units="ft", world_per_in=20),
    )

    data = to_dict(proj)
    clone = from_dict(data)

    assert clone.scale is not None
    assert clone.scale.ft_per_px == pytest.approx(20 / 96)


# ---------------------------------------------------------------------------
# Parametrised round-trip across different units (ID 6-a)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "units,val_per_in", [("ft", 20.0), ("yd", 6.667), ("m", 6.096)])
def test_scale_roundtrip_param(units, val_per_in):
    """Project → dict → Project round-trip preserves ProjectScale values."""
    proj = Project(
        name="demo",
        scale=ProjectScale(px_per_in=96.0, world_units=units, world_per_in=val_per_in),
    )

    clone = from_dict(to_dict(proj))

    assert clone.scale is not None
    assert clone.scale.world_units == units
    # ft_per_px (alias of world_per_px when units==ft) should equal val/96 within tolerance
    expected = val_per_in / 96.0
    assert math.isclose(clone.scale.world_per_px, expected, rel_tol=1e-9, abs_tol=1e-9)
