import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QApplication, QGraphicsView

pytest.importorskip("PySide6")

from digcalc_project.src.ui.items.polyline_item import PolylineItem
from digcalc_project.src.ui.tracing_scene import TracingScene


class _Panel:
    current_project = None


@pytest.fixture
def scene_with_polyline(qtbot):
    view = QGraphicsView()
    scn = TracingScene(view, _Panel())
    qtbot.addWidget(view)
    view.setScene(scn)

    # Build a simple 2-vertex polyline with distinct elevations
    pen = QPen(QColor("#00ff00"))
    p_item = PolylineItem([QPointF(0, 0), QPointF(10, 0)], pen)
    # Set Z values
    verts = p_item.vertices()
    verts[0].set_z(0.0)
    verts[1].set_z(10.0)
    scn.addItem(p_item)

    return scn, verts


def test_elevation_heatmap_toggle(scene_with_polyline):
    scn, verts = scene_with_polyline

    # Initially disabled – vertices share layer colour
    default_cols = [v._colour_hex for v in verts]

    scn.set_elevation_heatmap_enabled(True)
    heat_cols = [v._colour_hex for v in verts]
    # Colours should have changed and differ between elevations
    assert heat_cols[0] != default_cols[0]
    assert heat_cols[0] != heat_cols[1]

    # Disable again – colours revert to default layer colour
    scn.set_elevation_heatmap_enabled(False)
    restored = [v._colour_hex for v in verts]
    assert restored == default_cols
