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

from ..core.calculations.volume_calculator import VolumeCalculator
from ..core.geometry.surface_builder import SurfaceBuilder, SurfaceBuilderError

# Local imports - Use relative paths
from ..models.project import PolylineData, Project
from ..visualization.pdf_renderer import PDFRenderer, PDFRendererError
from .dialogs.build_surface_dialog import BuildSurfaceDialog
from .dialogs.elevation_dialog import ElevationDialog

# --- NEW: Add missing import ---
from .dialogs.pdf_page_selector_dialog import PdfPageSelectorDialog
from .dialogs.report_dialog import ReportDialog
from .dialogs.volume_calculation_dialog import VolumeCalculationDialog
from .project_panel import ProjectPanel
from .properties_dock import PropertiesDock
from .visualization_panel import VisualizationPanel

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

        # --- END MODIFIED ---
        self._connect_signals()
        self._update_view_actions_state()

        self.logger.debug("MainWindow initialized")
        # Ensure Scale-Calibration menu action reflects current PDF state at startup
        self._update_scale_action_enabled(False)
        # --- Connect PdfService signal to update scale action ---
        if hasattr(self, "pdf_service") and self.pdf_service:
            self.pdf_service.documentLoaded.connect(
                lambda page_count: self._update_scale_action_enabled(page_count > 0),
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

        # Create project panel as a dock widget, passing self (MainWindow)
        self.project_dock = QDockWidget("Project", self)
        self.project_dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable,
        )
        self.project_panel = ProjectPanel(main_window=self, parent=self)
        self.project_dock.setWidget(self.project_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.project_dock)

        # --- Verify Project Dock ---
        self.layer_dock = QDockWidget("Layers", self)
        self.layer_dock.setObjectName("LayerDock")
        self.layer_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.layer_tree = QTreeWidget(self.layer_dock)
        self.layer_tree.setHeaderHidden(True)
        self.layer_dock.setWidget(self.layer_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layer_dock)

        # --- NEW: Create and add Properties Dock ---
        self.prop_dock = PropertiesDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.prop_dock)
        self.prop_dock.hide()
        # --- END NEW ---

        # --- NEW: Create and add PDF Thumbnail Dock ---
        # self.pdf_thumbnail_dock = PdfThumbnailDock(self.pdf_service, self.pdf_controller, self) # Incorrect
        self.pdf_thumbnail_dock = PdfThumbnailDock(self) # Correct - Pass only parent
        self.addDockWidget(Qt.LeftDockWidgetArea, self.pdf_thumbnail_dock)
        self.pdf_thumbnail_dock.hide() # Initially hidden, show when PDF is loaded?
        # --- END NEW ---

        # Connect the signal for item changes (checkbox toggles)
        self.layer_tree.itemChanged.connect(self._on_layer_visibility_changed)

    def _connect_signals(self):
        """Connect signals from UI components to main window slots."""
        self.logger.debug("Connecting MainWindow signals...")

        # --- Project Controller signals ---
        self.new_project_action.triggered.connect(self.project_controller.on_new_project)
        self.open_project_action.triggered.connect(self.project_controller.on_open_project)
        self.save_project_action.triggered.connect(self.project_controller.on_save_project) # save_as=False by default
        # Connect Save As action to on_save_project with save_as=True
        self.save_project_as_action.triggered.connect(lambda: self.project_controller.on_save_project(save_as=True))
        self.exit_action.triggered.connect(self.close)
        # --- End Connect Project Controller signals ---\

        # --- NEW: Connect Trace PDF Action ---
        self.trace_pdf_action.triggered.connect(self._on_trace_from_pdf)
        # --- END NEW ---

        # Connect visualization panel signals
        if hasattr(self.visualization_panel, "surface_visualization_failed"):
            self.visualization_panel.surface_visualization_failed.connect(self._on_visualization_failed)

        # Connect tracing scene signals (via visualization panel)
        if hasattr(self.visualization_panel, "scene_2d") and self.visualization_panel.scene_2d:
            self.visualization_panel.scene_2d.polyline_finalized.connect(self._on_polyline_drawn)
            self.visualization_panel.scene_2d.selectionChanged.connect(self._on_item_selected)
            # --- NEW: Connect pageRectChanged for fitting view ---
            if hasattr(self.visualization_panel.scene_2d, "pageRectChanged"):
                self.visualization_panel.scene_2d.pageRectChanged.connect(self._fit_view_to_scene)
            else:
                self.logger.warning("TracingScene does not have 'pageRectChanged' signal.")
            # --- NEW: Connect padDrawn signal ---
            if hasattr(self.visualization_panel.scene_2d, "padDrawn"):
                self.visualization_panel.scene_2d.padDrawn.connect(self._on_pad_drawn)
            else:
                self.logger.warning("TracingScene does not have 'padDrawn' signal.")
            # --- END NEW ---
        else:
             self.logger.warning("Could not connect tracing scene signals: scene_2d not found or is None.")

        # Connect layer tree signal
        self.layer_tree.itemChanged.connect(self._on_layer_visibility_changed)

        # --- NEW: Connect PropertiesDock signal ---
        # self.prop_dock.edited.connect(self._apply_elevation_edit) # Old signal name
        self.prop_dock.polylineEdited.connect(self._apply_elevation_edit) # Corrected signal name
        # TODO: Connect self.prop_dock.regionUpdated to a handler method
        # Connect the new settingsChanged signal
        self.prop_dock.settingsChanged.connect(self.project_controller.trigger_rebuild_if_needed)
        # --- END NEW ---


        # --- NEW: Connect View Actions ---
        if hasattr(self, "view_2d_action") and self.view_2d_action:
            self.view_2d_action.triggered.connect(self.on_view_2d)
        else:
             logger.error("view_2d_action not found during signal connection.")
        if hasattr(self, "view_3d_action") and self.view_3d_action:
            self.view_3d_action.triggered.connect(self.on_view_3d)
        else:
             logger.error("view_3d_action not found during signal connection.")
        # --- END NEW ---

        # --- Connect PDF Actions ---
        if hasattr(self, "load_pdf_background_action"):
            self.load_pdf_background_action.triggered.connect(self.on_load_pdf_background)
        if hasattr(self, "clear_pdf_background_action"):
            self.clear_pdf_background_action.triggered.connect(self.on_clear_pdf_background)
        if hasattr(self, "prev_pdf_page_action"):
            self.prev_pdf_page_action.triggered.connect(self.on_prev_pdf_page)
        if hasattr(self, "next_pdf_page_action"):
            self.next_pdf_page_action.triggered.connect(self.on_next_pdf_page)
        if hasattr(self, "toggle_trace_mode_action"):
            self.toggle_trace_mode_action.toggled.connect(self.on_toggle_tracing_mode)

        # --- Connect Analysis Actions ---
        if hasattr(self, "calculate_volume_action"):
            self.calculate_volume_action.triggered.connect(self.on_calculate_volume)
        if hasattr(self, "build_surface_action"):
            self.build_surface_action.triggered.connect(self.on_build_surface)
        if hasattr(self, "generate_report_action"):
            self.generate_report_action.triggered.connect(self.on_generate_report)

        # --- Connect Help Actions ---
        if hasattr(self, "about_action"):
            self.about_action.triggered.connect(self.on_about)

        # --- Connect Project Controller signals (for UI updates) ---
        if hasattr(self, "project_controller"):
            self.project_controller.project_loaded.connect(self._update_ui_for_project)
            self.project_controller.project_closed.connect(lambda: self._update_ui_for_project(None))
            self.project_controller.project_modified.connect(self._update_window_title)
            self.project_controller.surfaces_rebuilt.connect(self._on_surfaces_rebuilt)
            # Connect import actions through controller
            if hasattr(self, "import_csv_action"):
                self.import_csv_action.triggered.connect(lambda: self.project_controller.on_import_file("csv"))
            if hasattr(self, "import_dxf_action"):
                self.import_dxf_action.triggered.connect(lambda: self.project_controller.on_import_file("dxf"))
            if hasattr(self, "import_landxml_action"):
                self.import_landxml_action.triggered.connect(lambda: self.project_controller.on_import_file("landxml"))
        else:
            self.logger.error("ProjectController not found during signal connection.")

        # --- Connect PDF Controller Signal ---
        if hasattr(self, "pdf_controller") and self.pdf_controller:
            self.pdf_controller.pageSelected.connect(self._on_pdf_page_selected)
            self.logger.debug("Connected pdf_controller.pageSelected signal.")
        else:
            self.logger.error("PdfController not found during signal connection.")
        # --- End Connect PDF Controller Signal ---

        # ------------------------------------------------------------------
        # Tracing menu – elevation mode radio actions (update SettingsService)
        # ------------------------------------------------------------------
        if hasattr(self, "trace_point_action"):
            self.trace_point_action.triggered.connect(lambda _checked=False: self._set_tracing_elev_mode("point"))
        if hasattr(self, "trace_interpolate_action"):
            self.trace_interpolate_action.triggered.connect(lambda _checked=False: self._set_tracing_elev_mode("interpolate"))
        if hasattr(self, "trace_line_action"):
            self.trace_line_action.triggered.connect(lambda _checked=False: self._set_tracing_elev_mode("line"))

        self.logger.debug("Finished connecting MainWindow signals.")

    def _create_actions(self):
        """Create actions for menus and toolbars."""
        # File menu actions
        self.new_project_action = QAction("&New Project", self)
        self.new_project_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_project_action.setStatusTip("Create a new empty project.")

        self.open_project_action = QAction("&Open Project...", self)
        self.open_project_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_project_action.setStatusTip("Open an existing project file (.digcalc).")

        self.save_project_action = QAction("&Save Project", self)
        self.save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_project_action.setStatusTip("Save the current project.")
        self.save_project_action.setEnabled(False) # Initially disabled

        self.save_project_as_action = QAction("Save Project &As...", self)
        self.save_project_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_project_as_action.setStatusTip("Save the current project to a new file.")
        self.save_project_as_action.setEnabled(False) # Initially disabled

        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.setStatusTip("Exit the application.")

        # Import menu actions
        self.import_csv_action = QAction("Import &CSV...", self)
        self.import_csv_action.setStatusTip("Import points from a CSV file.")
        # Connect via controller in _connect_signals or elsewhere
        # self.import_csv_action.triggered.connect(lambda: self.project_controller.on_import_file('csv'))

        self.import_dxf_action = QAction("Import &DXF...", self)
        self.import_dxf_action.setStatusTip("Import geometry from a DXF file.")
        # self.import_dxf_action.triggered.connect(lambda: self.project_controller.on_import_file('dxf'))

        self.import_landxml_action = QAction("Import &LandXML...", self)
        self.import_landxml_action.setStatusTip("Import surfaces or points from a LandXML file.")
        # self.import_landxml_action.triggered.connect(lambda: self.project_controller.on_import_file('landxml'))

        # Background actions (Load/Clear PDF)
        self.load_pdf_background_action = QAction("Load PDF &Background...", self)
        self.load_pdf_background_action.setStatusTip("Load a PDF page as a background for tracing.")
        # Connection in _connect_signals

        self.clear_pdf_background_action = QAction("&Clear PDF Background", self)
        self.clear_pdf_background_action.setStatusTip("Remove the current PDF background image.")
        # Connection in _connect_signals
        self.clear_pdf_background_action.setEnabled(False)

        # PDF Navigation Actions
        self.prev_pdf_page_action = QAction("Previous PDF Page", self)
        self.prev_pdf_page_action.setStatusTip("Go to the previous page in the PDF background.")
        # Connection in _connect_signals
        self.prev_pdf_page_action.setEnabled(False)

        self.next_pdf_page_action = QAction("Next PDF Page", self)
        self.next_pdf_page_action.setStatusTip("Go to the next page in the PDF background.")
        # Connection in _connect_signals
        self.next_pdf_page_action.setEnabled(False)

        # Analysis menu actions
        self.calculate_volume_action = QAction("&Calculate Volume...", self)
        self.calculate_volume_action.setStatusTip("Calculate cut/fill volumes between surfaces.")
        # Connection in _connect_signals
        self.calculate_volume_action.setEnabled(False)

        self.build_surface_action = QAction("&Build Surface...", self)
        self.build_surface_action.setStatusTip("Build a TIN or Grid surface from project layers.")
        # Connection in _connect_signals
        self.build_surface_action.setEnabled(False)

        self.generate_report_action = QAction("Generate &Report...", self)
        self.generate_report_action.setStatusTip("Generate a PDF report of the project.")
        # Connection in _connect_signals
        self.generate_report_action.setEnabled(False)

        # --- NEW: Export Report Action ---
        self.export_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton),
                                    "Export Report…", self)
        self.export_action.setStatusTip("Export PDF report with CSV tables.")
        self.export_action.triggered.connect(self.on_export_report)

        # View menu actions (Toggles for docks - simplified creation)
        # Ensure docks exist before creating actions that depend on them
        if hasattr(self, "project_dock"):
            self.view_project_panel_action = self.project_dock.toggleViewAction()
            self.view_project_panel_action.setText("&Project Panel")
        else:
             self.logger.error("Cannot create view_project_panel_action: project_dock missing")

        if hasattr(self, "layer_dock"):
            self.view_layer_panel_action = self.layer_dock.toggleViewAction()
            self.view_layer_panel_action.setText("&Layer Panel")
        else:
             self.logger.error("Cannot create view_layer_panel_action: layer_dock missing")

        if hasattr(self, "prop_dock"):
            self.view_properties_dock_action = self.prop_dock.toggleViewAction()
            self.view_properties_dock_action.setText("P&roperties Dock")
        else:
             self.logger.error("Cannot create view_properties_dock_action: prop_dock missing")

        if hasattr(self, "pdf_thumbnail_dock"):
            self.view_pdf_thumbnail_dock_action = self.pdf_thumbnail_dock.toggleViewAction()
            self.view_pdf_thumbnail_dock_action.setText("PDF T&humbnails")
            self.view_pdf_thumbnail_dock_action.setEnabled(False)
        else:
             self.logger.error("Cannot create view_pdf_thumbnail_dock_action: pdf_thumbnail_dock missing")


        # View mode actions (2D/3D)
        self.view_2d_action = QAction("View &2D", self, checkable=True)
        self.view_3d_action = QAction("View &3D", self, checkable=True)
        self.view_action_group = QActionGroup(self)
        self.view_action_group.addAction(self.view_2d_action)
        self.view_action_group.addAction(self.view_3d_action)
        self.view_action_group.setExclusive(True)
        self.view_2d_action.setChecked(True) # Default to 2D view

        # 3-D Viewer Dock action
        self.view3d_action = QAction("3-D Viewer", self)
        self.view3d_action.setStatusTip("Open the 3-D viewer dock.")
        self.view3d_action.triggered.connect(self.on_open_3d)

        # Cut/Fill Map Action
        self.cutfill_action = QAction("Show Cut/Fill Map", self, checkable=True)
        self.cutfill_action.setChecked(False)
        self.cutfill_action.setEnabled(False)

        # Tool Actions
        self.toggle_trace_mode_action = QAction("&Enable Tracing", self, checkable=True)
        self.toggle_trace_mode_action.setStatusTip("Toggle polyline tracing mode for the 2D view.")
        self.toggle_trace_mode_action.setChecked(False)
        # Connection in _connect_signals
        self.toggle_trace_mode_action.setEnabled(False)

        self.trace_pdf_action = QAction("Trace from PDF Vectors...", self)
        self.trace_pdf_action.setStatusTip("Extract vector paths from a PDF page and create layers.")
        # Connection in _connect_signals
        self.trace_pdf_action.setEnabled(False)

        # --- NEW: Daylight Offset Action ---
        self.daylight_action = QAction(QIcon(":/icons/daylight.svg"), "Daylight Offset…", self)
        self.daylight_action.setStatusTip("Create daylight offset breakline from selected polyline.")
        self.daylight_action.triggered.connect(self.on_daylight_offset)
        # Toolbar hookup occurs in _create_toolbars after toolbar is created
        # --- END NEW ---

        # --- NEW: Mass-Haul Action ---
        self.masshaul_action = QAction(QIcon(":/icons/masshaul.svg"), "Mass-Haul…", self)
        self.masshaul_action.setStatusTip("Generate mass-haul diagram from Existing and Design surfaces.")
        self.masshaul_action.triggered.connect(self.on_mass_haul)
        self.masshaul_action.setEnabled(False)  # enable when conditions met later
        # --- END NEW ---

        # Help menu actions
        self.about_action = QAction("&About DigCalc", self)
        self.about_action.setStatusTip("Show information about the DigCalc application.")
        # Connection in _connect_signals

    def _create_menus(self):
        """Create the main menu bar."""
        self.menu_bar = self.menuBar()

        # File menu
        file_menu = self.menu_bar.addMenu("&File")
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.save_project_action)
        file_menu.addAction(self.save_project_as_action)
        file_menu.addSeparator()
        # Add Import actions to File menu for now
        # file_menu.addAction(self.import_cad_action)
        # file_menu.addAction(self.import_pdf_action) # This seems like viewing bg, not tracing
        # file_menu.addAction(self.import_landxml_action)
        # file_menu.addAction(self.import_csv_action)
        # file_menu.addSeparator() # Add separator before tracing action?
        # --- NEW: Add Trace PDF Action ---
        file_menu.addAction(self.trace_pdf_action)
        file_menu.addSeparator()
        # --- END NEW ---
        file_menu.addAction(self.exit_action)

        # Import menu
        self.import_menu = self.menu_bar.addMenu("Import")
        self.import_menu.addAction(self.import_csv_action)
        self.import_menu.addAction(self.import_dxf_action)
        self.import_menu.addAction(self.import_landxml_action)

        # View menu - Add PDF actions here
        self.view_menu = self.menu_bar.addMenu("View")
        self.view_menu.addAction(self.load_pdf_background_action)
        self.view_menu.addAction(self.clear_pdf_background_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.prev_pdf_page_action)
        self.view_menu.addAction(self.next_pdf_page_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.view_2d_action)
        self.view_menu.addAction(self.view_3d_action)
        # 3-D viewer dock action
        self.view_menu.addAction(self.view3d_action)
        self.view_menu.addSeparator()
        # Ensure project_dock exists before adding its action
        if hasattr(self, "project_dock"):
            self.view_menu.addAction(self.project_dock.toggleViewAction())
        else:
             self.logger.error("Project dock not created, cannot add toggle action.")
        # --- Verify Layer Dock Toggle Action ---
        # Check if layer_dock exists before adding its action
        if hasattr(self, "layer_dock") and self.layer_dock:
             self.view_menu.addAction(self.layer_dock.toggleViewAction())
        else:
             self.logger.error("Layer dock not created or is None, cannot add toggle action.")
        # --- End Verify Layer Dock Toggle Action ---
        # --- Properties Dock Toggle Action ---
        # Check if prop_dock exists before adding its action
        if hasattr(self, "prop_dock"):
            view_menu_actions = self.view_menu.actions()
            insert_before_action = None
            layer_toggle_action = self.layer_dock.toggleViewAction() if hasattr(self, "layer_dock") and self.layer_dock else None

            if layer_toggle_action:
                try:
                    idx = view_menu_actions.index(layer_toggle_action)
                    for i in range(idx + 1, len(view_menu_actions)):
                         if view_menu_actions[i].isSeparator():
                             insert_before_action = view_menu_actions[i]
                             break
                    if not insert_before_action:
                        if idx + 1 < len(view_menu_actions):
                             insert_before_action = view_menu_actions[idx+1]
                except ValueError:
                    self.logger.warning("Layer toggle action not found in view menu for inserting properties toggle.")

            if insert_before_action:
                self.view_menu.insertAction(insert_before_action, self.prop_dock.toggleViewAction())
            else:
                self.view_menu.addAction(self.prop_dock.toggleViewAction())
        else:
            self.logger.error("Properties dock not created, cannot add toggle action.")
        # --- End Properties Dock Toggle Action ---
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.toggle_trace_mode_action)

        # --- NEW: Surfaces Menu ---
        self.surfaces_menu = self.menu_bar.addMenu("Surfaces")
        self.surfaces_menu.addAction(self.build_surface_action)
        # --- END NEW ---

        # Analysis menu
        self.analysis_menu = self.menu_bar.addMenu("Analysis")
        self.analysis_menu.addAction(self.calculate_volume_action)

        # ------------------------------------------------------------------
        # Tracing menu (new)
        # ------------------------------------------------------------------
        self.tracing_menu = self.menu_bar.addMenu("Tracing")

        # Re-use the existing enable-tracing toggle action
        self.tracing_menu.addAction(self.toggle_trace_mode_action)
        self.tracing_menu.addSeparator()

        # NEW: Scale calibration action
        self.scale_calib_act = QAction(QIcon.fromTheme("mdi.ruler"), "Scale…", self)
        self.scale_calib_act.setToolTip("Calibrate or edit drawing scale (Ctrl+K)")
        self.scale_calib_act.setShortcut("Ctrl+K")
        self.scale_calib_act.triggered.connect(self.on_scale_calibration)
        self.scale_calib_act.setEnabled(False)  # Disabled until a PDF is loaded
        self.tracing_menu.addAction(self.scale_calib_act)
        self.tracing_menu.addSeparator()

        # Elevation-prompt mode radio actions
        self.trace_point_action = QAction("Point Prompt", self, checkable=True)
        self.trace_interpolate_action = QAction("First/Last Prompt (Interpolate)", self, checkable=True)
        self.trace_line_action = QAction("Line Elevation", self, checkable=True)

        self.trace_mode_group = QActionGroup(self)
        self.trace_mode_group.setExclusive(True)
        for act in (self.trace_point_action, self.trace_interpolate_action, self.trace_line_action):
            self.trace_mode_group.addAction(act)
            self.tracing_menu.addAction(act)

        # Initial checked state from SettingsService
        mode_pref = SettingsService().tracing_elev_mode()
        if mode_pref == "interpolate":
            self.trace_interpolate_action.setChecked(True)
        elif mode_pref == "line":
            self.trace_line_action.setChecked(True)
        else:  # fallback to point
            self.trace_point_action.setChecked(True)

        # ------------------------------------------------------------------
        # Connect mode actions to handler – done in _connect_signals
        # ------------------------------------------------------------------

        # --- NEW: Tools Toolbar ---
        self.tools_toolbar = QToolBar("Tools Toolbar")
        self.tools_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(self.tools_toolbar)
        self.tools_toolbar.addAction(self.daylight_action)
        # --- NEW: Add mass-haul action to tools toolbar ---
        self.tools_toolbar.addAction(self.masshaul_action)
        # --- END NEW ---

        # Help menu
        self.help_menu = self.menu_bar.addMenu("Help")
        # Add help actions here

    def _create_toolbars(self):
        """Create the application toolbars."""
        # Main toolbar
        self.main_toolbar = QToolBar("Main Toolbar")
        self.main_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(self.main_toolbar)

        # Add actions to toolbar
        self.main_toolbar.addAction(self.new_project_action)
        self.main_toolbar.addAction(self.open_project_action)
        self.main_toolbar.addAction(self.save_project_action)
        self.main_toolbar.addSeparator()

        # Add the layer selector from VisualizationPanel
        if hasattr(self, "visualization_panel") and hasattr(self.visualization_panel, "layer_selector"):
            self.main_toolbar.addSeparator()
            self.main_toolbar.addWidget(QLabel(" Layer:"))
            self.main_toolbar.addWidget(self.visualization_panel.layer_selector)
        else:
            self.logger.warning("Could not add layer selector to toolbar: visualization_panel or layer_selector not found.")

        # Import toolbar
        self.import_toolbar = QToolBar("Import Toolbar")
        self.import_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(self.import_toolbar)

        self.import_toolbar.addAction(self.import_csv_action)
        self.import_toolbar.addAction(self.import_dxf_action)
        self.import_toolbar.addAction(self.import_landxml_action)

        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.calculate_volume_action)

        # --- PDF Toolbar --- (Optional, could also be in status bar)
        self.pdf_toolbar = QToolBar("PDF Toolbar")
        self.pdf_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.pdf_toolbar)

        self.pdf_toolbar.addAction(self.load_pdf_background_action)
        self.pdf_toolbar.addAction(self.scale_calib_act)  # Add Scale action next to load
        self.pdf_toolbar.addAction(self.clear_pdf_background_action)
        self.pdf_toolbar.addSeparator()
        self.pdf_toolbar.addAction(self.prev_pdf_page_action)
        self.pdf_page_label = QLabel(" Page: ")
        self.pdf_page_spinbox = QSpinBox()
        self.pdf_page_spinbox.setRange(0, 0)
        self.pdf_page_spinbox.setEnabled(False)
        self.pdf_page_spinbox.valueChanged.connect(self.on_set_pdf_page_from_spinbox)
        self.pdf_toolbar.addWidget(self.pdf_page_label)
        self.pdf_toolbar.addWidget(self.pdf_page_spinbox)
        self.pdf_toolbar.addAction(self.next_pdf_page_action)
        self.pdf_toolbar.setVisible(False)

        # --- Tracing Toolbar Action ---
        self.pdf_toolbar.addSeparator()
        self.pdf_toolbar.addAction(self.toggle_trace_mode_action)

        # --- NEW: Optional View Toolbar ---
        self.view_toolbar = QToolBar("View Toolbar")
        self.view_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.view_toolbar)
        # Add actions (use icons later if desired)
        self.view_toolbar.addAction(self.view_2d_action)
        self.view_toolbar.addAction(self.view_3d_action)
        self.view_toolbar.addAction(self.view3d_action)
        # --- END NEW ---

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

    def on_toggle_tracing_mode(self, checked: bool):
        """Slot connected to the toggle_tracing_action.
        Enables/disables tracing mode in the VisualizationPanel.
        """
        if hasattr(self, "visualization_panel"):
            self.visualization_panel.set_tracing_mode(checked)
            self.logger.info(f"Tracing mode {'enabled' if checked else 'disabled'} via MainWindow action.")
            self.toggle_trace_mode_action.setText("Disable Tracing" if checked else "Enable Tracing")
        else:
            self.logger.warning("Cannot toggle tracing mode: VisualizationPanel not found.")

    @Slot(QTreeWidgetItem, int)
    def _on_layer_visibility_changed(self, item: QTreeWidgetItem, column: int):
        """Slot called when a layer's checkbox state changes in the dock."""
        if column == 0:
            layer_name = item.text(0)
            is_visible = item.checkState(0) == Qt.Checked
            self.logger.debug(f"Layer '{layer_name}' visibility toggle -> {is_visible}")
            if hasattr(self, "visualization_panel") and hasattr(self.visualization_panel, "scene_2d") and hasattr(self.visualization_panel.scene_2d, "setLayerVisible"):
                self.visualization_panel.scene_2d.setLayerVisible(layer_name, is_visible)
            else:
                self.logger.warning("Cannot toggle layer visibility: Visualization panel, scene_2d, or setLayerVisible method not found.")

    @Slot(list, QGraphicsPathItem)
    def _on_polyline_drawn(self, points_qpointf: list, item: QGraphicsPathItem):
        """Handles the polyline_finalized signal from TracingScene.
        Prompts for elevation and adds the polyline data to the project.
        Stores the final index back into the QGraphicsPathItem.
        """
        # Get project from controller first
        project = self.project_controller.get_current_project()
        if not project:
            logger.warning("Polyline drawn but no active project.")
            if item.scene(): item.scene().removeItem(item)
            return

        # --- FIX: Use correct key to get layer name ---
        layer_name = item.data(Qt.UserRole + 1) # Key used in _finalize_current_polyline
        # --- END FIX ---
        if layer_name is None:
             logger.error("Finalized polyline item is missing layer data! Assigning to 'Default'.")
             layer_name = "Default"

        point_tuples = [(p.x(), p.y()) for p in points_qpointf]

        if len(point_tuples) < 2:
             logger.warning(f"Ignoring finalized polyline with < 2 points for layer '{layer_name}'.")
             if item.scene(): item.scene().removeItem(item)
             return

        # Only prompt for a single elevation if the current tracing mode is *line*
        elev_mode = SettingsService().tracing_elev_mode()
        if elev_mode == "line":
            dlg = ElevationDialog(self)
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                elevation = dlg.value()
            else:
                elevation = None
        else:
            # For point / interpolate modes we already set per-vertex Zs — no extra prompt.
            elevation = None
        logger.debug("Polyline elevation recorded as %s (mode=%s)", elevation, elev_mode)

        polyline_data: PolylineData = {"points": point_tuples, "elevation": elevation}

        new_index: Optional[int] = project.add_traced_polyline(
            polyline=polyline_data,
            layer_name=layer_name,
        )

        if new_index is not None:
            try:
                item.setData(1, new_index)
                self.logger.info(f"Added traced polyline (Index: {new_index}, Elevation: {elevation}) to layer '{layer_name}'.")
                self.project_panel._update_tree()
                self._update_layer_tree()
                self.statusBar().showMessage(f"Polyline added to layer '{layer_name}' (Elev: {elevation})", 3000)
                # --- Trigger Rebuild ---
                self._queue_surface_rebuilds_for_layer(layer_name)
                # --- End Trigger ---
            except Exception as e:
                 logger.error(f"Error updating UI/logging after adding polyline (Index: {new_index}, Layer: '{layer_name}'): {e}", exc_info=True)
        else:
             self.logger.error(f"Failed to add traced polyline to layer '{layer_name}' in project (add_traced_polyline returned None).")
             if item.scene(): item.scene().removeItem(item) # Clean up scene item
             QMessageBox.warning(self, "Error", f"Could not add polyline to project layer '{layer_name}'.")
        # --- END FIX ---

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
        if hasattr(self, "visualization_panel"):
            self.logger.debug("Switching to 2D view.")
            self.visualization_panel.show_2d_view()
            self._update_view_actions_state() # Update check states
        else:
            self.logger.error("Cannot switch to 2D view: VisualizationPanel not found.")

    @Slot()
    def on_view_3d(self):
        """Switch to the 3D (Terrain) view."""
        if hasattr(self, "visualization_panel"):
            self.logger.debug("Switching to 3D view.")
            self.visualization_panel.show_3d_view()
            self._update_view_actions_state() # Update check states
        else:
            self.logger.error("Cannot switch to 3D view: VisualizationPanel not found.")

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
        """Updates various UI components based on the current project state.
        Called by ProjectController when the project changes.

        Args:
            project: The new current project (or None).

        """
        self.logger.debug(f"Updating UI for project: {project.name if project else 'None'}")
        # Update UI elements
        if hasattr(self, "project_panel"): self.project_panel.set_project(project)
        self._update_layer_tree() # Update layer tree
        if hasattr(self, "visualization_panel"): self.visualization_panel.set_project(project)
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
    # --- End Restore ---

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
                # Filter again here to ensure only dicts with elevation go to builder
                # Re-assign the real value here
                valid_polys_for_build = [
                    p for p in polylines_to_build
                    if isinstance(p, dict) and p.get("elevation") is not None
                ]
                # Check the filtered list, not the original
                if not valid_polys_for_build:
                    raise SurfaceBuilderError(f"Layer '{selected_layer}' has no polylines with elevation data suitable for building.")

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
                # --- ADD THIS LINE ---
                self.visualization_panel.update_surface_mesh(surface) # Add the surface to the 3D view
                # --- END ADD ---
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

                # Update visualization - Use update_surface_mesh (defined in Part 4)
                if hasattr(self.visualization_panel, "update_surface_mesh"):
                    self.visualization_panel.update_surface_mesh(surface)

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

            # Update visualization - Use update_surface_mesh (defined in Part 4)
            if hasattr(self.visualization_panel, "update_surface_mesh"):
                self.visualization_panel.update_surface_mesh(new_surf)
            else:
                 logger.error("VisualizationPanel does not have 'update_surface_mesh' method.")

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
                        self.logger.debug(f"Created empty traced polyline list for layer: {unique_layer_name}")
                    else:
                         # Layer might exist from previous tracing or other means
                         self.logger.warning(f"Layer '{unique_layer_name}' already exists. Adding PDF source info.")

                    # Add the PDF source information using the project method
                    project.add_pdf_trace_source(unique_layer_name, str(file_path), index)
                    added_layers_count += 1
                    self.logger.info(f"Added PDF trace source for layer '{unique_layer_name}' (PDF: {file_path.name}, Page Index: {index})")

                except Exception as e:
                    self.logger.error(f"Error processing page index {index} for tracing: {e}", exc_info=True)
                    QMessageBox.warning(self, "Layer Creation Error",
                                        f"Could not create tracing layer for page {index + 1}.\nError: {e}")

            if added_layers_count > 0:
                # Update the layer tree UI to show the new layers
                self._update_layer_tree()
                self.project_controller.set_project_modified(True) # Mark project as modified
                self.statusBar().showMessage(f"Added {added_layers_count} PDF trace layer(s).", 5000)
                self.logger.info(f"Successfully added {added_layers_count} PDF trace sources.")
                # Enable the action if it was previously disabled and a project exists
                self.trace_pdf_action.setEnabled(True)

                # --- NEW: Show the first selected page ---
                if selected_indices: # Ensure list is not empty
                    first_page_number = selected_indices[0] + 1 # Convert 0-based index to 1-based page number
                    self.logger.info(f"Automatically displaying first selected PDF page: {first_page_number}")
                    self.visualization_panel.set_pdf_page(first_page_number)
                # --- END NEW ---
            else:
                 self.logger.warning("No trace layers were added despite page selection.")
                 if selected_indices: # Only show message if pages were selected but failed
                     QMessageBox.warning(self, "No Layers Added", "Could not add tracing layers for the selected pages. Check logs for details.")

        else:
            self.logger.info("PDF page selection cancelled.")
            # Keep the PDF loaded in the service, user might want to use it for background.
            # self.pdf_service.clear_document() # Don't clear automatically

# --- End new slot ---

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    @Slot()
    def on_generate_report(self) -> None:
        """Generate a PDF report for the current project.

        For now this is a stub: it just shows a message box so the
        QAction connection works and avoids the AttributeError.
        """
        # Note: QMessageBox was imported at the top earlier
        QMessageBox.information(
            self,
            "DigCalc",
            "Report generation is not implemented yet.\n"
            "This placeholder slot proves the QAction hookup works.",
        )

    # ------------------------------------------------------------------
    # Help Menu Slots
    # ------------------------------------------------------------------
    @Slot()
    def on_about(self) -> None:
        """Show the About dialog."""
        # Note: QMessageBox was imported at the top
        QMessageBox.about(
            self,
            "About DigCalc",
            "DigCalc - Digital Calculation Tool\n\n"
            "Version 0.1 (Placeholder)\n"
            "Built with Python and PySide6.",
        )

    # ------------------------------------------------------------------
    # Shortcut Creation
    # ------------------------------------------------------------------
    # --- NEW: Slot for Alt+V shortcut ---
    @Slot()
    def _toggle_other_layers_visibility(self):
        """Toggles the visibility of all layers except the active tracing layer."""
        if not hasattr(self, "visualization_panel") or not hasattr(self, "layer_tree"):
            self.logger.warning("_toggle_other_layers_visibility called but panel or layer tree missing.")
            return

        active_layer = self.visualization_panel.layer_selector.currentText()
        self.logger.debug(f"Toggling other layers. Active layer: '{active_layer}'")

        # Determine target state: If any non-active layer is checked, uncheck all non-active.
        # Otherwise (all non-active are unchecked), check all non-active.
        target_state = Qt.Checked
        found_visible_other = False
        root = self.layer_tree.invisibleRootItem()
        child_count = root.childCount()
        for i in range(child_count):
            item = root.child(i)
            layer_name = item.text(0)
            if layer_name != active_layer and item.checkState(0) == Qt.Checked:
                found_visible_other = True
                break

        if found_visible_other:
            target_state = Qt.Unchecked
            self.logger.debug("Found visible non-active layer, target state is Unchecked.")
        else:
            self.logger.debug("No visible non-active layers found, target state is Checked.")

        # Apply the target state to all non-active layers
        self.layer_tree.blockSignals(True) # Block signals during batch update
        for i in range(child_count):
            item = root.child(i)
            layer_name = item.text(0)
            if layer_name != active_layer:
                current_state = item.checkState(0)
                if current_state != target_state:
                    item.setCheckState(0, target_state)
                    # Manually trigger the visibility update since signals are blocked
                    self._trigger_layer_visibility_update(layer_name, target_state == Qt.Checked)

        self.layer_tree.blockSignals(False) # Unblock signals
        self.logger.debug("Finished toggling other layer visibility.")
    # --- END NEW SLOT ---

    # --- Moved Helper Method ---
    def _trigger_layer_visibility_update(self, layer_name: str, visible: bool):
        """Helper to explicitly call the scene's visibility function."""
        if hasattr(self, "visualization_panel") and hasattr(self.visualization_panel, "scene_2d") and hasattr(self.visualization_panel.scene_2d, "setLayerVisible"):
            self.visualization_panel.scene_2d.setLayerVisible(layer_name, visible)
        else:
            self.logger.warning("Cannot trigger visibility update: Missing components.")
    # --- End Moved Helper ---

    def _create_shortcuts(self):
        """Create global application shortcuts (Placeholder)."""
        self.logger.debug("Creating application shortcuts...")
        # Example: Shortcut for Fit View (F key) - Needs QShortcut import
        # fit_shortcut = QShortcut(QKeySequence("F"), self)
        # fit_shortcut.activated.connect(self._fit_view_to_scene) # Requires _fit_view_to_scene slot
        # fit_shortcut.setContext(Qt.ApplicationShortcut)

        # --- NEW: Alt+V Shortcut ---
        alt_v_shortcut = QShortcut(QKeySequence("Alt+V"), self)
        # Connect to the newly added slot
        alt_v_shortcut.activated.connect(self._toggle_other_layers_visibility)
        alt_v_shortcut.setContext(Qt.WindowShortcut) # Use Window context so it doesn't interfere globally
        self.logger.debug("Created Alt+V shortcut to toggle other layer visibility.")
        # --- END NEW ---

        self.logger.debug("Shortcuts (currently placeholder) setup complete.")

    # ------------------------------------------------------------------
    # View/Scene Slots
    # ------------------------------------------------------------------
    @Slot()
    def _fit_view_to_scene(self):
        """Fits the 2D view to the current scene rectangle (Placeholder)."""
        self.logger.debug("Fitting view to scene requested (Placeholder)." )
        if hasattr(self.visualization_panel, "view_2d") and \
           hasattr(self.visualization_panel, "scene_2d") and \
           self.visualization_panel.view_2d and \
           self.visualization_panel.scene_2d:
            view = self.visualization_panel.view_2d
            scene = self.visualization_panel.scene_2d
            scene_rect = scene.sceneRect()

            if not scene_rect.isNull() and scene_rect.isValid():
                self.logger.debug(f"Fitting view to scene rect: {scene_rect}")
                view.fitInView(scene_rect, Qt.KeepAspectRatio)
            else:
                self.logger.warning("Cannot fit view: Scene rectangle is null or invalid.")
        else:
            self.logger.warning("Cannot fit view: 2D view or scene not available.")

        # ------------------------------------------------------------------
        # Undo/Redo stack
        # ------------------------------------------------------------------
        from PySide6.QtGui import QShortcut, QUndoStack  # Import both from QtGui

        self.undoStack = QUndoStack(self)

        # Global shortcuts for undo/redo
        QShortcut(QKeySequence.StandardKey.Undo, self, self.undoStack.undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, self.undoStack.redo)

    # --- NEW: Daylight Offset Slot ------------------------------------------------
    @Slot()
    def on_daylight_offset(self):
        """Create daylight offset breakline from the currently selected polyline."""
        # Deferred import to avoid heavy UI cost at startup
        try:
            from digcalc_project.src.ui.dialogs.daylight_dialog import DaylightDialog
        except ImportError as e:
            self.logger.error(f"Could not import DaylightDialog: {e}")
            QMessageBox.critical(self, "DigCalc", "Daylight dialog is unavailable.")
            return

        # Access TracingScene via VisualizationPanel
        scene = getattr(self.visualization_panel, "scene_2d", None)
        if scene is None:
            QMessageBox.warning(self, "DigCalc", "2D Tracing Scene is not active.")
            return

        # Ensure a polyline is selected
        if not hasattr(scene, "current_polyline") or not scene.current_polyline():
            QMessageBox.warning(self, "DigCalc", "Select a polyline first.")
            return

        dlg = DaylightDialog(self)
        if dlg.exec():
            dist, slope = dlg.values()
            if slope == 0:
                QMessageBox.warning(self, "DigCalc", "Slope ratio cannot be zero.")
                return
            try:
                poly = scene.current_polyline_points()
                from digcalc_project.src.tools.daylight_offset_tool import (
                    offset_polygon,
                    project_to_slope,
                )
                off2d = offset_polygon(poly, dist)
                off3d = project_to_slope(off2d, abs(dist), slope)
                if hasattr(scene, "add_offset_breakline"):
                    scene.add_offset_breakline(off3d)
                else:
                    # Fallback: log error if scene lacks helper
                    self.logger.error("TracingScene does not implement add_offset_breakline().")
                    QMessageBox.warning(self, "DigCalc", "Offset breakline feature is not available.")
            except Exception as e:
                self.logger.exception("Failed to create daylight offset: %s", e)
                QMessageBox.critical(self, "DigCalc", f"Failed to create daylight offset.\n{e}")
    # --- END NEW ---

    # ------------------------------------------------------------------
    # Pad elevation handling
    # ------------------------------------------------------------------
    @Slot(list)
    def _on_pad_drawn(self, points2d):
        """Handle closed pad polyline creation, prompting for elevation and adding to scene."""
        from PySide6.QtWidgets import QDialog, QUndoStack  # Local import

        from digcalc_project.src.ui.commands.set_pad_elevation_command import (
            SetPadElevationCommand,
        )
        from digcalc_project.src.ui.dialogs.pad_elevation_dialog import (
            PadElevationDialog,
        )
        # Ensure we have undoStack
        if not hasattr(self, "undoStack"):
            from PySide6.QtWidgets import QUndoStack
            self.undoStack = QUndoStack(self)
        # Dialog handling
        dlg = PadElevationDialog(self._last_pad_elev, self)
        # If user previously chose apply all and we have last elev, auto-apply
        if dlg.apply_to_all() and self._last_pad_elev is not None:
            elev = self._last_pad_elev
        else:
            if dlg.exec() != QDialog.Accepted:
                return
            elev = dlg.value()
            if dlg.apply_to_all():
                self._last_pad_elev = elev

        # Build 3-D vertices list (drop duplicate last point)
        if len(points2d) < 3:
            return  # safety
        pts3d = [(x, y, elev) for x, y in points2d[:-1]]
        scene = getattr(self.visualization_panel, "scene_2d", None)
        if scene is None:
            return
        cmd = SetPadElevationCommand(scene, pts3d)
        self.undoStack.push(cmd)
        # Trigger surface rebuilds or other updates as needed
        if hasattr(self, "project_controller"):
            try:
                self.project_controller.rebuild_surfaces()
            except AttributeError:
                # If method not yet implemented, fallback to generic update
                self.logger.debug("ProjectController lacks rebuild_surfaces(); skipping.")

    # ------------------------------------------------------------------
    # Surface rebuild listener
    # ------------------------------------------------------------------
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
        self._update_analysis_actions_state()

    # ------------------------------------------------------------------
    # Mass-Haul Slot
    # ------------------------------------------------------------------
    @Slot()
    def on_mass_haul(self):
        """Generate mass-haul curve, chart, and CSV report section."""
        from PySide6.QtWidgets import QDialog, QMessageBox

        from digcalc_project.src.core.calculations.mass_haul import build_mass_haul
        from digcalc_project.src.core.reporting.haul_chart import make_mass_haul_chart
        from digcalc_project.src.services.csv_writer import write_mass_haul
        from digcalc_project.src.ui.dialogs.haul_alignment_dialog import (
            HaulAlignmentDialog,
        )

        # Ensure tracing scene and alignment polyline
        if not hasattr(self.visualization_panel, "scene_2d"):
            QMessageBox.warning(self, "DigCalc", "2D scene not available.")
            return

        scene = self.visualization_panel.scene_2d
        if not hasattr(scene, "current_polyline"):
            QMessageBox.warning(self, "DigCalc", "Tracing scene missing polyline helpers.")
            return

        align_item = scene.current_polyline()
        if not align_item:
            QMessageBox.warning(self, "DigCalc", "Select an alignment polyline first.")
            return

        # Fetch the list of QPointF points from the current polyline
        if not hasattr(scene, "current_polyline_points"):
            QMessageBox.warning(self, "DigCalc", "Scene does not expose current_polyline_points().")
            return

        qpts = scene.current_polyline_points()
        pts = [(p.x(), p.y()) for p in qpts]

        # Build shapely LineString
        try:
            from shapely.geometry import (
                LineString,  # local import to avoid heavy cost if not used
            )
            alignment = LineString(pts)
        except Exception as exc:  # pragma: no cover
            QMessageBox.warning(self, "DigCalc", f"Failed to create alignment: {exc}")
            return

        # Ask user for parameters
        dlg = HaulAlignmentDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        interval, free = dlg.values()

        # Surfaces – expect Existing and Design set on project
        project = self.project_controller.get_current_project()
        if not project:
            QMessageBox.warning(self, "DigCalc", "No active project loaded.")
            return
        ref = getattr(project, "existing_surface", None)
        diff = getattr(project, "design_surface", None)
        if not (ref and diff):
            QMessageBox.warning(self, "DigCalc", "Need Existing and Design surfaces in the project.")
            return

        # Perform calculation
        stations = build_mass_haul(ref, diff, alignment, interval, free)

        # Prepare output files
        if hasattr(self.project_controller, "make_temp_path"):
            png_path = self.project_controller.make_temp_path("masshaul.png")
        else:
            # Fallback – store in project folder's reports dir
            report_dir = Path(project.file_path or Path.cwd()).with_suffix("") / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            png_path = str(report_dir / "masshaul.png")

        make_mass_haul_chart(
            [s.station for s in stations],
            [s.cumulative for s in stations],
            free,
            png_path,
        )

        csv_path = png_path.replace(".png", ".csv")
        write_mass_haul(stations, csv_path)

        # Inject into report if available
        if hasattr(self.project_controller, "current_report") and self.project_controller.current_report:
            try:
                self.project_controller.current_report.insert_mass_haul(stations, free)
            except Exception as exc:  # pragma: no cover
                self.logger.error("Failed to insert mass haul into report: %s", exc)

        QMessageBox.information(
            self,
            "DigCalc",
            f"Mass-haul diagram generated.\nPNG: {png_path}\nCSV: {csv_path}",
        )

    # ------------------------------------------------------------------
    #   Export Report
    # ------------------------------------------------------------------

    @Slot()
    def on_export_report(self):
        """Export a PDF report (and companion CSVs) via file dialog."""
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF files (*.pdf)")
        if not path:
            return

        # Gather data from project controller
        proj = getattr(self.project_controller, "project", None)
        calc = getattr(self.project_controller, "last_volume_calc", None)
        slices = getattr(self.project_controller, "last_slice_results", None)
        haul = getattr(self.project_controller, "last_mass_haul", None)

        # Build the PDF story using helpers
        try:
            from reportlab.platypus import SimpleDocTemplate

            from digcalc_project.src.core.reporting.pdf_report import (
                add_job_summary,
                add_mass_haul,
                add_region_table,
                add_slice_table,
            )
            from digcalc_project.src.services.settings_service import SettingsService
        except Exception as exc:  # pragma: no cover – missing optional deps
            QMessageBox.critical(self, "Export Error", f"Required libraries missing: {exc}")
            self.logger.exception("Failed to import reporting dependencies")
            return

        story: list = []
        add_job_summary(story, proj, SettingsService())

        if calc and getattr(calc, "region_results", None):
            add_region_table(story, calc.region_results)

        if slices:
            add_slice_table(story, slices)

        if haul:
            add_mass_haul(story, haul.png_path, haul.free_distance)

        SimpleDocTemplate(path).build(story)

        # Companion CSV exports
        try:
            from pathlib import Path as _Path

            from digcalc_project.src.services.csv_writer import (
                write_mass_haul,
                write_region_table,
                write_slice_table,
            )
        except Exception:
            self.logger.warning("CSV writer helpers not available – skipping CSV companions.")
            write_region_table = write_slice_table = write_mass_haul = None  # type: ignore
            _Path = Path  # fallback

        stem = _Path(path).with_suffix("")
        if calc and getattr(calc, "region_results", None) and write_region_table:
            write_region_table(calc.region_results, f"{stem}_regions.csv")

        if slices and write_slice_table:
            write_slice_table(slices, f"{stem}_slices.csv")

        if haul and write_mass_haul:
            write_mass_haul(haul.stations, f"{stem}_masshaul.csv")

        QMessageBox.information(self, "DigCalc", "Report exported.")

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
            for polys in project.traced_polylines.values():
                if not isinstance(polys, list):
                    continue  # skip invalid format
                for pdata in polys:
                    if isinstance(pdata, dict) and pdata.get("elevation") is not None:
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
    @Slot()
    def on_scale_calibration(self):
        """Handles the 'Calibrate Scale...' menu action."""
        if not self.project_controller or not self.project_controller.get_current_project():
            QMessageBox.warning(self, "No Project", "Please open or create a project first.")
            return

        project = self.project_controller.get_current_project()
        if not project.pdf_background_path:
            QMessageBox.information(self, "No PDF Loaded", "Please load a PDF background image first.")
            return

        # Ensure we have the TracingScene from the VisualizationPanel
        if not hasattr(self.visualization_panel, "scene_2d") or not self.visualization_panel.scene_2d:
            self.logger.error("TracingScene (scene_2d) not found in VisualizationPanel.")
            QMessageBox.critical(self, "Error", "Cannot open scale calibration: 2D scene not available.")
            return

        scene = self.visualization_panel.scene_2d
        # Get current page pixmap from TracingScene or VisualizationPanel if available
        # This part might need adjustment based on how TracingScene stores its current background
        current_bg_pixmap = None
        if scene._background_items: # Accessing protected member, consider a getter in TracingScene
            current_bg_pixmap = scene._background_items[0].pixmap() # Assuming first is current

        if not current_bg_pixmap or current_bg_pixmap.isNull():
            # As a fallback, or if TracingScene doesn't hold the main pixmap directly for calibration preview,
            # re-render the current page from the project's PDF path and DPI.
            # This ensures the dialog gets a pixmap rendered at the correct project DPI.
            if project.pdf_background_path and project.pdf_background_dpi > 0:
                self.logger.info(f"No direct pixmap from scene, re-rendering page {project.pdf_background_page} at {project.pdf_background_dpi} DPI for calibration dialog.")
                # Use PdfService to get the PdfDocument
                _pdf_service = PdfService()  # noqa: F841
                # pdf_service.load_pdf might have already been called, get current doc
                # This needs a way to get the PdfDocument instance that PDFRenderer would use.
                # For now, assuming PDFRenderer can be instantiated if needed.
                try:
                    # We need the PdfDocument that was loaded for the project.
                    # This logic is a bit convoluted because PDFRenderer is created in VisualizationPanel.
                    # A better way would be for PdfService to hold the *current* PdfDocument
                    # that the project is associated with.
                    temp_renderer = PDFRenderer(project.pdf_background_path, dpi=project.pdf_background_dpi)
                    qimage = temp_renderer.get_page_image(project.pdf_background_page)
                    if qimage and not qimage.isNull():
                        current_bg_pixmap = QPixmap.fromImage(qimage)
                    temp_renderer.close() # Important to close it
                except Exception as e_render:
                    self.logger.error(f"Failed to re-render PDF page for calibration dialog: {e_render}")
                    QMessageBox.warning(self, "PDF Error", "Could not prepare PDF preview for calibration.")
                    return # Exit if we can't get a pixmap
            else:
                 QMessageBox.warning(self, "PDF Error", "Could not prepare PDF preview for calibration: No PDF path or DPI.")
                 return

        if not current_bg_pixmap or current_bg_pixmap.isNull():
             QMessageBox.warning(self, "PDF Error", "Could not obtain PDF page image for calibration.")
             return

        # Pass the project instance to the dialog
        dlg = ScaleCalibrationDialog(parent=self, project=project, scene=scene, page_pixmap=current_bg_pixmap)
        dlg.finished.connect(lambda result, dialog=dlg: self._on_scale_dialog_done(dialog, result))
        dlg.exec()

    # ------------------------------------------------------------------
    # Scale-calibration dialog callback (modeless)
    # ------------------------------------------------------------------
    def _on_scale_dialog_done(self, dlg: "ScaleCalibrationDialog", result: int):
        """Handle completion of ScaleCalibrationDialog launched modelessly."""
        from PySide6.QtWidgets import QDialog
        if result != QDialog.DialogCode.Accepted:  # User cancelled
            return

        proj_scale = dlg.result_scale()
        if proj_scale is None:
            return

        current_project = self.project_controller.get_current_project()
        if current_project is not None:
            try:
                current_project.scale = proj_scale
                current_project.is_dirty = True
            except Exception as exc:
                self.logger.error("Failed to set project scale: %s", exc)

        # --- NEW: Refresh scale pill & tracing scene overlay ---
        try:
            self._update_scale_pill()
            if hasattr(self.visualization_panel, "scene_2d") and hasattr(self.visualization_panel.scene_2d, "invalidate_cache"):
                self.visualization_panel.scene_2d.invalidate_cache()
        except Exception as exc:
            self.logger.warning("Failed to refresh scale pill or scene after calibration: %s", exc)
        # --- END NEW ---

        # Settings already persisted by dialog
        try:
            self.statusBar().showMessage(
                f"Scale set: 1 in = {proj_scale.world_per_in:.2f} {proj_scale.world_units}",
                6000,
            )
            # Notify tracing scene so overlay disappears
            scene = getattr(self.visualization_panel, "scene_2d", None)
            if scene and hasattr(scene, "on_scale_calibrated"):
                scene.on_scale_calibrated()
        except Exception as exc:
            self.logger.warning("Status/scene update failed after scale calibration: %s", exc)

    # ------------------------------------------------------------------
    # Scale-calibration action enable/disable helper
    # ------------------------------------------------------------------
    def _update_scale_action_enabled(self, loaded: bool):
        """Enable the Tracing ▸ Calibrate Scale… action based on *loaded*."""
        if hasattr(self, "scale_calib_act") and self.scale_calib_act:
            self.scale_calib_act.setEnabled(bool(loaded))

    # --- NEW: _update_scale_pill method ---
    def _update_scale_pill(self):
        """Updates the scale pill's text and color based on the current project scale."""
        proj = getattr(self.project_controller, "project", None)
        text = "Scale: —"
        # Default style with grey background
        style = "QLabel#scalePill { background-color: #888888; color: white; border-radius: 8px; padding: 2px 5px; }"

        if proj and proj.scale and self.pdf_service:
            # Placeholder for proj.scale.to_short_str()
            # This method should be implemented in your ProjectScale model
            scale_str = "Unknown Scale"
            if hasattr(proj.scale, "to_short_str") and callable(proj.scale.to_short_str):
                try:
                    scale_str = proj.scale.to_short_str()
                except Exception as e:
                    self.logger.error(f"Error calling proj.scale.to_short_str(): {e}")
            elif hasattr(proj.scale, "world_per_paper_in") and proj.scale.world_per_paper_in is not None:
                scale_str = f"{proj.scale.world_per_paper_in:.2f} {proj.scale.world_units}/in"
            elif hasattr(proj.scale, "ratio_denom") and proj.scale.ratio_denom is not None:
                 scale_str = f"1 : {proj.scale.ratio_denom:.0f}"


            text = f"Scale: {scale_str}"

            current_render_dpi = getattr(self.pdf_service, "current_render_dpi", None)
            if current_render_dpi is not None and proj.scale.render_dpi_at_cal is not None:
                dpi_mismatch = abs(current_render_dpi - proj.scale.render_dpi_at_cal) > 0.5
                if dpi_mismatch:
                    # Red for DPI mismatch
                    style = "QLabel#scalePill { background-color: #D88080; color: white; border-radius: 8px; padding: 2px 5px; }"
                else:
                    # Green for valid scale
                    style = "QLabel#scalePill { background-color: #80D880; color: black; border-radius: 8px; padding: 2px 5px; }"
            else:
                # Could be grey if DPIs are not set, but defaults to grey anyway if this block is skipped
                self.logger.warning("Cannot determine DPI mismatch for scale pill: DPI info missing.")


        self.scale_pill.setText(text)
        self.scale_pill.setStyleSheet(style)
        self.logger.debug(f"Scale pill updated: Text='{text}', Style='{style}'")
    # --- END NEW ---
