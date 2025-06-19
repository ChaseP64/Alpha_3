import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGraphicsEllipseItem

from digcalc_project.src.ui.main_window import MainWindow

pytest.importorskip("PySide6")
pytest.skip("Skipping Borehole tool UI tests pending stabilization", allow_module_level=True)


@pytest.fixture
def main_window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    # ensure project exists with strata stack and one material so dialog combo has entry
    project = win.project_controller.get_current_project()
    if project.strata is None:
        from digcalc_project.src.models.strata_models import StrataStack, Material
        project.strata = StrataStack(id=1, materials=[Material(id=1, name="Clay")])
    yield win
    win.close()


def _ellipse_count(scene):
    return sum(1 for it in scene.items() if isinstance(it, QGraphicsEllipseItem))


def test_borehole_place_and_undo(qtbot, main_window):
    vp = main_window.visualization_panel
    scene = vp.scene_2d

    before = _ellipse_count(scene)

    # activate tool
    main_window.borehole_tool_action.setChecked(True)

    # simulate click at scene pos (10,10)
    view = vp.view_2d
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=view.mapFromScene(10, 10))

    # Wait for BoreholeEditorDialog, auto-accept
    from digcalc_project.src.ui.dialogs.borehole_editor_dialog import BoreholeEditorDialog

    dlg = None
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, BoreholeEditorDialog):
            dlg = widget
            break
    assert dlg is not None, "Editor dialog did not appear"
    qtbot.waitExposed(dlg)
    qtbot.mouseClick(dlg.button_box.button(dlg.button_box.StandardButton.Ok), Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: _ellipse_count(scene) == before + 1)

    # Undo via dock
    main_window.strata_manager_dock.undo_stack.undo()
    qtbot.waitUntil(lambda: _ellipse_count(scene) == before) 