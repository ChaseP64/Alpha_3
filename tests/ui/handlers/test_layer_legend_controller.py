from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

from digcalc_project.src.ui.main_window.layer_legend_controller import LayerLegendController


@pytest.fixture
def mock_main_window():
    """Fixture to create a mock MainWindow with necessary attributes."""
    mw = MagicMock()
    mw.legend_dock = MagicMock()
    mw.project_controller = MagicMock()
    mw.visualization_panel = MagicMock()
    return mw


def test_on_legend_layers_count_show(mock_main_window):
    """Test that the legend is shown when layer count is positive."""
    controller = LayerLegendController(mock_main_window)
    controller._on_legend_layers_count(1)
    mock_main_window.legend_dock.show.assert_called_once()
    mock_main_window.legend_dock.hide.assert_not_called()


def test_on_legend_layers_count_hide(mock_main_window):
    """Test that the legend is hidden when layer count is zero."""
    controller = LayerLegendController(mock_main_window)
    controller._on_legend_layers_count(0)
    mock_main_window.legend_dock.hide.assert_called_once()
    mock_main_window.legend_dock.show.assert_not_called()


def test_on_layer_visibility_toggled(mock_main_window):
    """Test toggling layer visibility from the legend."""
    controller = LayerLegendController(mock_main_window)
    mock_project = mock_main_window.project_controller.get_current_project.return_value
    mock_layer = MagicMock()
    mock_project.get_layer_by_name.return_value = mock_layer

    controller._on_layer_visibility_toggled("TestLayer", False)

    mock_project.get_layer_by_name.assert_called_once_with("TestLayer")
    assert mock_layer.is_visible is False
    mock_main_window._trigger_layer_visibility_update.assert_called_once_with("TestLayer", False)
    mock_main_window.visualization_panel.set_layer_visible.assert_called_once_with("TestLayer", False)


def test_on_layer_visibility_changed(mock_main_window):
    """Test toggling layer visibility from the main layer tree."""
    controller = LayerLegendController(mock_main_window)
    mock_project = mock_main_window.project_controller.get_current_project.return_value
    mock_layer = MagicMock()
    mock_project.get_layer_by_name.return_value = mock_layer

    mock_item = QTreeWidgetItem()
    mock_item.setText(0, "TestLayer")
    mock_item.setCheckState(0, Qt.CheckState.Checked)

    controller._on_layer_visibility_changed(mock_item, 0)

    mock_project.get_layer_by_name.assert_called_once_with("TestLayer")
    assert mock_layer.is_visible is True
    mock_main_window.visualization_panel.scene_2d.setLayerVisible.assert_called_once_with("TestLayer", True)
    mock_main_window.legend_dock.set_layer_visibility.assert_called_once_with("TestLayer", True) 