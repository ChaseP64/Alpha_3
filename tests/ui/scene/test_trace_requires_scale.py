from unittest.mock import patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QMessageBox, QWidget
from pytestqt.qt_compat import qt_api

from digcalc_project.src.models.project import Project
from digcalc_project.src.ui.visualization_panel import VisualizationPanel


@pytest.mark.skipif(not qt_api, reason="pytest-qt not available")
def test_trace_blocked_without_scale(qtbot):
    """Tracing should be blocked when the project lacks a valid scale."""
    # Create a minimal project WITHOUT a scale
    proj = Project(name="Scale-Test Project")

    # Parent widget to manage lifetime within the Qt event loop
    parent = QWidget()
    panel = VisualizationPanel(parent=parent)
    panel.set_project(proj)

    # Ensure tracing is *enabled* programmatically for the test
    panel.scene_2d.set_tracing_enabled(True)

    qtbot.addWidget(parent)

    scene = panel.scene_2d
    view = scene.views()[0]

    # Patch the modal dialog so it does not block the test runner
    with patch.object(QMessageBox, "warning", return_value=None) as mock_warn:
        # Record polyline count before click
        before_polys = sum(len(v) for v in proj.traced_polylines.values())

        # Simulate a user click in the view – arbitrary position (10,10)
        qtbot.mouseClick(view.viewport(), Qt.LeftButton, pos=QPoint(10, 10))

        qtbot.wait(50)  # Allow queued events to process

        # No new polylines should have been added
        after_polys = sum(len(v) for v in proj.traced_polylines.values())
        assert after_polys == before_polys, "Polyline was added despite invalid scale."

        # The warning dialog should have been invoked once
        mock_warn.assert_called_once()
