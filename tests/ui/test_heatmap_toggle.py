import pytest

from PySide6.QtWidgets import QApplication, QGraphicsView

pytest.importorskip("PySide6")

from digcalc_project.src.ui.tracing_scene import TracingScene


class _Panel:  # stub
    current_project = None


@pytest.fixture
def scene(qtbot):
    view = QGraphicsView()
    scn = TracingScene(view, _Panel())
    qtbot.addWidget(view)
    view.setScene(scn)
    return scn


def test_heatmap_toggle(scene):
    # Initially off
    scene.set_heatmap_enabled(False)
    assert not scene._heatmap_enabled

    # Enable and create a snap to ensure rects visible
    scene.set_heatmap_enabled(True)
    scene._apply_grid_snap(scene.sceneRect().center())
    assert scene._heatmap_enabled
    assert any(it.isVisible() for it in scene._heatmap_items.values())

    # Disable again → rects hidden
    scene.set_heatmap_enabled(False)
    assert all(not it.isVisible() for it in scene._heatmap_items.values()) 