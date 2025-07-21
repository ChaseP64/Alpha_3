import pytest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QGraphicsView

pytest.importorskip("PySide6")

from digcalc_project.src.ui.tracing_scene import TracingScene


class _DummyPanel:  # minimal stub of VisualizationPanel
    def __init__(self):
        self.current_project = None


@pytest.fixture
def tracing_scene(qtbot):
    app = QApplication.instance() or QApplication([])
    view = QGraphicsView()
    panel = _DummyPanel()
    scene = TracingScene(view, panel)
    qtbot.addWidget(view)
    view.setScene(scene)
    return scene


def test_grid_snap_shift_modifier(tracing_scene):
    scene = tracing_scene
    initial_point = QPointF(2.3, 3.7)

    snapped = scene._apply_grid_snap(initial_point)

    # With 1 ft grid spacing and 1:1 scale, expect rounding to nearest integer
    assert snapped == QPointF(round(initial_point.x()), round(initial_point.y()))


def test_no_snap_without_modifier(tracing_scene):
    p = QPointF(2.3, 3.7)
    assert tracing_scene._constrained_pos(p, Qt.NoModifier) == p 