import csv
from pathlib import Path

from digcalc_project.src.models.strata_models import (
    BoreholeLog,
    LayerDepth,
    Material,
    StrataStack,
)
from digcalc_project.src.services.borehole_csv_io import load_csv, save_csv


def _build_stack() -> StrataStack:
    st = StrataStack(id=1)
    clay = Material(id=1, name="Clay", colour="#964B00")
    st.materials.append(clay)
    bh = BoreholeLog(
        id=1, x=0.0, y=0.0, layers=[LayerDepth(material_id=1, top_z=0.0, bottom_z=-5.0)]
    )
    st.boreholes.append(bh)
    return st


def test_roundtrip(tmp_path):
    stack = _build_stack()
    csv_path = tmp_path / "bh.csv"
    save_csv(csv_path, stack)

    new_stack = StrataStack(id=1)
    load_csv(csv_path, new_stack)

    assert len(new_stack.boreholes) == len(stack.boreholes)
    assert len(new_stack.materials) == len(stack.materials)


def test_layer_order(tmp_path):
    st = StrataStack(id=1)
    st.materials.append(Material(id=1, name="Silt"))
    bh = BoreholeLog(
        id=1,
        x=1.0,
        y=1.0,
        layers=[
            LayerDepth(material_id=1, top_z=0.0, bottom_z=-2.0),
            LayerDepth(material_id=1, top_z=-2.0, bottom_z=-4.0),
        ],
    )
    st.boreholes.append(bh)
    p = tmp_path / "a.csv"
    save_csv(p, st)
    new = StrataStack(id=1)
    load_csv(p, new)
    new_layers = new.boreholes[0].layers
    assert new_layers[0].top_z == 0.0 and new_layers[1].bottom_z == -4.0
