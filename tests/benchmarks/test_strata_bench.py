"""Opt-in performance benchmarks for the IDW interpolator.

Enable by exporting the environment variable:

    DIGCALC_RUN_BENCH=1

and run with pytest (optionally filter by marker ``-m perf``).

Benchmarks are skipped unless a fast backend (SciPy or a functional Numba JIT)
is available.  Regular CI/test runs therefore remain quick.
"""

# Lightweight imports first
import pytest

# Check fast back-end availability *before* importing NumPy or other heavy deps.
from digcalc_project.src.services.interpolation_service import HAS_NUMBA, HAS_SCIPY

if not (HAS_SCIPY or HAS_NUMBA):
    pytest.skip(
        "Skipping IDW performance benchmarks – requires SciPy or Numba for timely execution.",
        allow_module_level=True,
    )

# Heavy imports below (only executed when we know a fast backend exists)
import os

import numpy as np

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.strata_models import BoreholeLog, LayerDepth, Material, StrataStack
from digcalc_project.src.models.surface import Surface
from digcalc_project.src.services.interpolation_service import HAS_NUMBA, HAS_SCIPY, IDWInterpolator

# Benchmarks run only when the developer explicitly opts in by setting an
# environment variable:
#
#     DIGCALC_RUN_BENCH=1 pytest -m perf tests/benchmarks
#
# This prevents accidental long-running jobs on CI or during routine `pytest`
# invocations.  The opt-in check is performed *before* heavy imports so that we
# exit quickly.

if os.getenv("DIGCALC_RUN_BENCH") != "1":
    pytest.skip("Benchmarks disabled – set DIGCALC_RUN_BENCH=1 to enable.", allow_module_level=True)


def _build_stack(n_bh: int = 500, n_layers: int = 4):  # Fewer boreholes for faster dev run
    materials = [Material(id=i + 1, name=f"Mat{i+1}") for i in range(n_layers)]
    boreholes: list[BoreholeLog] = []
    rng = np.random.default_rng(0)
    for i in range(n_bh):
        x, y = rng.uniform(0, 1000), rng.uniform(0, 1000)
        layers = []
        top = 0.0
        for j in range(n_layers):
            thickness = rng.uniform(1, 5)
            layers.append(LayerDepth(material_id=j + 1, top_z=top, bottom_z=top - thickness))
            top -= thickness
        boreholes.append(BoreholeLog(id=i + 1, x=x, y=y, layers=layers))
    return StrataStack(id=1, materials=materials, boreholes=boreholes)


def _dummy_surface():
    pts = [(0, 0, 0), (1000, 0, 0), (0, 1000, 0)]
    return Surface.from_point_list("base", pts)


# Build variant list dynamically – skip pure‐NumPy benchmark on CI.

_variants: list[str] = []
if HAS_SCIPY:
    _variants.append("scipy")
if HAS_NUMBA:
    _variants.append("numba")

if not _variants:
    pytest.skip("No accelerated backend for IDW benchmarks.", allow_module_level=True)


@pytest.mark.parametrize("variant", _variants)
def test_idw_variants_perf(benchmark, monkeypatch, variant):
    if variant == "scipy" and not HAS_SCIPY:
        pytest.skip("SciPy not available")
    if variant == "numba" and not HAS_NUMBA:
        pytest.skip("numba not available")

    # monkeypatch global flags inside module
    if variant == "numpy":
        monkeypatch.setattr(
            "digcalc_project.src.services.interpolation_service.HAS_SCIPY", False, raising=False
        )
        monkeypatch.setattr(
            "digcalc_project.src.services.interpolation_service.HAS_NUMBA", False, raising=False
        )
    elif variant == "scipy":
        monkeypatch.setattr(
            "digcalc_project.src.services.interpolation_service.HAS_SCIPY", True, raising=False
        )
        monkeypatch.setattr(
            "digcalc_project.src.services.interpolation_service.HAS_NUMBA", False, raising=False
        )
    elif variant == "numba":
        monkeypatch.setattr(
            "digcalc_project.src.services.interpolation_service.HAS_NUMBA", True, raising=False
        )

    project = Project(name="bench")
    stack = _build_stack()
    surf = _dummy_surface()
    interp = IDWInterpolator()

    def _run():
        interp.generate_surfaces(project, stack, surf)

    result = benchmark(_run)
    # ensure reasonable runtime (<10s target for dev) – but don't fail on CI
    assert result < 10.0
