#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualization panel for the DigCalc application.

This module defines the 3D visualization panel for displaying surfaces and calculations.
"""

import logging
from typing import Optional, Dict, List
import numpy as np

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, Slot

# Import visualization libraries
try:
    from pyqtgraph.opengl import GLViewWidget, GLMeshItem, GLGridItem, GLLinePlotItem
    import pyqtgraph.opengl as gl
    HAS_3D = True
except ImportError:
    HAS_3D = False
    
from models.surface import Surface
from models.point import Point
from models.triangle import Triangle


class VisualizationPanel(QWidget):
    """
    Panel for 3D visualization of surfaces and calculation results.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the visualization panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.surfaces: Dict[str, Dict] = {}  # Dictionary to store surface visualization objects
        
        # Initialize UI components
        self._init_ui()
        
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
            
            layout.addWidget(self.view_3d)
            
            self.logger.debug("3D view initialized")
        else:
            # Display a message if 3D visualization is not available
            self.placeholder = QWidget()
            self.placeholder.setStyleSheet("background-color: #f0f0f0;")
            layout.addWidget(self.placeholder)
            
            self.logger.warning("3D visualization libraries not available")
    
    def display_surface(self, surface: Surface):
        """
        Display a surface in the 3D view.
        
        Args:
            surface: Surface to display
        """
        if not HAS_3D:
            self.logger.warning("Cannot display surface: 3D visualization not available")
            return
        
        if not surface or not surface.triangles:
            self.logger.warning(f"Cannot display surface {surface.name}: No triangles available")
            return
        
        self.logger.info(f"Displaying surface: {surface.name}")
        
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
        
        # Create contour lines
        if surface.contours:
            contour_items = []
            for contour in surface.contours:
                if len(contour.points) < 2:
                    continue
                    
                # Create points for the contour line
                pts = np.array([[p.x, p.y, p.z] for p in contour.points])
                
                # Create line plot item
                line = GLLinePlotItem(
                    pos=pts,
                    color=(0, 0, 1, 1),
                    width=2,
                    antialias=True
                )
                self.view_3d.addItem(line)
                contour_items.append(line)
            
            if contour_items:
                surface_vis["contours"] = contour_items
        
        # Store visualization objects
        self.surfaces[surface.name] = surface_vis
        
        # Adjust view if this is the first surface
        if len(self.surfaces) == 1:
            self._adjust_view_to_surface(surface)
    
    def _create_mesh_data(self, surface: Surface) -> Optional[Dict]:
        """
        Create mesh data from surface triangles.
        
        Args:
            surface: Surface with triangles
            
        Returns:
            Dictionary with mesh data or None if not possible
        """
        if not surface.triangles:
            return None
        
        # Create vertices array
        points_dict = {id(p): i for i, p in enumerate(surface.points)}
        vertices = np.array([[p.x, p.y, p.z] for p in surface.points])
        
        # Create faces array
        faces = []
        for tri in surface.triangles:
            if not (tri.p1 and tri.p2 and tri.p3):
                continue
                
            # Get indices of points
            try:
                i1 = points_dict[id(tri.p1)]
                i2 = points_dict[id(tri.p2)]
                i3 = points_dict[id(tri.p3)]
                faces.append([i1, i2, i3])
            except KeyError:
                continue
        
        if not faces:
            return None
            
        faces = np.array(faces)
        
        # Create colors array - color based on elevation
        if vertices.shape[0] > 0:
            z_min = np.min(vertices[:, 2])
            z_max = np.max(vertices[:, 2])
            z_range = max(z_max - z_min, 0.1)  # Avoid division by zero
            
            colors = np.zeros((faces.shape[0], 4))
            
            # Compute average z for each face
            for i, face in enumerate(faces):
                z_avg = np.mean([vertices[idx, 2] for idx in face])
                t = (z_avg - z_min) / z_range  # Normalized height
                
                # Color gradient from blue (low) to red (high)
                # Lower elevations: blue (0,0,1)
                # Middle elevations: green (0,1,0)
                # Higher elevations: red (1,0,0)
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
    
    def _adjust_view_to_surface(self, surface: Surface):
        """
        Adjust view to center on the surface.
        
        Args:
            surface: Surface to center view on
        """
        if not surface.points:
            return
            
        # Calculate bounds
        x_vals = [p.x for p in surface.points]
        y_vals = [p.y for p in surface.points]
        z_vals = [p.z for p in surface.points]
        
        x_min, x_max = min(x_vals), max(x_vals)
        y_min, y_max = min(y_vals), max(y_vals)
        z_min, z_max = min(z_vals), max(z_vals)
        
        # Calculate center
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        center_z = (z_min + z_max) / 2
        
        # Calculate distance based on size
        size_x = x_max - x_min
        size_y = y_max - y_min
        size_z = z_max - z_min
        
        distance = max(size_x, size_y, size_z) * 1.5
        
        # Set camera position
        self.view_3d.setCameraPosition(
            pos=gl.Vector(center_x, center_y, center_z),
            distance=distance,
            elevation=30,
            azimuth=45
        )
    
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
        
        # Remove contours
        if "contours" in surface_vis:
            for contour in surface_vis["contours"]:
                self.view_3d.removeItem(contour)
        
        # Remove from dictionary
        del self.surfaces[surface_name]
    
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