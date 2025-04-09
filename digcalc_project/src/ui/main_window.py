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
        """
        Sets the current project and updates relevant UI elements consistently.
        This is the central method for changing the active project.
        """
        self.current_project = project
        self.project_panel.set_project(self.current_project) # Update project panel view
        
        # Clear visualization before displaying loaded surfaces
        if hasattr(self, 'visualization_panel') and self.visualization_panel:
             self.visualization_panel.clear_all()
        
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

        self._update_analysis_actions_state() # Update actions based on new project state

    def _update_analysis_actions_state(self):
        """
        Enable/disable analysis actions based on the current project state.
        Specifically, enables volume calculation if >= 2 surfaces exist.
        """
        can_calculate = bool(self.current_project and len(self.current_project.surfaces) >= 2)
        self.calculate_volume_action.setEnabled(can_calculate)
        # Add other analysis actions here later if needed
        self.logger.debug(f"Calculate Volume action enabled state: {can_calculate}")
    
    # Event handlers
    def on_new_project(self):
        """Handle the 'New Project' action."""
        self.logger.info("Creating new project")
        
        # Check if current project needs saving before proceeding
        if self.current_project and not self._confirm_close_project():
            return # User cancelled the operation
        
        # Create and set the new project
        new_project = Project("Untitled Project")
        self._update_project(new_project) # Use central update method
        
        self.statusBar().showMessage("New project created", 3000)
    
    def on_open_project(self):
        """Handle the 'Open Project' action."""
        self.logger.debug("Open Project action triggered.")
        # Check if current project needs saving
        if self.current_project and not self._confirm_close_project():
            return
        
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "DigCalc Project Files (*.digcalc);;All Files (*)"
        )
        if filename:
            self.logger.info(f"Attempting to open project file: {filename}")
            self.statusBar().showMessage(f"Opening project '{Path(filename).name}'...")
            try:
                # Load project using the Project class method
                project = Project.load(filename)
                if project:
                    self._update_project(project) # Update UI via central method
                    # Status bar message is handled within _update_project
                else:
                    # Project.load might return None on non-exception failure
                    raise RuntimeError("Project loading failed without specific exception.")
            except Exception as e:
                 # Catch any error during loading (file not found, JSON error, internal error)
                 error_msg = f"Failed to open project file '{Path(filename).name}'.\n\nError: {str(e)}"
                 self.logger.exception(f"Error opening project: {filename}")
                 QMessageBox.critical(self, "Open Project Error", error_msg)
                 self._update_project(None) # Ensure UI resets if load fails
                 self.statusBar().showMessage("Error opening project.", 5000)
        else:
             self.logger.debug("Open Project dialog cancelled by user.")
    
    def on_save_project(self, save_as=False) -> bool:
        """Handle the 'Save Project' or 'Save Project As' action.
        
        Args:
            save_as (bool): If True, always force the 'Save As' dialog.
        
        Returns:
            bool: True if the project was saved successfully or not needed, False if save failed or was cancelled.
        """
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

                # Perform calculation using the correct method name
                results = self.volume_calculator.calculate_surface_to_surface(
                    surface1=existing_surface,
                    surface2=proposed_surface,
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
            self.logger.info("Closing application.")
            event.accept() # Proceed with closing
        else:
            event.ignore() # User cancelled closing


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
    
    def __init__(self, parent, parser, default_name, filename: Optional[str] = None):
        """
        Initialize the dialog.
        
        Args:
            parent: Parent widget
            parser: File parser instance
            default_name: Default surface name
            filename (Optional[str]): The full path to the file being imported.
        """
        super().__init__(parent)
        
        self.parser = parser
        self.default_name = default_name
        self.file_path = filename
        self.logger = logging.getLogger(__name__)
        self.headers = []
        
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
    
    def get_surface_name(self) -> str:
        """Returns the entered surface name, falling back to the default if empty."""
        entered_name = self.name_edit.text().strip()
        return entered_name or self.default_name
        
    def _add_parser_options(self, layout):
        """
        Add parser-specific options to the dialog.
        
        Args:
            layout: Form layout
        """
        self.option_widgets = {} # Reset/initialize
        parser_type = type(self.parser)

        if parser_type is CSVParser:
            # --- CSV --- #
            self.option_widgets['has_header'] = QCheckBox("Has Header Row")
            self.option_widgets['has_header'].setChecked(True)
            self.option_widgets['has_header'].stateChanged.connect(self._update_csv_column_options)
            layout.addRow("", self.option_widgets['has_header'])

            self.option_widgets['x_column'] = QComboBox()
            self.option_widgets['y_column'] = QComboBox()
            self.option_widgets['z_column'] = QComboBox()
            layout.addRow("X Column:", self.option_widgets['x_column'])
            layout.addRow("Y Column:", self.option_widgets['y_column'])
            layout.addRow("Z Column:", self.option_widgets['z_column'])
            self._update_csv_column_options() # Initial population

        elif parser_type is LandXMLParser:
            # --- LandXML --- #
            # Placeholder logic for getting available surfaces. 
            # In a real implementation, the parser might need to peek the file.
            available_surfaces = [] 
            # Example: if hasattr(self.parser, 'peek_surfaces'): available_surfaces = self.parser.peek_surfaces(self.file_path)
            if available_surfaces:
                self.option_widgets['surface_name_combo'] = QComboBox()
                self.option_widgets['surface_name_combo'].addItems(available_surfaces)
                layout.addRow("Select Surface:", self.option_widgets['surface_name_combo'])
            # REMOVED incorrect duplicated logic from here.
            # This method only creates UI widgets.

        elif parser_type is DXFParser:
            # --- DXF --- #
            # Placeholder logic for getting layers.
            layers = []
            # Example: if hasattr(self.parser, 'peek_layers'): layers = self.parser.peek_layers(self.file_path)
            self.option_widgets['layer_combo'] = QComboBox()
            self.option_widgets['layer_combo'].addItems(["All Layers"] + sorted(layers))
            layout.addRow("Layer:", self.option_widgets['layer_combo'])

        elif parser_type is PDFParser:
            # --- PDF --- #
            # Placeholder logic for getting page count.
            page_count = 1 
            # Example: if hasattr(self.parser, 'peek_page_count'): page_count = self.parser.peek_page_count(self.file_path)
            self.option_widgets['page_spin'] = QSpinBox()
            self.option_widgets['page_spin'].setMinimum(1)
            self.option_widgets['page_spin'].setMaximum(max(1, page_count))
            layout.addRow("Page:", self.option_widgets['page_spin'])
            
            self.option_widgets['scale_spin'] = QDoubleSpinBox()
            self.option_widgets['scale_spin'].setDecimals(4)
            self.option_widgets['scale_spin'].setMinimum(0.0001)
            self.option_widgets['scale_spin'].setMaximum(10000.0)
            self.option_widgets['scale_spin'].setValue(1.0)
            self.option_widgets['scale_spin'].setSingleStep(0.1)
            layout.addRow("Scale:", self.option_widgets['scale_spin'])
        
    def _update_csv_column_options(self):
        """Update CSV column options based on the selected header checkbox."""
        has_header = self.option_widgets['has_header'].isChecked()
        self.headers = None if has_header else ['x', 'y', 'z']
        self.option_widgets['x_column'].clear()
        self.option_widgets['y_column'].clear()
        self.option_widgets['z_column'].clear()
        self.option_widgets['x_column'].addItems(self.headers or [])
        self.option_widgets['y_column'].addItems(self.headers or [])
        self.option_widgets['z_column'].addItems(self.headers or [])

    def _try_preselect_columns(self):
        """Try to preselect columns based on existing data."""
        if self.headers:
            self.option_widgets['x_column'].setCurrentIndex(self.headers.index('x') if 'x' in self.headers else 0)
            self.option_widgets['y_column'].setCurrentIndex(self.headers.index('y') if 'y' in self.headers else 0)
            self.option_widgets['z_column'].setCurrentIndex(self.headers.index('z') if 'z' in self.headers else 0)

    def get_options(self) -> Dict:
        """Gather import options based on the parser type and UI widgets."""
        options = {}
        parser_type = type(self.parser)

        if parser_type is CSVParser:
            # Retrieve 'has_header' state
            has_header_checkbox = self.option_widgets.get('has_header')
            if has_header_checkbox:
                options['has_header'] = has_header_checkbox.isChecked()
            
            # Retrieve selected column indices for CSV
            x_combo = self.option_widgets.get('x_column')
            y_combo = self.option_widgets.get('y_column')
            z_combo = self.option_widgets.get('z_column')
            # Check if headers were loaded (self.headers is populated) and selections are valid
            if self.headers and all([x_combo, y_combo, z_combo]) and all(c.currentIndex() >= 0 for c in [x_combo, y_combo, z_combo]):
                x_idx = x_combo.currentIndex()
                y_idx = y_combo.currentIndex()
                z_idx = z_combo.currentIndex()
                # Ensure indices are unique
                if len(set([x_idx, y_idx, z_idx])) == 3:
                    options['column_map'] = {'x': x_idx, 'y': y_idx, 'z': z_idx}
                    self.logger.info(f"Using selected CSV column indices: {options['column_map']}")
                else:
                    self.logger.warning("Duplicate columns selected for CSV. Parser will attempt auto-detection.")
            else:
                 self.logger.warning("Headers not available or invalid column selection for CSV. Parser will attempt auto-detection.")

        elif parser_type is LandXMLParser:
            # Retrieve selected surface name for LandXML
            combo = self.option_widgets.get('surface_name_combo')
            if combo: # Check if the widget exists
                 options['surface_name'] = combo.currentText()

        elif parser_type is DXFParser:
            # Retrieve selected layer name for DXF
            combo = self.option_widgets.get('layer_combo')
            if combo:
                 selected_layer = combo.currentText()
                 options['layer_name'] = None if selected_layer == "All Layers" else selected_layer

        elif parser_type is PDFParser:
            # Retrieve page number and scale for PDF
            page_spin = self.option_widgets.get('page_spin')
            if page_spin:
                 options['page_number'] = page_spin.value()
            scale_spin = self.option_widgets.get('scale_spin')
            if scale_spin:
                 options['scale'] = scale_spin.value()

        self.logger.debug(f"Collected import options: {options}")
        return options 