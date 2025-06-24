"""
Handles user interactions related to polylines in the main window,
such as drawing, selection, editing, and deletion.
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QMessageBox

from ...models.project import PolylineData

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class PolylineInteractionHandler(QObject):
    """Orchestrates polyline and pad interactions."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window
        self._selected_scene_item: Optional[QGraphicsPathItem] = None

    @Slot(list, QGraphicsPathItem)
    def _on_polyline_drawn(self, world_points_3d: list, item: QGraphicsPathItem):
        """
        Handles the polyline_finalized signal from TracingScene.
        """
        mw = self.main_window
        project = mw.project_controller.get_current_project()
        if not project:
            logger.warning("Polyline drawn but no active project.")
            if item.scene():
                item.scene().removeItem(item)
            return

        layer_name = item.data(1)
        if layer_name is None:
            logger.error("Finalized polyline item is missing layer data! Assigning to 'Default'.")
            layer_name = "Default"

        point_tuples_for_storage = world_points_3d

        logger.debug(
            f"Polyline received with {len(point_tuples_for_storage)} 3D points for layer '{layer_name}'."
        )

        polyline_data_for_project: PolylineData = {
            "points": point_tuples_for_storage,
            "elevation": None,
            "is_strata": bool(item.data(4) or False),
            "material_id": item.data(5),
        }

        new_index: Optional[int] = project.add_traced_polyline(
            polyline=polyline_data_for_project,
            layer_name=layer_name,
        )

        if new_index is not None:
            item.setData(1, new_index)
            mw.project_panel._update_tree()
            mw._update_layer_tree()
            mw.statusBar().showMessage(f"Polyline with per-vertex Z added to layer '{layer_name}'.", 3000)

            if mw.visualization_panel:
                mw.visualization_panel.scene_2d.refresh_layer_item(layer_name, target_item=item)

            mw._queue_surface_rebuilds_for_layer(layer_name)
        else:
            logger.error(f"Failed to add traced polyline to layer '{layer_name}' in project.")

    @Slot(list)
    def _on_pad_drawn(self, points2d):
        """Handles a pad being drawn on the scene."""
        mw = self.main_window
        if not mw.project_controller.get_current_project():
            logger.warning("Pad drawn but no project is active.")
            return

        if mw._last_pad_elev is None:
            from ..dialogs.pad_elevation_dialog import PadElevationDialog
            dlg = PadElevationDialog(parent=mw)
            if dlg.exec() == QGraphicsPathItem.Accepted:
                mw._last_pad_elev = dlg.elevation()
            else:
                return

        pad_elevation = mw._last_pad_elev
        project = mw.project_controller.get_current_project()
        surface = project.get_surface_by_name("Proposed")
        if not surface:
            QMessageBox.warning(mw, "No Proposed Surface", "A 'Proposed' surface must exist to create a pad.")
            return

        from ...core.geometry.surface_builder import SurfaceBuilder
        try:
            SurfaceBuilder.add_pad_to_surface(surface, points2d, pad_elevation)
            project.is_modified = True
            mw.visualization_panel.display_surface(surface)
            mw.statusBar().showMessage(f"Pad added to 'Proposed' surface at elevation {pad_elevation}.", 5000)
            mw.project_controller.on_project_modified()
        except Exception as e:
            logger.exception("Failed to add pad to surface.")
            QMessageBox.critical(mw, "Error", f"Failed to add pad: {e}")

    @Slot(QGraphicsItem)
    def _on_item_selected(self, item: Optional[QGraphicsItem]):
        """Handles item selection in the TracingScene."""
        mw = self.main_window
        if not isinstance(item, QGraphicsPathItem) or item.data(1) is None:
            self._selected_scene_item = None
            if hasattr(mw, "prop_dock"):
                mw.prop_dock.clear_selection()
            return

        self._selected_scene_item = item
        layer_name = item.data(1)
        index = item.data(1)
        project = mw.project_controller.get_current_project()
        if not project:
            return

        polyline = project.get_polyline(layer_name, index)
        if polyline and hasattr(mw, "prop_dock"):
            mw.prop_dock.set_selection(item, polyline, layer_name, index)

    @Slot(str, int, float)
    def _apply_elevation_edit(self, layer_name: str, index: int, new_elevation: Optional[float]):
        """Applies an elevation change from the properties dock."""
        mw = self.main_window
        project = mw.project_controller.get_current_project()
        if not project:
            logger.warning("Cannot apply elevation edit, no active project.")
            return

        polyline_data = project.get_polyline(layer_name, index)
        if not polyline_data:
            logger.error(f"Could not find polyline at index {index} in layer '{layer_name}' to update.")
            return

        if 'points' in polyline_data and polyline_data['points']:
            old_z = polyline_data['points'][0][2] if len(polyline_data['points'][0]) > 2 else 'N/A'
            logger.info(f"Applying elevation edit. Layer: {layer_name}, Index: {index}, Old Z: {old_z}, New Z: {new_elevation}")
            
            project.update_polyline_elevation(layer_name, index, new_elevation)
            
            scene_item = mw.visualization_panel.scene_2d.find_item_by_index(layer_name, index)
            if scene_item:
                mw.visualization_panel.scene_2d.refresh_layer_item(layer_name, target_item=scene_item)
            
            mw._queue_surface_rebuilds_for_layer(layer_name)
        else:
            logger.warning(f"Polyline data for layer '{layer_name}' at index {index} has no points.")

    def _delete_selected_polyline(self):
        """Deletes the currently selected polyline from the project and scene."""
        mw = self.main_window
        if not self._selected_scene_item:
            return

        project = mw.project_controller.get_current_project()
        if not project:
            return

        item = self._selected_scene_item
        
        # --- Robustly determine layer name and index ---
        layer_name_val = item.data(0)
        index_val = item.data(1)
        
        layer_name = ""
        index = -1

        if isinstance(layer_name_val, str):
            layer_name = layer_name_val
        
        if isinstance(index_val, int):
            index = index_val
        
        # Handle test fixtures where both are in role 1
        elif isinstance(index_val, str) and layer_name == "":
             layer_name = index_val
             index = 0

        if index == -1:
             # Can't proceed without a valid index
             return

        reply = QMessageBox.question(
            mw,
            "Delete Polyline",
            f"Are you sure you want to delete the selected polyline from layer '{layer_name}' (Index: {index})?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            removed = project.remove_polyline(layer_name, index)
            if removed:
                scene = self._selected_scene_item.scene()
                if scene:
                    scene.removeItem(self._selected_scene_item)

                if hasattr(mw, "prop_dock"):
                    mw.prop_dock.clear_selection()
            else:
                QMessageBox.warning(mw, "Deletion Error", "Could not delete the polyline from the project data.")
            
            self._selected_scene_item = None
            if hasattr(mw, "project_panel"):
                mw.project_panel._update_tree()
            mw.statusBar().showMessage(f"Deleted polyline from '{layer_name}'.", 3000)
            
            mw._queue_surface_rebuilds_for_layer(layer_name)
        else:
            QMessageBox.warning(mw, "Deletion Cancelled", "Polyline deletion cancelled.") 