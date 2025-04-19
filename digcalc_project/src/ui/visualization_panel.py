#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualization panel for the DigCalc application.

This module defines the 3D visualization panel for displaying surfaces and calculations.
It also manages the 2D view for PDF rendering and tracing (currently using QGraphicsView,
planned migration to QML via QQuickWidget).
"""

import logging
import enum # Add import
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
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QComboBox, QMessageBox
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QWheelEvent

# Import visualization libraries
try:
    from pyqtgraph.opengl import GLViewWidget, GLMeshItem, GLGridItem, GLLinePlotItem, GLAxisItem
    import pyqtgraph.opengl as gl
    import pyqtgraph
    HAS_3D = True
except ImportError:
    HAS_3D = False
    # Define dummy classes if needed for type hinting when HAS_3D is False
    class GLViewWidget:
        pass
    class GLMeshItem:
        pass
    
# Local imports - Use relative paths
from ..models.surface import Surface, Point3D, Triangle
from ..visualization.pdf_renderer import PDFRenderer, PDFRendererError
from .tracing_scene import TracingScene # Relative within ui package
from ..models.project import Project
# Import the new dialog
from .dialogs.elevation_dialog import ElevationDialog
from .interactive_graphics_view import InteractiveGraphicsView # Import the custom view

# --- Logger --- 
logger = logging.getLogger(__name__)

# --- Enums ---
class DrawingMode(enum.Enum):
    SELECT = 0
    TRACE = 1
    # Add other modes as needed

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
        # self.surfaces: Dict[str, Dict[str, Any]] = {} # Old storage
        # --- NEW: Store mesh items directly --- 
        self.surface_mesh_items: Dict[str, gl.GLMeshItem] = {}
        # --- END NEW ---
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
        
        self.drawing_mode = DrawingMode.SELECT
        self._pdf_bg_item: Optional[QGraphicsPixmapItem] = None # Initialize here
        self.surface_colors: Dict[str, str] = {}
    
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
        Display a surface in the 3D view. This now calls update_surface_mesh.
        Args: surface: Surface to display
        Returns: bool: True if update was initiated, False otherwise
        """
        if not HAS_3D or not isinstance(self.view_3d, gl.GLViewWidget):
            error_msg = "3D visualization libraries not available or view not initialized"
            self.logger.warning(f"Cannot display surface: {error_msg}")
            self.surface_visualization_failed.emit(surface.name, error_msg)
            return False

        if not surface or not surface.points or not surface.triangles:
            error_msg = "Surface has no points or triangles for rendering"
            self.logger.warning(f"Cannot display surface '{surface.name}': {error_msg}")
            self.surface_visualization_failed.emit(surface.name if surface else "Unknown", error_msg)
            return False # Cannot proceed without points/triangles

        try:
            self.show_3d_view() # Ensure 3D view is visible
            self.logger.info(f"Displaying/Updating surface: {surface.name}...")
            self.update_surface_mesh(surface) # Call the new update method

            # Adjust view only if it's the very first surface being added
            if len(self.surface_mesh_items) == 1:
                 self._adjust_view_to_surface(surface)

            # No separate logging here, update_surface_mesh handles it
            return True # Indicate update was attempted

        except Exception as e:
            error_msg = f"Visualization error: {str(e)}"
            self.logger.exception(f"Error displaying surface '{surface.name}': {e}")
            self.surface_visualization_failed.emit(surface.name, error_msg)
            return False

    def update_surface_mesh(self, surface: Surface):
        """
        Adds or replaces the GLMeshItem for the given surface in the 3D view.
        """
        if not HAS_3D or not isinstance(self.view_3d, gl.GLViewWidget):
            self.logger.warning("Cannot update surface mesh: 3D view not available.")
            return

        name = surface.name
        if not name:
             self.logger.error("Cannot update surface mesh: Surface name is missing.")
             return

        self.logger.debug(f"Updating mesh for surface: {name}")

        # Remove existing mesh item if it exists
        if name in self.surface_mesh_items:
            old_mesh = self.surface_mesh_items[name]
            if old_mesh in self.view_3d.items:
                 self.view_3d.removeItem(old_mesh)
                 self.logger.debug(f"Removed existing mesh item for '{name}'.")
            else:
                 # This can happen if the view was cleared externally
                 self.logger.warning(f"Mesh item for '{name}' in dict but not found in view items for removal.")
            # Always remove from dict if key exists
            del self.surface_mesh_items[name]

        # Create new mesh data and item
        mesh_data = self._create_mesh_data(surface)
        if mesh_data:
            try:
                new_mesh = gl.GLMeshItem(
                    vertexes=mesh_data["vertices"],
                    faces=mesh_data["faces"],
                    faceColors=mesh_data["colors"],
                    smooth=True,
                    drawEdges=True,
                    edgeColor=(0, 0, 0, 0.5)
                )
                self.view_3d.addItem(new_mesh)
                self.surface_mesh_items[name] = new_mesh # Store new item
                self.logger.debug(f"Added/Updated mesh item for '{name}'.")
            except Exception as e_mesh:
                 self.logger.exception(f"Error creating GLMeshItem for surface '{name}': {e_mesh}")
                 # Ensure entry is removed if creation failed after removal
                 if name in self.surface_mesh_items:
                     del self.surface_mesh_items[name]
                 self.surface_visualization_failed.emit(name, f"Failed to create 3D mesh: {e_mesh}")
        else:
            self.logger.error(f"Failed to create mesh data for surface '{name}' during update.")
            # Ensure entry is removed if creation failed after removal
            if name in self.surface_mesh_items:
                 del self.surface_mesh_items[name]
            self.surface_visualization_failed.emit(name, "Failed to generate mesh data")

    def _remove_surface_visualization(self, surface_name: str):
        """ Remove a surface's mesh item. """
        if surface_name not in self.surface_mesh_items:
            self.logger.debug(f"Attempted to remove non-existent surface visualization: '{surface_name}'")
            return

        mesh_item = self.surface_mesh_items.pop(surface_name) # Remove from dict and get item
        if HAS_3D and isinstance(self.view_3d, gl.GLViewWidget):
            if mesh_item in self.view_3d.items:
                 self.view_3d.removeItem(mesh_item)
                 self.logger.debug(f"Removed mesh item for surface: {surface_name}")
            else:
                 # Can happen if view was cleared externally
                 self.logger.warning(f"Mesh item for '{surface_name}' not found in view items during removal.")
        else:
             self.logger.warning("Cannot remove mesh item: 3D view not available or not initialized.")

    @Slot(Surface, bool)
    def set_surface_visibility(self, surface: Surface, visible: bool):
        """ Set the visibility of a surface's mesh. """
        if not surface or surface.name not in self.surface_mesh_items:
            # Log only if surface exists but not in visualized items
            if surface and surface.name:
                 self.logger.warning(f"Cannot set visibility for surface '{surface.name}': Mesh item not found.")
            return
        
        mesh_item = self.surface_mesh_items[surface.name]
        if hasattr(mesh_item, 'setVisible'):
             mesh_item.setVisible(visible)
             self.logger.debug(f"Surface '{surface.name}' mesh visibility set to {visible}")
        else:
             self.logger.error(f"Mesh item for '{surface.name}' does not have setVisible method.")

    def clear_all(self):
        """Clears surfaces, PDF background, and traced lines."""
        self.logger.info("Clearing all visualization data.")
        self.clear_pdf_background() # Handles view switching potentially
        self.clear_polylines_from_scene() # Ensure 2D lines are cleared

        # Clear 3D surfaces
        if HAS_3D and isinstance(self.view_3d, gl.GLViewWidget):
            # Use list of keys to avoid RuntimeError: dictionary changed size during iteration
            for surface_name in list(self.surface_mesh_items.keys()):
                self._remove_surface_visualization(surface_name)
        # Ensure the dictionary is empty after attempts
        if self.surface_mesh_items:
             self.logger.warning("surface_mesh_items not empty after clear_all loop. Force clearing.")
             # Force remove remaining items from view just in case
             if HAS_3D and isinstance(self.view_3d, gl.GLViewWidget):
                  for item in self.surface_mesh_items.values():
                       if item in self.view_3d.items:
                            self.view_3d.removeItem(item)
             self.surface_mesh_items.clear()

        # Reset the view camera position if 3D view exists
        if hasattr(self, 'view_3d') and isinstance(self.view_3d, gl.GLViewWidget):
            try:
                 self.view_3d.setCameraPosition(distance=100, elevation=30, azimuth=45)
            except Exception as cam_e:
                 self.logger.warning(f"Could not reset camera position: {cam_e}")

    def has_surfaces(self) -> bool:
         """Checks if any 3D surfaces are loaded and visualization is possible."""
         return HAS_3D and isinstance(self.view_3d, gl.GLViewWidget) and bool(self.surface_mesh_items)

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

        This replaces the `load_and_display_legacy_polylines`.

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

    # --- NEW: Helper Methods --- 
    def has_pdf(self) -> bool:
        """Checks if a PDF background is currently loaded."""
        return self.pdf_renderer is not None

    def current_view(self) -> str:
        """Returns the currently visible view mode ("2d" or "3d")."""
        if self.view_2d and self.view_2d.isVisible():
            return "2d"
        # Check if view_3d exists and is the actual GLWidget before checking visibility
        elif HAS_3D and self.view_3d and isinstance(self.view_3d, gl.GLViewWidget) and self.view_3d.isVisible():
            return "3d"
        else:
            # Fallback if state is ambiguous (e.g., during init or if 3D disabled)
            return "2d" 

    # --- NEW: View Switching Methods --- 
    def show_2d_view(self):
        """Shows the 2D view (PDF/Tracing) and hides the 3D view."""
        self.logger.debug("Switching to 2D view.")
        if self.view_3d: # Check if view_3d widget exists
            self.view_3d.setVisible(False)
        self.view_2d.setVisible(True)
        self.view_2d.raise_() # Bring to front

    def show_3d_view(self):
        """Shows the 3D view (Terrain) and hides the 2D view."""
        if not HAS_3D or not isinstance(self.view_3d, gl.GLViewWidget):
            self.logger.warning("Attempted to switch to 3D view, but it is unavailable.")
            # Optionally show a message to the user?
            # Maybe show the placeholder QLabel if it exists?
            if isinstance(self.view_3d, QLabel): self.view_3d.setVisible(True)
            self.view_2d.setVisible(False) # Still hide 2d
            return
        self.logger.debug("Switching to 3D view.")
        self.view_2d.setVisible(False)
        self.view_3d.setVisible(True)
        self.view_3d.raise_() # Bring to front

    # --- Update Existing Methods --- 
    def _adjust_view_to_surface(self, surface: Surface):
         if not HAS_3D or not isinstance(self.view_3d, gl.GLViewWidget) or not surface or not surface.points:
             return
         # ... rest of adjust logic using np ...
         try:
            points_list = list(surface.points.values())
            if not points_list: return # No points to adjust to
            
            x_vals = [p.x for p in points_list]
            y_vals = [p.y for p in points_list]
            z_vals = [p.z for p in points_list]
            
            center_x = (min(x_vals) + max(x_vals))/2
            center_y = (min(y_vals) + max(y_vals))/2
            center_z = (min(z_vals) + max(z_vals))/2

            size = max(max(x_vals) - min(x_vals), max(y_vals) - min(y_vals), max(z_vals) - min(z_vals), 1)
            distance = size * 2 # Adjust multiplier as needed

            center_vec = pyqtgraph.Vector(center_x, center_y, center_z)

            self.view_3d.setCameraPosition(
                pos=center_vec,  # Use 'pos' argument for the target position
                distance=distance,
                elevation=30,
                azimuth=45
            )
            
            self.logger.debug(f"Adjusted 3D view pos={center_vec}, distance={distance}")
         except Exception as e:
            self.logger.error(f"Error adjusting 3D view: {e}", exc_info=True)

    def _create_mesh_data(self, surface: Surface) -> Optional[Dict[str, Any]]:
         if not HAS_3D or not surface.triangles or not surface.points:
             return None
         # ... rest of mesh creation using np ...
         try:
            points_list = list(surface.points.values())
            points_id_map = {p.id: i for i, p in enumerate(points_list)}
            vertices = np.array([[p.x, p.y, p.z] for p in points_list])
            faces = []
            # ... face creation loop ...
            for tri_id, triangle in surface.triangles.items():
                try:
                    i1 = points_id_map[triangle.p1.id]
                    i2 = points_id_map[triangle.p2.id]
                    i3 = points_id_map[triangle.p3.id]
                    faces.append([i1, i2, i3])
                except (KeyError, AttributeError) as e:
                    self.logger.warning(f"Invalid triangle ID {tri_id} in surface {surface.name}: {e}")
                    continue
            
            if not faces: return None
            faces = np.array(faces)
            # ... color calculation ...
            z_min = np.min(vertices[:, 2])
            z_max = np.max(vertices[:, 2])
            z_range = max(z_max - z_min, 0.1)
            colors = np.zeros((len(faces), 4))
            # ... color loop ...
            for i, face in enumerate(faces):
                z_avg = np.mean(vertices[face, 2])
                t = np.clip((z_avg - z_min) / z_range, 0, 1)
                # Simple blue-red gradient
                colors[i] = [t, 0, 1-t, 0.7] # R, G, B, Alpha
                
            return {"vertices": vertices, "faces": faces, "colors": colors}
         except Exception as e:
             self.logger.exception(f"Error creating mesh data: {e}")
             return None

    # Add methods related to 2D scene interaction if needed
    def clear_polylines_from_scene(self):
        if hasattr(self, "scene_2d"):
             self.scene_2d.clear_finalized_polylines()

    def load_and_display_polylines(self, polylines_by_layer):
         if hasattr(self, "scene_2d"):
             self.scene_2d.load_polylines_with_layers(polylines_by_layer)

    # Potentially add wheelEvent override if needed here instead of InteractiveGraphicsView
    # def wheelEvent(self, event):
    #    pass 

    @Slot(str)
    def _on_visualization_failed(self, error_message: str):
        """Handle errors during surface visualization."""
        # Placeholder: Implement proper error handling (e.g., show message box)
        logger.error(f"Surface visualization failed: {error_message}")
        QMessageBox.critical(self, "Visualization Error", f"Failed to visualize surface:\n{error_message}") 

    @Slot()
    def clear_pdf_background(self):
        """Removes the PDF background image from the 2D view."""
        if self._pdf_bg_item and self._pdf_bg_item in self.scene_2d.items():
            self.scene_2d.removeItem(self._pdf_bg_item)
            self._pdf_bg_item = None
            logger.info("PDF background cleared.")
            # Optionally reset view scale/position if needed
            # self.view_2d.fitInView(self.scene_2d.sceneRect(), Qt.KeepAspectRatio) 

    @Slot(str, int)
    def load_pdf_background(self, pdf_path: str, dpi: int = 150):
        """Loads a PDF page as the background for the 2D view."""
        self.logger.info(f"Attempting to load PDF background: '{pdf_path}' at {dpi} DPI")
        
        # Close existing renderer if path changes or if it's None
        if self.pdf_renderer and self.pdf_renderer.pdf_path != pdf_path:
             self.pdf_renderer.close()
             self.pdf_renderer = None
             
        # Create renderer only if needed
        if self.pdf_renderer is None:
            try:
                # Pass pdf_path and dpi to constructor
                self.pdf_renderer = PDFRenderer(pdf_path=pdf_path, dpi=dpi)
            except PDFRendererError as e_init:
                self.logger.error(f"Failed to initialize PDF Renderer for '{pdf_path}': {e_init}")
                QMessageBox.critical(self, "PDF Load Error", f"""Could not initialize PDF renderer:
{e_init}"""
                )
                self.pdf_renderer = None # Ensure it's None
                return # Stop if renderer failed to init
            except FileNotFoundError:
                self.logger.error(f"PDF file not found during renderer init: {pdf_path}")
                # Use triple quotes for multi-line f-string
                QMessageBox.critical(self, "PDF Load Error", f"""PDF file not found:
{pdf_path}"""
                )
                self.pdf_renderer = None
                return
            except Exception as e_init_other:
                 self.logger.exception(f"Unexpected error initializing PDF Renderer: {e_init_other}")
                 QMessageBox.critical(self, "PDF Load Error", f"""Unexpected error initializing PDF renderer:
{e_init_other}"""
                 )
                 self.pdf_renderer = None
                 return

        # Now try rendering the page using the (hopefully) initialized renderer
        try:
            # Render the first page for now (add page selection later)
            self.current_pdf_page = 1
            qimage: Optional[QImage] = self.pdf_renderer.get_page_image(self.current_pdf_page)
            
            if qimage is None:
                 raise PDFRendererError(f"Renderer failed to provide image for page {self.current_pdf_page}.")
            
            # Clear previous background if any
            self.clear_pdf_background()

            # Display the new image
            pixmap = QPixmap.fromImage(qimage)
            self._pdf_bg_item = QGraphicsPixmapItem(pixmap)
            self.scene_2d.addItem(self._pdf_bg_item)
            self.scene_2d.setSceneRect(self._pdf_bg_item.boundingRect()) # Set scene rect to image size
            
            self.logger.info(f"Successfully loaded PDF page {self.current_pdf_page} from '{pdf_path}'")
            
            # Switch to 2D view and fit content
            self.show_2d_view()
            self.view_2d.fitInView(self._pdf_bg_item, Qt.KeepAspectRatio)
            
            # Allow tracing only after PDF is loaded
            # Consider enabling tracing action if it exists in MainWindow
            # Example: self.parent().toggle_tracing_action.setEnabled(True)

        except PDFRendererError as e:
            self.logger.error(f"Failed to load PDF background: {e}")
            QMessageBox.critical(self, "PDF Load Error", f"""Could not load PDF:
{e}"""
            )
            self._pdf_bg_item = None # Ensure item is None on failure
        except Exception as e:
            self.logger.exception(f"Unexpected error loading PDF: {e}")
            QMessageBox.critical(self, "PDF Load Error", f"""An unexpected error occurred:
{e}"""
            )
            self._pdf_bg_item = None # Ensure item is None on failure 

    @Slot(int)
    def set_pdf_page(self, page_number: int):
        """Sets the currently displayed PDF page."""
        if not self.pdf_renderer:
            self.logger.warning("Attempted to set PDF page, but no renderer is active.")
            return

        self.logger.info(f"Attempting to set PDF display to page: {page_number}")
        new_image = self.pdf_renderer.get_page_image(page_number)

        if new_image:
            self.current_pdf_page = page_number
            pixmap = QPixmap.fromImage(new_image)
            
            # Update existing item if possible, otherwise create new
            if self._pdf_bg_item:
                self._pdf_bg_item.setPixmap(pixmap)
                self.logger.debug(f"Updated existing PDF background item to page {page_number}.")
            else:
                self._pdf_bg_item = QGraphicsPixmapItem(pixmap)
                self.scene_2d.addItem(self._pdf_bg_item)
                self.logger.debug(f"Created new PDF background item for page {page_number}.")

            # Ensure scene rect is updated (might be same size, but good practice)
            self.scene_2d.setSceneRect(self._pdf_bg_item.boundingRect())
            
            # Ensure 2D view is visible
            if not self.view_2d.isVisible():
                self.show_2d_view()
            
            # Optionally fit view, though maybe preserve user zoom/pan?
            # self.view_2d.fitInView(self._pdf_bg_item, Qt.KeepAspectRatio)
            self.logger.info(f"Successfully set PDF display to page {page_number}.")
        else:
            self.logger.error(f"Failed to get image for page {page_number} from renderer.")
            # Optionally show error message?
            # QMessageBox.warning(self, "PDF Page Error", f"Could not load page {page_number}.") 