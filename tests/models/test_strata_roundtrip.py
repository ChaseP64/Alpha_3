"""Round-trip serialisation tests for strata models (Phase 0-3)."""

import digcalc_project.src.models.serializers as sz
from digcalc_project.src.models.project import Project
from digcalc_project.src.models.strata_models import (
    BoreholeLog,
    LayerDepth,
    Material,
    StrataStack,
    StrataSurface,
)


def _build_stack() -> StrataStack:
    mat = Material(id=1, name="Clay", colour="#964B00")
    bh = BoreholeLog(
        id=1, x=0.0, y=0.0, layers=[LayerDepth(material_id=1, top_z=0.0, bottom_z=-10.0)]
    )
    surf = StrataSurface(id=1, name="Clay/Bedrock", material_id=1)
    return StrataStack(id=1, materials=[mat], boreholes=[bh], surfaces=[surf])


def test_strata_roundtrip():
    project = Project("strata-rt")
    project.strata = _build_stack()

    d = sz.to_dict(project)
    p2 = sz.from_dict(d)

    assert p2.strata is not None
    assert len(p2.strata.materials) == 1
    assert p2.strata.materials[0].name == "Clay"
    assert len(p2.strata.boreholes) == 1
    assert len(p2.strata.surfaces) == 1
