import pytest

from PySide6.QtWidgets import QApplication, QGraphicsView
from PySide6.QtCore import QPointF

pytest.importorskip("PySide6")

from digcalc_project.src.ui.tracing_scene import TracingScene


class _Panel:  # minimal stub
    current_project = None


@pytest.fixture
def scene(qtbot):
    view = QGraphicsView()
    scn = TracingScene(view, _Panel())
    qtbot.addWidget(view)
    view.setScene(scn)
    return scn


def test_perf_warning_flag(scene):
    # Insert >50k points directly into spatial index to simulate heavy scene
    for i in range(50_100):
        scene._sp_index.insert(float(i), 0.0, None)
    # Trigger finalize to evaluate guard
    scene._perf_warn_shown = False
    scene._finalize_current_polyline("Default")  # type: ignore[arg-type]
    assert scene._perf_warn_shown is True 