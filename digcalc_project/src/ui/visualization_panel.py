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
from PySide6.QtCore import Qt, Slot, Signal, QRectF, QPointF, QPoint
# Import QtWidgets for QDialog enum access
from PySide6 import QtWidgets 
# Import QQuickWidget if we were fully integrating QML here
# from PySide6.QtQuickWidgets import QQuickWidget 
# Import QJSValue for type hinting if needed
from PySide6.QtQml import QJSValue # Use for type hint if receiving from QML
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QComboBox
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QWheelEvent

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
# Import the new dialog
from .dialogs.elevation_dialog import ElevationDialog


class InteractiveGraphicsView(QGraphicsView):
    """
    A custom QGraphicsView that adds interactive zooming with Ctrl+Wheel
    and panning with the middle mouse button drag.
    """
    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None):
        super().__init__(scene, parent)

        # Set transformation anchor for zooming centered on mouse
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # Start with no drag mode; middle mouse will activate ScrollHandDrag
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.logger = logging.getLogger(__name__ + ".InteractiveGraphicsView")
        self._is_manual_panning = False # Flag for middle/alt+left panning
        self._last_pan_pos: Optional[QPoint] = None

    def wheelEvent(self, event: QWheelEvent):
        """Handles mouse wheel events for zooming."""
        if event.modifiers() == Qt.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1.0 / zoom_in_factor

            # Save the scene pos at the cursor
            # Use position() which returns QPointF, convert to QPoint for mapToScene
            old_pos = self.mapToScene(event.position().toPoint())

            # Zoom
            if event.angleDelta().y() > 0:
                zoom_factor = zoom_in_factor
                self.logger.debug("Zooming in")
            else:
                zoom_factor = zoom_out_factor
                self.logger.debug("Zooming out")
            self.scale(zoom_factor, zoom_factor)

            # Get the new position
            new_pos = self.mapToScene(event.position().toPoint())

            # Move scene to keep cursor positioned over the same scene point
            delta = new_pos - old_pos
            self.translate(delta.x(), delta.y())

            event.accept() # Indicate we handled this event
        else:
            # Allow default vertical/horizontal scrolling if Ctrl is not pressed
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handles mouse press events to initiate panning with middle button or Alt+Left."""
        alt_pressed = event.modifiers() == Qt.AltModifier
        is_middle_button = event.button() == Qt.MiddleButton
        is_alt_left_button = alt_pressed and event.button() == Qt.LeftButton

        if is_middle_button or is_alt_left_button:
            self.logger.debug("Manual pan initiated.")
            self._is_manual_panning = True
            self._last_pan_pos = event.pos() # Store QPoint view coordinates
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            self.logger.debug("Standard mouse press, letting base class handle (current dragMode: %s).", self.dragMode())
            self._is_manual_panning = False
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handles mouse move for manual panning or passes to base class."""
        if self._is_manual_panning and self._last_pan_pos is not None:
            delta = event.pos() - self._last_pan_pos
            # Scroll the view's scroll bars
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._last_pan_pos = event.pos() # Update position
            event.accept()
        else:
            # Let the base class handle move events, e.g., for ScrollHandDrag
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handles mouse release events to stop manual panning or passes to base class."""
        if self._is_manual_panning and (event.button() == Qt.MiddleButton or event.button() == Qt.LeftButton):
            self.logger.debug("Manual pan finished.")
            self._is_manual_panning = False
            # Check current dragMode to set appropriate cursor
            cursor = Qt.ArrowCursor # Default
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                 cursor = Qt.OpenHandCursor
            elif self.dragMode() == QGraphicsView.DragMode.NoDrag:
                 # If NoDrag, maybe we are tracing? Check parent panel?
                 # For now, assume Arrow or check if viewport cursor is CrossCursor
                 if self.viewport().cursor().shape() == Qt.CrossCursor:
                      cursor = Qt.CrossCursor
            self.setCursor(cursor)
            self._last_pan_pos = None
            event.accept()
        else:
            # Let the base class handle release, e.g., for ScrollHandDrag
            super().mouseReleaseEvent(event)


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
        
        # Temporary default until layer selector UI is implemented
        self.active_layer_name: str = "Existing Surface"
        
        # Layer selector combobox (will be added to MainWindow toolbar)
        self.layer_selector = QComboBox(self) # Parented to panel, but not added to its layout
        self.layer_selector.addItems([
            "Existing Surface",
            "Proposed Surface",
            "Subgrade",
            "Annotations",
            "Report Regions",
        ])
        self.layer_selector.setCurrentText(self.active_layer_name)
        self.layer_selector.setToolTip("Choose the layer new traces belong to")
        self.layer_selector.currentTextChanged.connect(self._on_layer_changed)
        
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
    
    @Slot(str)
    def _on_layer_changed(self, layer: str) -> None:
        """
        Update the active layer when the combo-box changes.
        """
        self.logger.debug("Active tracing layer switched to %s", layer)
        self.active_layer_name = layer
        
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
        # Create the VIEW first
        self.view_2d = InteractiveGraphicsView(None, self) # Pass None for scene initially
        # Create the SCENE, passing the VIEW reference to it
        self.scene_2d = TracingScene(self.view_2d, self) 
        self.view_2d.setScene(self.scene_2d) # Set the scene for the view
        # DragMode, TransformationAnchor, ResizeAnchor are set within InteractiveGraphicsView.__init__
        self.view_2d.setVisible(False) # Keep legacy hidden by default if migrating
        layout.addWidget(self.view_2d)
        
        # --- FIX: Disconnect the legacy signal handler --- #
        # Ensure the connection to the legacy slot is removed.
        try:
            # Attempt to disconnect using the correct signal signature (list, QGraphicsPathItem)
            # Note: This might still fail if the slot signature doesn't match expected,
            # but the primary goal is to prevent the connection if it exists.
            self.scene_2d.polyline_finalized.disconnect(self._on_legacy_polyline_finalized)
            self.logger.debug("Attempted to disconnect legacy polyline_finalized signal from VisualizationPanel._on_legacy_polyline_finalized")
        except (RuntimeError, TypeError) as e:
            self.logger.debug("Legacy polyline_finalized signal was not connected or slot mismatch in VisualizationPanel: %s", e)
            pass # Ignore errors, main goal is removal
        # --- END FIX ---
        
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
        # # Old logic: always hide PDF view when displaying 3D
        # if self.pdf_renderer:
        #      self.logger.info("Hiding PDF background to display 3D surface.")
        #      self.view_2d.setVisible(False)
        #      if HAS_3D: self.view_3d.setVisible(True)
             
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
            # If displaying 3D, ensure 3D view is visible
            # Only hide 2D view if NO PDF is currently loaded
            if not self.pdf_renderer:
                 self.view_2d.setVisible(False)
            # Always ensure 3D view is visible when displaying a surface
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
        self.clear_polylines_from_scene() # Explicitly clear traced lines
        
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

    @Slot(str)
    def _on_layer_changed(self, layer: str) -> None:
        """
        Update the active layer when the combo-box changes.
        """
        self.logger.debug("Active tracing layer switched to %s", layer)
        self.active_layer_name = layer

    @Slot(list)
    def _on_legacy_polyline_finalized(self, points_qpointf: List[QPointF]):
        """
        DEPRECATED: This slot should no longer be called as the connection
        has been removed in _init_ui. Handling is now done in MainWindow.
        """
        self.logger.warning("DEPRECATED _on_legacy_polyline_finalized was called! This should not happen.")
        # Prevent any residual execution
        return
        # ... (Original code removed for clarity) ...

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

    def load_and_display_polylines(self, polylines_by_layer: Dict[str, List[List[Tuple[float, float]]]]):
        """
        Loads polylines from a dictionary (grouped by layer) into the 2D scene.

        This replaces the previous `load_and_display_legacy_polylines`.

        Args:
            polylines_by_layer: Dict where keys are layer names and values are lists of polylines.
        """
        # Clear existing lines first. Important!
        # self.scene_2d.clear_finalized_polylines() # Clearing is now handled within load_polylines_with_layers
        self.scene_2d.load_polylines_with_layers(polylines_by_layer)
        self.logger.info(f"Requested TracingScene to load polylines for {len(polylines_by_layer)} layers.")

    def clear_polylines_from_scene(self):
        """Clears all finalized polylines from the 2D scene."""
        self.scene_2d.clear_finalized_polylines()
        self.logger.info("Cleared all finalized polylines from the 2D scene.")

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
        
        # --- Log formatted data for verification ---
        self.logger.debug(f"Formatted data for QML: {qml_formatted_data}") # <-- TEMPORARY LOG (Uncommented)
        
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

    # --- QML Integration Slots (Placeholder/Future) ---
    @Slot(QJSValue, str) # Or Slot(list, str) if QML sends plain lists
    def _on_qml_polyline_finalized(self, polyline_data_qjs: QJSValue, layer_name: str):
        """
        Slot to receive finalized polyline data from QML.
        Prompts for elevation and saves the polyline with elevation to the project.
        
        Args:
            polyline_data_qjs: The QJSValue representing the array of points from QML.
                           Each point should be an object like { x: number, y: number }.
            layer_name: The name of the layer the polyline belongs to (passed from QML).
        """
        if self.current_project is None:
            self.logger.warning("_on_qml_polyline_finalized called but no project is active.")
            return
            
        self.logger.debug(f"Received finalized polyline from QML for layer: {layer_name}")
        
        # --- Convert QJSValue to Python list of tuples ---
        points: List[Tuple[float, float]] = []
        if not polyline_data_qjs or not polyline_data_qjs.isArray():
            self.logger.error("Invalid polyline data received from QML: not an array or is null.")
            return
            
        length = polyline_data_qjs.property('length').toInt() # QJSValue arrays need length property
        for i in range(length):
            qml_point = polyline_data_qjs.property(i) # Get the QJSValue for the point object
            if qml_point and qml_point.isObject():
                x = qml_point.property('x').toNumber()
                y = qml_point.property('y').toNumber()
                if x is not None and y is not None: # Check conversion success
                    points.append((float(x), float(y)))
                else:
                    self.logger.warning(f"Invalid point data in QML polyline at index {i}: {qml_point}")
            else:
                 self.logger.warning(f"Invalid item in QML polyline array at index {i}: {qml_point}")
        # --- End Conversion ---
        
        if not points:
            self.logger.warning("No valid points extracted from QML polyline data.")
            return

        if len(points) < 2:
            self.logger.warning(f"Received polyline with {len(points)} points from QML, ignoring (needs >= 2).")
            return

        # --- Prompt for Elevation ---
        dlg = ElevationDialog(self)
        z = dlg.value() if dlg.exec() == QtWidgets.QDialog.Accepted else None
        # Create the polyline data structure expected by Project.add_traced_polyline
        polyline_data = {"points": points, "elevation": z}
        # Use the layer_name provided by the QML signal
        layer_to_save = layer_name 

        self.logger.debug(
            "VisualizationPanel: saving QML polyline with %d vertices to layer '%s' (Elevation: %s)",
            len(points),
            layer_to_save,
            z
        )
        # --- Save the polyline to the Project Model ---
        self.current_project.add_traced_polyline(
            polyline_data, # Pass the dictionary
            layer_name=layer_to_save,
            # Elevation is now inside polyline_data
        )
        # Consider emitting a signal if other UI parts need to know about the update
        # self.project_updated.emit() 
        
        self.logger.info(f"Saved polyline with {len(points)} points (Elevation: {z}) to layer '{layer_to_save}' from QML.")

    # --- End QML Slots ---
    
    # --- Legacy Tracing Slots --- 
    @Slot(list)
    def _on_legacy_polyline_finalized(self, points_qpointf: List[QPointF]):
        """
        DEPRECATED: This slot should no longer be called as the connection
        has been removed in _init_ui. Handling is now done in MainWindow.
        """
        self.logger.warning("DEPRECATED _on_legacy_polyline_finalized was called! This should not happen.")
        # Prevent any residual execution
        return
        # ... (Original code removed for clarity) ...

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

    def load_and_display_polylines(self, polylines_by_layer: Dict[str, List[List[Tuple[float, float]]]]):
        """
        Loads polylines from a dictionary (grouped by layer) into the 2D scene.

        This replaces the previous `load_and_display_legacy_polylines`.

        Args:
            polylines_by_layer: Dict where keys are layer names and values are lists of polylines.
        """
        # Clear existing lines first. Important!
        # self.scene_2d.clear_finalized_polylines() # Clearing is now handled within load_polylines_with_layers
        self.scene_2d.load_polylines_with_layers(polylines_by_layer)
        self.logger.info(f"Requested TracingScene to load polylines for {len(polylines_by_layer)} layers.")

    def clear_polylines_from_scene(self):
        """Clears all finalized polylines from the 2D scene."""
        self.scene_2d.clear_finalized_polylines()
        self.logger.info("Cleared all finalized polylines from the 2D scene.")

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
        
        # --- Log formatted data for verification ---
        self.logger.debug(f"Formatted data for QML: {qml_formatted_data}") # <-- TEMPORARY LOG (Uncommented)
        
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