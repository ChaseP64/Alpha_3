#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main window for the DigCalc application.

This module defines the main application window and its components.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, List

# PySide6 imports
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QMenu, QToolBar,
    QFileDialog, QMessageBox, QVBoxLayout, QWidget, QDialog,
    QComboBox, QLabel, QGridLayout, QPushButton, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFormLayout
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
    
    def _create_statusbar(self):
        """Create the status bar."""
        self.statusBar().showMessage("Ready")
    
    def _create_default_project(self):
        """Create a default project on startup."""
        self.current_project = Project("Untitled Project")
        self.project_panel.set_project(self.current_project)
    
    # Event handlers
    def on_new_project(self):
        """Handle new project action."""
        self.logger.info("Creating new project")
        
        # Check if we need to save the current project
        if self.current_project and self._should_save_project():
            self.on_save_project()
        
        # Create new project
        self.current_project = Project("Untitled Project")
        self.project_panel.set_project(self.current_project)
        
        self.statusBar().showMessage("New project created", 3000)
    
    def on_open_project(self):
        """Handle open project action."""
        # Check if we need to save the current project
        if self.current_project and self._should_save_project():
            self.on_save_project()
        
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "DigCalc Project Files (*.digcalc);;All Files (*)"
        )
        if filename:
            self.logger.info(f"Opening project: {filename}")
            
            # Load project
            project = Project.load(filename)
            if project:
                self.current_project = project
                self.project_panel.set_project(self.current_project)
                self.statusBar().showMessage(f"Opened project: {filename}", 3000)
            else:
                QMessageBox.critical(
                    self, "Error", f"Failed to open project: {filename}"
                )
    
    def on_save_project(self):
        """Handle save project action."""
        if not self.current_project:
            return
            
        # If project doesn't have a file, prompt for filename
        filename = self.current_project.project_file
        if not filename:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Project", "", "DigCalc Project Files (*.digcalc);;All Files (*)"
            )
            if not filename:
                return
        
        # Save project
        self.logger.info(f"Saving project to: {filename}")
        if self.current_project.save(filename):
            self.statusBar().showMessage(f"Project saved to: {filename}", 3000)
        else:
            QMessageBox.critical(
                self, "Error", f"Failed to save project to: {filename}"
            )
    
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
        Import a file using the appropriate parser.
        
        Args:
            filename: Path to the file to import
            parser_class: Optional parser class to use
        """
        try:
            # Get file basename for default surface name
            basename = os.path.splitext(os.path.basename(filename))[0]
            surface_name = basename
            
            # Get parser
            if parser_class:
                parser = parser_class()
            else:
                parser = FileParser.get_parser_for_file(filename)
                
            if not parser:
                QMessageBox.critical(
                    self, "Error", f"Unsupported file format: {filename}"
                )
                return
            
            # Show progress in status bar
            self.statusBar().showMessage(f"Parsing file: {filename}...", 2000)
            
            # Parse file
            if parser.parse(filename):
                # Show import options dialog
                dialog = ImportOptionsDialog(self, parser, surface_name)
                if dialog.exec() == QDialog.Accepted:
                    # Get surface name from dialog
                    surface_name = dialog.get_surface_name()
                    
                    # Show progress
                    self.statusBar().showMessage(f"Creating surface: {surface_name}...", 2000)
                    
                    # Create surface
                    surface = parser.create_surface(surface_name)
                    if surface:
                        # Add surface to project
                        self.current_project.add_surface(surface)
                        
                        # Update project panel
                        self.project_panel.set_project(self.current_project)
                        
                        # Show progress
                        self.statusBar().showMessage(f"Rendering surface: {surface_name}...", 2000)
                        
                        # Display surface in the visualization panel
                        success = self.visualization_panel.display_surface(surface)
                        if success:
                            self.statusBar().showMessage(f"Imported and visualized surface: {surface_name}", 3000)
                        else:
                            # Surface was added to project, but visualization failed
                            self.statusBar().showMessage(f"Imported surface, but visualization failed: {surface_name}", 3000)
                            
                    else:
                        QMessageBox.critical(
                            self, "Error", f"Failed to create surface from file: {filename}"
                        )
                else:
                    self.statusBar().showMessage("Import cancelled", 2000)
            else:
                QMessageBox.critical(
                    self, "Error", f"Failed to parse file: {filename}\n\nError: {parser.get_last_error()}"
                )
                
        except Exception as e:
            self.logger.exception(f"Error importing file: {e}")
            QMessageBox.critical(
                self, "Error", f"Error importing file: {str(e)}"
            )
    
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


class ImportOptionsDialog(QDialog):
    """Dialog for configuring import options."""
    
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