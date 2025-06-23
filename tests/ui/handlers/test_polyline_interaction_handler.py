from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QGraphicsPathItem, QMessageBox

# Adjust import based on project structure
from digcalc_project.src.ui.main_window.polyline_interaction_handler import PolylineInteractionHandler


@pytest.fixture
def mock_main_window():
    """Fixture to create a mock MainWindow with necessary attributes."""
    mw = MagicMock()
    mw.project_controller = MagicMock()
    mw.visualization_panel = MagicMock()
    mw.project_panel = MagicMock()
    mw.prop_dock = MagicMock()
    mw.statusBar = MagicMock()
    return mw


def test_handler_initialization(mock_main_window):
    """Test that the handler initializes correctly."""
    handler = PolylineInteractionHandler(mock_main_window)
    assert handler.main_window == mock_main_window
    assert handler._selected_scene_item is None


@patch('digcalc_project.src.ui.main_window.polyline_interaction_handler.QMessageBox')
def test_delete_selected_polyline_no_selection(mock_qmessagebox, mock_main_window):
    """Test delete call with no item selected."""
    handler = PolylineInteractionHandler(mock_main_window)
    handler._delete_selected_polyline()
    # Assert that no confirmation dialog was shown and no deletion occurred
    mock_qmessagebox.question.assert_not_called()
    mock_main_window.project_controller.get_current_project().remove_polyline.assert_not_called()


@patch('digcalc_project.src.ui.main_window.polyline_interaction_handler.QMessageBox')
def test_delete_selected_polyline_confirmed(mock_qmessagebox, mock_main_window):
    """Test delete call when user confirms."""
    # Arrange
    mock_qmessagebox.question.return_value = QMessageBox.Yes
    
    handler = PolylineInteractionHandler(mock_main_window)
    
    mock_item = QGraphicsPathItem()
    mock_item.setData(1, "TestLayer")
    mock_item.setData(1, 0)
    handler._selected_scene_item = mock_item
    
    mock_project = mock_main_window.project_controller.get_current_project.return_value
    mock_project.remove_polyline.return_value = True

    # Act
    handler._delete_selected_polyline()

    # Assert
    mock_qmessagebox.question.assert_called_once()
    mock_project.remove_polyline.assert_called_once_with("TestLayer", 0)
    mock_main_window.statusBar().showMessage.assert_called()
    assert handler._selected_scene_item is None 