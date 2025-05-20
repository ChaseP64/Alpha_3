"""UI tests for layer colour propagation.

These tests exercise the SetLayerColorCommand + PolylineItem + TracingScene
integration without spinning up the full *MainWindow*.
"""

import pytest
from PySide6.QtGui import QPen, QColor
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from digcalc_project.src.services.layer_service import create_layer
from digcalc_project.src.ui.commands.set_layer_color_cmd import SetLayerColorCommand
from digcalc_project.src.ui.items.polyline_item import PolylineItem
from digcalc_project.src.ui.tracing_scene import TracingScene

# Dummy VisualizationPanel substitute (only needs current_project attr)
class _StubPanel:
    def __init__(self, project):
        self.current_project = project


@pytest.fixture(scope="module")
def qapp():  # noqa: D401 – used by qtbot if pytest-qt not present
    app = QApplication.instance() or QApplication([])
    yield app


def _make_scene_and_polyline(project):
    # Build scene stub (need a QGraphicsView for ctor)
    from PySide6.QtWidgets import QGraphicsView

    view = QGraphicsView()
    panel = _StubPanel(project)
    scene = TracingScene(view, panel)

    layer = project.layers[0]
    pen = QPen(QColor(layer.line_color), 2)
    poly = PolylineItem([QPointF(0, 0), QPointF(10, 0)], pen, layer_id=layer.id)
    scene.addItem(poly)
    return scene, poly


def test_recolor_updates_polyline(qapp):  # noqa: D401
    # --- Arrange -----------------------------------------------------------------
    from digcalc_project.src.models.project import Project

    layer = create_layer("Test")
    proj = Project(name="Tmp")
    proj.layers.append(layer)

    scene, poly = _make_scene_and_polyline(proj)

    old_hex = poly.pen().color().name()
    assert old_hex.lower() == layer.line_color.lower()

    # --- Act ---------------------------------------------------------------------
    new_hex = "#ff00ff"
    cmd = SetLayerColorCommand(layer, "line_color", new_hex, scene)
    scene.undoStack().push(cmd)

    # --- Assert ------------------------------------------------------------------
    assert poly.pen().color().name().lower() == new_hex 


def test_outline_visible(qapp):
    """Ensure polyline pen width defaults to 2 for main stroke."""
    from digcalc_project.src.models.project import Project

    layer = create_layer("Vis")
    proj = Project(name="VisProj")
    proj.layers.append(layer)

    from PySide6.QtWidgets import QGraphicsView

    view = QGraphicsView()
    panel = _StubPanel(proj)
    scene = TracingScene(view, panel)

    pen = QPen(QColor(layer.line_color), 2)
    poly = PolylineItem([QPointF(0, 0), QPointF(50, 0)], pen, layer_id=layer.id)
    scene.addItem(poly)

    assert poly.pen().widthF() == 2 