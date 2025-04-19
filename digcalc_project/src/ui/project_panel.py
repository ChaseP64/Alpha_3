#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project panel for the DigCalc application.

This module defines the project panel and its components.
"""

import sys
import logging
from typing import Optional, List, Dict, Tuple, Union

# PySide6 imports
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon, QFont, QColor, QAction, QMouseEvent, QContextMenuEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QMessageBox, QCheckBox, QAbstractItemView, QMenu, QHeaderView, QApplication, QDialog
)

# Local imports - Use relative paths
from ..models.project import Project
from ..models.surface import Surface

# --- Logger --- 
logger = logging.getLogger(__name__) # Initialize logger

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
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.on_context_menu)
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
        """Populates the tree widget with project data."""
        self.tree_widget.blockSignals(True)
        self.tree_widget.clear()
        if not self.project:
            self.tree_widget.blockSignals(False)
            return

        # --- Surfaces Node --- 
        surfaces_node = QTreeWidgetItem(self.tree_widget, ["Surfaces"])
        surfaces_node.setData(0, Qt.UserRole, ("category", "surfaces")) # Store type
        surfaces_node.setFlags(surfaces_node.flags() & ~Qt.ItemIsSelectable)

        if self.project.surfaces:
            sorted_surface_names = sorted(self.project.surfaces.keys())
            for name in sorted_surface_names:
                surface = self.project.surfaces.get(name)
                if not surface: continue # Should not happen, but safety check
                
                text = name
                # --- Stale Indicator --- 
                is_stale = getattr(surface, 'is_stale', False) # Check if attribute exists
                if is_stale:
                    text += " ⚠︎" # Append warning symbol
                # --- End Stale Indicator ---
                
                item = QTreeWidgetItem(surfaces_node, [text])
                item.setData(0, Qt.UserRole, ("surface", name)) # Store type and name
                
                # --- Stale Formatting --- 
                if is_stale:
                     font = item.font(0)
                     font.setItalic(True)
                     item.setFont(0, font)
                     # Use standard palette text color for theme compatibility, but maybe gray?
                     # item.setForeground(0, self.palette().color(self.foregroundRole()))
                     item.setForeground(0, QColor("gray")) # Use gray for clear visual distinction
                # --- End Stale Formatting ---
        else:
            no_surfaces_item = QTreeWidgetItem(surfaces_node, ["No surfaces loaded"])
            no_surfaces_item.setFlags(no_surfaces_item.flags() & ~Qt.ItemIsSelectable)
            no_surfaces_item.setDisabled(True)
            font = no_surfaces_item.font(0)
            font.setItalic(True)
            no_surfaces_item.setFont(0, font)

        # --- Traced Layers Node --- 
        layers_node = QTreeWidgetItem(self.tree_widget, ["Traced Layers"])
        layers_node.setData(0, Qt.UserRole, ("category", "layers"))
        layers_node.setFlags(layers_node.flags() & ~Qt.ItemIsSelectable)

        if self.project.calculations:
            sorted_layer_names = sorted(self.project.calculations.keys())
            for layer_name in sorted_layer_names:
                polylines = self.project.calculations[layer_name]
                layer_item = QTreeWidgetItem(layers_node, [f"{layer_name} ({len(polylines)} polylines)"])
                layer_item.setData(0, Qt.UserRole, ("layer", layer_name))
                layer_item.setFlags(layer_item.flags() & ~Qt.ItemIsSelectable)
                # Optionally add individual polylines as children here if needed
        else:
            no_layers_item = QTreeWidgetItem(layers_node, ["No traced layers"])
            no_layers_item.setFlags(no_layers_item.flags() & ~Qt.ItemIsSelectable)
            no_layers_item.setDisabled(True)
            font = no_layers_item.font(0)
            font.setItalic(True)
            no_layers_item.setFont(0, font)

        # Expand all top-level nodes
        self.tree_widget.expandItem(surfaces_node)
        self.tree_widget.expandItem(layers_node)
        # self.tree_widget.expandAll() # Might expand too much if polylines added later
        self.tree_widget.blockSignals(False)
        logger.debug("Project panel tree updated.")
    
    def _update_tree_item_text(self, surface_name: str):
         """Updates the text and appearance of a specific surface item in the tree."""
         root = self.tree_widget.invisibleRootItem()
         surfaces_node = None
         for i in range(root.childCount()):
              node = root.child(i)
              data = node.data(0, Qt.UserRole)
              if isinstance(data, tuple) and data[0] == "category" and data[1] == "surfaces":
                   surfaces_node = node
                   break
         if not surfaces_node: 
              logger.warning("Could not find 'Surfaces' category node in tree.")
              return

         for i in range(surfaces_node.childCount()):
              item = surfaces_node.child(i)
              data = item.data(0, Qt.UserRole)
              # Check if data indicates it's a surface and matches the name
              if isinstance(data, tuple) and data[0] == "surface" and data[1] == surface_name:
                   surface = self.project.surfaces.get(surface_name) if self.project else None
                   if surface:
                       text = surface_name
                       is_stale = getattr(surface, 'is_stale', False)
                       if is_stale:
                           text += " ⚠︎"
                       item.setText(0, text)

                       # Reset font/color before applying potentially new style
                       font = item.font(0)
                       font.setItalic(False)
                       item.setFont(0, font)
                       item.setForeground(0, self.palette().color(self.foregroundRole())) # Use default text color

                       # Apply stale formatting if needed
                       if is_stale:
                           font.setItalic(True)
                           item.setFont(0, font)
                           item.setForeground(0, QColor("gray")) 
                   break # Found the item
    
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

    def on_context_menu(self, point):
        """Handle context menu request."""
        selected_items = self.tree_widget.selectedIndexes()
        if not selected_items:
            return
        
        item = self.tree_widget.itemAt(point)
        if not item:
            return
        
        data = item.data(0, Qt.UserRole)
        if isinstance(data, Surface):
            surface = data
            menu = QMenu()
            
            # Add actions to the context menu
            action_show = QAction("Show", self)
            action_show.triggered.connect(lambda: self._on_show_clicked(surface))
            menu.addAction(action_show)
            
            action_hide = QAction("Hide", self)
            action_hide.triggered.connect(lambda: self._on_hide_clicked(surface))
            menu.addAction(action_hide)
            
            action_delete = QAction("Delete", self)
            action_delete.triggered.connect(lambda: self._on_delete_clicked(surface))
            menu.addAction(action_delete)
            
            menu.exec(self.tree_widget.viewport().mapToGlobal(point))
    
    def _on_show_clicked(self, surface: Surface):
        """Handle show action."""
        self.surface_visibility_changed.emit(surface, True)
    
    def _on_hide_clicked(self, surface: Surface):
        """Handle hide action."""
        self.surface_visibility_changed.emit(surface, False)
    
    def _on_delete_clicked(self, surface: Surface):
        """Handle delete action."""
        self._on_remove_clicked() 