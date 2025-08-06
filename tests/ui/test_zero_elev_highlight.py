import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QGraphicsView
from PySide6.QtGui import QPen, QColor
from PySide6.QtCore import QPointF

from digcalc_project.src.ui.tracing_scene import TracingScene
from digcalc_project.src.ui.items.polyline_item import PolylineItem


class _Panel:
    """Minimal stub matching attributes accessed by TracingScene in tests."""

    current_project = None


@pytest.fixture
def scene_with_vertices(qtbot):
    view = QGraphicsView()
    scene = TracingScene(view, _Panel())
    qtbot.addWidget(view)
    view.setScene(scene)

    # Construct a simple two-vertex polyline so we can inspect colour changes
    pen = QPen(QColor("#00ff00"))  # layer colour = green
    p_item = PolylineItem([QPointF(0, 0), QPointF(10, 0)], pen)

    verts = p_item.vertices()
    verts[0].set_z(0.0)   # zero-elevation vertex – should be highlighted
    verts[1].set_z(8.5)   # non-zero – should keep default colour

    scene.addItem(p_item)
    return scene, verts


def test_zero_elev_highlight_toggle(scene_with_vertices):
    scene, verts = scene_with_vertices

    # Baseline colours (layer pen colour for both)
    default_colours = [v._colour_hex for v in verts]

    # Enable highlight – first vertex should turn magenta, second unchanged
    scene.set_zero_elev_highlight_enabled(True)
    colours_on = [v._colour_hex for v in verts]
    assert colours_on[0].lower() == "#ff00ff"  # magenta
    assert colours_on[1] == default_colours[1]

    # Disable highlight – colours should revert to defaults
    scene.set_zero_elev_highlight_enabled(False)
    colours_off = [v._colour_hex for v in verts]
    assert colours_off == default_colours


def test_zero_elev_highlight_with_heatmap(scene_with_vertices):
    scene, verts = scene_with_vertices

    # Turn on heat-map first (changes colours based on elevation)
    scene.set_elevation_heatmap_enabled(True)
    heatmap_colours = [v._colour_hex for v in verts]
    assert heatmap_colours[0] != heatmap_colours[1]  # different elevations

    # Now enable zero-Z highlight – zero-vertex must turn magenta
    scene.set_zero_elev_highlight_enabled(True)
    assert verts[0]._colour_hex.lower() == "#ff00ff"

    # Disabling highlight should restore heat-map colours
    scene.set_zero_elev_highlight_enabled(False)
    assert [v._colour_hex for v in verts] == heatmap_colours


def test_zero_elev_highlight_no_vertices(qtbot):
    """Ensure no error when scene has no vertices."""
    view = QGraphicsView()
    scene = TracingScene(view, _Panel())
    qtbot.addWidget(view)
    view.setScene(scene)

    # Should not raise when toggling highlight with empty scene
    scene.set_zero_elev_highlight_enabled(True)
    scene.set_zero_elev_highlight_enabled(False)
