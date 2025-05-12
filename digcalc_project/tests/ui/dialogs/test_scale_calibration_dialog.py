import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene
from pytestqt.qt_compat import qt_api

try:
    from digcalc_project.src.ui.dialogs.scale_calibration_dialog import ScaleCalibrationDialog
except ImportError:  # pragma: no cover – fallback for alternative paths during CI
    from src.ui.dialogs.scale_calibration_dialog import ScaleCalibrationDialog  # type: ignore

# Skip tests entirely if pytest-qt (qt_api) is not available
if not qt_api:
    pytest.skip("pytest-qt not available – skipping Qt dialog tests", allow_module_level=True)


@pytest.fixture()
def pdf_view_widget(qtbot):
    """Create a dummy top-level window containing a QGraphicsView named 'pdf_view'."""
    win = QWidget()
    scene = QGraphicsScene()
    view = QGraphicsView(scene, win)
    view.setObjectName("pdf_view")
    # Important: add the widgets to qtbot so they are cleaned up automatically
    qtbot.addWidget(win)
    qtbot.addWidget(view)
    return win, view


def test_pick_falls_back_when_pdf_view_hidden(qtbot, pdf_view_widget):
    """If the main PDF view exists but is hidden, the dialog should use the embedded picker."""
    win, view = pdf_view_widget
    # Do *not* show the window → view.isVisible() is False
    dlg = ScaleCalibrationDialog(parent=None, scene=None)
    qtbot.addWidget(dlg)

    # Invoke the private slot directly (simulate clicking the button)
    dlg._on_pick()

    # The dialog should have created an embedded _PointPicker instance
    assert getattr(dlg, "_point_picker_instance", None) is not None
    # And should *not* have a _global_picker yet
    assert getattr(dlg, "_global_picker", None) is None


def test_pick_uses_global_when_pdf_view_visible(qtbot, pdf_view_widget):
    """When the PDF view is visible the dialog should attach the global picker."""
    win, view = pdf_view_widget
    # Show the window so the view is visible
    win.show()  # noqa: E305 – required for visibility
    view.show()
    qtbot.waitExposed(win)  # Ensure window is processed

    dlg = ScaleCalibrationDialog(parent=None, scene=None)
    qtbot.addWidget(dlg)

    # Trigger pick
    dlg._on_pick()

    # Now a _GlobalPointPicker should be attached
    assert getattr(dlg, "_global_picker", None) is not None
    # Embedded picker should not exist in this branch
    assert getattr(dlg, "_point_picker_instance", None) is None 