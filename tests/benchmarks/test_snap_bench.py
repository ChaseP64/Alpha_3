import os
import random

import pytest

from digcalc_project.src.utils.spatial_index import QuadTree

# Opt-in guard – skip unless explicitly enabled
if os.getenv("DIGCALC_RUN_BENCH") != "1":
    pytest.skip("Benchmarks disabled – set DIGCALC_RUN_BENCH=1 to enable.", allow_module_level=True)


def _build_qt(num_pts: int = 10_000):
    qt = QuadTree(boundary=(-1000, -1000, 2000, 2000))
    pts = [(random.uniform(-500, 500), random.uniform(-500, 500), None) for _ in range(num_pts)]
    qt.bulk_insert(pts)
    return qt


@pytest.mark.perf
def test_nearest_vertex_benchmark(benchmark):
    qt = _build_qt()
    qx, qy = 0.123, -0.456

    def _query():
        qt.nearest((qx, qy), radius=5.0)

    benchmark(_query)
