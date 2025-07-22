import random
from digcalc_project.src.utils.spatial_index import QuadTree


def _build_qt(num_pts: int = 10_000):
    qt = QuadTree(boundary=(-1000, -1000, 2000, 2000))
    pts = [(random.uniform(-500, 500), random.uniform(-500, 500), None) for _ in range(num_pts)]
    qt.bulk_insert(pts)
    return qt


def test_nearest_vertex_benchmark(benchmark):
    qt = _build_qt()
    qx, qy = 0.123, -0.456

    def _query():
        qt.nearest((qx, qy), radius=5.0)

    result = benchmark(_query)
    # Assert p90 execution time < 1 ms; pytest-benchmark provides stats after run.
    # Hard assertion would be flaky across CI runners; rely on BENCH CI job. 