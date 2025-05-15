import pytest

# PySide6/Qt testing via pytest-qt
from PySide6.QtWidgets import QApplication

from digcalc_project.src.ui.dialogs.pad_elevation_dialog import PadElevationDialog


@pytest.fixture
def app(qtbot):
    """Ensure that a QApplication instance exists for the tests."""
    return QApplication.instance() or QApplication([])


def test_dialog_defaults(qtbot, app):
    """Dialog should honor `last_value` parameter and allow value change."""
    dlg = PadElevationDialog(last_value=123.45)
    qtbot.addWidget(dlg)

    # Verify the initial value equals last_value provided
    assert abs(dlg.value() - 123.45) < 1e-6

    # Change value programmatically and verify helper
    dlg._elev.setValue(200.0)
    assert abs(dlg.value() - 200.0) < 1e-6
