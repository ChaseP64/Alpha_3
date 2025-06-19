from __future__ import annotations

"""SceneEventHandler – centralises scene-interaction slots & signals.

Phase-2 refactor extracts all scene/tracing-related slots from
``main_window.py`` so they can be unit-tested in isolation and so the
MainWindow becomes a thin orchestrator.
"""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QMessageBox, QDialog, QGraphicsPathItem, QGraphicsItem

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QGraphicsItem
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class SceneEventHandler:  # noqa: D101
    def __init__(self, mw: "MainWindow") -> None:  # noqa: D401 – simple init
        self._mw = mw
        self.logger = getattr(mw, "logger", logger)
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Wire scene and interaction signals to this handler's slots."""
        mw = self._mw
        if not hasattr(mw, "visualization_panel"):
            return
        scene = getattr(mw.visualization_panel, "scene_2d", None)
        if scene is None:
            return

        scene.polyline_finalized.connect(self._on_polyline_drawn)
        scene.selectionChanged.connect(self._on_item_selected)
        scene.pad_finalized.connect(self._on_pad_drawn)
        scene.borehole_point_picked.connect(self._on_borehole_point)
        
        prop_dock = getattr(mw, "prop_dock", None)
        if prop_dock:
            prop_dock.edited.connect(self._apply_elevation_edit)
        
        actions = getattr(mw, "action_manager", None)
        if actions:
            actions.toggle_tracing.toggled.connect(self.on_toggle_tracing_mode)
            actions.fit_view.triggered.connect(self._fit_view_to_scene)

        self.logger.debug("SceneEventHandler signals bound.")

    # --- Public Slots (delegating) ---
    
    @Slot(bool)
    def on_toggle_tracing_mode(self, checked: bool):
        if not self._mw.visualization_panel:
            return
        self._mw.visualization_panel.set_tracing_mode(checked)

    @Slot(list, QGraphicsPathItem)
    def _on_polyline_drawn(self, world_points_3d: list, item: QGraphicsPathItem):
        project = self._mw.project_controller.get_current_project()
        if not project:
            if item.scene(): item.scene().removeItem(item)
            return

        layer_name = item.data(Qt.UserRole + 1) or "Default"
        polyline_data = {"points": world_points_3d, "elevation": None, "is_strata": bool(item.data(Qt.UserRole + 4) or False), "material_id": item.data(Qt.UserRole + 5)}
        new_index = project.add_traced_polyline(polyline=polyline_data, layer_name=layer_name)

        if new_index is not None:
            item.setData(1, new_index)
            self._mw.project_panel._update_tree()
            self._mw._update_layer_tree()
            self._mw.statusBar().showMessage(f"Polyline added to layer '{layer_name}'.", 3000)
            self._mw.visualization_panel.scene_2d.refresh_layer_item(layer_name, target_item=item)
            self._mw._queue_surface_rebuilds_for_layer(layer_name)
        else:
            if item.scene(): item.scene().removeItem(item)

    @Slot(QGraphicsItem)
    def _on_item_selected(self, item: Optional[QGraphicsItem]):
        project = self._mw.project_controller.get_current_project()
        prop_dock = getattr(self._mw, "prop_dock", None)
        if not project or not prop_dock:
            if prop_dock: prop_dock.clear_selection()
            return

        if item and isinstance(item, QGraphicsPathItem):
            self._mw._selected_scene_item = item
            layer_name, index = item.data(0), item.data(1)
            if layer_name is not None and index is not None:
                try:
                    poly_data = project.traced_polylines[layer_name][index]
                    elevation = poly_data.get("elevation") if isinstance(poly_data, dict) else None
                    prop_dock.load_polyline(layer_name, index, elevation)
                    prop_dock.show()
                except Exception as e:
                    prop_dock.clear_selection()
            else:
                prop_dock.clear_selection()
        else:
            self._mw._selected_scene_item = None
            prop_dock.clear_selection()

    def _delete_selected_polyline(self):
        project = self._mw.project_controller.get_current_project()
        if not project or not self._mw._selected_scene_item:
            return

        item = self._mw._selected_scene_item
        layer_name, index = item.data(0), item.data(1)
        if layer_name is None or index is None:
            return

        reply = QMessageBox.question(self._mw, "Delete Polyline", f"Delete polyline from layer '{layer_name}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if project.remove_polyline(layer_name, index):
                if item.scene(): item.scene().removeItem(item)
                if hasattr(self._mw, "prop_dock"): self._mw.prop_dock.clear_selection()
                self._mw.project_panel._update_tree()
                self._mw._queue_surface_rebuilds_for_layer(layer_name)
            self._mw._selected_scene_item = None

    @Slot(str, int, float)
    def _apply_elevation_edit(self, layer_name: str, index: int, new_elevation: Optional[float]):
        project = self._mw.project_controller.get_current_project()
        if not project: return
        try:
            poly_list = project.traced_polylines[layer_name]
            if abs(poly_list[index].get("elevation", 0) - new_elevation) > 1e-6:
                poly_list[index]["elevation"] = new_elevation
                project._bump_layer_revision(layer_name)
                self._mw.ui_state.update_build_surface_action_state()
                self._mw._queue_surface_rebuilds_for_layer(layer_name)
        except Exception as e:
            QMessageBox.warning(self._mw, "Edit Error", f"Could not apply elevation change:\n{e}")

    @Slot()
    def _fit_view_to_scene(self):
        if self._mw.visualization_panel and self._mw.visualization_panel.view_2d:
            self._mw.visualization_panel.view_2d.fitInView(self._mw.visualization_panel.scene_2d.sceneRect(), Qt.KeepAspectRatio)

    @Slot(list)
    def _on_pad_drawn(self, points2d):
        from ...ui.commands.set_pad_elevation_command import SetPadElevationCommand
        from ...ui.dialogs.pad_elevation_dialog import PadElevationDialog
        
        dlg = PadElevationDialog(self._mw._last_pad_elev, self._mw)
        if dlg.exec() != QDialog.Accepted: return
        
        elev = dlg.value()
        if dlg.apply_to_all(): self._mw._last_pad_elev = elev
        
        pts3d = [(x, y, elev) for x, y in points2d[:-1]]
        scene = self._mw.visualization_panel.scene_2d
        cmd = SetPadElevationCommand(scene, pts3d)
        self._mw.undoStack.push(cmd)
        if hasattr(self._mw.project_controller, "rebuild_surfaces"):
            self._mw.project_controller.rebuild_surfaces()

    @Slot(float, float)
    def _on_borehole_point(self, x: float, y: float):
        from ...models.strata_models import StrataStack, Material
        from ...ui.dialogs.borehole_editor_dialog import BoreholeEditorDialog
        from ...ui.commands.add_borehole_command import AddBoreholeCommand

        if hasattr(self._mw, "borehole_tool_action"):
            self._mw.borehole_tool_action.setChecked(False)

        project = self._mw.project_controller.get_current_project()
        if not project: return

        if not project.strata:
            project.strata = StrataStack(id=1)
        if not project.strata.materials:
            project.strata.materials.append(Material(id=1, name="Material 1"))

        dlg = BoreholeEditorDialog(project.strata, self._mw)
        if dlg.exec() == QDialog.Accepted:
            borehole = dlg.to_borehole(x, y, project.strata.next_borehole_id())
            cmd = AddBoreholeCommand(project.strata, borehole, self._mw.visualization_panel.scene_2d)
            if hasattr(self._mw, "strata_manager_dock"):
                self._mw.strata_manager_dock.undo_stack.push(cmd)
                self._mw.strata_manager_dock.refresh_boreholes()

    def _set_tracing_elev_mode(self, mode: str):
        from ...services.settings_service import SettingsService
        SettingsService().set_tracing_elev_mode(mode)
        scene = getattr(self._mw.visualization_panel, "scene_2d", None)
        if scene and hasattr(scene, "set_elevation_mode"):
            scene.set_elevation_mode(mode) 