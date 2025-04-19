#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main window for the DigCalc application.

This module defines the main application window and its components.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# PySide6 imports
from PySide6.QtCore import Qt, QSize, Signal, Slot, QTimer # Added QTimer
from PySide6.QtGui import QIcon, QAction, QKeySequence, QKeyEvent, QActionGroup
from PySide6 import QtWidgets
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QMenu, QToolBar,
    QFileDialog, QMessageBox, QVBoxLayout, QWidget, QDialog,
    QComboBox, QLabel, QGridLayout, QPushButton, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFormLayout, QHBoxLayout, QDialogButtonBox,
    QSplitter, QMenuBar, QStatusBar, QSizePolicy, QTreeWidget, QTreeWidgetItem,
    QGraphicsItem, QGraphicsPathItem
)

# Local imports - Use relative paths
from ..core.importers.csv_parser import CSVParser
from ..core.importers.dxf_parser import DXFParser
from ..core.importers.file_parser import FileParser
from ..core.importers.landxml_parser import LandXMLParser
from ..core.importers.pdf_parser import PDFParser
from ..models.project import Project, PolylineData
from ..models.surface import Surface
from .project_panel import ProjectPanel
from .visualization_panel import VisualizationPanel, HAS_3D
from .properties_dock import PropertiesDock
from ..core.calculations.volume_calculator import VolumeCalculator
from .dialogs.import_options_dialog import ImportOptionsDialog
from .dialogs.report_dialog import ReportDialog
from .dialogs.volume_calculation_dialog import VolumeCalculationDialog
from ..visualization.pdf_renderer import PDFRenderer, PDFRendererError
from .dialogs.elevation_dialog import ElevationDialog
from .dialogs.build_surface_dialog import BuildSurfaceDialog
from ..core.geometry.surface_builder import SurfaceBuilder, SurfaceBuilderError
import numpy as np # Added for type hinting dz_grid etc.

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main application window for DigCalc.
    Handles menus, toolbars, docking widgets (Project Panel, Visualization),
    and overall application workflow for project management and analysis.
    """
    
    def __init__(self):
        """
        Initialize the main window and its components.
        """
        super().__init__()
        
        self.logger = logging.getLogger(__name__)
        self.current_project: Optional[Project] = None
        self._selected_scene_item: Optional[QGraphicsPathItem] = None
        self.pdf_dpi_setting = 300
        self._last_volume_calculation_params: Optional[dict] = None # Cache params
        self._last_dz_cache: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None # Cache dz grid
        
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
        self.menu_bar = self.menuBar()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()
        self._connect_signals()
        self._create_default_project()
        self._update_view_actions_state()
        
        self.logger.debug("MainWindow initialized")
    
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
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
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
        
        # Connect the signal for item changes (checkbox toggles)
        self.layer_tree.itemChanged.connect(self._on_layer_visibility_changed)
        
        # Give visualization panel a reference to the main window (for project access etc)
        # self.visualization_panel.set_main_window(self)
        
        # --- Layer Control Panel Dock ---
        # self.layer_control_panel_widget = self.visualization_panel.get_layer_control_panel()
        # if self.layer_control_panel_widget:
        #     self.layer_dock = QDockWidget("Layers", self)
        #     self.layer_dock.setFeatures(
        #         QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        #     )
        #     self.layer_dock.setWidget(self.layer_control_panel_widget)
        #     # Start hidden, only relevant when PDF is loaded? Or always visible? Let's start visible.
        #     self.addDockWidget(Qt.RightDockWidgetArea, self.layer_dock)
        #     self.layer_dock.setVisible(True)
        # else:
        #     self.layer_dock = None
        #     self.logger.error("Could not create Layer Control dock widget: Panel not found.")
    
    def _connect_signals(self):
        """Connect signals from UI components to main window slots."""
        self.logger.debug("Connecting MainWindow signals...")

        # Connect visualization panel signals
        if hasattr(self.visualization_panel, 'surface_visualization_failed'):
            self.visualization_panel.surface_visualization_failed.connect(self._on_visualization_failed)

        # Connect tracing scene signals (via visualization panel)
        if hasattr(self.visualization_panel, 'scene_2d'):
            self.visualization_panel.scene_2d.polyline_finalized.connect(self._on_polyline_drawn)
            self.visualization_panel.scene_2d.selectionChanged.connect(self._on_item_selected)
        else:
             self.logger.warning("Could not connect tracing scene signals: scene_2d not found on visualization_panel.")

        # Connect layer tree signal
        self.layer_tree.itemChanged.connect(self._on_layer_visibility_changed)

        # --- NEW: Connect PropertiesDock signal --- 
        self.prop_dock.edited.connect(self._apply_elevation_edit)
        # --- END NEW ---

        # Connect project panel signals (if any needed later)
        # self.project_panel.some_signal.connect(self._some_handler)

        # --- NEW: Connect View Actions ---
        if hasattr(self, 'view_2d_action') and self.view_2d_action:
            self.view_2d_action.triggered.connect(self.on_view_2d)
        else:
             logger.error("view_2d_action not found during signal connection.")
        if hasattr(self, 'view_3d_action') and self.view_3d_action:
            self.view_3d_action.triggered.connect(self.on_view_3d)
        else:
             logger.error("view_3d_action not found during signal connection.")
        # --- END NEW ---

        # --- NEW: Connect Cut/Fill Action ---
        self.cutfill_action.toggled.connect(self.visualization_panel.set_cutfill_visible)
        # --- END NEW ---

        self.logger.debug("MainWindow signals connected.")
    
    def _create_actions(self):
        """Create actions for menus and toolbars."""
        # File menu actions
        self.new_project_action = QAction("New Project", self)
        self.new_project_action.triggered.connect(self.on_new_project)
        
        self.open_project_action = QAction("Open Project", self)
        self.open_project_action.triggered.connect(self.on_open_project)
        
        self.save_project_action = QAction("Save Project", self)
        self.save_project_action.triggered.connect(self.on_save_project)
        
        self.exit_action = QAction("Exit", self)
        self.exit_action.triggered.connect(self.close)
        
        # Import actions
        self.import_cad_action = QAction("Import CAD (DXF)", self)
        self.import_cad_action.triggered.connect(self.on_import_cad)
        
        self.import_pdf_action = QAction("Import PDF", self)
        self.import_pdf_action.triggered.connect(self.on_import_pdf)
        
        self.import_landxml_action = QAction("Import LandXML", self)
        self.import_landxml_action.triggered.connect(self.on_import_landxml)
        
        self.import_csv_action = QAction("Import CSV", self)
        self.import_csv_action.triggered.connect(self.on_import_csv)
        
        # --- NEW: Surface Actions ---
        self.build_surface_action = QAction("Build Surface from Layer...", self)
        self.build_surface_action.setStatusTip("Create a TIN surface from a layer of traced polylines with elevation.")
        self.build_surface_action.triggered.connect(self.on_build_surface)
        self.build_surface_action.setEnabled(True)
        # --- END NEW ---

        # Analysis actions
        self.calculate_volume_action = QAction("Calculate Volumes...", self)
        self.calculate_volume_action.setStatusTip("Calculate cut/fill volumes between two surfaces")
        self.calculate_volume_action.triggered.connect(self.on_calculate_volume)
        self.calculate_volume_action.setEnabled(False)
        
        # --- PDF Background Actions ---
        self.load_pdf_background_action = QAction("Load PDF Background...", self)
        self.load_pdf_background_action.setStatusTip("Load a PDF page as a background image for tracing")
        self.load_pdf_background_action.triggered.connect(self.on_load_pdf_background)
        
        self.clear_pdf_background_action = QAction("Clear PDF Background", self)
        self.clear_pdf_background_action.setStatusTip("Remove the current PDF background image")
        self.clear_pdf_background_action.triggered.connect(self.on_clear_pdf_background)
        self.clear_pdf_background_action.setEnabled(False)

        self.next_pdf_page_action = QAction("Next Page", self)
        self.next_pdf_page_action.triggered.connect(self.on_next_pdf_page)
        self.next_pdf_page_action.setEnabled(False)
        
        self.prev_pdf_page_action = QAction("Previous Page", self)
        self.prev_pdf_page_action.triggered.connect(self.on_prev_pdf_page)
        self.prev_pdf_page_action.setEnabled(False)
        
        # --- Tracing Action ---
        self.toggle_tracing_action = QAction("Enable Tracing", self)
        self.toggle_tracing_action.setStatusTip("Toggle snapping and polyline drawing mode")
        self.toggle_tracing_action.setCheckable(True)
        self.toggle_tracing_action.setChecked(False)
        self.toggle_tracing_action.triggered.connect(self.on_toggle_tracing_mode)
        self.toggle_tracing_action.setEnabled(False)
        
        # --- NEW: View Actions --- 
        self.view_group = QActionGroup(self)
        self.view_group.setExclusive(True)

        self.view_2d_action = QAction("Show 2D View", self, checkable=True)
        self.view_2d_action.setStatusTip("Switch to the 2D PDF and tracing view")
        self.view_2d_action.setShortcut("Alt+2")
        self.view_group.addAction(self.view_2d_action)

        self.view_3d_action = QAction("Show 3D View", self, checkable=True)
        self.view_3d_action.setStatusTip("Switch to the 3D terrain view")
        self.view_3d_action.setShortcut("Alt+3")
        self.view_group.addAction(self.view_3d_action)
        # --- END NEW --- 

        # --- NEW: Cut/Fill Map Action ---
        self.cutfill_action = QAction("Show Cut/Fill Map", self, checkable=True)
        self.cutfill_action.setChecked(False)
        self.cutfill_action.setEnabled(False) # Disabled until a map is generated
        self.cutfill_action.setStatusTip("Toggle visibility of the cut/fill heatmap/mesh")
        # --- END NEW ---

        # --- NEW: Surfaces Menu ---
        # Action creation belongs here, menu population happens in _create_menus
        # self.surfaces_menu = self.menu_bar.addMenu("Surfaces") # Moved to _create_menus
        # self.surfaces_menu.addAction(self.build_surface_action) # Moved to _create_menus
        # --- END NEW ---

        # Analysis menu
        self.analysis_menu = self.menu_bar.addMenu("Analysis")
        self.analysis_menu.addAction(self.calculate_volume_action)
        
        # Help menu
        self.help_menu = self.menu_bar.addMenu("Help")
        # Add help actions here
    
    def _create_menus(self):
        """Create the application menus."""
        # Main menu bar
        self.menu_bar = self.menuBar()
        
        # File menu
        self.file_menu = self.menu_bar.addMenu("File")
        self.file_menu.addAction(self.new_project_action)
        self.file_menu.addAction(self.open_project_action)
        self.file_menu.addAction(self.save_project_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)
        
        # Import menu
        self.import_menu = self.menu_bar.addMenu("Import")
        self.import_menu.addAction(self.import_cad_action)
        self.import_menu.addAction(self.import_pdf_action)
        self.import_menu.addAction(self.import_landxml_action)
        self.import_menu.addAction(self.import_csv_action)
        
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
        self.view_menu.addSeparator()
        # Ensure project_dock exists before adding its action
        if hasattr(self, 'project_dock'):
            self.view_menu.addAction(self.project_dock.toggleViewAction())
        else:
             self.logger.error("Project dock not created, cannot add toggle action.")
        # --- Verify Layer Dock Toggle Action ---
        # Check if layer_dock exists before adding its action
        if hasattr(self, 'layer_dock') and self.layer_dock:
             self.view_menu.addAction(self.layer_dock.toggleViewAction())
        else:
             self.logger.error("Layer dock not created or is None, cannot add toggle action.")
        # --- End Verify Layer Dock Toggle Action ---
        # --- Properties Dock Toggle Action --- 
        # Check if prop_dock exists before adding its action
        if hasattr(self, 'prop_dock'):
            view_menu_actions = self.view_menu.actions()
            insert_before_action = None
            layer_toggle_action = self.layer_dock.toggleViewAction() if hasattr(self, 'layer_dock') and self.layer_dock else None

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
        self.view_menu.addAction(self.toggle_tracing_action)
        
        # --- NEW: Surfaces Menu ---
        self.surfaces_menu = self.menu_bar.addMenu("Surfaces")
        self.surfaces_menu.addAction(self.build_surface_action)
        # --- END NEW ---

        # Analysis menu
        self.analysis_menu = self.menu_bar.addMenu("Analysis")
        self.analysis_menu.addAction(self.calculate_volume_action)
        
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
        if hasattr(self, 'visualization_panel') and hasattr(self.visualization_panel, 'layer_selector'):
            self.main_toolbar.addSeparator()
            self.main_toolbar.addWidget(QLabel(" Layer:"))
            self.main_toolbar.addWidget(self.visualization_panel.layer_selector)
        else:
            self.logger.warning("Could not add layer selector to toolbar: visualization_panel or layer_selector not found.")
        
        # Import toolbar
        self.import_toolbar = QToolBar("Import Toolbar")
        self.import_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(self.import_toolbar)
        
        self.import_toolbar.addAction(self.import_cad_action)
        self.import_toolbar.addAction(self.import_pdf_action)
        self.import_toolbar.addAction(self.import_landxml_action)
        self.import_toolbar.addAction(self.import_csv_action)
        
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.calculate_volume_action)
        
        # --- PDF Toolbar --- (Optional, could also be in status bar)
        self.pdf_toolbar = QToolBar("PDF Toolbar")
        self.pdf_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.pdf_toolbar)
        
        self.pdf_toolbar.addAction(self.load_pdf_background_action)
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
        self.pdf_toolbar.addAction(self.toggle_tracing_action)
        
        # --- NEW: Optional View Toolbar --- 
        self.view_toolbar = QToolBar("View Toolbar")
        self.view_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.view_toolbar)
        # Add actions (use icons later if desired)
        self.view_toolbar.addAction(self.view_2d_action)
        self.view_toolbar.addAction(self.view_3d_action)
        # --- END NEW --- 
    
    def _create_statusbar(self):
        """Create the status bar."""
        self.statusBar().showMessage("Ready")
        # Maybe add PDF page info to status bar later?
    
    def _create_default_project(self):
        """Creates a new, empty default project on startup."""
        self._update_project(Project(name="Untitled Project"))
        # Update Layer Panel UI state after potentially loading project/PDF
        # if self.layer_control_panel_widget:
        #     self.layer_control_panel_widget.update_ui_from_scene()
    
    def _update_project(self, project: Optional[Project]):
        """Updates the current project and refreshes relevant UI elements."""
        # Clear PDF before changing project context
        if hasattr(self, 'visualization_panel') and self.visualization_panel:
             self.visualization_panel.clear_pdf_background()
             self._update_pdf_controls()
             self.visualization_panel.clear_all()
        
        self.current_project = project
        self.project_panel.set_project(self.current_project)
        self.visualization_panel.set_project(self.current_project)
        
        # --- Populate Layers Dock --- 
        try:
            self.layer_tree.itemChanged.disconnect(self._on_layer_visibility_changed)
        except RuntimeError:
            pass
        self.layer_tree.clear()
        if hasattr(self, 'visualization_panel') and hasattr(self.visualization_panel, 'layer_selector'):
            for i in range(self.visualization_panel.layer_selector.count()):
                name = self.visualization_panel.layer_selector.itemText(i)
                item = QTreeWidgetItem(self.layer_tree, [name])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Checked)
            self.layer_tree.expandAll()
        try: 
            self.layer_tree.itemChanged.connect(self._on_layer_visibility_changed)
        except RuntimeError:
            self.logger.warning("Error reconnecting layer_tree.itemChanged signal.")
            
        # Update window title and status bar & Redisplay loaded surfaces
        if self.current_project:
             # Display loaded surfaces in visualization panel
             if hasattr(self, 'visualization_panel') and self.visualization_panel:
                 self.logger.info(f"Displaying {len(self.current_project.surfaces)} loaded surfaces...")
                 for surface in self.current_project.surfaces.values():
                     self.visualization_panel.display_surface(surface)
                     # Note: _adjust_view_to_surface is called internally by display_surface on first surface
             
             # Update Title
             title = f"DigCalc - {self.current_project.name}"
             if self.current_project.project_file:
                 title += f" [{Path(self.current_project.project_file).name}]"
             self.setWindowTitle(title)
             self.statusBar().showMessage(f"Project '{self.current_project.name}' loaded.", 5000)
             self.logger.info(f"Switched to project: {self.current_project.name}")
        else:
             self.setWindowTitle("DigCalc - Excavation Takeoff Tool")
             self.statusBar().showMessage("No project loaded.", 5000)
             self.logger.info("Project cleared.")

        # --- Load PDF/Tracing state from Project --- 
        if project and project.pdf_background_path:
            try:
                # Add log here to check the value being passed
                self.logger.info(f"Calling load_pdf_background with path='{project.pdf_background_path}' and dpi={project.pdf_background_dpi}")
                self.visualization_panel.load_pdf_background(
                    project.pdf_background_path, project.pdf_background_dpi
                )
                self.visualization_panel.set_pdf_page(project.pdf_background_page)
                
                if project.traced_polylines:
                    self.logger.info(f"Restoring {sum(len(v) for v in project.traced_polylines.values())} polylines across {len(project.traced_polylines)} layers.")
                    self.visualization_panel.load_and_display_polylines(project.traced_polylines)
                else:
                    self.visualization_panel.clear_polylines_from_scene()
                    
                # TODO: When QML is integrated, call load_polylines_into_qml here
                # self.visualization_panel.load_polylines_into_qml() 
            except Exception as e:
                 self.logger.error(f"Error restoring PDF/Tracing state from project: {e}", exc_info=True)
                 QMessageBox.warning(self, "Project Load Warning", f"Could not restore PDF background or traced lines:\n{e}")
                 if self.visualization_panel.pdf_renderer:
                      self.visualization_panel.clear_pdf_background()
                 project.pdf_background_path = None
                 project.traced_polylines = {}
        else:
            if self.visualization_panel.pdf_renderer:
                 self.visualization_panel.clear_pdf_background()
                 self.visualization_panel.clear_polylines_from_scene()
        
        # Update controls based on final state
        self._update_analysis_actions_state()
        self._update_pdf_controls()

        # Refresh visualization
        self.visualization_panel.clear_all()
        if project:
            # Load surfaces
            surfaces_exist = bool(project.surfaces)
            if surfaces_exist:
                for surface_name, surface in project.surfaces.items():
                    self.logger.info(f"Displaying surface: {surface_name}")
                    self.visualization_panel.display_surface(surface)
            
            # Load PDF background if path exists
            pdf_loaded = False
            if project.pdf_background_path:
                try:
                    self.logger.info(f"Loading PDF background from project: {project.pdf_background_path}")
                    self.visualization_panel.load_pdf_background(
                        project.pdf_background_path,
                        project.pdf_background_dpi
                    )
                    self.visualization_panel.set_pdf_page(project.pdf_background_page)
                    pdf_loaded = True # Mark PDF as successfully loaded
                except Exception as e:
                    self.logger.error(f"Failed to load PDF background from project: {e}")
                    QMessageBox.warning(self, "PDF Error", f"Could not load PDF background:\n{project.pdf_background_path}\nError: {e}")
            
            # Load traced polylines (always load if they exist, visibility handled by view)
            if project.traced_polylines:
                self.visualization_panel.load_and_display_polylines(project.traced_polylines)

            # REMOVED explicit view switching logic from here.
            # Let _update_view_actions_state handle the final state.

        else:
            # No project loaded, clear everything and let actions update
            pass # clear_all() already called

        # Update status bar
        self.statusBar().showMessage(f"Project '{project.name if project else 'None'}' loaded", 5000)
        
        # Update the enabled/checked state of view actions based on loaded content
        self._update_view_actions_state() 

        # Reset cut/fill map state when project changes
        self._clear_cutfill_state()

        self.logger.info(f"Updated project: {project.name if project else 'None'}")

    def _update_analysis_actions_state(self):
        """
        Enable/disable analysis actions based on the current project state.
        Specifically, enables volume calculation if >= 2 surfaces exist.
        """
        can_calculate = bool(self.current_project and len(self.current_project.surfaces) >= 2)
        self.calculate_volume_action.setEnabled(can_calculate)
        self.logger.debug(f"Calculate Volume action enabled state: {can_calculate}")
    
    def _update_pdf_controls(self):
        """Updates the state of PDF navigation and tracing controls."""
        pdf_loaded = False
        page_count = 0
        current_page = 0
        if hasattr(self, 'visualization_panel') and self.visualization_panel.pdf_renderer:
            pdf_loaded = True
            page_count = self.visualization_panel.pdf_renderer.get_page_count()
            current_page = self.visualization_panel.current_pdf_page

        self.logger.debug(f"Updating PDF controls: pdf_loaded={pdf_loaded}, page_count={page_count}, current_page={current_page}")

        self.pdf_toolbar.setVisible(pdf_loaded)

        self.clear_pdf_background_action.setEnabled(pdf_loaded)
        self.prev_pdf_page_action.setEnabled(pdf_loaded and current_page > 1)
        self.next_pdf_page_action.setEnabled(pdf_loaded and current_page < page_count)

        self.pdf_page_spinbox.setEnabled(pdf_loaded)
        if pdf_loaded:
            self.pdf_page_spinbox.blockSignals(True)
            self.pdf_page_spinbox.setRange(1, page_count)
            self.pdf_page_spinbox.setValue(current_page)
            self.pdf_page_spinbox.blockSignals(False)
        else:
            self.pdf_page_spinbox.setRange(0, 0)
            self.pdf_page_spinbox.setValue(0)
            
        self.toggle_tracing_action.setEnabled(pdf_loaded)
        if not pdf_loaded and self.toggle_tracing_action.isChecked():
             self.toggle_tracing_action.setChecked(False)

    # Event handlers
    def on_new_project(self):
        """Handle the 'New Project' action."""
        if not self._confirm_close_project():
            return
            
        # Create the new project object first
        new_project = Project("Untitled Project")
        
        # Clear visualization (including PDF and traces)
        if hasattr(self, 'visualization_panel'):
             self.visualization_panel.clear_all()
             self.visualization_panel.clear_polylines_from_scene() 
            
        # Update the UI with the new project
        self._update_project(new_project)
        
        self.statusBar().showMessage("New project created", 3000)
    
    def on_open_project(self):
        """Handle the 'Open Project' action."""
        if not self._confirm_close_project():
            return

        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "DigCalc Project Files (*.digcalc);;All Files (*)"
        )
        if filename:
            self.logger.info(f"Opening project from: {filename}")
            self.statusBar().showMessage(f"Opening project '{Path(filename).name}'...", 0)
            try:
                project = Project.load(filename)
                if project:
                    self._update_project(project)
                    self.statusBar().showMessage(f"Project '{project.name}' opened successfully.", 5000)
                else:
                    raise RuntimeError("Project.load returned None without raising an exception.")
            except Exception as e:
                self.logger.exception(f"Error opening project file: {filename}")
                QMessageBox.critical(self, "Open Project Error", f"Failed to open project file.\n\nError: {e}")
                self.statusBar().showMessage("Error opening project.", 5000)
                self._create_default_project()
        else:
            self.logger.info("Open project dialog cancelled by user.")
            self.statusBar().showMessage("Open cancelled.", 3000)
    
    def on_save_project(self, save_as=False) -> bool:
        """Handle the 'Save Project' and 'Save Project As' actions."""
        self.logger.debug(f"Save Project action triggered (save_as={save_as})")
        if not self.current_project:
            self.logger.warning("Save attempt failed: No active project.")
            return True
            
        filename = self.current_project.project_file
        
        if save_as or not filename:
            prompt_title = "Save Project As" if save_as else "Save Project"
            filename, _ = QFileDialog.getSaveFileName(
                self, prompt_title, "", "DigCalc Project Files (*.digcalc);;All Files (*)"
            )
            if not filename:
                 self.logger.info("Save project dialog cancelled by user.")
                 self.statusBar().showMessage("Save cancelled.", 3000)
                 return False
            
            if not filename.lower().endswith(".digcalc"):
                 filename += ".digcalc"
        
        self.logger.info(f"Saving project to: {filename}")
        self.statusBar().showMessage(f"Saving project to '{Path(filename).name}'...")
        try:
            self.logger.info(f"Calling _update_project for project: {self.current_project.name}")
            success = self.current_project.save(filename)
            if success:
                self.statusBar().showMessage(f"Project saved successfully to '{Path(filename).name}'", 5000)
                self._update_project(self.current_project) 
                return True
            else:
                 raise RuntimeError("Project save method returned False without raising an exception.")
        except Exception as e:
            error_msg = f"Failed to save project to '{Path(filename).name}'.\n\nError: {str(e)}"
            self.logger.exception(f"Error saving project: {filename}")
            QMessageBox.critical(self, "Save Project Error", error_msg)
            self.statusBar().showMessage("Error saving project.", 5000)
            return False
    
    def on_import_cad(self):
        """Handle CAD import action."""
        if not self.current_project:
            self._create_default_project()
            
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import CAD", "", "CAD Files (*.dxf);;All Files (*)"
        )
        if filename:
            self.logger.info(f"Importing CAD file: {filename}")
            self._import_file(filename, DXFParser)
    
    def on_import_pdf(self):
        """Handle PDF import action."""
        if not self.current_project:
            self._create_default_project()
            
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if filename:
            self.logger.info(f"Importing PDF file: {filename}")
            self._import_file(filename, PDFParser)
    
    def on_import_landxml(self):
        """Handle LandXML import action."""
        if not self.current_project:
            self._create_default_project()
            
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import LandXML", "", "LandXML Files (*.xml);;All Files (*)"
        )
        if filename:
            self.logger.info(f"Importing LandXML file: {filename}")
            self._import_file(filename, LandXMLParser)
    
    def on_import_csv(self):
        """Handle CSV import action."""
        if not self.current_project:
            self._create_default_project()
            
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        if filename:
            self.logger.info(f"Importing CSV file: {filename}")
            self._import_file(filename, CSVParser)
    
    def _import_file(self, filename: str, parser_class=None):
        """
        Internal helper to handle file import logic, including options dialog
        and adding the surface to the project.
        """
        if not self.current_project:
            self.logger.error("Cannot import file: No active project.")
            QMessageBox.warning(self, "No Project", "Please create or open a project before importing files.")
            return

        if not parser_class:
             ext = Path(filename).suffix.lower()
             if ext == '.dxf':
                 parser_class = DXFParser
             elif ext == '.pdf':
                 parser_class = PDFParser
             elif ext == '.xml':
                 parser_class = LandXMLParser
             elif ext == '.csv':
                 parser_class = CSVParser
             else:
                 QMessageBox.warning(self, "Unsupported File", f"File type '{ext}' is not supported.")
                 return

        try:
            parser = parser_class()
            default_surface_name = Path(filename).stem 

            options_dialog = ImportOptionsDialog(self, parser, default_surface_name, filename=filename)
            if options_dialog.exec():
                surface_name = options_dialog.get_surface_name()
                options = options_dialog.get_options()

                self.logger.info(f"Parsing '{filename}' with options: {options}. Surface name: '{surface_name}'")
                self.statusBar().showMessage(f"Importing '{Path(filename).name}' as '{surface_name}'...")

                surface = parser.parse(filename, options)

                if surface:
                    if not surface.points:
                        self.logger.warning(f"Imported surface '{surface_name}' from '{filename}' contains no data points.")
                        QMessageBox.warning(self, "Import Warning", f"The imported surface '{surface_name}' contains no data points.")
                    
                    unique_name = self.current_project.get_unique_surface_name(surface_name)
                    if unique_name != surface_name:
                        self.logger.info(f"Surface name adjusted to '{unique_name}' for uniqueness.")
                        QMessageBox.information(self, "Name Adjusted", f"The surface name was changed to '{unique_name}' to avoid duplicates.")
                    
                    surface.name = unique_name
                    
                    self.current_project.add_surface(surface)
                    # self.project_panel._update_tree() # _update_project handles this
                    # self._update_analysis_actions_state() # Remove direct call

                    self.statusBar().showMessage(f"Successfully imported '{surface.name}'", 5000)
                    self.logger.info(f"Surface '{surface.name}' added to project '{self.current_project.name}'.")

                    # self.visualization_panel.display_surface(surface) # _update_project handles this

                    # --- Call _update_project to refresh everything --- 
                    self._update_project(self.current_project)
                    # --- End Call --- 

                else:
                    raise RuntimeError("Parser returned None, indicating import failure.")

            else:
                self.logger.info("Import cancelled by user.")
                self.statusBar().showMessage("Import cancelled.", 3000)

        except Exception as e:
            self.logger.exception(f"Error importing file '{filename}': {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to import file:\n{e}")
            self.statusBar().showMessage("Import failed.", 3000)
    
    def _should_save_project(self) -> bool:
        """
        Check if the current project should be saved.
        
        Returns:
            bool: True if user wants to save, False otherwise
        """
        response = QMessageBox.question(
            self, "Save Project?",
            "Do you want to save the current project?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if response == QMessageBox.Cancel:
            return False
        elif response == QMessageBox.Yes:
            return True
        else:
            return False

    def _on_visualization_failed(self, surface_name: str, error_msg: str):
        """
        Handle visualization failure.
        
        Args:
            surface_name: Name of the surface that failed to visualize
            error_msg: Error message
        """
        self.statusBar().showMessage(f"Failed to visualize surface '{surface_name}': {error_msg}", 5000)
        self.logger.error(f"Visualization failed for surface '{surface_name}': {error_msg}")

    def on_calculate_volume(self):
        """Handle the 'Calculate Volumes' action."""
        if not self.current_project or len(self.current_project.surfaces) < 2:
            QMessageBox.warning(self, "Cannot Calculate Volumes", 
                                "Please ensure at least two surfaces exist in the project.")
            self.logger.warning("Volume calculation attempted with insufficient surfaces.")
            return

        surface_names = list(self.current_project.surfaces.keys())
        dialog = VolumeCalculationDialog(surface_names, self)
        
        if dialog.exec():
            selection = dialog.get_selected_surfaces()
            resolution = dialog.get_grid_resolution()

            if selection and resolution > 0:
                existing_name = selection['existing']
                proposed_name = selection['proposed']
                self.logger.info(f"Starting volume calculation: Existing='{existing_name}', Proposed='{proposed_name}', Resolution={resolution}")
                self.statusBar().showMessage(f"Calculating volumes (Grid: {resolution})...", 0)

                try:
                    existing_surface = self.current_project.get_surface(existing_name)
                    proposed_surface = self.current_project.get_surface(proposed_name)

                    if not existing_surface or not proposed_surface:
                         raise ValueError("Selected surface(s) not found in project.")
                         
                    if not existing_surface.points or not proposed_surface.points:
                         raise ValueError("Selected surface(s) have no data points for calculation.")

                    calculator = VolumeCalculator()
                    results = calculator.calculate_surface_to_surface(
                        surface1=existing_surface, 
                        surface2=proposed_surface, 
                        grid_resolution=resolution
                    )
                    cut_volume = results['cut_volume']
                    fill_volume = results['fill_volume']
                    net_volume = results['net_volume']

                    self.statusBar().showMessage(f"Calculation complete: Cut={cut_volume:.2f}, Fill={fill_volume:.2f}, Net={net_volume:.2f}", 5000)
                    self.logger.info(f"Volume calculation successful: Cut={cut_volume:.2f}, Fill={fill_volume:.2f}, Net={net_volume:.2f}")
                    
                    report_dialog = ReportDialog(
                        existing_surface_name=existing_name,
                        proposed_surface_name=proposed_name,
                        grid_resolution=resolution,
                        cut_volume=cut_volume,
                        fill_volume=fill_volume,
                        net_volume=net_volume,
                        parent=self
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

    def _confirm_close_project(self) -> bool:
        """
        Checks if the current project has unsaved changes and asks the user
        if they want to save before proceeding (e.g., closing, opening new).
        
        Returns:
            bool: True if the operation should proceed (saved, not saved, or no changes), 
                  False if the user cancels the operation.
        """
        if not self.current_project:
            return True
            
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "The current project has unsaved changes. Do you want to save them before proceeding?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Cancel)

        if reply == QMessageBox.Cancel:
            self.logger.debug("Project close/switch cancelled by user due to unsaved changes.")
            return False
        elif reply == QMessageBox.Save:
            return self.on_save_project()
        elif reply == QMessageBox.Discard:
            self.logger.info("Discarding unsaved changes in current project.")
            return True
            
        return False

    def closeEvent(self, event):
        """Handle the main window close event."""
        self.logger.info("Close event triggered.")
        if self._confirm_close_project():
            if hasattr(self, 'visualization_panel'):
                 self.visualization_panel.clear_pdf_background() 
            self.logger.info("Closing application.")
            event.accept()
        else:
            event.ignore()

    # --- PDF Background and Tracing Handlers ---

    def on_load_pdf_background(self):
        """Handles loading a PDF file as a background."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load PDF Background",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        
        if filename:
            self.logger.info(f"User selected PDF for background: {filename}")
            self.statusBar().showMessage(f"Loading PDF background '{Path(filename).name}'...", 0)
            try:
                self.visualization_panel.load_pdf_background(filename, dpi=self.pdf_dpi_setting)
                if self.current_project:
                    self.current_project.pdf_background_path = filename
                    self.current_project.pdf_background_page = 1
                    self.current_project.pdf_background_dpi = self.pdf_dpi_setting
                    self.current_project.clear_traced_polylines()
                    self.visualization_panel.clear_polylines_from_scene()
                self.statusBar().showMessage(f"Loaded PDF background '{Path(filename).name}' ({self.visualization_panel.pdf_renderer.get_page_count()} pages).", 5000)
            except (FileNotFoundError, PDFRendererError, Exception) as e:
                 self.logger.exception(f"Failed to load PDF background: {e}")
                 QMessageBox.critical(self, "PDF Load Error", f"Failed to load PDF background:\n{e}")
                 self.statusBar().showMessage("Failed to load PDF background.", 5000)
            finally:
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
                  if self.current_project:
                       self.current_project.pdf_background_page = current + 1
                  self._update_pdf_controls()
                  self.statusBar().showMessage(f"Showing PDF page {current + 1}/{total}", 3000)

    def on_prev_pdf_page(self):
        """Handles moving to the previous PDF page."""
        if self.visualization_panel.pdf_renderer:
             current = self.visualization_panel.current_pdf_page
             total = self.visualization_panel.pdf_renderer.get_page_count()
             if current > 1:
                  self.visualization_panel.set_pdf_page(current - 1)
                  if self.current_project:
                       self.current_project.pdf_background_page = current - 1
                  self._update_pdf_controls()
                  self.statusBar().showMessage(f"Showing PDF page {current - 1}/{total}", 3000)
                  
    def on_set_pdf_page_from_spinbox(self, page_number: int):
        """Handles setting the PDF page from the spinbox."""
        if self.pdf_page_spinbox.isEnabled() and page_number > 0:
             self.logger.debug(f"Setting PDF page from spinbox to: {page_number}")
             self.visualization_panel.set_pdf_page(page_number)
             if self.current_project:
                  self.current_project.pdf_background_page = page_number
             self._update_pdf_controls()
             total = self.visualization_panel.pdf_renderer.get_page_count() if self.visualization_panel.pdf_renderer else 0
             self.statusBar().showMessage(f"Showing PDF page {page_number}/{total}", 3000)

    def on_toggle_tracing_mode(self, checked: bool):
        """
        Slot connected to the toggle_tracing_action.
        Enables/disables tracing mode in the VisualizationPanel.
        """
        if hasattr(self, 'visualization_panel'):
            self.visualization_panel.set_tracing_mode(checked)
            self.logger.info(f"Tracing mode {'enabled' if checked else 'disabled'} via MainWindow action.")
            self.toggle_tracing_action.setText("Disable Tracing" if checked else "Enable Tracing")
        else:
            self.logger.warning("Cannot toggle tracing mode: VisualizationPanel not found.")

    @Slot(QTreeWidgetItem, int)
    def _on_layer_visibility_changed(self, item: QTreeWidgetItem, column: int):
        """Slot called when a layer's checkbox state changes in the dock."""
        if column == 0:
            layer_name = item.text(0)
            is_visible = item.checkState(0) == Qt.Checked
            self.logger.debug(f"Layer '{layer_name}' visibility toggle -> {is_visible}")
            if hasattr(self, 'visualization_panel') and hasattr(self.visualization_panel, 'scene_2d') and hasattr(self.visualization_panel.scene_2d, 'setLayerVisible'):
                self.visualization_panel.scene_2d.setLayerVisible(layer_name, is_visible)
            else:
                self.logger.warning("Cannot toggle layer visibility: Visualization panel, scene_2d, or setLayerVisible method not found.")

    @Slot(list, QGraphicsPathItem)
    def _on_polyline_drawn(self, points_qpointf: list, item: QGraphicsPathItem):
        """
        Handles the polyline_finalized signal from TracingScene.
        Prompts for elevation and adds the polyline data to the project.
        Stores the final index back into the QGraphicsPathItem.
        """
        if not self.current_project:
            logger.warning("Polyline drawn but no active project.")
            if item.scene(): item.scene().removeItem(item)
            return

        layer_name = item.data(0)
        if layer_name is None:
             logger.error("Finalized polyline item is missing layer data! Assigning to 'Default'.")
             layer_name = "Default"

        point_tuples = [(p.x(), p.y()) for p in points_qpointf]

        if len(point_tuples) < 2:
             logger.warning(f"Ignoring finalized polyline with < 2 points for layer '{layer_name}'.")
             if item.scene(): item.scene().removeItem(item)
             return

        dlg = ElevationDialog(self)
        dialog_result = dlg.exec()
        elevation = dlg.value() if dialog_result == QtWidgets.QDialog.Accepted else None
        logger.debug(f"Elevation dialog result: Accepted={dialog_result == QtWidgets.QDialog.Accepted}, Elevation={elevation}")

        polyline_data: PolylineData = {"points": point_tuples, "elevation": elevation}

        new_index: Optional[int] = self.current_project.add_traced_polyline(
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
        """
        Handles the selectionChanged signal from the TracingScene.
        Loads the selected polyline's data into the PropertiesDock.
        Stores a reference to the selected scene item.
        """
        logger.debug(f"--- _on_item_selected --- START --- Item: {item}")

        if not self.current_project:
            self._selected_scene_item = None # Clear selection reference
            logger.warning("_on_item_selected called but no current project.")
            if hasattr(self, 'prop_dock'): self.prop_dock.clear_selection()
            if hasattr(self, 'prop_dock'): self.prop_dock.hide()
            logger.debug("--- _on_item_selected --- END (no project) ---")
            return
        if not hasattr(self, 'prop_dock') or not self.prop_dock:
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
                logger.debug(f"  Attempting to load data for Layer=\'{layer_name}\', Index={index}")
                try:
                    # Retrieve the polyline data - could be dict or list
                    if layer_name not in self.current_project.traced_polylines or \
                       not isinstance(self.current_project.traced_polylines[layer_name], list) or \
                       index >= len(self.current_project.traced_polylines[layer_name]):
                        logger.warning(f"  Invalid layer/index lookup ({layer_name}/{index}).")
                        raise IndexError(f"Invalid layer/index ({layer_name}/{index}) for selection.")

                    poly_data = self.current_project.traced_polylines[layer_name][index]
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

                    logger.debug(f"  Calling prop_dock.load_polyline with: layer=\'{layer_name}\', index={index}, elevation={elevation}")
                    self.prop_dock.load_polyline(layer_name, index, elevation)

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
        """
        Handles the \'edited\' signal from PropertiesDock.
        Updates the elevation in the current project\'s data model.
        """
        # --- DEBUG: Log entry ---
        logger.debug(f"_apply_elevation_edit called: Layer={layer_name}, Index={index}, New Elevation={new_elevation}")
        # --- END DEBUG ---

        if not self.current_project:
            logger.error("Cannot apply elevation edit: No current project.")
            QMessageBox.critical(self, "Error", "No active project to apply changes to.")
            return

        try:
            poly_list = self.current_project.traced_polylines.get(layer_name)
            if poly_list is None or not isinstance(poly_list, list) or index >= len(poly_list):
                raise IndexError(f"Invalid layer '{layer_name}' or index {index} for elevation edit.")

            if not isinstance(poly_list[index], dict):
                raise TypeError(f"Polyline data at {layer_name}[{index}] is not a dictionary.")

            current_elevation = poly_list[index].get("elevation")

            # --- DEBUG: Log values before comparison ---
            logger.debug(f"Comparing elevation for {layer_name}[{index}]: Current={current_elevation} (Type: {type(current_elevation)}), New={new_elevation} (Type: {type(new_elevation)})")
            # --- END DEBUG ---

            elevation_changed = False
            if current_elevation is None and new_elevation is not None:
                elevation_changed = True
            elif current_elevation is not None and new_elevation is None:
                 elevation_changed = True
            elif current_elevation is not None and new_elevation is not None:
                 if abs(current_elevation - new_elevation) > 1e-6:
                     elevation_changed = True
            # --- END FIX ---

            if elevation_changed:
                poly_list[index]["elevation"] = new_elevation
                # self.current_project.is_modified = True # Done by bump revision
                
                # --- Bump Revision --- 
                new_revision = self.current_project._bump_layer_revision(layer_name) # Call project helper
                # --- End Bump ---
                
                logger.info(f"Updated elevation for polyline (Layer: {layer_name}, Index: {index}) to {new_elevation}. New layer revision: {new_revision}")
                self.statusBar().showMessage(f"Elevation updated for {layer_name} polyline {index}.", 3000)

                # Reload properties dock after update
                if self._selected_scene_item and \
                   self._selected_scene_item.data(0) == layer_name and \
                   self._selected_scene_item.data(1) == index:
                    if hasattr(self, 'prop_dock') and self.prop_dock:
                         self.prop_dock.load_polyline(layer_name, index, new_elevation)
                         logger.debug("Refreshed PropertiesDock with updated elevation.")
                    else:
                         logger.warning("Properties dock not found, cannot refresh after edit.")

                # --- Trigger Rebuild --- 
                self._queue_surface_rebuilds_for_layer(layer_name)
                # --- End Trigger --- 
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
        if self.current_project:
             surface_layers = list(self.current_project.surfaces.keys())
             trace_layers = self.current_project.get_layers()
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
        if not self.current_project or not self._selected_scene_item:
            self.logger.warning("Attempted to delete polyline, but no project or item selected.")
            return

        layer_name = self._selected_scene_item.data(0)
        index = self._selected_scene_item.data(1)

        if layer_name is None or index is None:
            self.logger.error("Selected item is missing layer or index data, cannot delete.")
            self._selected_scene_item = None
            if hasattr(self, 'prop_dock'): # Check if dock exists
                self.prop_dock.clear_selection()
                self.prop_dock.hide()
            return

        # Confirm deletion with user
        reply = QMessageBox.question(
            self,
            "Delete Polyline",
            f"Are you sure you want to delete the selected polyline from layer \'{layer_name}\' (Index: {index})?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.logger.info(f"Attempting to delete polyline: Layer='{layer_name}', Index={index}")
            layer_name_to_rebuild = layer_name # Store before item might be invalidated
            
            # --- Remove from Project --- 
            removed_from_project = self.current_project.remove_polyline(layer_name, index)

            if removed_from_project:
                # --- Remove from Scene --- 
                scene = self._selected_scene_item.scene()
                if scene:
                    scene.removeItem(self._selected_scene_item)
                    self.logger.info("Removed polyline item from scene.")
                else:
                    self.logger.warning("Could not remove item from scene (item has no scene).")

                # --- Update UI --- 
                if hasattr(self, 'prop_dock'):
                    self.prop_dock.clear_selection()
                    self.prop_dock.hide()
                if hasattr(self, 'project_panel'):
                    self.project_panel._update_tree()
                self.statusBar().showMessage(f"Deleted polyline from '{layer_name}'.", 3000)
                
                # --- Trigger Rebuild --- 
                self._queue_surface_rebuilds_for_layer(layer_name_to_rebuild)
                # --- End Trigger --- 
                
                # --- Reload polylines for the affected layer --- (Optional, but good for indices)
                # if hasattr(self, 'visualization_panel'):
                #     self.logger.info("Reloading all traced polylines in scene to update indices after deletion.")
                #     self.visualization_panel.load_and_display_polylines(self.current_project.traced_polylines)
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
        if hasattr(self, 'visualization_panel'):
            self.logger.debug("Switching to 2D view.")
            self.visualization_panel.show_2d_view()
            self._update_view_actions_state() # Update check states
        else:
            self.logger.error("Cannot switch to 2D view: VisualizationPanel not found.")

    @Slot()
    def on_view_3d(self):
        """Switch to the 3D (Terrain) view."""
        if hasattr(self, 'visualization_panel'):
            self.logger.debug("Switching to 3D view.")
            self.visualization_panel.show_3d_view()
            self._update_view_actions_state() # Update check states
        else:
            self.logger.error("Cannot switch to 3D view: VisualizationPanel not found.")

    def _update_view_actions_state(self):
        """
        Updates the enabled and checked state of the view toggle actions (2D/3D)
        based on available content (PDF/Surfaces) and the current view mode.
        """
        # Check if actions exist before proceeding
        if not hasattr(self, 'view_2d_action') or not hasattr(self, 'view_3d_action'):
            logger.warning("_update_view_actions_state called before view actions were created.")
            return

        has_pdf = False
        has_surfaces = False
        current_view = 'unknown' # Default state

        if hasattr(self, 'visualization_panel'):
            has_pdf = self.visualization_panel.has_pdf()
            has_surfaces = self.visualization_panel.has_surfaces()
            current_view = self.visualization_panel.current_view()
            logger.debug(f"Updating view actions: has_pdf={has_pdf}, has_surfaces={has_surfaces}, current_view='{current_view}'")
        else:
            logger.warning("Cannot update view actions state: VisualizationPanel not found.")

        # Enable actions based on content
        self.view_2d_action.setEnabled(has_pdf)
        self.view_3d_action.setEnabled(has_surfaces)

        # Set checked state based on current view
        self.view_2d_action.setChecked(current_view == '2d' and has_pdf)
        self.view_3d_action.setChecked(current_view == '3d' and has_surfaces)

        # Ensure at least one is checked if content exists, default to 3D if both possible?
        # Or handle the case where switching is impossible. If !has_pdf & !has_surfaces, both disabled.
        if not self.view_2d_action.isChecked() and not self.view_3d_action.isChecked():
             # If neither is checked, but one *could* be, maybe force a default?
             # For now, just log. The logic in show_2d/3d should handle the actual switch.
             logger.debug("Neither view action is checked after update.")

    # --- END NEW ---

    # --- NEW: Slot for Building Surface --- 
    @Slot()
    def on_build_surface(self):
        """Handles the 'Build Surface from Layer' action."""
        if not self.current_project or not self.current_project.traced_polylines:
            QMessageBox.information(self, "Build Surface", "No traced polylines available...")
            logger.warning("Build Surface action triggered but no traced polylines exist.")
            return

        # --- FIX: Handle list/dict format when checking for elevation --- 
        layers_with_elevation = []
        for layer, polys in self.current_project.traced_polylines.items():
            if not isinstance(polys, list): # Skip if layer data isn't a list
                logger.warning(f"Layer '{layer}' data is not a list, skipping elevation check.")
                continue
            has_elevation = False
            for p_data in polys:
                # Check if p_data is a dict AND has a non-None elevation
                if isinstance(p_data, dict) and p_data.get('elevation') is not None:
                    has_elevation = True
                    break # Found one with elevation in this layer
                # Ignore lists or dicts without elevation for this check
            if has_elevation:
                layers_with_elevation.append(layer)
        # --- END FIX ---

        if not layers_with_elevation:
             QMessageBox.information(self, "Build Surface", "No layers with elevation data found...")
             logger.warning("Build Surface action triggered but no layers have elevation data.")
             return

        dlg = BuildSurfaceDialog(self.current_project, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            selected_layer = dlg.layer()
            surface_name = dlg.surface_name()

            if not selected_layer or not surface_name:
                 logger.error("Build Surface dialog accepted but returned invalid layer or name.")
                 return

            unique_surface_name = self.current_project.get_unique_surface_name(surface_name)
            if unique_surface_name != surface_name:
                 logger.warning(f"Surface name '{surface_name}' adjusted to '{unique_surface_name}' for uniqueness.")
                 surface_name = unique_surface_name

            logger.info(f"Starting surface build: Source='{selected_layer}', Target='{surface_name}'")
            self.statusBar().showMessage(f"Building surface '{surface_name}' from layer '{selected_layer}'...")

            try:
                polylines_to_build = self.current_project.traced_polylines.get(selected_layer, [])
                # Filter again here to ensure only dicts with elevation go to builder
                valid_polys_for_build = [
                    p for p in polylines_to_build
                    if isinstance(p, dict) and p.get('elevation') is not None
                ]
                if not valid_polys_for_build:
                    raise SurfaceBuilderError(f"Layer '{selected_layer}' has no polylines with elevation data suitable for building.")

                # --- Get current layer revision for the build --- 
                current_layer_rev = self.current_project.layer_revisions.get(selected_layer, 0)
                self.logger.debug(f"Building surface '{surface_name}' from layer '{selected_layer}' at revision {current_layer_rev}")

                surface = SurfaceBuilder.build_from_polylines(
                    layer_name=selected_layer, 
                    polylines_data=valid_polys_for_build, 
                    revision=current_layer_rev # Pass the revision
                )
                surface.name = surface_name
                # source_layer_name and source_layer_revision are now set by the builder
                self.current_project.add_surface(surface)
                if hasattr(self, 'visualization_panel'):
                    displayed = self.visualization_panel.display_surface(surface)
                    if displayed:
                         logger.info(f"Successfully displayed new surface '{surface.name}'.")
                    else:
                         logger.warning(f"Surface '{surface.name}' added to project, but visualization failed.")
                         QMessageBox.warning(self, "Visualization Warning", f"Surface '{surface.name}' was created but could not be displayed in the 3D view.")
                if hasattr(self, 'project_panel'):
                    self.project_panel._update_tree()
                self.statusBar().showMessage(f"Surface '{surface_name}' created from layer '{selected_layer}'.", 5000)

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
        if not self.current_project or not self._rebuild_needed_layers:
            if self._rebuild_needed_layers:
                 self.logger.warning("Rebuild queue processed but no current project.")
                 self._rebuild_needed_layers.clear()
            return

        layers_to_process = self._rebuild_needed_layers.copy()
        self._rebuild_needed_layers.clear() # Clear queue before processing

        self.logger.info(f"Processing rebuild queue for layers: {layers_to_process}")
        surfaces_to_check = list(self.current_project.surfaces.values()) # Copy to avoid issues if modified

        processed_count = 0
        for surf in surfaces_to_check:
            # Check if surface exists in project (might have been deleted)
            if surf.name not in self.current_project.surfaces:
                 continue
            if surf.source_layer_name in layers_to_process:
                self._rebuild_surface_now(surf.name)
                processed_count += 1

        self.logger.info(f"Finished processing rebuild queue. Rebuilt {processed_count} surfaces derived from {layers_to_process}.")

    def _rebuild_surface_now(self, surface_name: str):
        """Rebuilds a specific surface if necessary."""
        if not self.current_project: return
        surf = self.current_project.surfaces.get(surface_name)

        if not surf or not surf.source_layer_name:
            self.logger.debug(f"Skipping rebuild for '{surface_name}': No surface or source layer.")
            return

        layer = surf.source_layer_name
        current_layer_rev = self.current_project.layer_revisions.get(layer, 0)

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
                  self.current_project.is_modified = True
                  if hasattr(self.project_panel, '_update_tree_item_text'):
                      self.project_panel._update_tree_item_text(surf.name)
             return
        
        self.logger.debug(f" -> Surface '{surface_name}' needs rebuild (SavedRev={surf.source_layer_revision} != CurrentRev={current_layer_rev}).")
        # ... (rest of rebuild logic) ...

        polys_data = self.current_project.traced_polylines.get(layer, [])
        valid_polys = [
            p for p in polys_data
            if isinstance(p, dict) and p.get("elevation") is not None
        ]

        if not valid_polys:
            logger.warning(f"Layer '{layer}' has no valid polylines with elevation to rebuild surface '{surface_name}'. Marking as stale.")
            surf.is_stale = True
            self.current_project.is_modified = True
            if hasattr(self.project_panel, '_update_tree_item_text'): # Check if method exists
                self.project_panel._update_tree_item_text(surf.name)
            return

        self.statusBar().showMessage(f"Rebuilding surface '{surface_name}' from layer '{layer}'...", 0)
        try:
            # Use SurfaceBuilder directly
            new_surf = SurfaceBuilder.build_from_polylines(layer, valid_polys, current_layer_rev)
            new_surf.name = surface_name # Keep the original name
            new_surf.is_stale = False # Mark as not stale

            # Replace in project
            self.current_project.surfaces[surface_name] = new_surf
            self.current_project.is_modified = True

            # Update visualization - Use update_surface_mesh (defined in Part 4)
            if hasattr(self.visualization_panel, 'update_surface_mesh'):
                self.visualization_panel.update_surface_mesh(new_surf)
            else:
                 logger.error("VisualizationPanel does not have 'update_surface_mesh' method.")

            # Update project panel
            if hasattr(self.project_panel, '_update_tree_item_text'): # Check if method exists
                self.project_panel._update_tree_item_text(new_surf.name)

            self.logger.info(f"Successfully rebuilt surface '{surface_name}' from layer '{layer}' (New Rev: {current_layer_rev}).")
            self.statusBar().showMessage(f"Surface '{surface_name}' rebuilt successfully.", 3000)

        except SurfaceBuilderError as e:
            logger.error(f"Failed to rebuild surface '{surface_name}': {e}")
            QMessageBox.warning(self, "Rebuild Failed", f"Could not rebuild surface '{surface_name}':\n{e}")
            self.statusBar().showMessage(f"Rebuild failed for '{surface_name}'.", 5000)
            surf.is_stale = True
            self.current_project.is_modified = True
            if hasattr(self.project_panel, '_update_tree_item_text'): # Check if method exists
                self.project_panel._update_tree_item_text(surf.name)
        except Exception as e:
            logger.exception(f"Unexpected error rebuilding surface '{surface_name}'")
            QMessageBox.critical(self, "Rebuild Error", f"An unexpected error occurred rebuilding '{surface_name}':\n{e}")
            self.statusBar().showMessage(f"Rebuild error for '{surface_name}'.", 5000)
            surf.is_stale = True
            self.current_project.is_modified = True
            if hasattr(self.project_panel, '_update_tree_item_text'): # Check if method exists
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
        """
        Handles the results of a volume calculation, including updating the cut/fill map.
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


class VolumeCalculationDialog(QDialog):
    """Dialog for selecting surfaces and parameters for volume calculation."""
    def __init__(self, surface_names: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Calculate Volumes")
        self.surface_names = surface_names
        self.setMinimumWidth(350) # Set a minimum width

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(10)

        # --- Surface Selection ---
        self.combo_existing = QComboBox(self)
        self.combo_existing.addItems(self.surface_names)
        self.combo_existing.setToolTip("Select the surface representing the original ground or starting condition.")
        form_layout.addRow("Existing Surface:", self.combo_existing)

        self.combo_proposed = QComboBox(self)
        self.combo_proposed.addItems(self.surface_names)
        self.combo_proposed.setToolTip("Select the surface representing the final grade or proposed design.")
        form_layout.addRow("Proposed Surface:", self.combo_proposed)

        # --- Grid Resolution ---
        self.spin_resolution = QDoubleSpinBox(self)
        self.spin_resolution.setRange(0.1, 1000.0) # Sensible range
        self.spin_resolution.setValue(5.0) # Default value
        self.spin_resolution.setDecimals(2)
        self.spin_resolution.setSingleStep(0.5)
        self.spin_resolution.setToolTip("Specify the size of the grid cells for volume calculation (e.g., 5.0 means 5x5 units). Smaller values increase accuracy but take longer.")
        form_layout.addRow("Grid Resolution (units):", self.spin_resolution)
        
        # Align labels to the right
        for i in range(form_layout.rowCount()):
            label_item = form_layout.itemAt(i, QFormLayout.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addLayout(form_layout)

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Attempt to pre-select surfaces
        self._preselect_surfaces()

        # Connect signals for validation AFTER pre-selection attempt
        self.combo_existing.currentIndexChanged.connect(self._validate_selection)
        self.combo_proposed.currentIndexChanged.connect(self._validate_selection)
        self._validate_selection() # Initial validation
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.adjustSize() # Adjust size to fit contents

    def _preselect_surfaces(self):
        """Attempts to pre-select likely existing and proposed surfaces based on name."""
        existing_keywords = ["existing", "eg", "topo", "original"]
        proposed_keywords = ["proposed", "design", "fg", "final"]

        found_existing = None
        found_proposed = None

        # Find first match for existing
        for name in self.surface_names:
            name_lower = name.lower()
            if any(keyword in name_lower for keyword in existing_keywords):
                found_existing = name
                break
        
        # Find first match for proposed (must be different from existing)
        for name in self.surface_names:
            name_lower = name.lower()
            if any(keyword in name_lower for keyword in proposed_keywords):
                if name != found_existing: # Ensure it's not the same surface
                    found_proposed = name
                    break

        # Set selections if found
        if found_existing:
            self.combo_existing.setCurrentText(found_existing)
            logger.debug(f"Pre-selected Existing Surface: {found_existing}")
        
        if found_proposed:
            self.combo_proposed.setCurrentText(found_proposed)
            logger.debug(f"Pre-selected Proposed Surface: {found_proposed}")
        elif len(self.surface_names) > 1 and found_existing: 
            # If only existing was found, try setting proposed to the first *different* surface
            first_different = next((s for s in self.surface_names if s != found_existing), None)
            if first_different:
                self.combo_proposed.setCurrentText(first_different)
                logger.debug(f"Pre-selected Proposed Surface (fallback): {first_different}")

    def _validate_selection(self):
        """Enable OK button only if different surfaces are selected."""
        valid = (self.combo_existing.currentText() != self.combo_proposed.currentText())
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(valid)
        # Provide visual feedback or a status tip if desired
        if not valid and len(self.surface_names) > 1:
            # Optional: Add a small label or status tip indicating the issue
            # self.statusBar().showMessage("Existing and Proposed surfaces must be different.", 2000)
            pass # Simple button disabling is usually sufficient

    def get_selected_surfaces(self) -> Optional[Dict[str, str]]:
        """Get the names of the selected existing and proposed surfaces."""
        if self._validate_selection and self.combo_existing.currentText() and self.combo_proposed.currentText():
             return {
                 'existing': self.combo_existing.currentText(),
                 'proposed': self.combo_proposed.currentText()
             }
        return None

    def get_grid_resolution(self) -> float:
        """Get the selected grid resolution."""
        return self.spin_resolution.value()

    def should_generate_map(self) -> bool:
        """Get the state of the checkbox for generating a cut/fill map."""
        return self.button_box.button(QDialogButtonBox.Ok).isEnabled()

class ImportOptionsDialog(QDialog):
    """Dialog for configuring import options for various file types."""
    def __init__(self, parent, parser, default_name, filename: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Import Options")
        self.parser = parser
        self.filename = filename # Store filename for potential use (e.g., CSV header peek)
        self.setMinimumWidth(400) # Increase minimum width for better layout

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(10)

        # --- Surface Name ---
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setToolTip("Enter a name for the surface to be created from this file.")
        form_layout.addRow("Surface Name:", self.name_edit)

        # --- Parser-Specific Options ---
        self._add_parser_options(form_layout)
        
        # Align labels to the right
        for i in range(form_layout.rowCount()):
            label_item = form_layout.itemAt(i, QFormLayout.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addLayout(form_layout)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.adjustSize() # Adjust size to fit contents

    def get_surface_name(self) -> str:
        """Get the desired surface name entered by the user."""
        return self.name_edit.text().strip() or "Imported Surface" # Provide a fallback

    def _add_parser_options(self, layout: QFormLayout):
        """Dynamically add options based on the parser type."""
        if isinstance(self.parser, CSVParser):
            # --- CSV Specific Options ---
            self.combo_x = QComboBox()
            self.combo_y = QComboBox()
            self.combo_z = QComboBox()
            self.spin_skip_rows = QSpinBox()
            self.spin_skip_rows.setRange(0, 100)
            self.spin_skip_rows.setValue(0)
            self.spin_skip_rows.setToolTip("Number of header rows to skip before data starts.")
            self.combo_delimiter = QComboBox()
            self.combo_delimiter.addItems([",", "\t", " ", ";"])
            self.combo_delimiter.setEditable(True)
            self.combo_delimiter.setToolTip("Select or enter the character separating columns.")

            layout.addRow("Delimiter:", self.combo_delimiter)
            layout.addRow("Skip Header Rows:", self.spin_skip_rows)
            layout.addRow("X Column:", self.combo_x)
            layout.addRow("Y Column:", self.combo_y)
            layout.addRow("Z/Elevation Column:", self.combo_z)
            
            self.combo_x.setToolTip("Select the column containing X coordinates.")
            self.combo_y.setToolTip("Select the column containing Y coordinates.")
            self.combo_z.setToolTip("Select the column containing Z (elevation) values.")

            # Populate column dropdowns if filename is available
            if self.filename:
                self._update_csv_column_options()
                self.spin_skip_rows.valueChanged.connect(self._update_csv_column_options)
                self.combo_delimiter.currentTextChanged.connect(self._update_csv_column_options)
                
        # Add elif blocks here for other parsers (DXFParser, PDFParser, etc.)
        # elif isinstance(self.parser, DXFParser):
        #     # Add DXF specific options (e.g., layer selection)
        #     pass 
        else:
            # Default/Fallback message if no specific options needed
            no_options_label = QLabel("No specific import options available for this file type.")
            no_options_label.setStyleSheet("font-style: italic; color: gray;")
            layout.addRow(no_options_label)

    def _update_csv_column_options(self):
        """Read CSV headers and update column selection comboboxes."""
        if not self.filename or not isinstance(self.parser, CSVParser):
            return

        skip_rows = self.spin_skip_rows.value()
        delimiter_text = self.combo_delimiter.currentText()
        # Explicitly checking against correct string literals
        if delimiter_text == "\t":
            delimiter = '\t'
        elif delimiter_text == " ":
            delimiter = ' '
        else:
            delimiter = delimiter_text # Use the text directly (covers comma, semicolon, custom)
            
        if not delimiter: # Handle empty case
            delimiter = ',' # Default to comma if empty

        try:
            headers = self.parser.peek_headers(self.filename, num_lines=skip_rows + 1, delimiter=delimiter)
            if headers:
                # Clear existing items before adding new ones
                self.combo_x.clear()
                self.combo_y.clear()
                self.combo_z.clear()
                # Populate with actual headers
                self.combo_x.addItems(headers)
                self.combo_y.addItems(headers)
                self.combo_z.addItems(headers)
                self._try_preselect_columns(headers) # Attempt to guess columns
            else:
                # Handle case where no headers could be read (e.g., file error, wrong delimiter/skip)
                 self.combo_x.clear()
                 self.combo_y.clear()
                 self.combo_z.clear()
                 self.combo_x.addItem("- Error reading headers -")
                 self.combo_y.addItem("- Error reading headers -")
                 self.combo_z.addItem("- Error reading headers -")
        except Exception as e:
            # Log the error, maybe show a non-modal status? 
            print(f"Error peeking headers: {e}") # Replace with proper logging
            self.combo_x.clear()
            self.combo_y.clear()
            self.combo_z.clear()
            self.combo_x.addItem("- Error reading headers -")
            self.combo_y.addItem("- Error reading headers -")
            self.combo_z.addItem("- Error reading headers -")

    def _try_preselect_columns(self, headers: List[str]):
        """Attempt to automatically select common column names."""
        common_x = ['x', 'easting', 'lon']
        common_y = ['y', 'northing', 'lat']
        common_z = ['z', 'elevation', 'elev', 'height']

        for i, header in enumerate(headers):
            h_lower = header.lower()
            if any(term in h_lower for term in common_x) and self.combo_x.currentIndex() == -1:
                self.combo_x.setCurrentIndex(i)
            if any(term in h_lower for term in common_y) and self.combo_y.currentIndex() == -1:
                self.combo_y.setCurrentIndex(i)
            if any(term in h_lower for term in common_z) and self.combo_z.currentIndex() == -1:
                self.combo_z.setCurrentIndex(i)

    def get_options(self) -> Dict:
        """Get the parser-specific options selected by the user."""
        options = {}
        if isinstance(self.parser, CSVParser):
            options['delimiter'] = self.combo_delimiter.currentText() # Pass raw text back
            options['skip_rows'] = self.spin_skip_rows.value()
            options['x_col'] = self.combo_x.currentText()
            options['y_col'] = self.combo_y.currentText()
            options['z_col'] = self.combo_z.currentText()
        # Add elif blocks for other parsers
        # elif isinstance(self.parser, DXFParser):
        #     options['layer'] = self.layer_combo.currentText()
        return options 