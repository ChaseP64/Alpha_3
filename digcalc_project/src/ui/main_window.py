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
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QMenu, QToolBar,
    QFileDialog, QMessageBox, QVBoxLayout, QWidget, QDialog,
    QComboBox, QLabel, QGridLayout, QPushButton, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFormLayout, QHBoxLayout, QDialogButtonBox,
    QSplitter, QMenuBar, QStatusBar, QSizePolicy
)

# Local imports
from src.core.importers.csv_parser import CSVParser
from src.core.importers.dxf_parser import DXFParser
from src.core.importers.file_parser import FileParser
from src.core.importers.landxml_parser import LandXMLParser
from src.core.importers.pdf_parser import PDFParser
from src.models.project import Project
from src.models.surface import Surface
from src.ui.project_panel import ProjectPanel
from src.ui.visualization_panel import VisualizationPanel
from src.core.calculations.volume_calculator import VolumeCalculator
from src.ui.dialogs.import_options_dialog import ImportOptionsDialog
from src.ui.dialogs.report_dialog import ReportDialog
from src.ui.dialogs.volume_calculation_dialog import VolumeCalculationDialog
from src.visualization.pdf_renderer import PDFRenderer, PDFRendererError


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
        self.pdf_dpi_setting = 150 # Default DPI for rendering
        
        # Set up the main window properties
        self.setWindowTitle("DigCalc - Excavation Takeoff Tool")
        self.setMinimumSize(1024, 768)
        
        # Initialize UI components
        self._init_ui()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()
        
        # Connect visualization panel signals
        if hasattr(self, 'visualization_panel') and hasattr(self.visualization_panel, 'surface_visualization_failed'):
             self.visualization_panel.surface_visualization_failed.connect(self._on_visualization_failed)
        
        # Create default project
        self._create_default_project()
        
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
        self.project_panel = ProjectPanel(main_window=self, parent=self) # Pass self here
        self.project_dock.setWidget(self.project_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.project_dock)
        
        # Give visualization panel a reference to the main window (for project access etc)
        # self.visualization_panel.set_main_window(self) # Or pass project directly later
        
        # --- Layer Control Panel Dock ---
        # self.layer_control_panel_widget = self.visualization_panel.get_layer_control_panel()
        # if self.layer_control_panel_widget:
        #     self.layer_dock = QDockWidget("Layers", self)
        #     self.layer_dock.setFeatures(
        #         QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        #     )
        #     self.layer_dock.setWidget(self.layer_control_panel_widget)
        #     # Start hidden, only relevant when PDF is loaded? Or always visible? Let's start visible.
        #     self.addDockWidget(Qt.RightDockWidgetArea, self.layer_dock) # Add to the right side
        #     self.layer_dock.setVisible(True) # Make it visible by default
        # else:
        #     self.layer_dock = None
        #     self.logger.error("Could not create Layer Control dock widget: Panel not found.")
    
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
        self.clear_pdf_background_action.setEnabled(False) # Initially disabled

        self.next_pdf_page_action = QAction("Next Page", self)
        self.next_pdf_page_action.triggered.connect(self.on_next_pdf_page)
        self.next_pdf_page_action.setEnabled(False)
        
        self.prev_pdf_page_action = QAction("Previous Page", self)
        self.prev_pdf_page_action.triggered.connect(self.on_prev_pdf_page)
        self.prev_pdf_page_action.setEnabled(False)
        
        # --- Tracing Action ---
        self.toggle_tracing_action = QAction("Enable Tracing", self)
        self.toggle_tracing_action.setStatusTip("Toggle interactive polyline tracing on the PDF background")
        self.toggle_tracing_action.setCheckable(True)
        self.toggle_tracing_action.toggled.connect(self.on_toggle_tracing_mode)
        self.toggle_tracing_action.setEnabled(False) # Initially disabled
        
        # Maybe add actions for DPI, calibrate later
    
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
        # Add view toggles here (e.g., toggle Project Panel)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.project_dock.toggleViewAction())
        # Add toggle for Layer Panel if it was created
        # if self.layer_dock:
        #     self.view_menu.addAction(self.layer_dock.toggleViewAction())
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.toggle_tracing_action) # Add tracing action
        
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
        # Add page number display/control
        self.pdf_page_label = QLabel(" Page: ")
        self.pdf_page_spinbox = QSpinBox()
        self.pdf_page_spinbox.setRange(0, 0) # Disabled initially
        self.pdf_page_spinbox.setEnabled(False)
        self.pdf_page_spinbox.valueChanged.connect(self.on_set_pdf_page_from_spinbox)
        self.pdf_toolbar.addWidget(self.pdf_page_label)
        self.pdf_toolbar.addWidget(self.pdf_page_spinbox)
        self.pdf_toolbar.addAction(self.next_pdf_page_action)
        self.pdf_toolbar.setVisible(False) # Initially hidden
        
        # --- Tracing Toolbar Action ---
        # Add the tracing action to the PDF toolbar
        self.pdf_toolbar.addSeparator()
        self.pdf_toolbar.addAction(self.toggle_tracing_action)
    
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
             self._update_pdf_controls() # Disable PDF controls
             self.visualization_panel.clear_all()
        
        self.current_project = project
        self.project_panel.set_project(self.current_project) # Update project panel view
        self.visualization_panel.set_project(self.current_project) # Update viz panel project ref
        
        # Update window title and status bar & Redisplay loaded surfaces
        if self.current_project:
             # Display loaded surfaces in visualization panel
             if hasattr(self, 'visualization_panel') and self.visualization_panel:
                 self.logger.info(f"Displaying {len(self.current_project.surfaces)} loaded surfaces...")
                 for surface in self.current_project.surfaces.values():
                     # TODO: Check surface visibility state saved in project if implemented
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
                self.visualization_panel.load_pdf_background(project.pdf_background_path, project.pdf_background_dpi)
                self.visualization_panel.set_pdf_page(project.pdf_background_page)
                # Load polylines after PDF is loaded and page is set
                self.visualization_panel.load_and_display_polylines(project.traced_polylines)
            except Exception as e:
                 self.logger.error(f"Error restoring PDF/Tracing state from project: {e}")
                 QMessageBox.warning(self, "Project Load Warning", f"Could not restore PDF background or traced lines:\n{e}")
                 # Clear potentially partial state
                 if self.visualization_panel.pdf_renderer:
                      self.visualization_panel.clear_pdf_background()
                 project.pdf_background_path = None # Clear from project if load failed
                 project.traced_polylines = []
        else:
            # If no PDF path in project, ensure view is clear
            if self.visualization_panel.pdf_renderer:
                 self.visualization_panel.clear_pdf_background()
                 self.visualization_panel.clear_displayed_polylines()
        
        # Update controls based on final state
        self._update_analysis_actions_state()
        self._update_pdf_controls()

    def _update_analysis_actions_state(self):
        """
        Enable/disable analysis actions based on the current project state.
        Specifically, enables volume calculation if >= 2 surfaces exist.
        """
        can_calculate = bool(self.current_project and len(self.current_project.surfaces) >= 2)
        self.calculate_volume_action.setEnabled(can_calculate)
        # Add other analysis actions here later if needed
        self.logger.debug(f"Calculate Volume action enabled state: {can_calculate}")
    
    def _update_pdf_controls(self):
        """Updates the state of PDF navigation and tracing controls."""
        # Check if the visualization panel exists and has a PDF renderer
        pdf_loaded = False
        page_count = 0
        current_page = 0
        if hasattr(self, 'visualization_panel') and self.visualization_panel.pdf_renderer:
            pdf_loaded = True
            page_count = self.visualization_panel.pdf_renderer.get_page_count()
            current_page = self.visualization_panel.current_pdf_page

        self.logger.debug(f"Updating PDF controls: pdf_loaded={pdf_loaded}, page_count={page_count}, current_page={current_page}")

        # Update toolbar visibility
        self.pdf_toolbar.setVisible(pdf_loaded)

        # Update navigation actions
        self.clear_pdf_background_action.setEnabled(pdf_loaded)
        self.prev_pdf_page_action.setEnabled(pdf_loaded and current_page > 1)
        self.next_pdf_page_action.setEnabled(pdf_loaded and current_page < page_count)

        # Update page spinbox
        self.pdf_page_spinbox.setEnabled(pdf_loaded)
        if pdf_loaded:
            # Block signals temporarily to prevent feedback loop
            self.pdf_page_spinbox.blockSignals(True)
            self.pdf_page_spinbox.setRange(1, page_count)
            self.pdf_page_spinbox.setValue(current_page)
            self.pdf_page_spinbox.blockSignals(False)
        else:
            self.pdf_page_spinbox.setRange(0, 0)
            self.pdf_page_spinbox.setValue(0)
            
        # Update tracing action state
        self.toggle_tracing_action.setEnabled(pdf_loaded)
        # Uncheck tracing if PDF is unloaded
        if not pdf_loaded and self.toggle_tracing_action.isChecked():
             self.toggle_tracing_action.setChecked(False) # This will trigger the toggled signal

    # Event handlers
    def on_new_project(self):
        """Handle the 'New Project' action."""
        if not self._confirm_close_project():
            return
            
        # Create the new project object first
        new_project = Project("Untitled Project")
        
        # Clear visualization (including PDF and traces)
        if hasattr(self, 'visualization_panel'):
             self.visualization_panel.clear_all() # Assumes clear_all also handles PDF/traces
             # Explicitly ensure polylines are cleared if clear_all doesn't handle it
             self.visualization_panel.clear_displayed_polylines() 
            
        # Update the UI with the new project
        self._update_project(new_project)
        
        self.statusBar().showMessage("New project created", 3000)
    
    def on_open_project(self):
        """Handle the 'Open Project' action."""
        # Manual Test Suggestion:
        # 1. Click 'File -> Open Project'.
        # 2. If a project is open and unsaved, expect a 'Save Project?' prompt.
        # 3. Select a valid '.digcalc' file.
        # 4. Expect the project to load, window title to update, and surfaces to appear in panels.
        # 5. Try opening an invalid/corrupt file; expect an error message.
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
                    # This case might indicate an issue with the load method itself
                    raise RuntimeError("Project.load returned None without raising an exception.")
            except Exception as e:
                self.logger.exception(f"Error opening project file: {filename}")
                QMessageBox.critical(self, "Open Project Error", f"Failed to open project file.\n\nError: {e}")
                self.statusBar().showMessage("Error opening project.", 5000)
                self._create_default_project() # Reset to a clean state
        else:
            self.logger.info("Open project dialog cancelled by user.")
            self.statusBar().showMessage("Open cancelled.", 3000)
    
    def on_save_project(self, save_as=False) -> bool:
        """Handle the 'Save Project' and 'Save Project As' actions."""
        # Manual Test Suggestion (Save):
        # 1. Create or open a project, make a change (e.g., import a surface).
        # 2. Click 'File -> Save Project'.
        # 3. If it's a new project, expect 'Save As' dialog.
        # 4. If it's an existing project, expect it to save without a dialog.
        # Manual Test Suggestion (Save As):
        # 1. Open an existing project.
        # 2. Click 'File -> Save Project As...'.
        # 3. Expect 'Save As' dialog.
        # 4. Save with a new name. Expect window title to update.
        self.logger.debug(f"Save Project action triggered (save_as={save_as})")
        if not self.current_project:
            self.logger.warning("Save attempt failed: No active project.")
            return True # No project, so technically save wasn't needed/failed
            
        filename = self.current_project.project_file
        
        # Determine if we need to show the 'Save As' dialog
        if save_as or not filename:
            prompt_title = "Save Project As" if save_as else "Save Project"
            filename, _ = QFileDialog.getSaveFileName(
                self, prompt_title, "", "DigCalc Project Files (*.digcalc);;All Files (*)"
            )
            if not filename:
                 self.logger.info("Save project dialog cancelled by user.")
                 self.statusBar().showMessage("Save cancelled.", 3000)
                 return False # User cancelled
            
            # Ensure filename has the correct extension
            if not filename.lower().endswith(".digcalc"):
                 filename += ".digcalc"
        
        # Proceed with saving
        self.logger.info(f"Saving project to: {filename}")
        self.statusBar().showMessage(f"Saving project to '{Path(filename).name}'...")
        try:
            # Call the project's save method
            success = self.current_project.save(filename)
            if success:
                self.statusBar().showMessage(f"Project saved successfully to '{Path(filename).name}'", 5000)
                # Update window title if file path changed
                self._update_project(self.current_project) 
                return True
            else:
                 # Should ideally not happen if save returns bool, but handle defensively
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
        # Manual Test Suggestion (Import):
        # 1. Ensure a project is open (or create new).
        # 2. Click 'File -> Import -> [File Type]'.
        # 3. Select a valid data file (e.g., sample.csv).
        # 4. Configure options in the Import Options dialog (e.g., select columns for CSV).
        # 5. Click 'OK' / 'Import'.
        # 6. Expect the surface to appear in the Project Panel and Visualization Panel.
        # 7. Try importing an invalid file or cancelling; expect appropriate feedback.
        if not self.current_project:
            self.logger.error("Cannot import file: No active project.")
            QMessageBox.warning(self, "No Project", "Please create or open a project before importing files.")
            return

        if not parser_class:
             # Basic file type detection (can be expanded)
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
            # Use filename base as default surface name
            default_surface_name = Path(filename).stem 

            # Show options dialog
            # Pass filename to dialog to allow peeking headers
            options_dialog = ImportOptionsDialog(self, parser, default_surface_name, filename=filename)
            if options_dialog.exec():
                surface_name = options_dialog.get_surface_name()
                options = options_dialog.get_options()

                self.logger.info(f"Parsing '{filename}' with options: {options}. Surface name: '{surface_name}'")
                self.statusBar().showMessage(f"Importing '{Path(filename).name}' as '{surface_name}'...")

                surface = parser.parse(filename, options)

                if surface:
                    # Check if the points dictionary is empty
                    if not surface.points:
                        self.logger.warning(f"Imported surface '{surface_name}' from '{filename}' contains no data points.")
                        QMessageBox.warning(self, "Import Warning", f"The imported surface '{surface_name}' contains no data points.")
                    
                    # Ensure unique surface name within the project
                    unique_name = self.current_project.get_unique_surface_name(surface_name)
                    if unique_name != surface_name:
                        self.logger.info(f"Surface name adjusted to '{unique_name}' for uniqueness.")
                        QMessageBox.information(self, "Name Adjusted", f"The surface name was changed to '{unique_name}' to avoid duplicates.")
                    
                    surface.name = unique_name # Assign the final name
                    
                    # Add surface to project
                    self.current_project.add_surface(surface)
                    self.project_panel._update_tree()
                    self._update_analysis_actions_state()
                    
                    self.statusBar().showMessage(f"Successfully imported '{surface.name}'", 5000)
                    self.logger.info(f"Surface '{surface.name}' added to project '{self.current_project.name}'.")

                    # Optionally visualize the newly imported surface
                    self.visualization_panel.display_surface(surface)

                else:
                    # Parser might return None if parsing fundamentally failed
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
        # Don't show a modal dialog as this can disrupt workflow, 
        # just update the status bar and log the error
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
        
        # Manual Test Suggestion: 
        # 1. Create/Open a project with at least two surfaces (e.g., 'existing', 'proposed').
        # 2. Click 'Analysis -> Calculate Volumes...'.
        # 3. In the dialog, select 'existing' and 'proposed'. Set a resolution (e.g., 5.0).
        # 4. Click 'OK'. Expect results or error message.

        if dialog.exec():
            selection = dialog.get_selected_surfaces()
            resolution = dialog.get_grid_resolution()

            if selection and resolution > 0:
                existing_name = selection['existing']
                proposed_name = selection['proposed']
                self.logger.info(f"Starting volume calculation: Existing='{existing_name}', Proposed='{proposed_name}', Resolution={resolution}")
                self.statusBar().showMessage(f"Calculating volumes (Grid: {resolution})...", 0) # Persistent message

                try:
                    existing_surface = self.current_project.get_surface(existing_name)
                    proposed_surface = self.current_project.get_surface(proposed_name)

                    if not existing_surface or not proposed_surface:
                         raise ValueError("Selected surface(s) not found in project.")
                         
                    # Corrected check: verify if the points dictionary is empty
                    if not existing_surface.points or not proposed_surface.points:
                         raise ValueError("Selected surface(s) have no data points for calculation.")

                    # Initialize calculator without arguments
                    calculator = VolumeCalculator()
                    # Call the appropriate method and unpack results from the dictionary
                    results = calculator.calculate_surface_to_surface(
                        surface1=existing_surface, 
                        surface2=proposed_surface, 
                        grid_resolution=resolution
                    )
                    cut_volume = results['cut_volume']
                    fill_volume = results['fill_volume']
                    net_volume = results['net_volume']

                    # Calculation successful
                    self.statusBar().showMessage(f"Calculation complete: Cut={cut_volume:.2f}, Fill={fill_volume:.2f}, Net={net_volume:.2f}", 5000)
                    self.logger.info(f"Volume calculation successful: Cut={cut_volume:.2f}, Fill={fill_volume:.2f}, Net={net_volume:.2f}")
                    
                    # --- Show Report Dialog ---
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
                    # --------------------------

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
                    # Selection was likely invalid (same surface twice), handled in dialog validation
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
        # TODO: Implement actual change tracking in the Project model
        # For now, assume changes exist if a project is loaded.
        if not self.current_project: #or not self.current_project.has_unsaved_changes: 
            return True
            
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "The current project has unsaved changes. Do you want to save them before proceeding?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                     QMessageBox.Cancel) # Default to Cancel

        if reply == QMessageBox.Cancel:
            self.logger.debug("Project close/switch cancelled by user due to unsaved changes.")
            return False
        elif reply == QMessageBox.Save:
            # Attempt to save, if save fails or is cancelled by user, don't proceed
            return self.on_save_project()
        elif reply == QMessageBox.Discard:
            self.logger.info("Discarding unsaved changes in current project.")
            return True
            
        return False # Should not be reached

    def closeEvent(self, event):
        """Handle the main window close event."""
        self.logger.info("Close event triggered.")
        if self._confirm_close_project():
            # Clean up PDF renderer before closing
            if hasattr(self, 'visualization_panel') and self.visualization_panel:
                 self.visualization_panel.clear_pdf_background() 
            self.logger.info("Closing application.")
            event.accept() # Proceed with closing
        else:
            event.ignore() # User cancelled closing

    # --- PDF Background and Tracing Handlers ---

    def on_load_pdf_background(self):
        """Handles loading a PDF file as a background."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load PDF Background",
            "", # Start directory
            "PDF Files (*.pdf);;All Files (*)"
        )
        
        if filename:
            self.logger.info(f"User selected PDF for background: {filename}")
            self.statusBar().showMessage(f"Loading PDF background '{Path(filename).name}'...", 0)
            try:
                # Use the DPI setting
                self.visualization_panel.load_pdf_background(filename, dpi=self.pdf_dpi_setting)
                # Store PDF info in the project
                if self.current_project:
                    self.current_project.pdf_background_path = filename
                    self.current_project.pdf_background_page = 1 # Reset to page 1 on new load
                    self.current_project.pdf_background_dpi = self.pdf_dpi_setting
                    # Clear any previous polylines when loading a new PDF
                    self.current_project.clear_traced_polylines()
                    self.visualization_panel.clear_displayed_polylines() 
                self.statusBar().showMessage(f"Loaded PDF background '{Path(filename).name}' ({self.visualization_panel.pdf_renderer.get_page_count()} pages).", 5000)
            except (FileNotFoundError, PDFRendererError, Exception) as e:
                 self.logger.exception(f"Failed to load PDF background: {e}")
                 QMessageBox.critical(self, "PDF Load Error", f"Failed to load PDF background:\n{e}")
                 self.statusBar().showMessage("Failed to load PDF background.", 5000)
            finally:
                 self._update_pdf_controls() # Update UI state regardless of success/failure
        else:
            self.logger.info("Load PDF background cancelled by user.")
            self.statusBar().showMessage("Load cancelled.", 3000)

    def on_clear_pdf_background(self):
        """Handles clearing the PDF background."""
        self.logger.info("Clearing PDF background.")
        self.visualization_panel.clear_pdf_background()
        # Clear PDF info from the project
        if self.current_project:
            self.current_project.pdf_background_path = None
            self.current_project.pdf_background_page = 1
            self.current_project.pdf_background_dpi = 150
            # Also clear traced polylines when PDF is cleared
            self.current_project.clear_traced_polylines()
            self.visualization_panel.clear_displayed_polylines() 
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
        # This check prevents acting if the value is set programmatically while signals blocked
        if self.pdf_page_spinbox.isEnabled() and page_number > 0:
             self.logger.debug(f"Setting PDF page from spinbox to: {page_number}")
             self.visualization_panel.set_pdf_page(page_number)
             if self.current_project:
                  self.current_project.pdf_background_page = page_number
             self._update_pdf_controls() # Update button states after spinbox change
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
            # Update action text for clarity
            self.toggle_tracing_action.setText("Disable Tracing" if checked else "Enable Tracing")
        else:
            self.logger.warning("Cannot toggle tracing mode: VisualizationPanel not found.")


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

        # Connect signals for validation
        self.combo_existing.currentIndexChanged.connect(self._validate_selection)
        self.combo_proposed.currentIndexChanged.connect(self._validate_selection)
        self._validate_selection() # Initial validation
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.adjustSize() # Adjust size to fit contents

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