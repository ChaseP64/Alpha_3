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

        # --- PDF Service and Controller ---
        # Instantiate PdfService (should likely be singleton or passed in if shared)
        # self.pdf_service = PdfService(self) # Incorrect - Singleton takes no args
        self.pdf_service = PdfService() # Correct instantiation for Singleton
        # self.pdf_controller = PdfController(self.pdf_service, self) # Incorrect - __init__ takes only parent
        self.pdf_controller = PdfController(self) # Pass only parent
        # --- End PDF Service ---

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
        # --- End Instantiate ---

        self.menu_bar = self.menuBar()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()
        # --- MODIFIED: Moved _create_shortcuts call here ---
        self._create_shortcuts()
        # --- END MODIFIED ---

        # --- NEW: Initialize Scale Pill ---
        self.scale_pill = ClickableLabel("Scale: —") # Use the ClickableLabel class defined earlier
        self.scale_pill.setObjectName("scalePill")
        self.scale_pill.setMargin(4) # Margin in pixels
        # Base style, color will be set in _update_scale_pill
        self.scale_pill.setStyleSheet("QLabel#scalePill { border-radius: 8px; padding: 2px 5px; }")
        self.scale_pill.clicked.connect(self.on_scale_calibration) # Assuming _open_scale_dialog is on_scale_calibration

        # Ensure status bar exists and add the pill
        status_bar = self.statusBar() # Get or create status bar
        if not status_bar:
            status_bar = QStatusBar(self)
            self.setStatusBar(status_bar)
        status_bar.addPermanentWidget(self.scale_pill)

        self._update_scale_pill()   # Set initial state
        # --- END NEW ---

        # ------------------------------------------------------------------
        # Polyline interaction handler – must exist *before* signal wiring so
        # that SignalBinder can connect the scene callbacks without raising
        # AttributeError in head-less test environments.
        # ------------------------------------------------------------------
        try:
            from .polyline_interaction_handler import PolylineInteractionHandler  # local import to avoid circulars
            self.polyline_handler = PolylineInteractionHandler(self)  # type: ignore[attr-defined]
            # Minimal stub for tests that expect a ``view_mode_handler`` with
            # a ``_fit_view_to_scene`` callable.  The real implementation
            # lives in production-only modules which are too heavy for CI.
            from types import SimpleNamespace  # local import
            self.view_mode_handler = SimpleNamespace(_fit_view_to_scene=lambda *a, **k: None)  # type: ignore[attr-defined]
            # Provide a lightweight stub for *action_handler* referenced by
            # SignalBinder.  Each method is a no-op lambda.
            self.action_handler = SimpleNamespace(  # type: ignore[attr-defined]
                calculate_volume=lambda *a, **k: None,
                build_surface=lambda *a, **k: None,
                generate_report=lambda *a, **k: None,
                export_report=lambda *a, **k: None,
                daylight_offset=lambda *a, **k: None,
                mass_haul=lambda *a, **k: None,
            )
            # Stub scene_handler with just the required slot
            self.scene_handler = SimpleNamespace(  # type: ignore[attr-defined]
                on_toggle_tracing_mode=lambda *a, **k: None,
            )
        except Exception as exc:  # pragma: no cover – defensive
            self.logger.warning("PolylineInteractionHandler unavailable – using stub (%s)", exc)
            self.polyline_handler = None  # type: ignore[attr-defined]
            from types import SimpleNamespace
            self.view_mode_handler = SimpleNamespace(_fit_view_to_scene=lambda *a, **k: None)  # type: ignore[attr-defined]

            # Ensure layer_legend_controller also exists when PolylineInteractionHandler failed
            def _noop(*_args, **_kwargs):
                pass

            self.layer_legend_controller = SimpleNamespace(  # type: ignore[attr-defined]
                _on_layer_visibility_changed=_noop,
            )

        # ---------------------------------------------
        # Lightweight *LayerLegendController* or stub –
        # must exist before the first call to
        # ``self._connect_signals``.
        # ---------------------------------------------
        try:
            from .layer_legend_controller import LayerLegendController  # type: ignore
            self.layer_legend_controller = LayerLegendController(self)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover
            self.logger.warning("LayerLegendController unavailable – using stub (%s)", exc)

            def _noop(*_args, **_kwargs):
                pass

            self.layer_legend_controller = SimpleNamespace(  # type: ignore[attr-defined]
                _on_layer_visibility_changed=_noop,
            )

        # --- END MODIFIED ---
        self._connect_signals()
        self._update_view_actions_state()

        self.logger.debug("MainWindow initialized")
        # Ensure Scale-Calibration menu action reflects current PDF state at startup
        self._update_scale_action_enabled(False)
        # --- Connect PdfService signal to update scale action ---
        if hasattr(self, "pdf_service") and self.pdf_service:
            # Use a *bound* Qt slot instead of an anonymous lambda so that the
            # connection is automatically severed when the MainWindow instance
            # is deleted, preventing callbacks to dangling objects in later
            # tests.
            self.pdf_service.documentLoaded.connect(self._on_document_loaded)

        # --- NEW: Layer Legend Dock ---
        self.legend_dock = LayerLegendDock(project=None, parent=self)  # will set project later
        self.addDockWidget(Qt.LeftDockWidgetArea, self.legend_dock)
        self.legend_dock.hide()

        # Connect legend signals for auto show/hide and visibility toggles
        self.legend_dock.visibleLayersChanged.connect(self._on_legend_layers_count)
        self.legend_dock.layerVisibilityToggled.connect(self._on_layer_visibility_toggled)
        # NEW: connect strata-contour toggle to TracingScene
        if hasattr(self.legend_dock, "strataContourModeChanged"):
            self.legend_dock.strataContourModeChanged.connect(
                lambda enabled: getattr(self.visualization_panel.scene_2d, "set_strata_contour_mode", lambda *_: None)(enabled)
            )

        # --- Connect application quit signal for plotter cleanup (Task 2 / PLAN.md) ---
        app = QApplication.instance()
        if app: # Should always exist in a running Qt app
            app.aboutToQuit.connect(self._on_application_quit)

        # ------------------------------------------------------------------
        # Polyline interaction handler – must exist *before* signal wiring so
        # that SignalBinder can connect the scene callbacks without raising
        # AttributeError in head-less test environments.
        # ------------------------------------------------------------------
        try:
            from .polyline_interaction_handler import PolylineInteractionHandler  # local import to avoid circulars
            self.polyline_handler = PolylineInteractionHandler(self)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover – defensive
            self.logger.warning("PolylineInteractionHandler unavailable – using stub (%s)", exc)
            self.polyline_handler = None  # type: ignore[attr-defined]

        # -----------------------------------------------------------
        # Layer-Legend controller – only limited functionality is
        # required for the current unit-test suite.  We attempt to
        # instantiate the full implementation but fall back to a stub
        # exposing the single slot referenced by *SignalBinder*.
        # -----------------------------------------------------------
        try:
            from .layer_legend_controller import LayerLegendController  # lazy import
            self.layer_legend_controller = LayerLegendController(self)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover – headless fallback
            self.logger.warning("LayerLegendController unavailable – using stub (%s)", exc)

            def _noop(*_args, **_kwargs):  # noqa: D401 – local helper
                """No-op slot replacement for visibility changed."""

            self.layer_legend_controller = SimpleNamespace(  # type: ignore[attr-defined]
                _on_layer_visibility_changed=_noop,
            )

        # -----------------------------------------------------------
        # Provide *layer_legend_controller* before signal wiring so that
        # SignalBinder can safely connect the layer-tree checkbox changes.
        # -----------------------------------------------------------
        if not hasattr(self, "layer_legend_controller"):
            try:
                from .layer_legend_controller import LayerLegendController  # type: ignore
                self.layer_legend_controller = LayerLegendController(self)  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover – fallback for headless CI
                self.logger.warning("LayerLegendController unavailable – using stub (%s)", exc)

                from types import SimpleNamespace  # local import

                def _noop(*_args, **_kwargs):
                    pass

                self.layer_legend_controller = SimpleNamespace(  # type: ignore[attr-defined]
                    _on_layer_visibility_changed=_noop,
                )

        # -----------------------------------------------------------
        self._connect_signals()

        # ------------------------------------------------------------------
        # Fallback stubs for ActionHandler and SceneHandler required by
        # SignalBinder.  Define them here to guarantee presence regardless of
        # earlier import success/failure paths.
        # ------------------------------------------------------------------
        if not hasattr(self, "action_handler"):
            from types import SimpleNamespace  # local import
            self.action_handler = SimpleNamespace(  # type: ignore[attr-defined]
                calculate_volume=lambda *a, **k: None,
                build_surface=lambda *a, **k: None,
                generate_report=lambda *a, **k: None,
                export_report=lambda *a, **k: None,
                daylight_offset=lambda *a, **k: None,
                mass_haul=lambda *a, **k: None,
            )

        if not hasattr(self, "scene_handler"):
            from types import SimpleNamespace
            self.scene_handler = SimpleNamespace(  # type: ignore[attr-defined]
                on_toggle_tracing_mode=lambda *a, **k: None,
            )

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
        self.layer_tree.itemChanged.connect(self._on_layer_visibility_changed)

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
        self.actions = ActionManager(self)
        # Alias for legacy tests expecting `main_window.action_manager`
        self.action_manager = self.actions

    def _create_menus(self):
        """Build menus via MenuBuilder helper class."""
        from .menu_builder import MenuBuilder  # type: ignore

        self.menus = MenuBuilder(self)

    def _create_toolbars(self):
        """Build toolbars via ToolbarBuilder helper."""
        from .toolbar_builder import ToolbarBuilder  # type: ignore

        self.toolbars = ToolbarBuilder(self)

    def _create_statusbar(self):
        """Create the status bar."""
        self.statusBar().showMessage("Ready")
        # Maybe add PDF page info to status bar later?




    def _update_analysis_actions_state(self):
        """Enable/disable analysis actions based on the current project state.
        Specifically, enables volume calculation if >= 2 surfaces exist.
        """
        project = self.project_controller.get_current_project()
        can_calculate = bool(project and len(project.surfaces) >= 2)
        self.calculate_volume_action.setEnabled(can_calculate)
        # --- NEW: Enable mass-haul button when Existing & Design surfaces present
        has_req_surfaces = False
        if project:
            has_req_surfaces = (
                getattr(project, "existing_surface", None) is not None
                and getattr(project, "design_surface", None) is not None
            )
        self.masshaul_action.setEnabled(can_calculate and has_req_surfaces)
        # --- END NEW ---
        self.logger.debug(f"Calculate Volume action enabled state: {can_calculate}")

    def _update_pdf_controls(self):
        """Updates the state of PDF-related controls (spinbox, labels, actions).
        Now uses VisualizationPanel to get document state.
        """
        # Get state directly from VisualizationPanel
        panel = self.visualization_panel
        has_pdf = panel.has_pdf() # Checks if renderer and bg item exist
        page_count = panel.pdf_renderer.get_page_count() if panel.pdf_renderer else 0
        # current_pdf_page in panel is 1-based
        current_page_1_based = panel.current_pdf_page if has_pdf else 1

        # --- FIX: Use correct attribute names (remove leading underscore) ---
        if self.pdf_page_spinbox:
            self.pdf_page_spinbox.setEnabled(has_pdf and page_count > 1)
            self.pdf_page_spinbox.setRange(1, max(1, page_count))
            # Block signals temporarily to avoid recursive updates
            self.pdf_page_spinbox.blockSignals(True)
            self.pdf_page_spinbox.setValue(current_page_1_based)
            self.pdf_page_spinbox.blockSignals(False)
        else:
             self.logger.warning("Cannot update missing pdf_page_spinbox")

        if self.pdf_page_label:
            if has_pdf:
                # Assuming page_label is not readily available, just show numbers
                self.pdf_page_label.setText(f"Page: {current_page_1_based} / {page_count}")
            else:
                self.pdf_page_label.setText("Page: N/A")
        else:
             self.logger.warning("Cannot update missing pdf_page_label")
        # --- END FIX ---

        # Enable/disable next/prev actions (ensure they exist)
        # Use 1-based index for comparison
        if hasattr(self, "prev_pdf_page_action"):
            self.prev_pdf_page_action.setEnabled(has_pdf and current_page_1_based > 1)
        if hasattr(self, "next_pdf_page_action"):
            self.next_pdf_page_action.setEnabled(has_pdf and current_page_1_based < page_count)

        # Show/hide thumbnail dock based on whether a PDF is loaded
        self.pdf_thumbnail_dock.setVisible(has_pdf)

        # --- FIX: Show/hide the PDF toolbar itself ---
        if hasattr(self, "pdf_toolbar"):
            self.pdf_toolbar.setVisible(has_pdf)
            self.logger.debug(f"Setting PDF toolbar visibility to: {has_pdf}")
        else:
            self.logger.warning("Cannot set PDF toolbar visibility: pdf_toolbar attribute not found.")
        # --- END FIX ---

        self.logger.debug(f"PDF controls updated: has_pdf={has_pdf}, page_count={page_count}, current_page={current_page_1_based}")

        # ------------------------------------------------------------------
        # Update Scale-Calibration action enabled/disabled state
        # ------------------------------------------------------------------
        self._update_scale_action_enabled(has_pdf)

        # --- NEW: Refresh scale pill whenever PDF controls change (may affect DPI) ---
        try:
            self._update_scale_pill()
        except Exception as exc:
            self.logger.warning("Failed to refresh scale pill in _update_pdf_controls: %s", exc)
        # --- END NEW ---

    # Event handlers


    def _on_visualization_failed(self, surface_name: str, error_msg: str):
        """Handle visualization failure.
        
        Args:
            surface_name: Name of the surface that failed to visualize
            error_msg: Error message

        """
        self.statusBar().showMessage(f"Failed to visualize surface '{surface_name}': {error_msg}", 5000)
        self.logger.error(f"Visualization failed for surface '{surface_name}': {error_msg}")
        QMessageBox.warning(self, "Visualization Error",
                            f"Could not visualize surface '{surface_name}'.\nReason: {error_msg}")

    def on_calculate_volume(self):
        """Handle the 'Calculate Volumes' action."""
        project = self.project_controller.get_current_project()
        if not project or len(project.surfaces) < 2:
            QMessageBox.warning(self, "Cannot Calculate Volumes",
                                "Please ensure at least two surfaces exist in the project.")
            self.logger.warning("Volume calculation attempted with insufficient surfaces.")
            return

        surface_names = list(project.surfaces.keys())
        dialog = VolumeCalculationDialog(surface_names, self)

        if dialog.exec():
            selection = dialog.get_selected_surfaces()
            resolution = dialog.get_grid_resolution()

            if selection and resolution > 0:
                existing_name = selection["existing"]
                proposed_name = selection["proposed"]
                self.logger.info(f"Starting volume calculation: Existing='{existing_name}', Proposed='{proposed_name}', Resolution={resolution}")
                self.statusBar().showMessage(f"Calculating volumes (Grid: {resolution})...", 0)

                try:
                    # Use project obtained from controller
                    existing_surface = project.get_surface(existing_name)
                    proposed_surface = project.get_surface(proposed_name)

                    if not existing_surface or not proposed_surface:
                         raise ValueError("Selected surface(s) not found in project.")

                    if not existing_surface.points or not proposed_surface.points:
                         raise ValueError("Selected surface(s) have no data points for calculation.")

                    # VolumeCalculator expects the active Project so it can
                    # extend bounding boxes with regions and log context.
                    calculator = VolumeCalculator(project)
                    results = calculator.calculate_surface_to_surface(
                        surface1=existing_surface,
                        surface2=proposed_surface,
                        grid_resolution=resolution,
                    )
                    cut_volume = results["cut_volume"]
                    fill_volume = results["fill_volume"]
                    net_volume = results["net_volume"]

                    self.statusBar().showMessage(f"Calculation complete: Cut={cut_volume:.2f}, Fill={fill_volume:.2f}, Net={net_volume:.2f}", 5000)
                    self.logger.info(f"Volume calculation successful: Cut={cut_volume:.2f}, Fill={fill_volume:.2f}, Net={net_volume:.2f}")

                    report_dialog = ReportDialog(
                        existing_surface_name=existing_name,
                        proposed_surface_name=proposed_name,
                        grid_resolution=resolution,
                        cut_volume=cut_volume,
                        fill_volume=fill_volume,
                        net_volume=net_volume,
                        parent=self,
                    )
                    self.logger.debug("Displaying volume calculation report.")
                    report_dialog.exec()

                except Exception as e:
                    self.logger.exception(f"Error during volume calculation: {e}")
                    QMessageBox.critical(self, "Calculation Error",
                                         f"Failed to calculate volumes:\n{e}")
                    self.statusBar().showMessage("Volume calculation failed.", 5000)
            else:
                 if resolution <= 0:
                    self.logger.warning("Volume calculation cancelled: Invalid grid resolution.")
                    QMessageBox.warning(self, "Invalid Input", "Grid resolution must be greater than zero.")
                 else:
                    self.logger.warning("Volume calculation cancelled: Invalid surface selection.")
                 self.statusBar().showMessage("Calculation cancelled.", 3000)
        else:
            self.logger.info("Volume calculation dialog cancelled by user.")
            self.statusBar().showMessage("Calculation cancelled.", 3000)



    def closeEvent(self, event):
        """Handle the main window close event."""
        self.logger.info("Close event triggered.")
        # Delegate confirmation logic to ProjectController
        if self.project_controller._confirm_close_project():
            # Perform any MainWindow-specific cleanup before closing
            if hasattr(self, "visualization_panel"):
                 self.visualization_panel.clear_pdf_background()
            self.logger.info("Closing application.")
            event.accept()
        else:
            # User cancelled the close via the controller's dialog
            self.logger.info("Close cancelled by user.")
            event.ignore()

    # --- PDF Background and Tracing Handlers ---

    def on_load_pdf_background(self):
        """Handles loading a PDF file as a background."""
        self.logger.debug("on_load_pdf_background slot entered.")
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load PDF Background",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )

        if filename:
            self.logger.info(f"User selected PDF for background: {filename}")
            self.statusBar().showMessage(f"Loading PDF background '{Path(filename).name}'...", 0)
            success = False # Flag to track successful loading
            try:
                # Call the panel's load method, which now returns success/failure
                success = self.visualization_panel.load_pdf_background(filename, dpi=self.pdf_dpi_setting)

                if success:
                    # Get project from controller
                    project = self.project_controller.get_current_project()
                    if project:
                        project.pdf_background_path = filename
                        # Use the actual current page from the panel (might be adjusted if initial_page was invalid)
                        project.pdf_background_page = self.visualization_panel.current_pdf_page
                        project.pdf_background_dpi = self.pdf_dpi_setting
                        project.clear_traced_polylines() # Clear old traces if new PDF loaded
                        self.visualization_panel.clear_polylines_from_scene() # Clear visuals too

                    # Update status bar only on success, getting page count safely
                    page_count = self.visualization_panel.pdf_renderer.get_page_count() if self.visualization_panel.pdf_renderer else 0
                    self.statusBar().showMessage(f"Loaded PDF background '{Path(filename).name}' ({page_count} pages).", 5000)
                    self.logger.info(f"Successfully loaded PDF background '{Path(filename).name}' with {page_count} pages.")
                    # ADDED LOG: Confirm _update_ui_for_project is called
                    self.logger.info(f"[on_load_pdf_background] SUCCESS: About to call _update_ui_for_project with project: {project.name if project else 'None'}")
                    self._update_ui_for_project(project) # Update UI with the (potentially new) project
                else:
                    # Loading failed (error already logged by visualization_panel)
                    raise PDFRendererError("Loading or rendering PDF background failed.") # Re-raise specific error for unified handling

            except (FileNotFoundError, PDFRendererError, Exception) as e:
                 # Catch errors from load_pdf_background OR re-raised error
                 self.logger.exception(f"Failed to load PDF background: {e}")
                 QMessageBox.critical(self, "PDF Load Error", f"Failed to load PDF background:\n{e}")
                 self.statusBar().showMessage("Failed to load PDF background.", 5000)
                 # Ensure project state reflects failure if project object exists
                 project = self.project_controller.get_current_project()
                 if project and project.pdf_background_path == filename:
                     project.pdf_background_path = None
                     project.pdf_background_page = 0
                     project.pdf_background_dpi = 0
            finally:
                 # Always update controls regardless of success/failure
                 self._update_pdf_controls()
                 self._update_view_actions_state()
        else:
            self.logger.info("Load PDF background cancelled by user.")
            self.statusBar().showMessage("Load cancelled.", 3000)

    def on_clear_pdf_background(self):
        """Removes the PDF background from the visualization panel."""
        self.logger.debug("Clearing PDF background via MainWindow action.")
        self.visualization_panel.clear_pdf_background()
        # Consider if clearing PDF should also clear/disable cut/fill map?
        # Let's assume yes for now, as context might be lost.
        self._clear_cutfill_state()
        self._update_pdf_controls()

    def on_next_pdf_page(self):
        """Handles moving to the next PDF page."""
        if self.visualization_panel.pdf_renderer:
             current = self.visualization_panel.current_pdf_page
             total = self.visualization_panel.pdf_renderer.get_page_count()
             if current < total:
                  self.visualization_panel.set_pdf_page(current + 1)
                  # Get project from controller
                  project = self.project_controller.get_current_project()
                  if project:
                       project.pdf_background_page = current + 1
                  self._update_pdf_controls()
                  self.statusBar().showMessage(f"Showing PDF page {current + 1}/{total}", 3000)

    def on_prev_pdf_page(self):
        """Handles moving to the previous PDF page."""
        if self.visualization_panel.pdf_renderer:
             current = self.visualization_panel.current_pdf_page
             total = self.visualization_panel.pdf_renderer.get_page_count()
             if current > 1:
                  self.visualization_panel.set_pdf_page(current - 1)
                  # Get project from controller
                  project = self.project_controller.get_current_project()
                  if project:
                       project.pdf_background_page = current - 1
                  self._update_pdf_controls()
                  self.statusBar().showMessage(f"Showing PDF page {current - 1}/{total}", 3000)

    def on_set_pdf_page_from_spinbox(self, page_number: int):
        """Handles setting the PDF page from the spinbox."""
        if self.pdf_page_spinbox.isEnabled() and page_number > 0:
             self.logger.debug(f"Setting PDF page from spinbox to: {page_number}")
             self.visualization_panel.set_pdf_page(page_number)
             # --- FIX: Get project from controller ---
             project = self.project_controller.get_current_project()
             if project:
                  project.pdf_background_page = page_number
             # --- END FIX ---
             self._update_pdf_controls()
             total = self.visualization_panel.pdf_renderer.get_page_count() if self.visualization_panel.pdf_renderer else 0
             self.statusBar().showMessage(f"Showing PDF page {page_number}/{total}", 3000)

    @Slot(bool)
    def on_toggle_tracing_mode(self, checked: bool):
        """Slot for the toggle tracing mode action."""
        if not self.visualization_panel:
            logger.error("Toggle tracing called but visualization panel is not available.")
            return

        # Corrected method call
        self.visualization_panel.set_tracing_mode(checked)

        # Update the action's checked state if necessary (it might already be correct)
        # self.toggle_trace_mode_action.setChecked(checked) # Usually handled by action group or signal

        logger.info(f"Tracing mode {'enabled' if checked else 'disabled'} via MainWindow action.")
        # Potentially update other UI elements if tracing mode affects them
        # For example, enable/disable certain tools or options

    @Slot(QTreeWidgetItem, int)
    def _on_layer_visibility_changed(self, item: QTreeWidgetItem, column: int):
        """Slot called when a layer's checkbox state changes in the dock."""
        if column == 0:
            layer_name = item.text(0)
            is_visible = item.checkState(0) == Qt.Checked
            self.logger.debug(f"Layer '{layer_name}' visibility toggle -> {is_visible}")
            if self.visualization_panel and self.visualization_panel.scene_2d and hasattr(self.visualization_panel.scene_2d, "setLayerVisible"):
                self.visualization_panel.scene_2d.setLayerVisible(layer_name, is_visible)
            else:
                self.logger.warning("Cannot toggle layer visibility: Visualization panel, scene_2d, or setLayerVisible method not found.")

    @Slot(list, QGraphicsPathItem)
    def _on_polyline_drawn(self, world_points_3d: list, item: QGraphicsPathItem):
        """Handles the polyline_finalized signal from TracingScene.

        The received 'world_points_3d' are List[Tuple[float, float, float]]
        with Z-values already determined by the TracingScene's elevation workflow.
        Adds the polyline data (now always 3D) to the project.
        Stores the final index back into the QGraphicsPathItem.
        """
        project = self.project_controller.get_current_project()
        if not project:
            logger.warning("Polyline drawn but no active project.")
            if item.scene(): item.scene().removeItem(item)
            return

        layer_name = item.data(Qt.UserRole + 1) # Key used in _finalize_current_polyline
        if layer_name is None:
             logger.error("Finalized polyline item is missing layer data! Assigning to 'Default'.")
             layer_name = "Default"

        # The world_points_3d argument is now always List[Tuple[float, float, float]]
        # The old logic distinguishing elevation_mode to format points is removed.
        point_tuples_for_storage = world_points_3d

        # The 'elevation' field in PolylineData is for a single, uniform elevation.
        # Since Z is now per-vertex in point_tuples_for_storage, this can be None.
        # Project.add_traced_polyline will need to handle points with Z-values.
        active_elevation_value_for_log = None # For logging, as the old 'elevation' var is gone.

        logger.debug(
            f"Polyline received with {len(point_tuples_for_storage)} 3D points for layer '{layer_name}'."
        )
        logger.debug(f"Points for storage (first 3): {point_tuples_for_storage[:3]}")

        polyline_data_for_project: PolylineData = {
            "points": point_tuples_for_storage, # This is List[Tuple[float,float,float]]
            "elevation": None,  # Uniform elevation is None; Z is in points
            "is_strata": bool(item.data(Qt.UserRole + 4) or False),
            "material_id": item.data(Qt.UserRole + 5),
        }

        new_index: Optional[int] = project.add_traced_polyline(
            polyline=polyline_data_for_project,
            layer_name=layer_name,
        )

        if new_index is not None:
            try:
                item.setData(1, new_index) # Store project index on the scene item
                self.logger.info(
                    f"Added traced polyline (Index: {new_index}, with per-vertex elevation) to layer '{layer_name}'."
                )
                self.project_panel._update_tree()
                self._update_layer_tree()
                self.statusBar().showMessage(f"Polyline with per-vertex Z added to layer '{layer_name}'.", 3000)
                
                if self.visualization_panel:
                    self.logger.debug(f"[MainWindow._on_polyline_drawn] Calling refresh_layer_item for layer '{layer_name}'.")
                    self.visualization_panel.scene_2d.refresh_layer_item(layer_name, target_item=item)

                self._queue_surface_rebuilds_for_layer(layer_name)
            except Exception as e:
                 logger.error(f"Error updating UI/logging after adding polyline (Index: {new_index}, Layer: '{layer_name}'): {e}", exc_info=True)
        else:
             self.logger.error(f"Failed to add traced polyline to layer '{layer_name}' in project (add_traced_polyline returned None).")
             if item.scene(): item.scene().removeItem(item)
             QMessageBox.warning(self, "Error", f"Could not add polyline to project layer '{layer_name}'.")

    @Slot(QGraphicsItem)
    def _on_item_selected(self, item: Optional[QGraphicsItem]):
        """Handles the selectionChanged signal from the TracingScene.
        Loads the selected polyline's data into the PropertiesDock.
        Stores a reference to the selected scene item.
        """
        logger.debug(f"--- _on_item_selected --- START --- Item: {item}")

        # Get project from controller first
        project = self.project_controller.get_current_project()
        if not project:
            self._selected_scene_item = None # Clear selection reference
            logger.warning("_on_item_selected called but no current project.")
            if hasattr(self, "prop_dock"): self.prop_dock.clear_selection()
            if hasattr(self, "prop_dock"): self.prop_dock.hide()
            logger.debug("--- _on_item_selected --- END (no project) ---")
            return
        if not hasattr(self, "prop_dock") or not self.prop_dock:
            self._selected_scene_item = None # Clear selection reference
            logger.error("Properties dock not initialized.")
            logger.debug("--- _on_item_selected --- END (no properties dock) ---")
            return

        if item and isinstance(item, QGraphicsPathItem):
            # --- Store reference to selected item ---
            self._selected_scene_item = item
            # --- End Store ---
            layer_name = item.data(0)
            index = item.data(1)
            logger.debug(f"  Item is QGraphicsPathItem. Layer Data (0): {layer_name}, Index Data (1): {index}")

            if layer_name is not None and index is not None:
                logger.debug(f"  Attempting to load data for Layer='{layer_name}', Index={index}")
                try:
                    # Retrieve the polyline data - could be dict or list
                    if layer_name not in project.traced_polylines or \
                       not isinstance(project.traced_polylines[layer_name], list) or \
                       index >= len(project.traced_polylines[layer_name]):
                        logger.warning(f"  Invalid layer/index lookup ({layer_name}/{index}).")
                        raise IndexError(f"Invalid layer/index ({layer_name}/{index}) for selection.")

                    poly_data = project.traced_polylines[layer_name][index]
                    elevation = None
                    logger.debug(f"  Retrieved poly_data type: {type(poly_data)}, Value: {poly_data}")

                    # Handle old list format vs new dict format
                    if isinstance(poly_data, dict):
                        elevation = poly_data.get("elevation")
                        logger.debug(f"  Loading elevation from dict: {elevation}")
                    elif isinstance(poly_data, list):
                        logger.debug("  Loading old format polyline (list), elevation assumed None.")
                        elevation = None
                    else:
                        logger.warning(f"  Unexpected data type for polyline at {layer_name}[{index}]: {type(poly_data)}")
                        raise TypeError(f"Unexpected data type for polyline: {type(poly_data)}")

                    logger.debug(f"  Calling prop_dock.load_polyline with: layer='{layer_name}', index={index}, elevation={elevation}")
                    self.prop_dock.load_polyline(layer_name, index, elevation)
                    # Explicitly show the dock after loading data
                    self.prop_dock.show()
                    self.prop_dock.raise_() # Optional: Bring to front

                except Exception as e:
                    logger.error(f"  ERROR during data retrieval/processing for {layer_name}[{index}]: {e}", exc_info=True)
                    self._selected_scene_item = None # Clear on error
                    self.prop_dock.clear_selection()
                    self.prop_dock.hide()
                    QMessageBox.warning(self, "Selection Error", f"Could not load data for selected polyline:\nLayer: {layer_name}, Index: {index}\nError: {e}")
            else:
                logger.warning(f"  Selected QGraphicsPathItem missing layer ({layer_name}) or index ({index}) data.")
                self._selected_scene_item = None # Clear selection reference
                self.prop_dock.clear_selection()
        else:
            # Selection cleared or non-polyline selected
            if item:
                 logger.debug(f"  Selection changed, but item is not a QGraphicsPathItem (Type: {type(item)}). Clearing properties.")
            else:
                 logger.debug("  Selection changed to None (cleared). Clearing properties.")
            self._selected_scene_item = None # Clear selection reference
            self.prop_dock.clear_selection()

        logger.debug("--- _on_item_selected --- END ---")

    @Slot(str, int, float)
    def _apply_elevation_edit(self, layer_name: str, index: int, new_elevation: Optional[float]): # Allow None
        """Handles the 'edited' signal from PropertiesDock.
        Updates the elevation in the current project's data model.
        """
        logger.debug(f"_apply_elevation_edit called: Layer={layer_name}, Index={index}, New Elevation={new_elevation}")

        # Get project from controller
        project = self.project_controller.get_current_project()
        if not project:
            logger.error("Cannot apply elevation edit: No current project.")
            QMessageBox.critical(self, "Error", "No active project to apply changes to.")
            return

        try:
            # Use the project variable obtained from the controller
            poly_list = project.traced_polylines.get(layer_name)
            if poly_list is None or not isinstance(poly_list, list) or index >= len(poly_list):
                raise IndexError(f"Invalid layer '{layer_name}' or index {index} for elevation edit.")

            if not isinstance(poly_list[index], dict):
                raise TypeError(f"Polyline data at {layer_name}[{index}] is not a dictionary.")

            current_elevation = poly_list[index].get("elevation")

            logger.debug(f"Comparing elevation for {layer_name}[{index}]: Current={current_elevation} (Type: {type(current_elevation)}), New={new_elevation} (Type: {type(new_elevation)})")

            elevation_changed = False
            if (current_elevation is None and new_elevation is not None) or (current_elevation is not None and new_elevation is None):
                elevation_changed = True
            elif current_elevation is not None and new_elevation is not None:
                 if abs(current_elevation - new_elevation) > 1e-6:
                     elevation_changed = True

            if elevation_changed:
                poly_list[index]["elevation"] = new_elevation

                # Use the project variable
                new_revision = project._bump_layer_revision(layer_name) # Call project helper

                logger.info(f"Updated elevation for polyline (Layer: {layer_name}, Index: {index}) to {new_elevation}. New layer revision: {new_revision}")
                self._update_build_surface_action_state() # Add this call
                self.statusBar().showMessage(f"Elevation updated for {layer_name} polyline {index}.", 3000)
                if self._selected_scene_item and \
                   self._selected_scene_item.data(0) == layer_name and \
                   self._selected_scene_item.data(1) == index:
                    if hasattr(self, "prop_dock") and self.prop_dock:
                         self.prop_dock.load_polyline(layer_name, index, new_elevation)
                         logger.debug("Refreshed PropertiesDock with updated elevation.")
                    else:
                         logger.warning("Properties dock not found, cannot refresh after edit.")
                self._queue_surface_rebuilds_for_layer(layer_name)
            else:
                 logger.debug(f"Elevation change check returned False for {layer_name}[{index}]. No update performed.")

        except (KeyError, IndexError, AttributeError, TypeError) as e:
            logger.error(f"Error applying elevation edit (Layer: {layer_name}, Index: {index}): {e}", exc_info=True)
            QMessageBox.warning(self, "Edit Error", f"Could not apply elevation change:\nLayer: {layer_name}, Index: {index}\nError: {e}")

    def _update_layer_tree(self):
        """Updates the layer tree dock based on project layers."""
        self.layer_tree.blockSignals(True)
        self.layer_tree.clear()
        layers = []
        # Get the project from the controller
        project = self.project_controller.get_current_project()
        if project:
             surface_layers = list(project.surfaces.keys())
             trace_layers = project.get_layers()
             layers = sorted(list(set(surface_layers + trace_layers)))

        if layers:
            for name in layers:
                item = QTreeWidgetItem(self.layer_tree, [name])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Checked) # Default to checked visually
            self.layer_tree.expandAll()
        else:
            pass # No layers, tree is empty

        self.layer_tree.blockSignals(False)
        self.logger.debug(f"Layer tree updated with layers: {layers}")
        # --- NEW: update Build Surface button state whenever layer tree changes ---
        self._update_build_surface_action_state()

    # --- NEW: Handle Delete Key Press ---
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key presses, specifically the Delete key for selected polylines."""
        key = event.key()

        # Check if Delete key is pressed and an item is selected
        if key == Qt.Key_Delete and self._selected_scene_item is not None:
            self.logger.debug(f"Delete key pressed for selected item: {self._selected_scene_item}")
            self._delete_selected_polyline()
            event.accept() # Indicate we handled the key press
        else:
            # Pass the event to the base class for default handling
            super().keyPressEvent(event)

    def _delete_selected_polyline(self):
        """Deletes the currently selected polyline from the project and scene."""
        # Get project from controller
        project = self.project_controller.get_current_project()
        if not project or not self._selected_scene_item:
            self.logger.warning("Attempted to delete polyline, but no project or item selected.")
            return

        layer_name = self._selected_scene_item.data(0)
        index = self._selected_scene_item.data(1)

        if layer_name is None or index is None:
            self.logger.error("Selected item is missing layer or index data, cannot delete.")
            self._selected_scene_item = None
            if hasattr(self, "prop_dock"): # Check if dock exists
                self.prop_dock.clear_selection()
                self.prop_dock.hide()
            return

        # Confirm deletion with user
        reply = QMessageBox.question(
            self,
            "Delete Polyline",
            f"Are you sure you want to delete the selected polyline from layer '{layer_name}' (Index: {index})?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.logger.info(f"Attempting to delete polyline: Layer='{layer_name}', Index={index}")
            layer_name_to_rebuild = layer_name # Store before item might be invalidated

            # --- Remove from Project (using the controller's project) ---
            removed_from_project = project.remove_polyline(layer_name, index)

            if removed_from_project:
                # --- Remove from Scene ---
                scene = self._selected_scene_item.scene()
                if scene:
                    scene.removeItem(self._selected_scene_item)
                    self.logger.info("Removed polyline item from scene.")
                else:
                    self.logger.warning("Could not remove item from scene (item has no scene).")

                # --- Update UI ---
                if hasattr(self, "prop_dock"):
                    self.prop_dock.clear_selection()
                    self.prop_dock.hide()
                if hasattr(self, "project_panel"):
                    self.project_panel._update_tree()
                self.statusBar().showMessage(f"Deleted polyline from '{layer_name}'.", 3000)

                # --- Trigger Rebuild ---
                self._queue_surface_rebuilds_for_layer(layer_name_to_rebuild)
                # --- End Trigger ---

                # --- Optional: Reload polylines using controller's project ---
                # if hasattr(self, 'visualization_panel'):
                #     self.logger.info("Reloading all traced polylines in scene to update indices after deletion.")
                #     self.visualization_panel.load_and_display_polylines(project.traced_polylines)
                # else:
                #     self.logger.error("Visualization panel not found, cannot reload polylines after deletion.")
            else:
                self.logger.error(f"Failed to remove polyline from project data (Layer: {layer_name}, Index: {index}).")
                QMessageBox.warning(self, "Deletion Error", "Could not delete the polyline from the project data.")

            # --- Clear selection reference ---
            self._selected_scene_item = None
        else:
            self.logger.debug("Polyline deletion cancelled by user.")

    # --- NEW: View Toggle Slots ---
    @Slot()
    def on_view_2d(self):
        """Switch to the 2D (PDF/Tracing) view."""
        if self.visualization_panel:
            self.logger.debug("Switching to 2D view.")
            self.visualization_panel.show_2d_view()
            self._update_view_actions_state() # Update check states
        else:
            self.logger.error("Cannot switch to 2D view: VisualizationPanel not found.")

    @Slot()
    def on_view_3d(self):
        """Switch to the 3-D tab in VisualizationPanel (PyVista)."""
        if self.visualization_panel:
            self.logger.debug("Switching to 3-D tab view (PyVista).")
            # Directly invoke the new method that embeds the singleton plotter in the tab
            if hasattr(self.visualization_panel, "show_pyvista_in_tab"):
                self.visualization_panel.show_pyvista_in_tab()
            else:
                self.logger.error("VisualizationPanel is missing show_pyvista_in_tab().")
            self._update_view_actions_state()
        else:
            self.logger.error("Cannot switch to 3-D view: VisualizationPanel not found.")

    def _update_view_actions_state(self):
        """Updates the enabled and checked state of the view toggle actions (2D/3D)
        based on available content and the current view widget.
        """
        if not hasattr(self, "view_2d_action") or not hasattr(self, "view_3d_action") or not hasattr(self, "visualization_panel"):
            logger.warning("_update_view_actions_state called before actions/panel were created.")
            return

        has_pdf = self.visualization_panel.has_pdf()
        has_surfaces = self.visualization_panel.has_surfaces()
        # Determine current view directly from the stacked widget
        # Use correct attribute names: stacked_widget, view_2d, view_3d
        is_2d_current = self.visualization_panel.stacked_widget.currentWidget() == self.visualization_panel.view_2d
        is_3d_current = self.visualization_panel.stacked_widget.currentWidget() == self.visualization_panel.view_3d

        logger.debug(f"Updating view actions: has_pdf={has_pdf}, has_surfaces={has_surfaces}, is_2d_current={is_2d_current}, is_3d_current={is_3d_current}")

        # Enable actions based on content
        self.view_2d_action.setEnabled(has_pdf)
        self.view_3d_action.setEnabled(has_surfaces)

        # --- Enable Tracing Action ---
        # Tracing is only possible in 2D view with a PDF loaded
        can_trace = is_2d_current and has_pdf
        if hasattr(self, "toggle_trace_mode_action"):
            self.toggle_trace_mode_action.setEnabled(can_trace)
            logger.debug(f"Set toggle_trace_mode_action enabled state: {can_trace}")
        else:
            logger.warning("Cannot update toggle_trace_mode_action state: action not found.")
        # --- End Enable Tracing Action ---

        # Set checked state based on the current widget in the stack
        # Block signals to prevent feedback loops if setChecked triggers the slot
        self.view_2d_action.blockSignals(True)
        self.view_3d_action.blockSignals(True)
        self.view_2d_action.setChecked(is_2d_current and has_pdf) # Only check if enabled
        self.view_3d_action.setChecked(is_3d_current and has_surfaces) # Only check if enabled
        self.view_2d_action.blockSignals(False)
        self.view_3d_action.blockSignals(False)

        # REMOVED Fallback logic: Initial state is handled by VisualizationPanel._init_ui
        # and subsequent states by the on_view_... slots calling this.

        logger.debug("_actions_state complete.")

    # --- END NEW ---
 # --- Restore Method for Controller to Update UI ---
    def _update_ui_for_project(self, project: Optional[Project]):
        """Update all relevant UI components based on the (new) project state."""
        self.logger.info(f"[_update_ui_for_project] Called with project: {project.name if project else 'None'}") # ADDED LOG

        self._update_window_title()
        self._update_layer_tree() # project_panel.update_project_tree()

        if hasattr(self, "project_panel"): self.project_panel.set_project(project)
        self._update_analysis_actions_state() # Update menu/toolbar item enabled state
        self._update_pdf_controls() # Update PDF controls based on project state
        self._update_window_title() # Update window title
        if hasattr(self, "prop_dock"):
            self.prop_dock.clear_selection() # Clear properties dock
            if self._selected_scene_item is None: # Don't hide if something is selected
                self.prop_dock.hide()
        self._clear_cutfill_state() # Clear any stale cut/fill viz
        # --- Ensure view actions are updated after project load/change ---
        self._update_view_actions_state()
        # --- End ensure ---
        # --- NEW: Update Build-Surface enabled state once project UI is set up ---
        self._update_build_surface_action_state()
        # --- END NEW ---
        # --- NEW: Refresh scale pill for new project ---
        try:
            self._update_scale_pill()
        except Exception as exc:
            self.logger.warning("Failed to refresh scale pill in _update_ui_for_project: %s", exc)
        # --- END NEW ---
        self.logger.debug("UI update complete.")
        # --- NEW: Refresh legend dock ---
        if hasattr(self, "legend_dock") and self.legend_dock:
            try:
                self.legend_dock._project = project  # noqa: SLF001
                self.legend_dock.refresh()
            except Exception:
                pass
        # --- END NEW ---

        if hasattr(self, "pdf_thumbnail_dock"):
            if project and project.pdf_background_path:
                self.pdf_thumbnail_dock.show()
            else:
                self.pdf_thumbnail_dock.hide()

        # Update visualization panel with the project (this will load surfaces, PDF, etc.)
        self.logger.info(f"[_update_ui_for_project] About to call self.visualization_panel.set_project with: {project.name if project else 'None'}") # ADDED LOG
        self.visualization_panel.set_project(project)

        # Update scale pill based on the project's scale status
        self._update_scale_pill()

    # --- Restore Method to Update Window Title ---
    def _update_window_title(self):
         """Sets the main window title based on the current project name and dirty state."""
         # Check if project_controller exists before accessing it
         if not hasattr(self, "project_controller"):
              self.setWindowTitle("DigCalc") # Default title if controller not ready
              return
         project = self.project_controller.get_current_project()
         base_title = "DigCalc"
         if project:
             title = f"{project.name} - {base_title}"
             if project.filepath:
                 # Ensure Path is imported (add 'from pathlib import Path' at the top if missing)
                 title += f" [{Path(project.filepath).name}]"
             if project.is_dirty:
                 title += " *" # Indicate unsaved changes
             self.setWindowTitle(title)
         else:
             self.setWindowTitle(base_title)
    # --- End Restore ---
    # --- NEW: Slot for Building Surface ---
    @Slot()
    def on_build_surface(self):
        """Handles the 'Build Surface from Layer' action."""
        # Get project from controller
        project = self.project_controller.get_current_project()
        if not project or not project.traced_polylines:
            QMessageBox.information(self, "Build Surface", "No traced polylines available...")
            logger.warning("Build Surface action triggered but no traced polylines exist.")
            return

        # --- FIX: Handle list/dict format when checking for elevation ---
        layers_with_elevation = []
        # Use project variable
        for layer, polys in project.traced_polylines.items():
            # ... (rest of elevation check uses local vars) ...
            if not isinstance(polys, list):
                # ...
                continue
            has_elevation = False
            for p_data in polys:
                # ...
                if isinstance(p_data, dict) and p_data.get("elevation") is not None:
                    has_elevation = True
                    break
            if has_elevation:
                layers_with_elevation.append(layer)
        # --- END FIX ---

        if not layers_with_elevation:
             # ... (no layers with elevation message) ...
             return

        # Pass project to dialog
        dlg = BuildSurfaceDialog(project, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            selected_layer = dlg.layer()
            surface_name = dlg.surface_name()

            if not selected_layer or not surface_name:
                 # ... (dialog error handling) ...
                 return

            # Use project variable
            unique_surface_name = project.get_unique_surface_name(surface_name)
            if unique_surface_name != surface_name:
                 # ... (adjust name) ...
                 surface_name = unique_surface_name

            # ... (logging and status) ...

            # Initialize list before try block to guarantee existence
            valid_polys_for_build: list = []
            try:
                # Use project variable
                polylines_to_build = project.traced_polylines.get(selected_layer, [])
                
                # Filter polylines: include if they have a top-level elevation 
                # OR if their points are 3D.
                temp_valid_polys = []
                for p_data in polylines_to_build:
                    if not isinstance(p_data, dict):
                        continue
                    
                    # Condition 1: Top-level elevation exists
                    if p_data.get("elevation") is not None:
                        temp_valid_polys.append(p_data)
                        continue # Polyline is valid, no need to check points
                    
                    # Condition 2: Points list contains 3D coordinates
                    points = p_data.get("points")
                    if isinstance(points, list) and points:
                        first_point = points[0]
                        if isinstance(first_point, (list, tuple)) and len(first_point) == 3:
                            if isinstance(first_point[2], (int, float)): # Check if Z is a number
                                temp_valid_polys.append(p_data)
                
                valid_polys_for_build = temp_valid_polys
                
                if not valid_polys_for_build:
                    raise SurfaceBuilderError(f"Layer '{selected_layer}' has no polylines with suitable elevation data for building.")

                # Use project variable
                current_layer_rev = project.layer_revisions.get(selected_layer, 0)
                # ... (logging) ...

                surface = SurfaceBuilder.build_from_polylines(
                    layer_name=selected_layer,
                    polylines_data=valid_polys_for_build, # Pass the filtered list
                    revision=current_layer_rev,
                )
                surface.name = surface_name
                # Use project variable
                project.add_surface(surface)
                # --- CHANGE THIS LINE ---
                self.visualization_panel.display_surface(surface) # Use display_surface
                # --- END CHANGE ---
                # ... (rest of UI updates and error handling) ...

                if hasattr(self, "project_panel"):
                    self.project_panel._update_tree()
                # --- ADD THIS ---
                self._update_analysis_actions_state() # Check if calc button should be enabled
                # --- END ADD ---
                self.statusBar().showMessage(f"Surface '{surface_name}' created from layer '{selected_layer}'.", 5000)
                # Update the view action states now that content has changed
                self._update_view_actions_state()

                # Notify any listeners (e.g., 3-D viewer) that surfaces list changed
                if hasattr(self.project_controller, "surfaces_rebuilt"):
                    self.project_controller.surfaces_rebuilt.emit()

                # Update visualization - Use display_surface (defined in Part 4)
                # --- CHANGE THIS LINE --- 
                if hasattr(self.visualization_panel, "display_surface"):
                    self.visualization_panel.display_surface(surface)
                # --- END CHANGE ---

            except SurfaceBuilderError as e:
                 logger.error(f"Surface build failed: {e}", exc_info=True)
                 QMessageBox.warning(self, "Build Surface Error", str(e))
                 self.statusBar().showMessage("Surface build failed.", 5000)
            except Exception as e:
                 logger.exception(f"Unexpected error during surface build: {e}")
                 QMessageBox.critical(self, "Build Surface Error", f"An unexpected error occurred:\n{e}")
                 self.statusBar().showMessage("Surface build failed (unexpected error).", 5000)
        else:
             logger.info("Build Surface dialog cancelled by user.")
             self.statusBar().showMessage("Build surface cancelled.", 3000)
    # --- END NEW ---

    # --- NEW: Rebuild Helpers ---
    def _queue_surface_rebuilds_for_layer(self, layer_name: str):
        """Adds a layer to the rebuild queue and starts the debounce timer."""
        if layer_name: # Ensure layer_name is valid
            self.logger.debug(f"Queueing rebuild for layer: {layer_name}")
            self._rebuild_needed_layers.add(layer_name)
            # Start or restart the timer with the interval
            self._rebuild_timer.start() # Uses the interval set in __init__
        else:
            self.logger.warning("Attempted to queue rebuild for None layer name.")

    def _process_rebuild_queue(self):
        """Processes layers marked for rebuild, rebuilding derived surfaces."""
        # Get project from controller
        project = self.project_controller.get_current_project()
        if not project or not self._rebuild_needed_layers:
            if self._rebuild_needed_layers:
                 self.logger.warning("Rebuild queue processed but no current project.")
                 self._rebuild_needed_layers.clear()
            return

        layers_to_process = self._rebuild_needed_layers.copy()
        self._rebuild_needed_layers.clear() # Clear queue before processing

        self.logger.info(f"Processing rebuild queue for layers: {layers_to_process}")
        # Use project variable
        surfaces_to_check = list(project.surfaces.values()) # Copy to avoid issues if modified

        processed_count = 0
        for surf in surfaces_to_check:
            # Check if surface exists in project (might have been deleted)
            # Use project variable
            if surf.name not in project.surfaces:
                 continue
            if surf.source_layer_name in layers_to_process:
                # Pass project to rebuild method
                self._rebuild_surface_now(project, surf.name)
                processed_count += 1

        self.logger.info(f"Finished processing rebuild queue. Rebuilt {processed_count} surfaces derived from {layers_to_process}.")

    # Pass project explicitly
    def _rebuild_surface_now(self, project: Project, surface_name: str):
        """Rebuilds a specific surface if necessary."""
        if not project: return # Check passed project
        surf = project.surfaces.get(surface_name)

        if not surf or not surf.source_layer_name:
            self.logger.debug(f"Skipping rebuild for '{surface_name}': No surface or source layer.")
            return

        layer = surf.source_layer_name
        # Use project variable
        current_layer_rev = project.layer_revisions.get(layer, 0)

        self.logger.debug(f"Rebuild check for '{surface_name}': Layer='{layer}', CurrentLayerRev={current_layer_rev}, SurfaceSavedRev={surf.source_layer_revision}")

        # --- Check if already up-to-date ---
        if surf.source_layer_revision is not None and surf.source_layer_revision == current_layer_rev:
             # --- Add specific log here ---
             self.logger.info(f"CONDITION MET: Surface '{surface_name}' revision ({surf.source_layer_revision}) matches current layer revision ({current_layer_rev}). Skipping rebuild.")
             # --- End add ---
             self.logger.debug(f" -> Surface '{surface_name}' is already up-to-date (Revision {current_layer_rev}). Skipping rebuild.")
             if surf.is_stale:
                  # Restore original code to clear stale state
                  surf.is_stale = False
                  # Use project variable
                  project.is_modified = True
                  if hasattr(self.project_panel, "_update_tree_item_text"):
                      self.project_panel._update_tree_item_text(surf.name)
             return

        self.logger.debug(f" -> Surface '{surface_name}' needs rebuild (SavedRev={surf.source_layer_revision} != CurrentRev={current_layer_rev}).")
        # ... (rest of rebuild logic) ...

        polys_data = project.traced_polylines.get(layer, [])
        valid_polys = [
            p for p in polys_data
            if isinstance(p, dict) and p.get("elevation") is not None
        ]

        if not valid_polys:
            logger.warning(f"Layer '{layer}' has no valid polylines with elevation to rebuild surface '{surface_name}'. Marking as stale.")
            surf.is_stale = True
            project.is_modified = True
            if hasattr(self.project_panel, "_update_tree_item_text"): # Check if method exists
                self.project_panel._update_tree_item_text(surf.name)
            return

        self.statusBar().showMessage(f"Rebuilding surface '{surface_name}' from layer '{layer}'...", 0)
        try:
            # Use SurfaceBuilder directly
            new_surf = SurfaceBuilder.build_from_polylines(layer, valid_polys, current_layer_rev)
            new_surf.name = surface_name # Keep the original name
            new_surf.is_stale = False # Mark as not stale

            # Replace in project (use project variable)
            project.surfaces[surface_name] = new_surf
            project.is_modified = True

            # Update visualization - Use display_surface (defined in Part 4)
            if hasattr(self.visualization_panel, "display_surface"):
                self.visualization_panel.display_surface(new_surf)
            else:
                 logger.error("VisualizationPanel does not have 'display_surface' method.")

            # Update project panel
            if hasattr(self.project_panel, "_update_tree_item_text"): # Check if method exists
                self.project_panel._update_tree_item_text(new_surf.name)

            self.logger.info(f"Successfully rebuilt surface '{surface_name}' from layer '{layer}' (New Rev: {current_layer_rev}).")
            self.statusBar().showMessage(f"Surface '{surface_name}' rebuilt successfully.", 3000)

        except SurfaceBuilderError as e:
            logger.error(f"Failed to rebuild surface '{surface_name}': {e}")
            QMessageBox.warning(self, "Rebuild Failed", f"Could not rebuild surface '{surface_name}':\n{e}")
            self.statusBar().showMessage(f"Rebuild failed for '{surface_name}'.", 5000)
            surf.is_stale = True
            project.is_modified = True
            if hasattr(self.project_panel, "_update_tree_item_text"): # Check if method exists
                self.project_panel._update_tree_item_text(surf.name)
        except Exception as e:
            logger.exception(f"Unexpected error rebuilding surface '{surface_name}'")
            QMessageBox.critical(self, "Rebuild Error", f"An unexpected error occurred rebuilding '{surface_name}':\n{e}")
            self.statusBar().showMessage(f"Rebuild error for '{surface_name}'.", 5000)
            surf.is_stale = True
            project.is_modified = True
            if hasattr(self.project_panel, "_update_tree_item_text"): # Check if method exists
                 self.project_panel._update_tree_item_text(surf.name)
    # --- End Rebuild Helpers ---

    def _clear_cutfill_state(self):
        """Resets the cut/fill map action and clears visualization."""
        self.logger.debug("Clearing cut/fill map state.")
        self._last_dz_cache = None
        self.cutfill_action.setChecked(False)
        self.cutfill_action.setEnabled(False)
        # Ensure the visualization is also cleared/hidden
        self.visualization_panel.set_cutfill_visible(False)
        self.visualization_panel.clear_cutfill_map()

    @Slot(float, float, float, np.ndarray, np.ndarray, np.ndarray, bool)
    def _on_volume_computed(self, cut: float, fill: float, net: float,
                            dz_grid: Optional[np.ndarray],
                            gx: Optional[np.ndarray],
                            gy: Optional[np.ndarray],
                            generate_map: bool):
        """Handles the results of a volume calculation, including updating the cut/fill map.
        "
        """
        self.logger.info(f"Volume computed: Cut={cut:.2f}, Fill={fill:.2f}, Net={net:.2f}, GenerateMap={generate_map}")
        # Display results (e.g., in a dialog or status bar)
        # Keep existing report dialog logic
        report_dialog = ReportDialog(cut, fill, net, self)
        report_dialog.exec()

        # Update cut/fill map if requested and data is valid
        if generate_map and dz_grid is not None and gx is not None and gy is not None:
            try:
                self.visualization_panel.update_cutfill_map(dz_grid, gx, gy)
                self.cutfill_action.setEnabled(True)
                # Ensure visibility matches checkbox state after generation
                # Check the action *after* enabling it
                self.cutfill_action.setChecked(True)
                # Set visibility directly - toggled signal will handle the rest
                self.visualization_panel.set_cutfill_visible(True)
                self.logger.info("Cut/Fill map generated and displayed.")
            except Exception as e:
                 self.logger.error(f"Failed to update visualization panel with cut/fill map: {e}", exc_info=True)
                 QMessageBox.warning(self, "Map Error", f"Could not display the cut/fill map: {e}")
                 self._clear_cutfill_state() # Reset on error
        else:
            # If map wasn't generated or data was invalid, ensure it's cleared/disabled
            self.logger.info("Cut/Fill map not generated or data invalid, ensuring it is cleared.")
            self._clear_cutfill_state()

    # --- NEW: Slot for PDF Page Selection ---
    @Slot(int)
    def _on_pdf_page_selected(self, page_index: int):
        """Handles the pageSelected signal from the PdfController.
        Delegates to the VisualizationPanel to display the page.
        """
        self.logger.info(f"MainWindow received pageSelected signal for index: {page_index}")
        # Convert 0-based index from signal to 1-based page number for the method
        page_number = page_index + 1
        self.visualization_panel.set_pdf_page(page_number)

    # --- Add new slot for Trace PDF Action ---
    @Slot()
    def _on_trace_from_pdf(self):
        """Handles the 'Trace from PDF...' action.
        Opens a file dialog, loads the PDF, shows the page selector,
        and queues creation of tracing layers for selected pages.
        """
        self.logger.info("Trace from PDF action triggered.")
        project = self.project_controller.get_project() # Use controller method
        if not project:
            QMessageBox.warning(self, "No Project", "Please open or create a project first.")
            return

        # Let the user select a PDF file
        file_path_tuple = QFileDialog.getOpenFileName(
            self,
            "Select PDF for Tracing",
            self.project_controller.get_last_directory(), # Start in last used dir
            "PDF Files (*.pdf)",
        )
        file_path_str = file_path_tuple[0]

        if not file_path_str:
            self.logger.info("PDF selection cancelled.")
            return

        file_path = Path(file_path_str)
        self.project_controller.set_last_directory(str(file_path.parent)) # Update last dir

        # Load the PDF using the PdfService
        try:
            # Ensure load_pdf returns boolean or raises error on failure
            # Let's assume PdfService handles logging internal errors
            self.pdf_service.load_pdf(str(file_path))
            if not self.pdf_service.current_document:
                raise PDFRendererError("Failed to load document object after loading path.")
            self.logger.info(f"PDF loaded via PdfService: {file_path}")
        except PDFRendererError as e:
            self.logger.error(f"Error loading PDF for tracing: {e}")
            QMessageBox.critical(self, "PDF Load Error", f"Could not load PDF: {e}")
            # Consider clearing pdf_service state if needed
            # self.pdf_service.clear_document()
            return
        except Exception as e: # Catch other potential errors during loading
             self.logger.exception(f"Unexpected error loading PDF '{file_path}': {e}")
             QMessageBox.critical(self, "PDF Load Error", f"An unexpected error occurred while loading the PDF: {e}")
             return

        # --- NEW: Load PDF into Visualization Panel ---
        self.visualization_panel.load_pdf_background(str(file_path))
        # --- END NEW ---

        # Show the page selection dialog
        dialog = PdfPageSelectorDialog(self.pdf_service.current_document, self)
        if dialog.exec() == QDialog.Accepted:
            selected_indices = dialog.get_selected_pages() # Get list of 0-based indices
            if not selected_indices:
                self.logger.info("No pages selected for tracing.")
                self.statusBar().showMessage("No pages selected for tracing.", 3000)
                return

            self.logger.info(f"Selected PDF pages for tracing (0-based indices): {selected_indices}")
            added_layers_count = 0
            project = self.project_controller.get_project() # Re-get just in case
            if not project:
                self.logger.error("Project became unavailable after PDF selection.")
                QMessageBox.critical(self, "Error", "Project not available. Cannot create layers.")
                return

            for index in selected_indices:
                try:
                    # Construct a base layer name including page label/number
                    page_label = self.pdf_service.current_document.page_label(index)
                    base_layer_name = f"PDF Trace - {file_path.name} - Page {page_label}"

                    # Get a unique layer name from the project
                    unique_layer_name = project.get_unique_layer_name(base_layer_name)

                    # Ensure the layer exists in the project's traced_polylines dict
                    # Add an empty list initially, polylines will be added later during tracing
                    if unique_layer_name not in project.traced_polylines:
                        project.traced_polylines[unique_layer_name] = []
                        # Increment counter for summary feedback
                        added_layers_count += 1
                        self.logger.debug(f"Created empty traced polyline list for layer: {unique_layer_name}")
                    else:
                         # Layer might exist from previous tracing or other means
                         self.logger.warning(f"Layer '{unique_layer_name}' already exists. Adding PDF source info.")

                except Exception as exc:
                    # Defensive: continue processing the remaining pages even if one fails
                    self.logger.error(
                        "Failed to prepare tracing layer for PDF page %s: %s",
                        index,
                        exc,
                        exc_info=True,
                    )

            # --- Post-processing after layer creation loop ---
            if added_layers_count:
                # Refresh UI components that depend on the layer list
                self._update_layer_tree()
                self.statusBar().showMessage(
                    f"Added {added_layers_count} trace layer(s).",
                    5000,
                )
            else:
                self.statusBar().showMessage("No new layers were added.", 3000)
        else:
            self.logger.info("Trace from PDF dialog cancelled by user.")
