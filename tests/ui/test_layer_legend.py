"""GUI-level test for LayerLegendDock visibility toggling and undo support."""

import pytest
from PySide6.QtWidgets import QApplication, QGraphicsView
from PySide6.QtGui import QPen, QColor
from PySide6.QtCore import QPointF, Qt

from digcalc_project.src.services.layer_service import create_layer
from digcalc_project.src.ui.tracing_scene import TracingScene
from digcalc_project.src.ui.docks.layer_legend_dock import LayerLegendDock
from digcalc_project.src.ui.items.polyline_item import PolylineItem
from digcalc_project.src.ui.commands.set_layer_visibility_cmd import SetLayerVisibilityCommand
from digcalc_project.src.models.project import Project


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_scene(project: Project):
    view = QGraphicsView()
    panel = type("StubPanel", (), {"current_project": project})()
    scene = TracingScene(view, panel)
    return scene


def test_layer_legend_visibility_toggle(qapp):
    # Arrange -----------------------------------------------------------
    proj = Project(name="LegendProj")
    layers = [create_layer(f"L{i}") for i in range(4)]
    proj.layers.extend(layers)

    scene = _make_scene(proj)

    # add simple polylines for first two layers so visibility can be checked
    for lyr in layers[:2]:
        pen = QPen(QColor(lyr.line_color), 2)
        item = PolylineItem([QPointF(0, 0), QPointF(10, 0)], pen, layer_id=lyr.id)
        # store layer name for scene visibility API
        item.setData(Qt.UserRole + 1, lyr.name)
        scene.addItem(item)

    legend = LayerLegendDock(project=proj)

    # Ensure legend counts layers
    emitted = []

    def _capture(cnt):
        emitted.append(cnt)

    legend.visibleLayersChanged.connect(_capture)
    legend.refresh()
    assert emitted[-1] == 4

    # Connect legend signal to scene visibility
    legend.layerVisibilityToggled.connect(
        lambda lid, vis: scene.setLayerVisible(
            next(l.name for l in proj.layers if l.id == lid), vis,
        ),
    )

    # Act --------------------------------------------------------------
    cmd = SetLayerVisibilityCommand(layers[0], False, legend)
    scene.undoStack().push(cmd)

    # Assert – polyline for layer 0 should now be hidden
    hidden = all(not it.isVisible() for it in scene.items() if isinstance(it, PolylineItem) and it.layer_id == layers[0].id)
    assert hidden

    # Undo -------------------------------------------------------------
    scene.undoStack().undo()
    visible_again = any(it.isVisible() for it in scene.items() if isinstance(it, PolylineItem) and it.layer_id == layers[0].id)
    assert visible_again 