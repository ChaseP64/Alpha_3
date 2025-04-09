#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualization panel for the DigCalc application.

This module defines the 3D visualization panel for displaying surfaces and calculations.
"""

import logging
from typing import Optional, Dict, List, Any, Tuple
import numpy as np

# PySide6 imports
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

# Import visualization libraries
try:
    from pyqtgraph.opengl import GLViewWidget, GLMeshItem, GLGridItem, GLLinePlotItem, GLAxisItem
    import pyqtgraph.opengl as gl
    import pyqtgraph
    HAS_3D = True
except ImportError:
    HAS_3D = False
    
# Local imports
from src.models.surface import Surface, Point3D, Triangle


class VisualizationPanel(QWidget):
    """
    Panel for 3D visualization of surfaces and calculation results.
    """
    
    # Signals
    surface_visualization_failed = Signal(str, str)  # (surface name, error message)
    
    def __init__(self, parent=None):
        """
        Initialize the visualization panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.surfaces: Dict[str, Dict[str, Any]] = {}  # Dictionary to store surface visualization objects
        
        # Initialize UI components
        self._init_ui()
        
        # Connect signals
        self.surface_visualization_failed.connect(self._on_visualization_failed)
        
        self.logger.debug("VisualizationPanel initialized")
    
    def _init_ui(self):
        """Initialize the UI components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if HAS_3D:
            # Create 3D view
            self.view_3d = GLViewWidget()
            self.view_3d.setCameraPosition(distance=100, elevation=30, azimuth=45)
            
            # Add a grid
            grid = GLGridItem()
            grid.setSize(x=100, y=100, z=0)
            grid.setSpacing(x=10, y=10, z=10)
            self.view_3d.addItem(grid)
            
            # Add axis items for orientation
            axis = GLAxisItem()
            axis.setSize(x=20, y=20, z=20)
            self.view_3d.addItem(axis)
            
            layout.addWidget(self.view_3d)
            
            self.logger.debug("3D view initialized")
        else:
            # Display a message if 3D visualization is not available
            self.placeholder = QLabel("3D visualization not available.\nPlease install pyqtgraph and PyOpenGL.")
            self.placeholder.setAlignment(Qt.AlignCenter)
            self.placeholder.setStyleSheet("background-color: #f0f0f0; padding: 20px;")
            layout.addWidget(self.placeholder)
            
            self.logger.warning("3D visualization libraries not available")
    
    def display_surface(self, surface: Surface) -> bool:
        """
        Display a surface in the 3D view.
        
        Args:
            surface: Surface to display
            
        Returns:
            bool: True if display was successful, False otherwise
        """
        if not HAS_3D:
            error_msg = "3D visualization libraries not available"
            self.logger.warning(f"Cannot display surface: {error_msg}")
            self.surface_visualization_failed.emit(surface.name, error_msg)
            return False
        
        # Validate surface
        if not surface:
            error_msg = "Invalid surface object"
            self.logger.warning(f"Cannot display surface: {error_msg}")
            self.surface_visualization_failed.emit("Unknown", error_msg)
            return False
            
        if not surface.points:
            error_msg = "Surface has no points"
            self.logger.warning(f"Cannot display surface '{surface.name}': {error_msg}")
            self.surface_visualization_failed.emit(surface.name, error_msg)
            return False
            
        if not surface.triangles:
            error_msg = "Surface has no triangles for rendering"
            self.logger.warning(f"Cannot display surface '{surface.name}': {error_msg}")
            self.surface_visualization_failed.emit(surface.name, error_msg)
            return False
        
        try:
            self.logger.info(f"Displaying surface: {surface.name} with {len(surface.points)} points and {len(surface.triangles)} triangles")
            
            # Remove existing surface if it exists
            if surface.name in self.surfaces:
                self._remove_surface_visualization(surface.name)
            
            # Create new visualization objects
            surface_vis = {}
            
            # Create mesh from triangles
            mesh_data = self._create_mesh_data(surface)
            if mesh_data:
                mesh = GLMeshItem(
                    vertexes=mesh_data["vertices"],
                    faces=mesh_data["faces"],
                    faceColors=mesh_data["colors"],
                    smooth=True,
                    drawEdges=True,
                    edgeColor=(0, 0, 0, 0.5)
                )
                self.view_3d.addItem(mesh)
                surface_vis["mesh"] = mesh
                
                # Store visualization objects
                self.surfaces[surface.name] = surface_vis
                
                # Adjust view if this is the first surface
                if len(self.surfaces) == 1:
                    self._adjust_view_to_surface(surface)
                
                self.logger.info(f"Successfully rendered surface: {surface.name}")
                return True
            else:
                error_msg = "Failed to create mesh data for visualization"
                self.logger.warning(f"Cannot display surface '{surface.name}': {error_msg}")
                self.surface_visualization_failed.emit(surface.name, error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Visualization error: {str(e)}"
            self.logger.exception(f"Error displaying surface '{surface.name}': {e}")
            self.surface_visualization_failed.emit(surface.name, error_msg)
            return False
    
    def _create_mesh_data(self, surface: Surface) -> Optional[Dict[str, Any]]:
        """
        Create mesh data from surface triangles.
        
        Args:
            surface: Surface with triangles
            
        Returns:
            Dictionary with mesh data or None if not possible
        """
        if not surface.triangles or not surface.points:
            return None
        
        try:
            # Extract points from dictionary to list for easier indexing
            points_list = list(surface.points.values())
            
            # Create mapping from point ID to index in vertices array
            points_id_map = {p.id: i for i, p in enumerate(points_list)}
            
            # Create vertices array
            vertices = np.array([[p.x, p.y, p.z] for p in points_list])
            
            # Create faces array
            faces = []
            for triangle in surface.triangles.values():
                # Skip invalid triangles (those with missing points)
                if not (triangle.p1 and triangle.p2 and triangle.p3):
                    continue
                    
                # Get indices of points
                try:
                    i1 = points_id_map[triangle.p1.id]
                    i2 = points_id_map[triangle.p2.id]
                    i3 = points_id_map[triangle.p3.id]
                    faces.append([i1, i2, i3])
                except (KeyError, AttributeError) as e:
                    self.logger.warning(f"Invalid triangle in surface {surface.name}: {e}")
                    continue
            
            if not faces:
                self.logger.warning(f"No valid triangles found in surface {surface.name}")
                return None
                
            faces = np.array(faces)
            
            # Create colors array - color based on elevation
            if len(vertices) > 0:
                z_min = np.min(vertices[:, 2])
                z_max = np.max(vertices[:, 2])
                z_range = max(z_max - z_min, 0.1)  # Avoid division by zero
                
                # Create colors for each face
                colors = np.zeros((len(faces), 4))
                
                # Compute average z for each face
                for i, face in enumerate(faces):
                    z_avg = np.mean([vertices[idx, 2] for idx in face])
                    t = (z_avg - z_min) / z_range  # Normalized height between 0-1
                    
                    # Color gradient from blue (low) to red (high) through green (middle)
                    if t < 0.5:
                        # Blue to green
                        colors[i] = [0, t * 2, 1 - t * 2, 0.7]
                    else:
                        # Green to red
                        t2 = (t - 0.5) * 2
                        colors[i] = [t2, 1 - t2, 0, 0.7]
            else:
                # Default color if no vertices
                colors = np.array([[0, 0, 1, 0.7]])
            
            return {
                "vertices": vertices,
                "faces": faces,
                "colors": colors
            }
            
        except Exception as e:
            self.logger.exception(f"Error creating mesh data: {e}")
            return None
    
    def _adjust_view_to_surface(self, surface: Surface):
        """
        Adjust view to center on the surface.
        
        Args:
            surface: Surface to center view on
        """
        if not surface or not surface.points:
            return
            
        try:
            # Get all points
            points_list = list(surface.points.values())
            
            # Calculate bounds
            x_vals = [p.x for p in points_list]
            y_vals = [p.y for p in points_list]
            z_vals = [p.z for p in points_list]
            
            x_min, x_max = min(x_vals), max(x_vals)
            y_min, y_max = min(y_vals), max(y_vals)
            z_min, z_max = min(z_vals), max(z_vals)
            
            # Calculate center
            center_x = (x_min + x_max) / 2
            center_y = (y_min + y_max) / 2
            center_z = (z_min + z_max) / 2
            
            # Calculate distance based on size
            size_x = max(x_max - x_min, 1)
            size_y = max(y_max - y_min, 1)
            size_z = max(z_max - z_min, 1)
            
            distance = max(size_x, size_y, size_z) * 2
            
            # Set camera position using pyqtgraph.Vector
            self.view_3d.setCameraPosition(
                pos=pyqtgraph.Vector(center_x, center_y, center_z),
                distance=distance,
                elevation=30,
                azimuth=45
            )
            
            # Update the grid to match the size of the surface
            if hasattr(self, 'view_3d'):
                for item in self.view_3d.items:
                    if isinstance(item, GLGridItem):
                        # Update grid size
                        grid_size = max(size_x, size_y) * 1.5
                        grid_spacing = grid_size / 10
                        item.setSize(x=grid_size, y=grid_size, z=0)
                        item.setSpacing(x=grid_spacing, y=grid_spacing, z=grid_spacing)
                        
                        # Position grid at the lowest point
                        item.translate(center_x, center_y, z_min)
                        break
                        
            self.logger.debug(f"Adjusted view to surface: {surface.name}")
            
        except Exception as e:
            self.logger.warning(f"Error adjusting view to surface: {e}")
    
    def _remove_surface_visualization(self, surface_name: str):
        """
        Remove a surface's visualization objects.
        
        Args:
            surface_name: Name of the surface to remove
        """
        if surface_name not in self.surfaces:
            return
            
        surface_vis = self.surfaces[surface_name]
        
        # Remove mesh
        if "mesh" in surface_vis:
            self.view_3d.removeItem(surface_vis["mesh"])
        
        # Remove contours (if any)
        if "contours" in surface_vis:
            for contour in surface_vis["contours"]:
                self.view_3d.removeItem(contour)
        
        # Remove from dictionary
        del self.surfaces[surface_name]
        self.logger.debug(f"Removed visualization for surface: {surface_name}")
    
    @Slot(Surface, bool)
    def set_surface_visibility(self, surface: Surface, visible: bool):
        """
        Set the visibility of a surface.
        
        Args:
            surface: Surface to change visibility
            visible: Whether the surface should be visible
        """
        if not surface or surface.name not in self.surfaces:
            return
            
        surface_vis = self.surfaces[surface.name]
        
        # Set mesh visibility
        if "mesh" in surface_vis:
            surface_vis["mesh"].setVisible(visible)
        
        # Set contours visibility
        if "contours" in surface_vis:
            for contour in surface_vis["contours"]:
                contour.setVisible(visible)
                
        self.logger.debug(f"Surface {surface.name} visibility set to {visible}")
    
    def clear_all(self):
        """Clear all surfaces from the visualization."""
        if not HAS_3D:
            return
            
        # Remove all surfaces
        for surface_name in list(self.surfaces.keys()):
            self._remove_surface_visualization(surface_name)
            
        self.logger.debug("All surfaces cleared from visualization")
        
        # Reset the view
        if hasattr(self, 'view_3d'):
            self.view_3d.setCameraPosition(distance=100, elevation=30, azimuth=45)
    
    @Slot(str, str)
    def _on_visualization_failed(self, surface_name: str, error_msg: str):
        """
        Handle visualization failure.
        
        Args:
            surface_name: Name of the surface that failed to visualize
            error_msg: Error message
        """
        # This method could be connected to the UI to show error messages
        # For now, we just log it
        self.logger.error(f"Visualization failed for surface '{surface_name}': {error_msg}") 