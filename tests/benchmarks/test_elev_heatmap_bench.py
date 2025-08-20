"""Benchmark for TracingScene._refresh_elevation_heatmap performance.

Run with:

    DIGCALC_RUN_BENCH=1 pytest -m perf tests/benchmarks/test_elev_heatmap_bench.py

The benchmark is **opt-in** so normal CI runs remain fast.  It constructs a
:class:`digcalc_project.src.ui.tracing_scene.TracingScene` containing 10 000
vertices with random elevations and measures the wall-clock runtime of
``_refresh_elevation_heatmap``.  The Phase-5 performance guard requires that
the 90th-percentile runtime stays below **100 ms** on a typical developer
machine – we therefore assert the measured time is under ``0.1`` seconds.
"""

import os
import random
from typing import List

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsView

from digcalc_project.src.ui.items.vertex_item import VertexItem
from digcalc_project.src.ui.tracing_scene import TracingScene

# ---------------------------------------------------------------------------
# Opt-in guard – skip unless explicitly enabled by developer/CI job
# ---------------------------------------------------------------------------
if os.getenv("DIGCALC_RUN_BENCH") != "1":
    pytest.skip(
        "Benchmarks disabled – set DIGCALC_RUN_BENCH=1 to enable.",
        allow_module_level=True,
    )


@pytest.mark.perf
def test_elev_heatmap_refresh_p90(benchmark):
    """The heat-map refresh must complete in < 100 ms for 10 k vertices."""

    # Ensure QApplication instance (headless is fine)
    app = QApplication.instance() or QApplication([])

    # Stub panel object – TracingScene only accesses ``current_project`` attr
    class _Panel:
        current_project = None

    view = QGraphicsView()
    scene = TracingScene(view, _Panel())
    view.setScene(scene)

    # ------------------------------------------------------------------
    # Populate scene with 10 000 vertices of random elevation (-50 → 50 ft)
    # ------------------------------------------------------------------
    for _ in range(10_000):
        v = VertexItem(QPointF(random.uniform(0, 1000), random.uniform(0, 1000)))
        v.set_z(random.uniform(-50, 50))
        scene.addItem(v)

    # Warm-up – the first call may pay one-off Qt costs; exclude from bench
    scene._refresh_elevation_heatmap()

    runtime = benchmark(scene._refresh_elevation_heatmap)

    # Assert wall-clock runtime below 100 ms (0.1 s)
    assert runtime < 0.1, f"Heat-map refresh too slow: {runtime:.3f}s > 0.1s"
