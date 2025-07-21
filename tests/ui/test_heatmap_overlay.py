import pytest

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsRectItem

pytest.importorskip("PySide6")

from digcalc_project.src.ui.tracing_scene import TracingScene


class _Panel:
    current_project = None


@pytest.fixture
def scene(qtbot):
    view = QGraphicsView()
    scn = TracingScene(view, _Panel())
    qtbot.addWidget(view)
    view.setScene(scn)
    # Force heatmap on for test
    scn._heatmap_enabled = True
    return scn


def test_heatmap_cell_created(scene):
    p = QPointF(1.2, 0.8)
    scene._apply_grid_snap(p)
    # Expect at least one heat-map rect item added
    rects = [it for it in scene.items() if isinstance(it, QGraphicsRectItem)]
    assert rects, "Heat-map rectangle not created" 