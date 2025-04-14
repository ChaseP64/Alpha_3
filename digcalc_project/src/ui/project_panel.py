#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project panel for the DigCalc application.

This module defines the project panel and its components.
"""

import logging
from typing import Optional, List, Dict

# PySide6 imports
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QMessageBox, QCheckBox
)

# Local imports - Use relative paths
from ..models.project import Project
from ..models.surface import Surface


class ProjectPanel(QWidget):
    """
    Panel for displaying project information and structure.
    """
    
    # Signals
    surface_selected = Signal(Surface)
    surface_visibility_changed = Signal(Surface, bool)
    
    def __init__(self, main_window: QWidget, parent=None):
        """
        Initialize the project panel.
        
        Args:
            main_window: Reference to the main application window.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self.main_window = main_window # Store reference
        self.logger = logging.getLogger(__name__)
        self.project: Optional[Project] = None
        self.selected_surface: Optional[Surface] = None
        self.surface_checkboxes: Dict[str, QCheckBox] = {}  # Keep track of checkboxes by surface ID
        
        # Initialize UI components
        self._init_ui()
        
        self.logger.debug("ProjectPanel initialized")
    
    def _init_ui(self):
        """Initialize the UI components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Project tree
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("Project Structure")
        self.tree_widget.setMinimumHeight(200)
        self.tree_widget.itemSelectionChanged.connect(self._on_item_selection_changed)
        layout.addWidget(self.tree_widget)
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Add")
        self.add_button.setToolTip("Add a new item")
        self.add_button.clicked.connect(self._on_add_clicked)
        toolbar_layout.addWidget(self.add_button)
        
        self.remove_button = QPushButton("Remove")
        self.remove_button.setToolTip("Remove selected item")
        self.remove_button.clicked.connect(self._on_remove_clicked)
        toolbar_layout.addWidget(self.remove_button)
        
        self.properties_button = QPushButton("Properties")
        self.properties_button.setToolTip("View properties of selected item")
        self.properties_button.clicked.connect(self._on_properties_clicked)
        toolbar_layout.addWidget(self.properties_button)
        
        layout.addLayout(toolbar_layout)
    
    def set_project(self, project: Project):
        """
        Set the project to display.
        
        Args:
            project: Project to display
        """
        self.project = project
        self.surface_checkboxes.clear()  # Clear checkbox references
        self._update_tree()
    
    def _update_tree(self):
        """Update the project tree with the current project."""
        self.tree_widget.clear()
        
        if not self.project:
            return
        
        # Create root item
        root_item = QTreeWidgetItem(self.tree_widget)
        root_item.setText(0, self.project.name)
        root_item.setExpanded(True)
        
        # Create surfaces group
        surfaces_item = QTreeWidgetItem(root_item)
        surfaces_item.setText(0, "Surfaces")
        surfaces_item.setExpanded(True)
        
        # Add surfaces
        if self.project.surfaces:
            for surface in self.project.surfaces.values():
                self._add_surface_item(surfaces_item, surface)
        
        # Create volumes group
        volumes_item = QTreeWidgetItem(root_item)
        volumes_item.setText(0, "Volumes")
        volumes_item.setExpanded(True)
        
        # Add volumes
        if self.project.calculations:
            for volume in self.project.calculations:
                volume_item = QTreeWidgetItem(volumes_item)
                volume_item.setText(0, volume.name)
                volume_item.setData(0, Qt.UserRole, volume)
    
    def _add_surface_item(self, parent_item, surface: Surface) -> QTreeWidgetItem:
        """
        Add a surface item to the tree.
        
        Args:
            parent_item: Parent tree item
            surface: Surface to add
            
        Returns:
            Created tree item
        """
        surface_item = QTreeWidgetItem(parent_item)
        surface_item.setText(0, surface.name)
        surface_item.setData(0, Qt.UserRole, surface)
        
        # Add checkbox for visibility
        checkbox = self._create_visibility_checkbox(surface)
        self.tree_widget.setItemWidget(surface_item, 1, checkbox)
        
        # Store reference to checkbox
        self.surface_checkboxes[surface.id] = checkbox
        
        # Add details as child items
        if surface.points:
            points_item = QTreeWidgetItem(surface_item)
            points_item.setText(0, f"Points: {len(surface.points)}")
        
        if surface.triangles:
            triangles_item = QTreeWidgetItem(surface_item)
            triangles_item.setText(0, f"Triangles: {len(surface.triangles)}")
        
        # Add elevation range info
        elev_range = surface.get_elevation_range()
        if elev_range:
            elevation_item = QTreeWidgetItem(surface_item)
            zmin, zmax = elev_range
            elevation_item.setText(0, f"Elevation: {zmin:.2f} to {zmax:.2f}")
        
        return surface_item
    
    def _create_visibility_checkbox(self, surface: Surface) -> QCheckBox:
        """
        Create a visibility checkbox for a surface.
        
        Args:
            surface: Surface to create checkbox for
            
        Returns:
            Checkbox widget
        """
        checkbox = QCheckBox()
        checkbox.setChecked(True)  # Default to visible
        checkbox.setToolTip("Toggle visibility")
        
        # Connect using lambda to capture surface
        checkbox.stateChanged.connect(
            lambda state: self._on_surface_visibility_changed(surface, state == Qt.Checked)
        )
        return checkbox
    
    def _on_surface_visibility_changed(self, surface: Surface, visible: bool):
        """
        Handle visibility change for a surface.
        
        Args:
            surface: Surface whose visibility changed
            visible: New visibility state
        """
        self.logger.debug(f"Surface {surface.name} visibility changed to {visible}")
        self.surface_visibility_changed.emit(surface, visible)
    
    def _on_item_selection_changed(self):
        """Handle item selection change in the tree."""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            self.selected_surface = None
            return
        
        item = selected_items[0]
        data = item.data(0, Qt.UserRole)
        
        if isinstance(data, Surface):
            self.selected_surface = data
            self.surface_selected.emit(data)
    
    def _on_add_clicked(self):
        """Handle add button click."""
        # Placeholder for add functionality
        self.logger.debug("Add button clicked")
    
    def _on_remove_clicked(self):
        """Handle remove button click."""
        if not self.project or not self.selected_surface:
            return
        
        # Confirm removal
        result = QMessageBox.question(
            self,
            "Remove Surface",
            f"Are you sure you want to remove surface '{self.selected_surface.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            surface_to_remove = self.selected_surface # Store reference before potentially clearing
            surface_name = surface_to_remove.name
            
            # Remove from project model
            removed = self.project.remove_surface(surface_name)
            
            if removed:
                self.logger.info(f"Removed surface: {surface_name}")
                
                # Update tree view
                self._update_tree()
                
                # Update main window state (e.g., disable analysis actions if needed)
                if self.main_window and hasattr(self.main_window, '_update_analysis_actions_state'):
                     self.main_window._update_analysis_actions_state()
                
                # Emit signal to remove from visualization
                self.surface_visibility_changed.emit(surface_to_remove, False)
                
                # Clear selection
                self.selected_surface = None
            else:
                 # Should not happen if selection is valid, but handle defensively
                 self.logger.error(f"Failed to remove surface '{surface_name}' via project model.")
    
    def _on_properties_clicked(self):
        """Handle properties button click."""
        if not self.selected_surface:
            return
        
        # Placeholder for properties dialog
        self.logger.debug(f"Properties for surface: {self.selected_surface.name}") 