#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualization panel for the DigCalc application.

This module defines the 3D visualization panel for displaying surfaces and calculations.
It also manages the 2D view for PDF rendering and tracing (currently using QGraphicsView,
planned migration to QML via QQuickWidget).
"""

import logging
from typing import Optional, Dict, List, Any, Tuple
import numpy as np

# PySide6 imports
from PySide6.QtCore import Qt, Slot, Signal, QRectF, QPointF
# Import QQuickWidget if we were fully integrating QML here
# from PySide6.QtQuickWidgets import QQuickWidget 
# Import QJSValue for type hinting if needed
from PySide6.QtQml import QJSValue # Use for type hint if receiving from QML
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QImage, QPixmap

# Import visualization libraries
try:
    from pyqtgraph.opengl import GLViewWidget, GLMeshItem, GLGridItem, GLLinePlotItem, GLAxisItem
    import pyqtgraph.opengl as gl
    import pyqtgraph
    HAS_3D = True
except ImportError:
    HAS_3D = False
    
# Local imports - Use relative paths
from ..models.surface import Surface, Point3D, Triangle
from ..visualization.pdf_renderer import PDFRenderer, PDFRendererError
from .tracing_scene import TracingScene # Relative within ui package
from ..models.project import Project


class VisualizationPanel(QWidget):
    """
    Panel for 3D visualization of surfaces and calculation results.
    Also includes components for 2D PDF viewing and tracing.
    """
    
    # Signals
    surface_visualization_failed = Signal(str, str)  # (surface name, error message)
    # Signal to indicate polyline data needs to be sent TO QML
    request_polylines_load_to_qml = Signal() 
    
    def __init__(self, parent=None):
        """
        Initialize the visualization panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.surfaces: Dict[str, Dict[str, Any]] = {}  # Dictionary to store surface visualization objects
        self.pdf_renderer: Optional[PDFRenderer] = None
        self.pdf_background_item: Optional[QGraphicsPixmapItem] = None
        self.current_pdf_page: int = 1
        self.current_project: Optional[Project] = None
        
        # --- Tracing Scene and Layer Panel ---
        self.scene_2d: TracingScene = None # Will be initialized in _init_ui
        # --- QML Widget Placeholder (to be added when integrating QML) ---
        # self.qml_widget: Optional[QQuickWidget] = None 
        
        # Initialize UI components
        self._init_ui()
        
        # Connect signals
        self.surface_visualization_failed.connect(self._on_visualization_failed)
        # Connect the request signal to the actual loading method
        self.request_polylines_load_to_qml.connect(self.load_polylines_into_qml)
        
        self.logger.debug("VisualizationPanel initialized")
    
    def _init_ui(self):
        """Initialize the UI components, including QGraphicsView for 2D/PDF."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- QML View Placeholder ---
        # When integrating QML, instantiate QQuickWidget here
        # self.qml_widget = QQuickWidget(self)
        # self.qml_widget.setSource(QUrl.fromLocalFile('path/to/your/TracingComponent.qml')) # Example
        # self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        # layout.addWidget(self.qml_widget)
        # self.qml_widget.setVisible(False) # Initially hidden?
        
        # --- Get the root QML object to interact with it ---
        # self.qml_root_object = self.qml_widget.rootObject()
        # if self.qml_root_object:
        #    # Connect signals FROM QML (example)
        #    self.qml_root_object.polylineFinalized.connect(self._on_qml_polyline_finalized)
        #    self.logger.info("Connected to QML signals.")
        # else:
        #    self.logger.error("Failed to get QML root object!")

        # --- Legacy 2D Scene/View (To be removed/replaced by QML) ---
        self.scene_2d = TracingScene(self) # Create the legacy scene
        self.view_2d = QGraphicsView(self.scene_2d)
        self.view_2d.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view_2d.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view_2d.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view_2d.setVisible(False) # Keep legacy hidden by default if migrating
        layout.addWidget(self.view_2d)
        
        # Connect legacy scene signal (keep for now, remove when QML fully replaces it)
        self.scene_2d.polyline_finalized.connect(self._on_legacy_polyline_finalized)
        
        # --- 3D View --- 
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
        
        self.logger.debug("VisualizationPanel UI initialized")
    
    def set_project(self, project: Optional[Project]):
        """
        Sets the current project for the panel, allowing access to project data.
        """
        self.current_project = project
        # Potentially update visualizations based on the new project here?
        # For now, just store the reference.

    def display_surface(self, surface: Surface) -> bool:
        """
        Display a surface in the 3D view.
        
        Args:
            surface: Surface to display
            
        Returns:
            bool: True if display was successful, False otherwise
        """
        # Hide PDF view if displaying surfaces for now?
        if self.pdf_renderer:
             self.logger.info("Hiding PDF background to display 3D surface.")
             self.view_2d.setVisible(False)
             if HAS_3D: self.view_3d.setVisible(True)
             # Or should we overlay points/lines on the 2D view?
             
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
            # If displaying 3D, ensure 2D/tracing view is hidden and 3D is visible
            self.view_2d.setVisible(False)
            if HAS_3D: self.view_3d.setVisible(True)
            
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
        """Clears all visualizations, including PDF background and legacy traced lines."""
        self.clear_pdf_background()
        self.clear_displayed_legacy_polylines() # Explicitly clear legacy lines
        
        if HAS_3D:
            for surface_name in list(self.surfaces.keys()):
                self._remove_surface_visualization(surface_name)
        self.surfaces.clear()
        self.logger.info("Cleared all visualizations.")
        
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

    # --- PDF Background and Tracing Methods ---
    
    def load_pdf_background(self, pdf_path: str, dpi: int = 150):
        """Loads a PDF and displays the first page as background."""
        self.logger.info(f"Attempting to load PDF background: {pdf_path}")
        # Clean up previous PDF if any
        self.clear_pdf_background()

        try:
            self.pdf_renderer = PDFRenderer(pdf_path, dpi)
            self.current_pdf_page = 1
            self._display_current_pdf_page()
            
            # Make 2D view visible and hide 3D view
            self.view_2d.setVisible(True)
            if HAS_3D: self.view_3d.setVisible(False)
            self.logger.info(f"PDF background loaded: {pdf_path}")
            
        except (FileNotFoundError, PDFRendererError) as e:
             self.logger.error(f"Failed to load PDF: {e}")
             # Propagate error via signal or show message?
             # For now, just log it.
             # self.pdf_load_failed.emit(str(e)) # Example signal
             self.pdf_renderer = None # Ensure renderer is None on failure
             self.view_2d.setVisible(False) # Keep 2D view hidden
             # Also hide QML view if it exists
             # if self.qml_widget: self.qml_widget.setVisible(False) 
             if HAS_3D:
                  self.view_3d.setVisible(True) # Ensure 3D view is visible
             # Re-raise or handle? For now, just log and return.
             raise e # Re-raise to be caught by MainWindow

    def _display_current_pdf_page(self):
        """Renders and displays the current PDF page in the TracingScene."""
        if not self.pdf_renderer:
            self.logger.warning("Cannot display PDF page: PDF renderer not initialized.")
            return

        try:
            page_image = self.pdf_renderer.get_page_image(self.current_pdf_page)
            if page_image:
                # Set the image in the TracingScene
                self.scene_2d.set_background_image(page_image)
                # Fit view to the scene content (the background image)
                self.view_2d.fitInView(self.scene_2d.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
                # --- Pass PDF info TO QML component ---
                # if self.qml_root_object and hasattr(self.qml_root_object, 'loadPdfPage'):
                #     # Assuming QML can handle the QImage directly or needs a path/data
                #     # This might need conversion depending on QML component's needs
                #     # For example, save QImage to temp file and pass path, or pass raw data
                #     # For now, let's assume it can take basic info
                #     page_width = page_image.width()
                #     page_height = page_image.height()
                #     # You might need to provide the image data itself if QML can't load from path easily
                #     # image_path_for_qml = self.pdf_renderer.get_image_path_for_page(self.current_pdf_page) # Hypothetical method
                #     self.qml_root_object.loadPdfPage(self.pdf_renderer.pdf_path, self.current_pdf_page, page_width, page_height, self.pdf_renderer.dpi)
                #     self.logger.info(f"Sent PDF page {self.current_pdf_page} info to QML.")
                self.logger.info(f"Displayed PDF page {self.current_pdf_page}")
            else:
                # Clear background if image is invalid
                self.scene_2d.set_background_image(None)
                self.logger.warning(f"Failed to get image for PDF page {self.current_pdf_page}.")

        except PDFRendererError as e:
            self.logger.error(f"Error displaying PDF page {self.current_pdf_page}: {e}")
            self.scene_2d.set_background_image(None) # Clear on error
        except Exception as e:
            self.logger.exception(f"Unexpected error displaying PDF page: {e}")
            self.scene_2d.set_background_image(None) # Clear on error

    def set_pdf_page(self, page_number: int):
        """Sets the current PDF page to display."""
        if not self.pdf_renderer or not (1 <= page_number <= self.pdf_renderer.get_page_count()):
            self.logger.warning(f"Cannot set PDF page to invalid number: {page_number}")
            return
            
        if page_number != self.current_pdf_page:
            self.current_pdf_page = page_number
            self._display_current_pdf_page()
            
    def clear_pdf_background(self):
        """Clears the PDF background image and hides the 2D view."""
        self.logger.info("Clearing PDF background.")
        if self.pdf_renderer:
            self.pdf_renderer.close()
            self.pdf_renderer = None
        
        # Clear the background in TracingScene (legacy)
        self.scene_2d.set_background_image(None)
        
        # --- Clear background in QML ---
        # if self.qml_root_object and hasattr(self.qml_root_object, 'clearPdfBackground'):
        #    self.qml_root_object.clearPdfBackground()
        #    self.logger.info("Cleared PDF background in QML.")
        
        # Optionally hide the 2D/QML view and show 3D view if available
        self.view_2d.setVisible(False)
        # if self.qml_widget: self.qml_widget.setVisible(False)
        if HAS_3D:
             self.view_3d.setVisible(True)
        else:
            # If no 3D view, maybe show a placeholder or leave blank?
             pass 

    # --- Optional Tracing Control and Signal Handling ---

    @Slot(list)
    def _on_legacy_polyline_finalized(self, points: List[QPointF]):
        """
        Slot called when the *legacy* tracing scene emits a finalized polyline.
        Stores the polyline data in the current project (uses a default layer).
        
        Args:
            points (List[QPointF]): List of vertices in the finalized polyline.
        """
        if not self.current_project:
            self.logger.warning("Cannot save finalized polyline: No active project.")
            return
        
        # Convert QPointF list to list of tuples (float, float)
        point_tuples: List[Tuple[float, float]] = [(p.x(), p.y()) for p in points]
        
        self.logger.info(f"Received finalized polyline from LEGACY scene with {len(point_tuples)} points.")
        
        # Store the polyline in the project using a default layer
        try:
            # Use the updated project model method with a default layer
            default_layer = "Legacy Traces"
            self.current_project.add_traced_polyline(point_tuples, default_layer)
            self.logger.info(f"Legacy polyline with {len(point_tuples)} vertices added to project layer '{default_layer}'.")
        except Exception as e:
            self.logger.error(f"Failed to add legacy polyline to project: {e}", exc_info=True)
            # Optionally, inform the user via status bar or message box
            # self.parent().statusBar().showMessage(f"Error saving polyline: {e}", 5000)
            # QMessageBox.warning(self, "Error", f"Could not save the traced polyline: {e}")
            # Should we remove the visually finalized line from the scene if saving fails?
            # For now, we leave it, but the project data is out of sync.

    def set_tracing_mode(self, enabled: bool):
         """
         Enables or disables the interactive tracing mode on the scene.
         Also changes the view's drag mode and cursor accordingly.
         """
         # Only allow enabling tracing if a PDF is loaded
         if enabled and not self.pdf_renderer:
             self.logger.warning("Cannot enable tracing: No PDF background is loaded.")
             # Optionally force the action back to unchecked if called directly
             # main_window = self.parent() # Need a way to access MainWindow if needed
             # if main_window and hasattr(main_window, 'toggle_tracing_action'):
             #     main_window.toggle_tracing_action.setChecked(False)
             return
             
         if enabled:
              self.scene_2d.start_drawing()
              self.logger.info("Tracing mode enabled.")
              # Disable view dragging and set cross cursor
              self.view_2d.setDragMode(QGraphicsView.DragMode.NoDrag)
              self.view_2d.viewport().setCursor(Qt.CrossCursor)
              # Ensure 2D view is visible
              if not self.view_2d.isVisible():
                  self.view_2d.setVisible(True)
                  if HAS_3D: self.view_3d.setVisible(False)
         else:
              self.scene_2d.stop_drawing()
              self.logger.info("Tracing mode disabled.")
              # Restore view dragging and reset cursor
              self.view_2d.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
              # Use OpenHandCursor when ScrollHandDrag is active
              self.view_2d.viewport().setCursor(Qt.OpenHandCursor)
              # Reset cursor etc. <- covered by line above

    def load_and_display_legacy_polylines(self, polylines: List[List[Tuple[float, float]]]):
        """
        Loads polylines from data and displays them on the LEGACY TracingScene.
        Clears any previously displayed finalized polylines first.
        """
        if hasattr(self.scene_2d, 'load_polylines'):
            self.logger.info(f"Loading and displaying {len(polylines)} traced polylines on LEGACY scene.")
            self.scene_2d.load_polylines(polylines)
        else:
            self.logger.error("Cannot load polylines: TracingScene does not have 'load_polylines' method.")

    def clear_displayed_legacy_polylines(self):
        """
        Clears all finalized polylines currently displayed on the LEGACY TracingScene.
        """
        if hasattr(self.scene_2d, 'clear_finalized_polylines'):
            self.logger.info("Clearing displayed polylines from LEGACY scene.")
            self.scene_2d.clear_finalized_polylines()
        else:
            self.logger.error("Cannot clear polylines: TracingScene does not have 'clear_finalized_polylines' method.")

    @Slot()
    def load_polylines_into_qml(self):
        """
        Retrieves layered polyline data from the current project
        and sends it to the QML tracing component.
        Assumes a QML function like `loadPolylines(polylinesDict)` exists.
        """
        if not self.current_project:
            self.logger.warning("Cannot load polylines into QML: No active project.")
            return
        
        # Get the dictionary {layer_name: [polyline1, polyline2, ...]} 
        polylines_by_layer = self.current_project.traced_polylines
        
        # Ensure data format is suitable for QML (e.g., list of lists for points)
        qml_formatted_data = {}
        total_polylines = 0
        for layer, polylines in polylines_by_layer.items():
            formatted_polylines = []
            for poly in polylines:
                # Convert list of tuples [(x,y), ...] to list of lists [[x,y], ...]
                formatted_poly = [[pt[0], pt[1]] for pt in poly]
                formatted_polylines.append(formatted_poly)
                total_polylines += 1
            qml_formatted_data[layer] = formatted_polylines
        
        self.logger.info(f"Preparing to load {total_polylines} polylines across {len(qml_formatted_data)} layers into QML.")
        
        # --- Call the QML function --- 
        # try:
        #     if self.qml_root_object and hasattr(self.qml_root_object, 'loadPolylines'):
        #          # Assuming QML function accepts a dictionary/JS object
        #          self.qml_root_object.loadPolylines(qml_formatted_data)
        #          self.logger.info("Successfully sent polyline data to QML component.")
        #     elif self.qml_root_object:
        #          self.logger.error("QML root object found, but 'loadPolylines' method is missing.")
        #     else:
        #          self.logger.error("Cannot load polylines into QML: QML component not accessible.")
        # except Exception as e:
        #     self.logger.error(f"Error calling QML function 'loadPolylines': {e}", exc_info=True)
        # Add user feedback if needed

    # Add wheel event for zooming 2D view
    def wheelEvent(self, event):
        # Zooming functionality
        if event.modifiers() & Qt.ControlModifier:
            if not self.view_2d.isVisible():
                super().wheelEvent(event)
                return
            
            zoom_factor = 1.15 # Adjust as needed
            if event.angleDelta().y() > 0:
                self.view_2d.scale(zoom_factor, zoom_factor)
            else:
                self.view_2d.scale(1.0 / zoom_factor, 1.0 / zoom_factor)
            event.accept()
        else:
            super().wheelEvent(event) 