from unittest.mock import MagicMock

import pytest

from digcalc_project.src.ui.main_window.view_mode_handler import ViewModeHandler


@pytest.fixture
def mock_main_window():
    """Fixture to create a mock MainWindow with necessary attributes."""
    mw = MagicMock()
    mw.visualization_panel = MagicMock()
    mw.ui_state = MagicMock()
    mw.project_controller = MagicMock()
    return mw


def test_handler_initialization(mock_main_window):
    """Test that the handler initializes correctly."""
    handler = ViewModeHandler(mock_main_window)
    assert handler.main_window == mock_main_window


def test_on_view_2d(mock_main_window):
    """Test switching to 2D view."""
    handler = ViewModeHandler(mock_main_window)
    handler.on_view_2d()
    mock_main_window.visualization_panel.show_2d_view.assert_called_once()
    mock_main_window.ui_state.update_view_actions_state.assert_called_once()


def test_on_view_3d(mock_main_window):
    """Test switching to 3D view."""
    handler = ViewModeHandler(mock_main_window)
    handler.on_view_3d()
    mock_main_window.visualization_panel.show_pyvista_in_tab.assert_called_once()
    mock_main_window.ui_state.update_view_actions_state.assert_called_once()


def test_set_tracing_elev_mode(mock_main_window):
    """Test setting the tracing elevation mode."""
    handler = ViewModeHandler(mock_main_window)
    mock_settings = MagicMock()
    mock_main_window.project_controller.get_settings.return_value = mock_settings

    handler._set_tracing_elev_mode("interpolate")

    mock_settings.set.assert_called_once_with("tracing.elevation_mode", "interpolate")
    mock_main_window.visualization_panel.scene_2d.set_elevation_mode.assert_called_once_with("interpolate") 