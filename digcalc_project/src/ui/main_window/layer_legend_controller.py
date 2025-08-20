"""
Controller for handling layer legend logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtWidgets import QTreeWidgetItem

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class LayerLegendController(QObject):
    """Manages interactions and logic for the layer legend."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window

    @Slot(int)
    def _on_legend_layers_count(self, count: int):
        """Show or hide the legend dock based on the number of layers."""
        mw = self.main_window
        if hasattr(mw, "legend_dock"):
            if count > 0:
                mw.legend_dock.show()
            else:
                mw.legend_dock.hide()

    @Slot(str, bool)
    def _on_layer_visibility_toggled(self, layer_name: str, visible: bool):
        """Handle visibility changes from the legend for a specific layer."""
        mw = self.main_window
        project = mw.project_controller.get_current_project()
        if not project:
            return

        layer = project.get_layer_by_name(layer_name)
        if layer:
            layer.is_visible = visible
            mw._trigger_layer_visibility_update(layer_name, visible)
            if mw.visualization_panel:
                mw.visualization_panel.set_layer_visible(layer_name, visible)

    @Slot(QTreeWidgetItem, int)
    def _on_layer_visibility_changed(self, item: QTreeWidgetItem, column: int):
        """Slot called when a layer's checkbox state changes in the main layer tree."""
        if column == 0:
            mw = self.main_window
            layer_name = item.text(0)
            is_visible = item.checkState(0) == Qt.CheckState.Checked

            project = mw.project_controller.get_current_project()
            if project:
                layer = project.get_layer_by_name(layer_name)
                if layer:
                    layer.is_visible = is_visible

            if mw.visualization_panel and mw.visualization_panel.scene_2d:
                mw.visualization_panel.scene_2d.setLayerVisible(layer_name, is_visible)

            if hasattr(mw, "legend_dock"):
                mw.legend_dock.set_layer_visibility(layer_name, is_visible)
