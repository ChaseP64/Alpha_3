import pytest
from pytestqt.qt_compat import qt_api
from PySide6 import QtCore

# Adjust import based on your project structure
try:
    from digcalc_project.src.ui.dialogs.elevation_dialog import ElevationDialog, _LAST_ELEV
except ImportError:
    # Handle potential path issues if running tests differently
    from src.ui.dialogs.elevation_dialog import ElevationDialog, _LAST_ELEV

# Check if qt_api is available (indicates pytest-qt is installed and working)
if not qt_api:
    pytest.skip("pytest-qt not found, skipping UI tests", allow_module_level=True)


def test_dialog_initialization(qtbot):
    """Test dialog initialization and default value."""
    initial_last_elev = _LAST_ELEV # Store initial value
    dlg = ElevationDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Enter Constant Elevation"
    assert dlg.isModal()
    assert abs(dlg._spinbox.value() - initial_last_elev) < 1e-9

def test_enter_and_accept_elevation(qtbot):
    """Test entering a value and accepting the dialog."""
    global _LAST_ELEV
    # Set a known starting point for _LAST_ELEV for this test
    original_last_elev = _LAST_ELEV
    _LAST_ELEV = 50.0 # Set a specific value before creating dialog
    
    dlg = ElevationDialog()
    qtbot.addWidget(dlg)
    
    # Check initial value matches the set _LAST_ELEV
    assert abs(dlg._spinbox.value() - 50.0) < 1e-9

    # Simulate user input
    test_value = 123.45
    dlg._spinbox.setValue(test_value)
    
    # Simulate clicking OK
    ok_button = dlg._buttonbox.button(dlg._buttonbox.StandardButton.Ok)
    assert ok_button is not None
    qtbot.mouseClick(ok_button, QtCore.Qt.MouseButton.LeftButton)
    
    # Verify dialog result and value
    assert dlg.result() == dlg.Accepted
    assert abs(dlg.value() - test_value) < 1e-9
    
    # Verify the module-level _LAST_ELEV was updated
    assert abs(_LAST_ELEV - test_value) < 1e-9
    
    # Restore original _LAST_ELEV if needed for other tests (though tests should be isolated)
    _LAST_ELEV = original_last_elev

def test_cancel_dialog(qtbot):
    """Test cancelling the dialog does not update _LAST_ELEV."""
    global _LAST_ELEV
    original_last_elev = 10.0 # Set a known starting value
    _LAST_ELEV = original_last_elev
    
    dlg = ElevationDialog()
    qtbot.addWidget(dlg)

    # Change value in spinbox but then cancel
    dlg._spinbox.setValue(999.99)
    
    # Simulate clicking Cancel
    cancel_button = dlg._buttonbox.button(dlg._buttonbox.StandardButton.Cancel)
    assert cancel_button is not None
    qtbot.mouseClick(cancel_button, QtCore.Qt.MouseButton.LeftButton)

    # Verify dialog result and that _LAST_ELEV remains unchanged
    assert dlg.result() == dlg.Rejected
    assert abs(_LAST_ELEV - original_last_elev) < 1e-9 