from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from digcalc_project.src.ui.main_window.key_binding_handler import KeyBindingHandler


@pytest.fixture
def mock_main_window():
    """Fixture to create a mock MainWindow with necessary handlers."""
    mw = MagicMock()
    mw.view_mode_handler = MagicMock()
    mw.polyline_handler = MagicMock()
    return mw


def test_handler_initialization(mock_main_window):
    """Test that shortcuts are created on initialization."""
    handler = KeyBindingHandler(mock_main_window)
    # The QShortcut constructor is called within __init__
    assert handler.toggle_others_shortcut is not None
    # We can't easily test the connection here without a full Qt loop,
    # but we can check that the handler was set up.
    assert handler.main_window == mock_main_window


def test_handle_key_press_delete_with_selection(mock_main_window):
    """Test that Delete key press calls the polyline handler when an item is selected."""
    # Arrange
    handler = KeyBindingHandler(mock_main_window)
    mock_main_window.polyline_handler._selected_scene_item = MagicMock()  # Simulate selection

    event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)

    # Act
    handler.handle_key_press(event)

    # Assert
    mock_main_window.polyline_handler._delete_selected_polyline.assert_called_once()
    assert event.isAccepted()


def test_handle_key_press_delete_no_selection(mock_main_window):
    """Test that Delete key press is ignored when nothing is selected."""
    # Arrange
    handler = KeyBindingHandler(mock_main_window)
    mock_main_window.polyline_handler._selected_scene_item = None  # No selection

    event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)

    # Act
    handler.handle_key_press(event)

    # Assert
    mock_main_window.polyline_handler._delete_selected_polyline.assert_not_called()
    assert not event.isAccepted()


def test_handle_key_press_other_key(mock_main_window):
    """Test that other key presses are ignored."""
    # Arrange
    handler = KeyBindingHandler(mock_main_window)
    event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.NoModifier)

    # Act
    handler.handle_key_press(event)

    # Assert
    mock_main_window.polyline_handler._delete_selected_polyline.assert_not_called()
    assert not event.isAccepted()
