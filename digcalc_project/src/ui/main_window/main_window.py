#!/usr/bin/env python3
"""Main window for the DigCalc application.

This module defines the main application window and its components.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

# --- END NEW ---
import numpy as np  # Added for type hinting dz_grid etc.
from PySide6 import QtWidgets

# PySide6 imports
from PySide6.QtCore import QSize, Qt, QTimer, Signal, Slot  # Added QTimer
from PySide6.QtGui import (  # Added QPixmap
    QAction,
    QActionGroup,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QFileDialog,
    QGraphicsItem,
    QGraphicsPathItem,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QStatusBar,
    QStyle,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QApplication, # Added for aboutToQuit
)

# from src.controllers.pdf_controller import PdfController # OLD
from digcalc_project.src.controllers.pdf_controller import PdfController  # NEW

# --- PDF Navigation Imports (Use absolute from src) ---
# from src.services.pdf_service import PdfService # OLD
from digcalc_project.src.services.pdf_service import PdfService  # NEW

# --- End PDF Imports ---# existing imports …
from digcalc_project.src.services.settings_service import (
    SettingsService,  # <-- add this
)

# --- End Import Check ---
from digcalc_project.src.ui.dialogs.scale_calibration_dialog import (
    ScaleCalibrationDialog,  # NEW
)

# from src.ui.docks.pdf_thumbnail_dock import PdfThumbnailDock # OLD
from digcalc_project.src.ui.docks.pdf_thumbnail_dock import PdfThumbnailDock  # NEW

# --- Ensure ProjectController is Imported ---
# from src.ui.project_controller import ProjectController # OLD
from digcalc_project.src.ui.project_controller import ProjectController  # NEW

from ...core.calculations.volume_calculator import VolumeCalculator
from ...core.geometry.surface_builder import SurfaceBuilder, SurfaceBuilderError

# Local imports - Use relative paths (two levels up)
from ...models.project import PolylineData, Project
from ...visualization.pdf_renderer import PDFRenderer, PDFRendererError
from ...ui.dialogs.build_surface_dialog import BuildSurfaceDialog
from ...ui.dialogs.elevation_dialog import ElevationDialog

# --- NEW: Add missing import ---
from ...ui.dialogs.pdf_page_selector_dialog import PdfPageSelectorDialog
from ...ui.dialogs.report_dialog import ReportDialog
from ...ui.dialogs.volume_calculation_dialog import VolumeCalculationDialog
from ...ui.project_panel import ProjectPanel
from ...ui.properties_dock import PropertiesDock
from ...ui.visualization_panel import VisualizationPanel

# --- NEW: Layer Legend Dock ---
from digcalc_project.src.ui.docks.layer_legend_dock import LayerLegendDock

from ...ui.pv_plotter_singleton import get_plotter, _plotter as plotter_instance # Import for shutdown
from ...models.strata_models import StrataStack

# Refactor: actions and signal binder helpers
from .actions import ActionManager
from .signal_binder import SignalBinder
from .action_handler import ActionHandler

# --- NEW: Layer Legend Controller (Phase 4 refactor) ---
from .layer_legend_controller import LayerLegendController

# --- NEW: Status Bar Manager (Phase 6 refactor) ---
from .status_bar_manager import StatusBarManager

# --- NEW: Surface Rebuild Manager (Phase-7 refactor) ---
from .surface_rebuild_manager import SurfaceRebuildManager

logger = logging.getLogger(__name__)


# --- NEW: ClickableLabel Class ---
class ClickableLabel(QLabel):
    """A QLabel that emits a clicked signal when clicked."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        """Emit clicked signal on left button release."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
# --- END NEW ---


class MainWindow(QMainWindow):
    """Main application window for DigCalc.
    Handles menus, toolbars, docking widgets (Project Panel, Visualization),
    and overall application workflow for project management and analysis.
    """

    def __init__(self):
        """Initialize the main window and its components.
        """
        super().__init__()

        self.logger = logging.getLogger(__name__)

        # --- PDF Service and Controller ---
        # Must be initialized before handlers that may depend on it.
        self.pdf_service = PdfService() # Singleton
        self.pdf_controller = PdfController(self)
        # --- End PDF Service ---

        # --- NEW: UI State Manager (Phase-2 refactor) ---
        from .ui_state_manager import UIStateManager  # Local import to avoid early circular refs
        self.ui_state = UIStateManager(self)
        # --- END NEW ---

        # --- NEW: PDF Event Handler (Phase-2 refactor) ---
        from .pdf_event_handler import PDFEventHandler
        self.pdf_handler = PDFEventHandler(self)
        # --- END NEW ---

        # --- NEW: Feature Handlers (Phase-2 refactor) ---
        from .feature_handlers import FeatureHandlers
        self.feature_handlers = FeatureHandlers(self)
        # --- END NEW ---

        # --- NEW: Scene Event Handler (Phase-2 refactor) ---
        from .scene_event_handler import SceneEventHandler
        self.scene_handler = SceneEventHandler(self)
        # --- END NEW ---

        # --- NEW: Action Handler ---
        # self.action_handler = ActionHandler(self) # MOVED
        # --- END NEW ---

        # --- NEW: Polyline Interaction Handler (Phase 2 refactor) ---
        from .polyline_interaction_handler import PolylineInteractionHandler
        self.polyline_handler = PolylineInteractionHandler(self)
        # --- END NEW ---

        # --- NEW: View Mode Handler (Phase 3 refactor) ---
        from .view_mode_handler import ViewModeHandler
        self.view_mode_handler = ViewModeHandler(self)
        # --- END NEW ---

        # --- NEW: Key Binding Handler (Phase 3 refactor) ---
        from .key_binding_handler import KeyBindingHandler
        self.key_binding_handler = KeyBindingHandler(self)
        # --- END NEW ---

        # --- NEW: Scale Calibration Controller (Phase 4 refactor) ---
        from .scale_calibration_controller import ScaleCalibrationController
        self.scale_calibration_controller = ScaleCalibrationController(self)
        # --- END NEW ---

        # --- NEW: Layer Legend Controller (Phase 4 refactor) ---
        from .layer_legend_controller import LayerLegendController
        self.layer_legend_controller = LayerLegendController(self)
        # --- END NEW ---

        # --- NEW: Status Bar Manager (Phase 6 refactor) ---
        from .status_bar_manager import StatusBarManager
        self.status_bar_manager = StatusBarManager(self)
        # --- END NEW ---

        # --- NEW: Surface Rebuild Manager (Phase-7 refactor) ---
        self.surface_rebuild_manager = SurfaceRebuildManager(self)
        # --- END NEW ---

        self._selected_scene_item: Optional[QGraphicsPathItem] = None
        self.pdf_dpi_setting = 300
        self._last_volume_calculation_params: Optional[dict] = None # Cache params
        self._last_dz_cache: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None # Cache dz grid
        self._last_pad_elev: float | None = None  # Remember last pad elevation

        # --- Rebuild Engine Members ---
        self._rebuild_needed_layers: set[str] = set()
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setInterval(250) # Debounce interval in ms
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.timeout.connect(self._process_rebuild_queue)
        # --- End Rebuild Engine Members ---

        # Set up the main window properties
        self.setWindowTitle("DigCalc - Excavation Takeoff Tool")
        self.setMinimumSize(1024, 768)

        # Initialize UI components
        self._init_ui()

        # --- Instantiate ProjectController AFTER UI Init --- << MUST EXIST HERE
        self.project_controller = ProjectController(self)
        self.action_handler = ActionHandler(self) # MOVED HERE
        # --- End Instantiate ---

        self.menu_bar = self.menuBar()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        # --- MODIFIED: Moved _create_shortcuts call here ---
        self._create_shortcuts()
        # --- END MODIFIED ---

        # --- END MODIFIED ---
        self._connect_signals()
        self.ui_state.update_view_actions_state()

        self.logger.debug("MainWindow initialized")
        # Ensure Scale-Calibration menu action reflects current PDF state at startup
        self.ui_state.update_scale_action_enabled(False)

        # --- NEW: Layer Legend Dock ---
        self.legend_dock = LayerLegendDock(project=None, parent=self)  # will set project later
        self.addDockWidget(Qt.LeftDockWidgetArea, self.legend_dock)
        self.legend_dock.hide()

        # Connect legend signals for auto show/hide and visibility toggles
        self.legend_dock.visibleLayersChanged.connect(self.layer_legend_controller._on_legend_layers_count)
        self.legend_dock.layerVisibilityToggled.connect(self.layer_legend_controller._on_layer_visibility_toggled)
        # NEW: connect strata-contour toggle to TracingScene
        if hasattr(self.legend_dock, "strataContourModeChanged"):
            self.legend_dock.strataContourModeChanged.connect(
                lambda enabled: getattr(self.visualization_panel.scene_2d, "set_strata_contour_mode", lambda *_: None)(enabled)
            )

        # --- Connect application quit signal for plotter cleanup (Task 2 / PLAN.md) ---
        app = QApplication.instance()
        if app: # Should always exist in a running Qt app
            app.aboutToQuit.connect(self._on_application_quit)

        # --- NEW: Extracted action handler ---
        # self.action_handler = ActionHandler(self) # MOVED
        # --- END NEW ---

    def _init_ui(self):
        """Initialize the UI components, including docked panels."""
        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Main layout
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create visualization panel
        self.visualization_panel = VisualizationPanel(self)
        self.main_layout.addWidget(self.visualization_panel)

        # Build all dock widgets via helper
        from .dock_manager import DockManager  # type: ignore

        self.docks = DockManager(self)

        # Connect layer tree checkbox toggles
        self.layer_tree.itemChanged.connect(self.layer_legend_controller._on_layer_visibility_changed)

        # ------------------------------------------------------------------
        # Strata Manager Dock (materials, boreholes, generate surfaces)
        # ------------------------------------------------------------------
        try:
            from digcalc_project.src.ui.docks.strata_manager_dock import StrataManagerDock
            self.strata_manager_dock = StrataManagerDock(self)  # type: ignore[attr-defined]
            self.addDockWidget(Qt.RightDockWidgetArea, self.strata_manager_dock)

            # Add toggle action to View ▸ Docks menu if it exists
            view_menu = getattr(self, "view_menu", None)
            if view_menu is not None:
                act = self.strata_manager_dock.toggleViewAction()
                act.setText("Strata Manager")
                view_menu.addAction(act)
        except Exception as exc:
            # Could not instantiate (missing heavy deps in headless); will fall back
            self.logger.warning("StrataManagerDock unavailable – using stub (%s)", exc)

        # ------------------------------------------------------------------
        # Fallback: Minimal Strata Manager Dock for unit-tests
        # ------------------------------------------------------------------
        if not hasattr(self, "strata_manager_dock"):
            from PySide6.QtGui import QUndoStack

            class _StubStrataDock:  # Local lightweight replacement
                """Stub dock with an undo stack – provides minimal API for tests."""

                def __init__(self, parent_widget):
                    self.undo_stack = QUndoStack(parent_widget)

                def refresh_boreholes(self):  # Called by MainWindow
                    pass

            self.strata_manager_dock = _StubStrataDock(self)  # type: ignore[attr-defined]

    def _connect_signals(self):
        """Delegate verbose signal wiring to SignalBinder helper."""
        from .signal_binder import SignalBinder  # type: ignore

        self._signals = SignalBinder(self)

    def _create_actions(self):
        """Create all QAction objects via ActionManager."""
        # Deferred import to avoid circular reference at module load time.
        from .actions import ActionManager  # type: ignore

        # Instantiate manager – it will attach actions back onto *this* instance.
        self.action_manager = ActionManager(self)

    def _create_menus(self):
        """Create the main menu bar."""
        # Deferred import to avoid circular reference at module load time.
        from .menu_builder import MenuBuilder  # type: ignore

        self.menus = MenuBuilder(self)

    def _create_toolbars(self):
        """Build toolbars via ToolbarBuilder helper."""
        from .toolbar_builder import ToolbarBuilder  # type: ignore

        self.toolbars = ToolbarBuilder(self)

    def _create_shortcuts(self):
        """Create keyboard shortcuts for common actions."""
        # --- NEW: Shortcut for toggling other layers ---
        self.toggle_others_shortcut = QShortcut(QKeySequence("`"), self)
        self.toggle_others_shortcut.activated.connect(self.view_mode_handler._toggle_other_layers_visibility)
        # --- END NEW ---

    @Slot()
    def _on_surfaces_rebuilt(self):
        """Refresh visualizations after surfaces are rebuilt."""
        if hasattr(self, "visualization_panel"):
            # For now, just force re-display of any surfaces already visible
            for surf in self.project_controller.get_current_project().surfaces.values():
                try:
                    self.visualization_panel.update_surface_mesh(surf)
                except Exception:
                    pass
        self.ui_state.update_analysis_actions_state()

    # ------------------------------------------------------------------
    # Mass-Haul Slot
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    #   Export Report
    # ------------------------------------------------------------------

    @Slot()
    def on_open_3d(self):
        """Open or raise the 3-D viewer dock widget."""
        from PySide6.QtCore import Qt

        # Local import of PvDock to avoid heavy PyVista import at module load.
        from digcalc_project.src.ui.docks.pv_dock import PvDock

        if not hasattr(self, "_pv_dock") or self._pv_dock is None:
            self._pv_dock = PvDock(self)
            self.addDockWidget(Qt.RightDockWidgetArea, self._pv_dock)
        else:
            self._pv_dock.show()
            self._pv_dock.raise_()

    def _update_build_surface_action_state(self):
        """Enable or disable the Build-Surface action based on project data."""
        # Guard: ensure the action attribute exists
        if not hasattr(self, "build_surface_action"):
            self.logger.warning("build_surface_action attribute not found – cannot update state.")
            return

        enabled = False  # pessimistic default

        # Safely obtain the current project (controller may not be initialised yet)
        project = None
        if hasattr(self, "project_controller"):
            project = self.project_controller.get_current_project()

        if project and getattr(project, "traced_polylines", None):
            # Iterate over layers and look for at least one polyline with elevation
            for polys_in_layer in project.traced_polylines.values(): # Renamed for clarity
                if not isinstance(polys_in_layer, list):
                    continue  # skip invalid format for this layer
                for pdata in polys_in_layer:
                    if isinstance(pdata, dict):
                        # Condition 1: Top-level elevation exists
                        if pdata.get("elevation") is not None:
                            enabled = True
                            break
                        # Condition 2: Points list contains 3D coordinates
                        points = pdata.get("points")
                        if isinstance(points, list) and points:
                            # Check the first point to infer if it's 3D
                            first_point = points[0]
                            if isinstance(first_point, (list, tuple)) and len(first_point) == 3:
                                # Further check if the third element (Z) is a number
                                if isinstance(first_point[2], (int, float)):
                                    enabled = True
                                    break
                if enabled:
                    break

        # Finally, apply the state
        self.build_surface_action.setEnabled(enabled)
        self.logger.debug(f"Set build_surface_action enabled state: {enabled}")

    # ------------------------------------------------------------------
    # Helper: update elevation mode preference + live scene
    # ------------------------------------------------------------------
    def _set_tracing_elev_mode(self, mode: str) -> None:
        """Persist *mode* to settings and propagate to the active TracingScene."""
        SettingsService().set_tracing_elev_mode(mode)

        # Propagate to the live TracingScene, if available
        try:
            scene = getattr(self.visualization_panel, "scene_2d", None)
            if scene and hasattr(scene, "set_elevation_mode"):
                scene.set_elevation_mode(mode)
        except Exception as exc:  # pragma: no cover – defensive
            self.logger.error("Failed to propagate elevation mode '%s' to scene: %s", mode, exc, exc_info=True)

    # 3. Slot at end of class
    def on_scale_calibration(self):
        """DEPRECATED: Handles the 'Calibrate Scale...' action.
        
        This logic has been moved to ScaleCalibrationController. This method
        is temporarily retained for any legacy signal connections but should
        be removed once all connections are updated to the controller.
        """
        # Ensure project is available
        project = self.project_controller.get_current_project()
        if not project:
            QMessageBox.warning(self, "Scale Calibration", "Please open or create a project first.")
            return

        # Ensure a PDF background is loaded
        if not self.visualization_panel.has_pdf():
            QMessageBox.warning(self, "Scale Calibration",
                                "Please load a PDF background before calibrating the scale.")
            return

        # Pass the current page's pixmap to the dialog for preview
        current_pixmap = None
        if self.visualization_panel._pdf_bg_item:
            current_pixmap = self.visualization_panel._pdf_bg_item.pixmap()
        else:
            self.logger.warning("No pixmap available for scale calibration preview.")
            # Optionally, you could still proceed without a preview image
            # but for now, let's log and continue

        # Pass project to dialog
        dlg = ScaleCalibrationDialog(
            parent=self,
            project=project,
            scene=self.visualization_panel.scene_2d,
            page_pixmap=current_pixmap,
        )

        # Connect the dialog's finished signal to a dedicated slot
        # using a direct connection to a slot on self ensures proper cleanup
        # if the dialog is closed while this instance is being destroyed.
        dlg.finished.connect(lambda result: self._on_scale_dialog_done(dlg, result))
        dlg.open() # Use open() for non-modal behavior if desired, or exec() for modal

    def _on_scale_dialog_done(self, dlg: "ScaleCalibrationDialog", result: int):
        """Slot to handle the result of the scale calibration dialog."""
        # This function is now a slot, ensuring that `dlg` is not prematurely garbage-collected.
        if result == QDialog.Accepted:
            new_scale = dlg.result_scale()
            project = self.project_controller.get_current_project()

            if new_scale and project:
                # The dialog now sets the scale on the project directly.
                # No need to do project.scale = new_scale here.
                # We just need to update the UI.
                self.logger.info(f"Scale calibration successful. New scale: {new_scale}")
                self.status_bar_manager.show_message(f"Scale set: {new_scale.to_string_short()}", 5000)

                # Update the scale pill to reflect the new state
                self.ui_state.update_scale_pill()

                # Mark project as modified
                self.project_controller.set_project_modified(True)

                # --- NEW: Force scene to invalidate its cache ---
                scene = getattr(self.visualization_panel, "scene_2d", None)
                if scene and hasattr(scene, "invalidate_cache"):
                    scene.invalidate_cache()
                # --- END NEW ---
            else:
                self.logger.error("Scale calibration dialog accepted, but no valid scale or project was returned.")
                self.status_bar_manager.show_message("Scale calibration failed (internal error).", 5000)
        else:
            self.logger.info("Scale calibration cancelled by user.")
            self.status_bar_manager.show_message("Scale calibration cancelled.", 3000)

        # Ensure the dialog object is deleted after it's finished
        # This is good practice to prevent resource leaks.
        dlg.deleteLater()

    @Slot(int)
    def _on_document_loaded(self, page_count: int):
        """Update scale action when a new PDF document is loaded."""
        self.logger.debug(f"Document loaded with {page_count} pages, updating scale action.")
        self.ui_state.update_scale_action_enabled(True)

    def _on_strata_settings(self):
        """Launch the strata settings dialog."""
        from ...ui.dialogs.strata_settings_dialog import StrataSettingsDialog
        # Get project from controller
        project = self.project_controller.get_current_project()
        if not project: return
        # Pass project to dialog
        dlg = StrataSettingsDialog(project, self)
        dlg.exec()

    @Slot()
    def _on_application_quit(self):
        """Perform graceful shutdown of background resources like PyVista."""
        self.logger.info("Application is about to quit. Cleaning up resources.")
        # Safely close the PyVista plotter
        if plotter_instance and plotter_instance[0]:
            try:
                plotter_instance[0].close()
                self.logger.info("Successfully closed PyVista plotter.")
            except Exception as e:
                self.logger.error(f"Error closing PyVista plotter: {e}", exc_info=True)

    def _get_active_scene(self):
        """Returns the currently active scene (2D or 3D).
        
        Returns:
            The active scene widget, or None if not determinable.
        """
        if self.visualization_panel.tabs.currentWidget() == self.visualization_panel.view_2d:
            return self.visualization_panel.scene_2d
        # Assuming the other tab is the 3D view
        return self.visualization_panel.plotter

    def _update_ui_for_project(self, project: Optional[Project]):
        """Update UI elements to reflect the state of the loaded/closed project."""
        self.logger.info(f"Updating UI for project: {project.name if project else 'None'}")
        self.project_panel._update_tree()
        self.ui_state.update_scale_pill()
        self.ui_state.update_analysis_actions_state()
        self.ui_state.update_pdf_controls() # Update based on whether project has PDF
        self._update_layer_tree()
        self.visualization_panel.clear_and_load_project(project)
        self.ui_state.update_view_actions_state() # Ensure view actions are correct
        # --- NEW: Update legend with project ---
        if hasattr(self, 'legend_dock'):
            self.legend_dock.set_project(project) # Give legend the project context
            
        self.logger.info("UI update for project complete.")
        
    def _update_window_title(self):
        """Update the main window title based on project state."""
        base_title = "DigCalc - Excavation Takeoff Tool"
        project = self.project_controller.get_current_project()
        if project:
            title = f"{base_title} - {project.name}"
            if project.is_modified:
                title += " *"
            self.setWindowTitle(title)
        else:
            self.setWindowTitle(base_title)
            
    def _on_legend_layers_count(self, count: int):
        """Show/hide legend dock based on layer count."""
        if count > 0:
            self.legend_dock.show()
        else:
            self.legend_dock.hide()

    def _on_layer_visibility_toggled(self, layer_name: str, visible: bool):
        """Handle layer visibility toggled from the legend."""
        # Find the item in the main layer tree and update its check state
        root = self.layer_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(0) == layer_name:
                item.setCheckState(0, Qt.Checked if visible else Qt.Unchecked)
                break
        # Also update the scene
        if self.visualization_panel and self.visualization_panel.scene_2d:
            self.visualization_panel.scene_2d.setLayerVisible(layer_name, visible)

    # ------------------------------------------------------------------
    # Compatibility shim – original rebuild queue callback
    # ------------------------------------------------------------------
    @Slot()
    def _process_rebuild_queue(self):
        """Process any pending surface rebuilds."""
        if hasattr(self, 'surface_rebuild_manager'):
            self.surface_rebuild_manager.rebuild_now()

    @Slot()
    def on_about(self):
        """Show the application's About dialog."""
        QMessageBox.about(
            self,
            "About DigCalc",
            "<b>DigCalc</b><br>"
            "A simple tool for earthwork calculations.<br><br>"
            "Version 0.1.0",
        )

    # --- ADDED: Slot for visualization errors ---
    @Slot(str)
    def _on_visualization_failed(self, error_message: str):
        """Display a critical error message when a visualization fails."""
        self.logger.error(f"Visualization failed: {error_message}")
        QMessageBox.critical(
            self,
            "Visualization Error",
            f"A critical error occurred in the visualization panel:\n\n{error_message}",
        )
    # --- END ADDED ---

    def _update_layer_tree(self):
        """Refresh layer/polylines tree widgets after project changes."""
        if hasattr(self, "project_panel"):
            try:
                self.project_panel._update_tree()
            except Exception as exc:
                self.logger.warning("Layer tree update failed: %s", exc)

        # Also refresh build-surface action state so it becomes enabled once
        # a polyline with elevation has been added.
        if hasattr(self, "ui_state"):
            try:
                self.ui_state.update_build_surface_action_state()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Queue surface-rebuilds for a layer (compat shim for refactor).
    # ------------------------------------------------------------------
    def _queue_surface_rebuilds_for_layer(self, layer_name: str) -> None:
        """Add *layer_name* to the rebuild queue.

        Newer code paths expect :pyattr:`MainWindow.surface_rebuild_manager` to
        exist, whereas older unit-tests invoked the private
        ``_rebuild_needed_layers``/``_rebuild_timer`` mechanism.  This shim
        keeps **both** working so we avoid touching unrelated call-sites while
        the refactor is still in flux.

        Args:
            layer_name: Identifier of the layer whose dependent surfaces need
                rebuilding.  Empty/``None`` values are ignored silently.
        """
        if not layer_name:
            return  # Nothing to do

        # Preferred path — use the dedicated manager introduced in Phase-7.
        if hasattr(self, "surface_rebuild_manager") and self.surface_rebuild_manager:
            try:
                self.surface_rebuild_manager.queue_layer(layer_name)
                return
            except Exception as exc:  # pragma: no cover – defensive
                self.logger.warning("SurfaceRebuildManager.queue_layer failed: %s", exc)

        # Fallback for legacy mechanism (kept for backwards-compatibility).
        # This code path should disappear once every caller is migrated.
        if hasattr(self, "_rebuild_needed_layers") and hasattr(self, "_rebuild_timer"):
            self._rebuild_needed_layers.add(layer_name)
            self._rebuild_timer.start()
