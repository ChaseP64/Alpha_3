"""Benchmark for TIN preview polydata conversion and actor creation.

The benchmark is opt-in via DIGCALC_RUN_BENCH=1 to keep normal CI fast.  It
creates a Surface with 10 000 random points forming a triangulated grid, then
calls `VisualizationPanel.set_tin_preview_enabled(True)` and measures wall-clock
runtime.  The SLA for Phase-7 is < 0.5 s.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from digcalc_project.src.models.surface import Point3D, Surface, Triangle
from digcalc_project.src.ui.visualization_panel import VisualizationPanel

# Skip unless developer/CI requested
if os.getenv("DIGCALC_RUN_BENCH") != "1":
    pytest.skip("Benchmarks disabled – set DIGCALC_RUN_BENCH=1 to enable.", allow_module_level=True)


@pytest.mark.perf
def test_tin_preview_refresh_p90(benchmark):
    """TIN preview overlay should build in < 500 ms for 10 k points."""
    app = QApplication.instance() or QApplication([])

    # Build grid of 100×100 points (10 000)
    n = 100
    xs, ys = np.meshgrid(np.arange(n), np.arange(n))
    zs = np.sin(xs * 0.1) + np.cos(ys * 0.1)  # some elevation variation
    points = [
        Point3D(float(x), float(y), float(z)) for x, y, z in zip(xs.ravel(), ys.ravel(), zs.ravel())
    ]

    surf = Surface("bench")
    # Add points and triangles (simple grid -> two tris per cell)
    surf.points = {p.id: p for p in points}

    def idx(i, j):
        return i * n + j

    for i in range(n - 1):
        for j in range(n - 1):
            p1 = points[idx(i, j)]
            p2 = points[idx(i + 1, j)]
            p3 = points[idx(i, j + 1)]
            p4 = points[idx(i + 1, j + 1)]
            surf.add_triangle(Triangle(p1, p2, p3))
            surf.add_triangle(Triangle(p2, p4, p3))

    panel = VisualizationPanel()
    panel.set_project(type("_P", (), {"surfaces": {surf.name: surf}})())  # minimal stub project

    # Warm-up
    panel.set_tin_preview_enabled(True)
    panel.set_tin_preview_enabled(False)

    runtime = benchmark(lambda: panel.set_tin_preview_enabled(True))

    assert runtime < 0.5, f"TIN preview too slow: {runtime:.3f}s > 0.5s"
