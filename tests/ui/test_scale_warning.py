import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.project_scale import ProjectScale
from digcalc_project.src.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _app(qtbot):
    """Ensure a QApplication instance is available for all tests."""
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def main_window(qtbot):
    """Create a main window and register with qtbot."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()
    return mw


def test_scale_warning_shown_once(qtbot, monkeypatch, main_window):
    """Verify warning dialog shows once and overlay disappears after calibration."""
    scene = main_window.visualization_panel.scene_2d

    # Attach an empty project with *no* scale so the scene detects un-calibrated state
    project = Project(name="Unit-Test Project")
    main_window.visualization_panel.set_project(project)

    # Ensure the scene can find the project via panel.current_project
    assert main_window.visualization_panel.current_project.scale is None

    # Mock QMessageBox.information to avoid modal UI blocking the test
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    # First call to start_drawing should set warn flag and create overlay
    scene.start_drawing()
    assert scene._scale_warn_shown is True, "Info dialog flag not set on first trace."
    assert scene._scale_overlay is not None, "Overlay not created when scale missing."

    # Simulate calibration by setting project.scale and notifying the scene
    project.scale = ProjectScale(
        input_method="two_point",
        world_units="ft",
        world_per_paper_in=20.0,
        render_dpi_at_cal=96.0,
    )
    scene.on_scale_calibrated()

    assert scene._scale_overlay is None, "Overlay not removed after calibration."
