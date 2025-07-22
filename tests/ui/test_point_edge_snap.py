import math
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsView

from digcalc_project.src.ui.tracing_scene import TracingScene


class _Panel:
    current_project = None


@pytest.fixture
def scene(qtbot):
    # Minimal scene plus view setup
    app = QApplication.instance() or QApplication([])
    view = QGraphicsView()
    scn = TracingScene(view, _Panel())
    qtbot.addWidget(view)
    view.setScene(scn)
    return scn


def test_point_snap(scene):
    # reference vertex
    scene._sp_index.insert(5.0, 5.0, None)

    raw = QPointF(5.2, 5.1)
    snapped = scene._apply_point_snap(raw, radius=0.5)

    assert snapped == QPointF(5.0, 5.0)


def test_edge_snap(scene):
    p1 = (0.0, 0.0)
    p2 = (10.0, 0.0)
    scene._sp_index.insert_edge(p1, p2, (p1, p2, None))

    raw = QPointF(4.0, 3.0)
    snapped = scene._apply_edge_snap(raw, radius=5.0)

    assert math.isclose(snapped.x(), 4.0, abs_tol=1e-6)
    assert math.isclose(snapped.y(), 0.0, abs_tol=1e-6) 