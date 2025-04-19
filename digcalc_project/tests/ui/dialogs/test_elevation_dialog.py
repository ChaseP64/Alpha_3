import pytest
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QDialog, QDialogButtonBox
from pytestqt.qt_compat import qt_api

# Adjust import based on your project structure
try:
    from digcalc_project.src.ui.dialogs import elevation_dialog # Import module
    from digcalc_project.src.ui.dialogs.elevation_dialog import ElevationDialog
except ImportError:
    # Handle potential path issues if running tests differently
    from src.ui.dialogs import elevation_dialog # Import module
    from src.ui.dialogs.elevation_dialog import ElevationDialog

# Check if qt_api is available (indicates pytest-qt is installed and working)
if not qt_api:
    pytest.skip("pytest-qt not found, skipping UI tests", allow_module_level=True)


@pytest.fixture(autouse=True)
def reset_last_elev():
    """Fixture to reset _LAST_ELEV before and after each test."""
    # Access global via module
    original = elevation_dialog._LAST_ELEV
    elevation_dialog._LAST_ELEV = 0.0 # Reset to default before test
    yield
    elevation_dialog._LAST_ELEV = original # Restore after test


def test_dialog_initialization(qtbot):
    """Test the dialog initializes with the last elevation."""
    test_value = 123.45 # Use a local variable for the test value
    dlg = ElevationDialog(initial_value=test_value) # Pass initial value
    qtbot.addWidget(dlg)
    assert abs(dlg._spinbox.value() - test_value) < 1e-9
    assert dlg.windowTitle() == "Enter Constant Elevation"

def test_enter_and_accept_elevation(qtbot):
    """Test entering a value and accepting the dialog."""
    # global _LAST_ELEV # No longer need to access global directly here
    original_last_elev = 50.0
    elevation_dialog._LAST_ELEV = original_last_elev # Set global via module

    dlg = ElevationDialog(initial_value=original_last_elev) # Pass initial value
    qtbot.addWidget(dlg)

    # --- Check initial value FIRST --- 
    assert abs(dlg._spinbox.value() - original_last_elev) < 1e-9

    # --- Set new value --- 
    new_value = -9.87
    # Use setValue directly for less fragility:
    dlg._spinbox.setValue(new_value)
    assert abs(dlg._spinbox.value() - new_value) < 1e-9

    # Simulate clicking OK
    ok_button = dlg._buttonbox.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button is not None
    
    # Click OK and wait for the accepted signal to be processed
    with qtbot.waitSignal(dlg.accepted, timeout=1000) as blocker:
        qtbot.mouseClick(ok_button, QtCore.Qt.MouseButton.LeftButton)

    # Verify dialog result and the dialog's internal value
    assert dlg.result() == QDialog.DialogCode.Accepted # Use correct enum
    assert abs(dlg.value() - new_value) < 1e-9 # Check dialog's final value

    # --- Check that the global _LAST_ELEV was updated --- 
    # Now that we've waited for the signal, check the module global
    assert abs(elevation_dialog._LAST_ELEV - new_value) < 1e-9 # Check module global

def test_cancel_dialog(qtbot):
    """Test cancelling the dialog does not update _LAST_ELEV."""
    # global _LAST_ELEV
    original_last_elev = 10.0
    elevation_dialog._LAST_ELEV = original_last_elev # Set global via module

    dlg = ElevationDialog(initial_value=original_last_elev) # Pass initial value
    qtbot.addWidget(dlg)

    # Check initial value
    assert abs(dlg._spinbox.value() - original_last_elev) < 1e-9

    # Change value in spinbox but then cancel
    dlg._spinbox.setValue(999.99)

    # Simulate clicking Cancel
    cancel_button = dlg._buttonbox.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel_button is not None
    qtbot.mouseClick(cancel_button, QtCore.Qt.MouseButton.LeftButton)

    # Verify dialog result and that _LAST_ELEV remains unchanged
    assert dlg.result() == QDialog.DialogCode.Rejected # Use correct enum
    assert abs(elevation_dialog._LAST_ELEV - original_last_elev) < 1e-9 # Check module global hasn't changed 