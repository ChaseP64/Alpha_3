"""Benchmark QuadTree query performance vs naïve list comprehension.

Run with:

    DIGCALC_RUN_BENCH=1 pytest -m perf tests/benchmarks/test_spatial_index_bench.py

The benchmark is opt-in so normal CI runs stay fast.  We simply assert that the
QuadTree implementation is at least **2×** faster than scanning the same list
with pure Python distance maths for a 50 000-point dataset.
"""

import os
import random
from typing import List, Tuple

import pytest

from digcalc_project.src.utils.spatial_index import QuadTree

# Opt-in guard – skip unless developer explicitly enables
if os.getenv("DIGCALC_RUN_BENCH") != "1":
    pytest.skip("Benchmarks disabled – set DIGCALC_RUN_BENCH=1 to enable.", allow_module_level=True)

Point = Tuple[float, float]

def _generate_points(n: int = 50_000) -> List[Point]:
    return [(random.uniform(-1000, 1000), random.uniform(-1000, 1000)) for _ in range(n)]


@pytest.mark.perf
def test_quad_tree_vs_naive(benchmark):
    pts = _generate_points()

    qt = QuadTree(boundary=(-1200, -1200, 2400, 2400))
    qt.bulk_insert([(x, y, None) for x, y in pts])

    query_pt = (0.0, 0.0)
    radius = 50.0

    # -------------------- benchmark QuadTree -----------------------
    qt_time = benchmark(lambda: qt.query(query_pt, radius))

    # -------------------- benchmark naïve -------------------------
    def _naive():
        qx, qy = query_pt
        r2 = radius * radius
        hits = []
        for x, y in pts:
            dx = x - qx
            dy = y - qy
            if dx * dx + dy * dy <= r2:
                hits.append((x, y))
        return hits

    import time
    start = time.perf_counter()
    naive_hits = _naive()
    naive_time = time.perf_counter() - start

    # Validate both methods return same set of points (order may differ)
    assert sorted(qt.query(query_pt, radius)) == sorted([(p, None) for p in naive_hits])

    # Expect QuadTree at least twice as fast (generous margin for CI variance)
    assert qt_time * 2 <= naive_time 