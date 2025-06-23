"""
Handles view mode switching and related UI updates for the main window.
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Slot, Qt

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class ViewModeHandler(QObject):
    """Manages view-related actions like 2D/3D switching."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window

    @Slot()
    def on_view_2d(self):
        """Switch to the 2D (PDF/Tracing) view."""
        mw = self.main_window
        if mw.visualization_panel:
            logger.debug("Switching to 2D view.")
            mw.visualization_panel.show_2d_view()
            mw.ui_state.update_view_actions_state()
        else:
            logger.error("Cannot switch to 2D view: VisualizationPanel not found.")

    @Slot()
    def on_view_3d(self):
        """Switch to the 3-D tab in VisualizationPanel (PyVista)."""
        mw = self.main_window
        if mw.visualization_panel:
            logger.debug("Switching to 3-D tab view (PyVista).")
            if hasattr(mw.visualization_panel, "show_pyvista_in_tab"):
                mw.visualization_panel.show_pyvista_in_tab()
            else:
                logger.error("VisualizationPanel is missing show_pyvista_in_tab().")
            mw.ui_state.update_view_actions_state()
        else:
            logger.error("Cannot switch to 3-D view: VisualizationPanel not found.")

    @Slot()
    def _fit_view_to_scene(self):
        """Fit the view to the scene contents."""
        mw = self.main_window
        if (
            mw.visualization_panel
            and mw.visualization_panel.scene_2d
            and mw.visualization_panel.scene_2d.itemsBoundingRect().width() > 0
        ):
            mw.visualization_panel.view_2d.fitInView(
                mw.visualization_panel.scene_2d.itemsBoundingRect(),
                Qt.AspectRatioMode.KeepAspectRatio,
            )

    @Slot()
    def _toggle_other_layers_visibility(self):
        """Toggles the visibility of all layers except the current one."""
        mw = self.main_window
        if not hasattr(mw, "layer_tree") or not hasattr(mw.layer_tree, "currentItem"):
             return
        current_item = mw.layer_tree.currentItem()
        if not current_item:
            return
        
        current_layer_name = current_item.text(0)
        
        root = mw.layer_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            layer_name = item.text(0)
            if layer_name != current_layer_name:
                is_visible = item.checkState(0) == Qt.CheckState.Checked
                item.setCheckState(0, Qt.CheckState.Unchecked if is_visible else Qt.CheckState.Checked)

    def _set_tracing_elev_mode(self, mode: str) -> None:
        """Set the tracing elevation mode in settings."""
        mw = self.main_window
        logger.debug(f"Setting tracing elevation mode to: {mode}")
        settings = mw.project_controller.get_settings()
        settings.set("tracing.elevation_mode", mode)
        if mw.visualization_panel:
            mw.visualization_panel.scene_2d.set_elevation_mode(mode) 