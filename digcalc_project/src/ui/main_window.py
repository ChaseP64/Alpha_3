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
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QMenu, QToolBar,
    QFileDialog, QMessageBox, QVBoxLayout, QWidget, QDialog,
    QComboBox, QLabel, QGridLayout, QPushButton, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFormLayout, QHBoxLayout
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


class MainWindow(QMainWindow):
    """
    Main application window for DigCalc.
    """
    
    def __init__(self):
        """
        Initialize the main window and its components.
        """
        super().__init__()
        
        self.logger = logging.getLogger(__name__)
        self.current_project: Optional[Project] = None
        self.volume_calculator = VolumeCalculator()
        
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
        """Initialize the UI components."""
        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create visualization panel
        self.visualization_panel = VisualizationPanel(self)
        self.main_layout.addWidget(self.visualization_panel)
        
        # Create project panel as a dock widget
        self.project_dock = QDockWidget("Project", self)
        self.project_dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self.project_panel = ProjectPanel(self)
        self.project_dock.setWidget(self.project_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.project_dock)
    
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
        
        # View menu
        self.view_menu = self.menu_bar.addMenu("View")
        # Add view toggles here
        
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
    
    def _create_statusbar(self):
        """Create the status bar."""
        self.statusBar().showMessage("Ready")
    
    def _create_default_project(self):
        """Create a default project on startup."""
        self.current_project = Project("Untitled Project")
        self.project_panel.set_project(self.current_project)
        self._update_analysis_actions_state()
    
    def _update_project(self, project: Optional[Project]):
        """Sets the current project and updates relevant UI elements."""
        self.current_project = project
        self.project_panel.set_project(self.current_project)
        self._update_analysis_actions_state()
        if self.current_project:
             self.setWindowTitle(f"DigCalc - {self.current_project.name}")
             self.statusBar().showMessage(f"Project '{self.current_project.name}' loaded.", 3000)
        else:
             self.setWindowTitle("DigCalc - Excavation Takeoff Tool")
             self.statusBar().showMessage("No project loaded.", 3000)

    def _update_analysis_actions_state(self):
        """Enable/disable analysis actions based on project state."""
        can_calculate = bool(self.current_project and len(self.current_project.surfaces) >= 2)
        self.calculate_volume_action.setEnabled(can_calculate)
        self.logger.debug(f"Calculate Volume action enabled: {can_calculate}")
    
    # Event handlers
    def on_new_project(self):
        """Handle new project action."""
        self.logger.info("Creating new project")
        
        # Check if we need to save the current project
        if self.current_project and self._should_save_project():
            if not self.on_save_project(): 
                return
        
        # Create new project
        new_proj = Project("Untitled Project")
        self._update_project(new_proj)
        
        self.statusBar().showMessage("New project created", 3000)
    
    def on_open_project(self):
        """Handle open project action."""
        # Check if we need to save the current project
        if self.current_project and self._should_save_project():
            if not self.on_save_project():
                return
        
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "DigCalc Project Files (*.digcalc);;All Files (*)"
        )
        if filename:
            self.logger.info(f"Opening project: {filename}")
            try:
                # Load project
                project = Project.load(filename)
                if project:
                    self._update_project(project)
                else:
                    raise RuntimeError("Project loading returned None.")
            except Exception as e:
                 self.logger.exception(f"Failed to open project: {filename}")
                 QMessageBox.critical(
                    self, "Error", f"Failed to open project file '{Path(filename).name}'.\nError: {e}"
                 )
                 self._update_project(None)
    
    def on_save_project(self) -> bool:
        """Handle save project action. Returns True if saved, False otherwise."""
        if not self.current_project:
            return False
            
        filename = self.current_project.project_file
        if not filename:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Project As", "", "DigCalc Project Files (*.digcalc);;All Files (*)"
            )
            if not filename:
                 self.logger.warning("Save project cancelled by user.")
                 return False
        
        # Ensure filename has the correct extension
        if not filename.lower().endswith(".digcalc"):
             filename += ".digcalc"
             
        # Save project
        self.logger.info(f"Saving project to: {filename}")
        try:
            if self.current_project.save(filename):
                self.statusBar().showMessage(f"Project saved to: {filename}", 3000)
                self.setWindowTitle(f"DigCalc - {self.current_project.name}")
                return True
            else:
                 raise RuntimeError("Project save method returned False.")
        except Exception as e:
            self.logger.exception(f"Failed to save project to: {filename}")
            QMessageBox.critical(
                self, "Error", f"Failed to save project to '{Path(filename).name}'.\nError: {e}"
            )
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
            options_dialog = ImportOptionsDialog(self, parser, default_surface_name)
            if options_dialog.exec():
                surface_name = options_dialog.get_surface_name()
                options = options_dialog.get_options()

                self.logger.info(f"Parsing '{filename}' with options: {options}. Surface name: '{surface_name}'")
                self.statusBar().showMessage(f"Importing '{Path(filename).name}'...")

                surface = parser.parse(filename, options)

                if surface:
                    if not surface.has_data:
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
                    self.project_panel.update_surface_list()
                    self._update_analysis_actions_state()
                    
                    self.statusBar().showMessage(f"Successfully imported '{surface.name}'", 3000)
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
            QMessageBox.warning(self, "Not Enough Surfaces",
                                "Volume calculation requires at least two surfaces in the project.")
            return

        surface_names = list(self.current_project.surfaces.keys())
        
        # Create and show the dialog
        dialog = VolumeCalculationDialog(surface_names, parent=self)
        if dialog.exec():
            selected_names = dialog.get_selected_surfaces()
            resolution = dialog.get_grid_resolution()

            if not selected_names:
                 self.logger.error("Volume calculation dialog returned success but no surfaces selected.")
                 return

            existing_name = selected_names['existing']
            proposed_name = selected_names['proposed']

            self.logger.info(f"Requesting volume calculation: Existing='{existing_name}', Proposed='{proposed_name}', Resolution={resolution}")
            self.statusBar().showMessage(f"Calculating volumes between '{existing_name}' and '{proposed_name}'...")

            try:
                existing_surface = self.current_project.get_surface(existing_name)
                proposed_surface = self.current_project.get_surface(proposed_name)

                if not existing_surface or not proposed_surface:
                     raise ValueError("Selected surface(s) not found in the current project.")

                # Perform calculation
                results = self.volume_calculator.calculate_volumes(
                    existing=existing_surface,
                    proposed=proposed_surface,
                    grid_resolution=resolution
                )

                # Display results
                cut = results.get('cut_volume', 0.0)
                fill = results.get('fill_volume', 0.0)
                net = results.get('net_volume', 0.0)

                result_message = (
                    f"Volume Calculation Results:\n\n"
                    f"Existing Surface: {existing_name}\n"
                    f"Proposed Surface: {proposed_name}\n"
                    f"Grid Resolution: {resolution}\n\n"
                    f"Cut Volume: {cut:.3f}\n"
                    f"Fill Volume: {fill:.3f}\n"
                    f"Net Volume: {net:.3f}"
                )
                QMessageBox.information(self, "Volume Calculation Complete", result_message)
                self.statusBar().showMessage("Volume calculation complete.", 3000)
                self.logger.info(f"Calculation successful: Cut={cut:.3f}, Fill={fill:.3f}, Net={net:.3f}")

            except (ValueError, TypeError, RuntimeError) as e:
                 # Catch specific errors from the calculator or data retrieval
                 error_title = "Calculation Error"
                 error_msg = f"Could not calculate volumes.\n\nError: {e}"
                 self.logger.error(f"Volume calculation failed: {e}", exc_info=True)
                 QMessageBox.critical(self, error_title, error_msg)
                 self.statusBar().showMessage("Volume calculation failed.", 3000)
            except Exception as e:
                 # Catch any unexpected errors
                 error_title = "Unexpected Error"
                 error_msg = f"An unexpected error occurred during volume calculation.\n\nError: {e}"
                 self.logger.exception("Unexpected error during volume calculation.")
                 QMessageBox.critical(self, error_title, error_msg)
                 self.statusBar().showMessage("Volume calculation failed (unexpected error).", 3000)


class VolumeCalculationDialog(QDialog):
    """Dialog for selecting surfaces and options for volume calculation."""
    def __init__(self, surface_names: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Calculate Volumes")
        self.setMinimumWidth(350)
        self.logger = logging.getLogger(__name__)
        
        self.surface_names = sorted(surface_names)

        # --- Widgets ---
        self.existing_label = QLabel("Existing Surface:")
        self.existing_combo = QComboBox()
        self.existing_combo.addItems(self.surface_names)

        self.proposed_label = QLabel("Proposed Surface:")
        self.proposed_combo = QComboBox()
        self.proposed_combo.addItems(self.surface_names)
        
        # Pre-select different surfaces if possible
        if len(self.surface_names) > 1:
            self.proposed_combo.setCurrentIndex(1)

        self.resolution_label = QLabel("Grid Resolution:")
        self.resolution_spinbox = QDoubleSpinBox()
        self.resolution_spinbox.setDecimals(3)
        self.resolution_spinbox.setMinimum(0.001)
        self.resolution_spinbox.setMaximum(1000.0)
        self.resolution_spinbox.setValue(1.0)
        self.resolution_spinbox.setSingleStep(0.1)

        self.calculate_button = QPushButton("Calculate")
        self.cancel_button = QPushButton("Cancel")

        # --- Layout ---
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        form_layout.addRow(self.existing_label, self.existing_combo)
        form_layout.addRow(self.proposed_label, self.proposed_combo)
        form_layout.addRow(self.resolution_label, self.resolution_spinbox)
        
        layout.addLayout(form_layout)
        
        # Button Box
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.calculate_button)
        layout.addLayout(button_layout)

        # --- Connections ---
        self.calculate_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        # Validation on accept
        self.accepted.connect(self._validate_selection)

    def _validate_selection(self):
        """Validate selections before closing the dialog."""
        existing = self.existing_combo.currentText()
        proposed = self.proposed_combo.currentText()
        if existing == proposed:
             QMessageBox.warning(self, "Invalid Selection", "Existing and Proposed surfaces cannot be the same.")
             self.logger.warning("Validation failed: Same surface selected for existing and proposed.")

    def get_selected_surfaces(self) -> Optional[Dict[str, str]]:
        """Returns the selected surface names."""
        existing = self.existing_combo.currentText()
        proposed = self.proposed_combo.currentText()
        
        if not existing or not proposed:
            self.logger.error("Could not retrieve selected surface names from combo boxes.")
            return None
            
        if existing == proposed:
            self.logger.warning("Attempting to calculate volume with identical surfaces selected.")
            QMessageBox.warning(self, "Invalid Selection", "Existing and Proposed surfaces cannot be the same. Please select different surfaces.")
            return None

        return {"existing": existing, "proposed": proposed}

    def get_grid_resolution(self) -> float:
        """Returns the selected grid resolution."""
        return self.resolution_spinbox.value()

class ImportOptionsDialog(QDialog):
    """Dialog for setting import options and surface name."""
    
    def __init__(self, parent, parser, default_name):
        """
        Initialize the dialog.
        
        Args:
            parent: Parent widget
            parser: File parser
            default_name: Default surface name
        """
        super().__init__(parent)
        
        self.parser = parser
        self.default_name = default_name
        
        self.setWindowTitle("Import Options")
        self.setMinimumWidth(400)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Surface name
        form_layout = QFormLayout()
        self.name_edit = QLineEdit(default_name)
        form_layout.addRow("Surface Name:", self.name_edit)
        
        # Add parser-specific options
        self._add_parser_options(form_layout)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QGridLayout()
        
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.accept)
        button_layout.addWidget(self.import_button, 0, 0)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button, 0, 1)
        
        layout.addLayout(button_layout)
    
    def _add_parser_options(self, layout):
        """
        Add parser-specific options to the dialog.
        
        Args:
            layout: Form layout
        """
        # Add options based on parser type
        if isinstance(self.parser, CSVParser):
            # CSV-specific options
            self.has_header_checkbox = QCheckBox("Has Header Row")
            self.has_header_checkbox.setChecked(True)
            layout.addRow("", self.has_header_checkbox)
            
        elif isinstance(self.parser, LandXMLParser):
            # LandXML-specific options
            if self.parser._surfaces:
                self.surface_combo = QComboBox()
                self.surface_combo.addItems(self.parser._surfaces)
                layout.addRow("Surface:", self.surface_combo)
                
        elif isinstance(self.parser, DXFParser):
            # DXF-specific options
            if self.parser._layers:
                self.layer_combo = QComboBox()
                self.layer_combo.addItems(["All Layers"] + self.parser._layers)
                layout.addRow("Layer:", self.layer_combo)
                
        elif isinstance(self.parser, PDFParser):
            # PDF-specific options
            self.page_spin = QSpinBox()
            self.page_spin.setMinimum(1)
            self.page_spin.setMaximum(max(1, self.parser._pages))
            layout.addRow("Page:", self.page_spin)
            
            self.scale_spin = QDoubleSpinBox()
            self.scale_spin.setMinimum(0.01)
            self.scale_spin.setMaximum(1000.0)
            self.scale_spin.setValue(1.0)
            layout.addRow("Scale:", self.scale_spin)
    
    def get_surface_name(self) -> str:
        """
        Get the surface name from the dialog.
        
        Returns:
            Surface name
        """
        name = self.name_edit.text().strip()
        if not name:
            name = self.default_name
        return name 