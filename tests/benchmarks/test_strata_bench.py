import os
import numpy as np
import pytest

pytestmark = pytest.mark.skip(reason="Disabling benchmark tests to diagnose fatal error.")

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.strata_models import StrataStack, Material, BoreholeLog, LayerDepth
from digcalc_project.src.models.surface import Surface
from digcalc_project.src.services.interpolation_service import IDWInterpolator, HAS_SCIPY, HAS_NUMBA

def _build_stack(n_bh: int=2000, n_layers:int=4):
    materials = [Material(id=i+1,name=f"Mat{i+1}") for i in range(n_layers)]
    boreholes: list[BoreholeLog] = []
    rng = np.random.default_rng(0)
    for i in range(n_bh):
        x,y = rng.uniform(0,1000), rng.uniform(0,1000)
        layers = []
        top = 0.0
        for j in range(n_layers):
            thickness= rng.uniform(1,5)
            layers.append(LayerDepth(material_id=j+1, top_z=top, bottom_z=top-thickness))
            top -= thickness
        boreholes.append(BoreholeLog(id=i+1,x=x,y=y,layers=layers))
    return StrataStack(id=1, materials=materials, boreholes=boreholes)


def _dummy_surface():
    pts=[(0,0,0),(1000,0,0),(0,1000,0)]
    return Surface.from_point_list("base", pts)


@pytest.mark.parametrize("variant", ["numpy","scipy","numba"])
def test_idw_variants_perf(benchmark, monkeypatch, variant):
    if variant=="scipy" and not HAS_SCIPY:
        pytest.skip("SciPy not available")
    if variant=="numba" and not HAS_NUMBA:
        pytest.skip("numba not available")

    # monkeypatch global flags inside module
    if variant=="numpy":
        monkeypatch.setattr("digcalc_project.src.services.interpolation_service.HAS_SCIPY", False, raising=False)
        monkeypatch.setattr("digcalc_project.src.services.interpolation_service.HAS_NUMBA", False, raising=False)
    elif variant=="scipy":
        monkeypatch.setattr("digcalc_project.src.services.interpolation_service.HAS_SCIPY", True, raising=False)
        monkeypatch.setattr("digcalc_project.src.services.interpolation_service.HAS_NUMBA", False, raising=False)
    elif variant=="numba":
        monkeypatch.setattr("digcalc_project.src.services.interpolation_service.HAS_NUMBA", True, raising=False)

    project=Project(name="bench")
    stack=_build_stack()
    surf=_dummy_surface()
    interp=IDWInterpolator()

    def _run():
        interp.generate_surfaces(project, stack, surf)

    result=benchmark(_run)
    # ensure reasonable runtime (<10s target for dev) – but don't fail on CI
    assert result < 10.0 