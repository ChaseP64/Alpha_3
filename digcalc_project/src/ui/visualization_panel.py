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
from pathlib import Path
import fitz # PyMuPDF

# PySide6 imports
from PySide6.QtCore import Qt, Slot, Signal, QRectF, QPointF, QPoint, QSize
from PySide6 import QtWidgets
from PySide6.QtGui import QPixmap, QImage, QPainter # Added QPainter, QSize
from PySide6.QtWidgets import QGraphicsPixmapItem
# Import QQuickWidget if we were fully integrating QML here
# from PySide6.QtQuickWidgets import QQuickWidget 
# Import QJSValue for type hinting if needed
from PySide6.QtQml import QJSValue # Use for type hint if receiving from QML
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsView, QGraphicsScene, QComboBox, QMessageBox, QStackedWidget
from PySide6.QtGui import QMouseEvent, QWheelEvent, QTransform
# Removed: from PySide6.QtPdf import QPdfDocument

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
from ..utils.color_maps import dz_to_rgba # Import the new color utility
from ..services.pdf_service import PdfService  # local import to avoid cycles

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
        self._pymupdf_doc: Optional[fitz.Document] = None
        self._pdf_bg_item: Optional[QGraphicsPixmapItem] = None
        self.current_pdf_page: int = 1
        self.current_project: Optional[Project] = None
        
        # Temporary default until layer selector UI is implemented
        self.active_layer_name: str = "Existing Surface"
        
        # Give the panel a minimum size
        self.setMinimumSize(400, 300)
        
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
        
        # --- Cut/Fill Map Attributes ---
        self._dz_image_item: Optional[QGraphicsPixmapItem] = None
        self._dz_mesh_item: Optional[gl.GLMeshItem] = None # For 3D pyqtgraph mesh
        self._cutfill_visible: bool = False
        # --- End Cut/Fill Map Attributes ---
        
        # Initialize UI components
        self._init_ui()
        
        # Connect signals
        self.surface_visualization_failed.connect(self._on_visualization_failed)
        # Connect the request signal to the actual loading method
        self.request_polylines_load_to_qml.connect(self.load_polylines_into_qml)
        
        self.logger.debug("VisualizationPanel initialized")
        
        self.drawing_mode = DrawingMode.SELECT
        self.surface_colors: Dict[str, str] = {}
    
    @Slot(str)
    def _on_layer_changed(self, layer: str) -> None:
        """
        Update the active layer when the combo-box changes.
        """
        self.logger.debug("Active tracing layer switched to %s", layer)
        self.active_layer_name = layer
        
    def _init_ui(self):
        """Initialize the UI components, using QStackedWidget for views."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create the Stacked Widget
        self.stacked_widget = QStackedWidget(self)
        layout.addWidget(self.stacked_widget)

        # --- Legacy 2D Scene/View --- 
        self.view_2d = InteractiveGraphicsView(None, self)
        self.scene_2d = TracingScene(self.view_2d, self)
        self.view_2d.setScene(self.scene_2d)
        # Add render hints for better quality rendering
        self.view_2d.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        # self.view_2d.setVisible(False) # Visibility managed by stack
        self.stacked_widget.addWidget(self.view_2d)

        # REMOVED: Disconnect legacy signal handler
        
        # --- 3D View / Placeholder --- 
        if HAS_3D:
            self.view_3d = GLViewWidget()
            # ... setup grid, axis ...
            grid = GLGridItem()
            grid.setSize(x=100, y=100, z=0)
            grid.setSpacing(x=10, y=10, z=10)
            self.view_3d.addItem(grid)
            axis = GLAxisItem()
            axis.setSize(x=20, y=20, z=20)
            self.view_3d.addItem(axis)
            # self.view_3d.setVisible(False) # Visibility managed by stack
            self.stacked_widget.addWidget(self.view_3d)
            self.logger.debug("3D view initialized and added to stack")
        else:
            # Create and add the placeholder QLabel to the stack
            self.view_3d = QLabel("3D visualization not available.\nPlease install pyqtgraph and PyOpenGL.")
            self.view_3d.setAlignment(Qt.AlignCenter)
            self.view_3d.setStyleSheet("background-color: #f0f0f0; padding: 20px;")
            # self.view_3d.setVisible(False) # Visibility managed by stack
            self.stacked_widget.addWidget(self.view_3d)
            self.logger.warning("3D visualization libraries not available, placeholder added to stack")
        
        # Set initial view (e.g., default to 3D/placeholder)
        self.stacked_widget.setCurrentWidget(self.view_3d)
        
        self.logger.debug("VisualizationPanel UI initialized with QStackedWidget")
    
    def set_project(self, project: Optional[Project]):
        """
        Sets the current project for the visualization panel and updates the display.

        Args:
            project: The Project object to visualize, or None to clear.
        """
        self.logger.info(f"Setting project in VisualizationPanel: {project.name if project else 'None'}")
        self.current_project = project

        # Clear existing visuals first
        self.clear_all() # This now closes pymupdf doc

        if project:
            # Load PDF Background if available
            if project.pdf_background_path and Path(project.pdf_background_path).is_file():
                self.logger.debug(f"Loading PDF background from project: {project.pdf_background_path}, page {project.pdf_background_page}, dpi {project.pdf_background_dpi}")
                try:
                    # Call the updated load_pdf_background with initial page and dpi
                    self.load_pdf_background(
                        project.pdf_background_path,
                        initial_page=project.pdf_background_page,
                        dpi=project.pdf_background_dpi
                    )
                    # No need to call set_pdf_page here anymore
                except Exception as e:
                    self.logger.error(f"Failed to load PDF background from project: {e}", exc_info=True)
                    # Optionally show a non-critical message to the user
                    # QMessageBox.warning(self, "PDF Load Warning", f"Could not load PDF background image:\n{project.pdf_background_path}\n\nError: {e}")
            else:
                if project.pdf_background_path:
                     self.logger.warning(f"PDF background path in project not found: {project.pdf_background_path}")
                else:
                     self.logger.debug("No PDF background path in project.")

            # Load Surfaces
            if project.surfaces:
                self.logger.debug(f"Loading {len(project.surfaces)} surfaces from project.")
                for surface_name, surface in project.surfaces.items():
                    self.logger.debug(f"Displaying surface: {surface_name}")
                    self.display_surface(surface)
            else:
                self.logger.debug("No surfaces found in project.")

            # --- Adjust 3D Camera AFTER loading all surfaces --- 
            if project.surfaces:
                all_points = []
                for surf in project.surfaces.values():
                    if surf and surf.points: # Check if surface and points exist
                        # Assuming surf.points is currently a dict {id: Point3D}
                        # Need to adapt if it changes structure
                        all_points.extend(surf.points.values()) 
                
                if all_points:
                    self._adjust_view_to_points(all_points)
                else:
                     self.logger.warning("Project has surfaces, but no points found to adjust camera view.")
            # --- End Adjust Camera ---

            # Load Traced Polylines
            if project.traced_polylines:
                self.logger.debug(f"Loading traced polylines from project ({len(project.traced_polylines)} layers).")
                # Assuming load_and_display_polylines takes the dict directly
                self.load_and_display_polylines(project.traced_polylines)
            else:
                self.logger.debug("No traced polylines found in project.")

            # --- Explicitly fit view AFTER loading everything --- 
            if self.view_2d.isVisible() and self.scene_2d:
                 # Fit to the entire scene content (PDF + polylines)
                 try:
                     # Ensure scene rect is updated if items were added
                     self.scene_2d.setSceneRect(self.scene_2d.itemsBoundingRect())
                     self.view_2d.fitInView(self.scene_2d.sceneRect(), Qt.KeepAspectRatio)
                     self.logger.debug("Called fitInView for 2D scene after loading project content.")
                 except Exception as fit_e:
                     self.logger.error(f"Error calling fitInView for 2D view: {fit_e}", exc_info=True)
            # --- End Fit View --- 
        else:
            # No project, ensure view is cleared (already done by clear_all)
            self.logger.info("Project cleared from VisualizationPanel.")
            # Set a default view (e.g., empty 3D)
            self.show_3d_view()

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

            # Adjust view every time a surface is displayed/updated
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

        self.logger.info(f"Attempting to update/create mesh for surface: {name}")

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
        mesh_data = None
        try:
            mesh_data = self._create_mesh_data(surface)
        except Exception as e_data:
            self.logger.error(f"Error calling _create_mesh_data for surface '{name}': {e_data}", exc_info=True)
            # Emit failure signal if appropriate?
            self.surface_visualization_failed.emit(name, f"Failed to generate mesh data: {e_data}")
            return # Exit if data creation fails

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
                # --- Explicitly set visible --- 
                new_mesh.setVisible(True)
                # --- End Set Visible ---
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
        """Clears surfaces, PDF background, traced lines, and cut/fill map."""
        self.logger.info("Clearing all visualization data.")
        self.clear_pdf_background()
        self.clear_polylines_from_scene()
        self.clear_cutfill_map() # Added call to clear cut/fill map

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
                 self.view_3d.update()
            except Exception as cam_e:
                 self.logger.warning(f"Could not reset camera position: {cam_e}")

        # Clear project reference
        self.current_project = None 

        # Reset camera/view
        if hasattr(self, 'view_2d'):
            self.view_2d.viewport().update()

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
        current = self.stacked_widget.currentWidget()
        if current == self.view_2d:
            return "2d"
        elif current == self.view_3d:
            # Return "3d" even if it's the placeholder Label
            return "3d"
        else:
            # Should not happen if stack contains only view_2d and view_3d
            logger.warning("Current widget in stacked_widget is unexpected!")
            return "unknown"

    # --- NEW: View Switching Methods --- 
    def show_2d_view(self):
        """Shows the 2D view (PDF/Tracing) and hides the 3D view."""
        self.logger.debug("Switching to 2D view.")
        self.stacked_widget.setCurrentWidget(self.view_2d)
        # No need to call raise_() with QStackedWidget

    def show_3d_view(self):
        """Shows the 3D view (Terrain) and hides the 2D view."""
        if not HAS_3D or not isinstance(self.view_3d, gl.GLViewWidget):
            self.logger.warning("Attempted to switch to 3D view, but it is unavailable.")
            # Explicitly set the placeholder if it's the current view_3d widget
            if isinstance(self.view_3d, QLabel):
                self.stacked_widget.setCurrentWidget(self.view_3d)
            else:
                # Fallback if something unexpected happened (e.g., HAS_3D changed)
                # Defaulting to 2D might be safer here?
                self.stacked_widget.setCurrentWidget(self.view_2d)
            return
        self.logger.debug("Switching to 3D view.")
        self.stacked_widget.setCurrentWidget(self.view_3d)
        # No need to call raise_() with QStackedWidget

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
        """Removes the PDF background image and closes the PyMuPDF document."""
        self.logger.debug("Clearing PDF background.")
        if self._pdf_bg_item:
            if self.scene_2d and self._pdf_bg_item in self.scene_2d.items():
                try:
                    self.scene_2d.removeItem(self._pdf_bg_item)
                except RuntimeError as e:
                    self.logger.warning(f"Error removing PDF background item: {e}")
            self._pdf_bg_item = None

        if self._pymupdf_doc:
            try:
                self._pymupdf_doc.close()
                self.logger.debug("Closed PyMuPDF document.")
            except Exception as e:
                self.logger.error(f"Error closing PyMuPDF document: {e}", exc_info=True)
            self._pymupdf_doc = None

        self.current_pdf_page = 1 # Reset page number

    def load_pdf_background(self, pdf_path: str, initial_page: int = 1, dpi: int = 150):
        """Opens a PDF using PyMuPDF and renders the initial page.

        Args:
            pdf_path (str): The path to the PDF file.
            initial_page (int): The 1-based page number to render initially.
            dpi (int): The target resolution for rendering the PDF page.
        """
        self.logger.info(f"Loading PDF background: {pdf_path}, initial page: {initial_page}, dpi: {dpi}")

        # Clear existing background and close previous document if different
        if self._pymupdf_doc and self._pymupdf_doc.name != pdf_path:
            self.logger.debug(f"PDF path changed from '{self._pymupdf_doc.name}' to '{pdf_path}'. Clearing old background.")
            self.clear_pdf_background()

        # Open new document if needed
        if not self._pymupdf_doc:
            try:
                self.logger.debug(f"Opening PDF with PyMuPDF: {pdf_path}")
                self._pymupdf_doc = fitz.open(pdf_path)
                self.logger.info(f"PyMuPDF document opened successfully. Page count: {self._pymupdf_doc.page_count}")
            except Exception as e:
                error_msg = f"Failed to open PDF '{pdf_path}' with PyMuPDF: {e}"
                self.logger.error(error_msg, exc_info=True)
                QMessageBox.critical(self, "PDF Load Error", error_msg)
                self._pymupdf_doc = None # Ensure it's None on failure
                # Explicitly clear any remnants if open failed after previous doc was closed
                self.clear_pdf_background()
                return

        # Render the initial page
        if self._pymupdf_doc:
            # Validate initial page number
            if not (1 <= initial_page <= self._pymupdf_doc.page_count):
                self.logger.warning(f"Initial page {initial_page} out of bounds (1-{self._pymupdf_doc.page_count}). Defaulting to page 1.")
                initial_page = 1

            self._render_and_display_page(initial_page, dpi)
        else:
            # This case should ideally not be reached if error handling above is correct
            self.logger.error("PDF document is not available after attempting to load.")

    def _render_and_display_page(self, page_number: int, dpi: int):
        """Internal helper to render a specific page using PyMuPDF and display it."""
        if not self._pymupdf_doc:
            self.logger.error("_render_and_display_page called but PyMuPDF document is not loaded.")
            return

        page_index = page_number - 1 # PyMuPDF uses 0-based index
        if not (0 <= page_index < self._pymupdf_doc.page_count):
            self.logger.error(f"Invalid page index {page_index} requested for rendering.")
            return

        self.logger.debug(f"Rendering page index {page_index} (Page {page_number}) at {dpi} DPI...")
        try:
            page = self._pymupdf_doc.load_page(page_index)
            zoom = dpi / 72.0 # PyMuPDF default is 72 DPI
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False) # Render to PyMuPDF Pixmap

            # Convert PyMuPDF Pixmap (RGB) to QImage
            img_format = QImage.Format.Format_RGB888
            if pix.alpha:
                 img_format = QImage.Format.Format_RGBA8888 # Should not happen with alpha=False
                 self.logger.warning("PyMuPDF rendered with alpha despite alpha=False request.")

            qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, img_format)
            if qimage.isNull():
                raise ValueError("Failed to create QImage from PyMuPDF pixmap samples.")

            # Important: Copy the QImage to ensure the underlying buffer doesn't get invalidated
            # when `pix` goes out of scope or is garbage collected.
            qpixmap = QPixmap.fromImage(qimage.copy())
            self.logger.debug(f"Page {page_number} rendered successfully (Size: {pix.width}x{pix.height}px).")

            # Remove old background item from scene
            if self._pdf_bg_item and self._pdf_bg_item in self.scene_2d.items():
                try:
                    self.scene_2d.removeItem(self._pdf_bg_item)
                except RuntimeError as e:
                    self.logger.warning(f"Error removing previous background item: {e}")
            self._pdf_bg_item = None # Clear reference

            # Create and add new QGraphicsPixmapItem
            self._pdf_bg_item = QGraphicsPixmapItem(qpixmap)
            # Scale factor should be 1 here, as scene units will be pixels
            self._pdf_bg_item.setScale(1.0)
            self._pdf_bg_item.setZValue(-1) # Ensure it's behind other items
            self.scene_2d.addItem(self._pdf_bg_item)
            self.logger.debug("Added new PDF background pixmap item to the scene.")

            # Update scene rect to match the pixel dimensions of the rendered page
            scene_rect = QRectF(0, 0, pix.width, pix.height)
            self.scene_2d.setSceneRect(scene_rect)
            self.logger.debug(f"Scene rect set to rendered pixmap dimensions: {scene_rect}")

            # Update current page tracker
            self.current_pdf_page = page_number

            # Fit view if needed (might be optional depending on desired behavior)
            self.show_2d_view() # Ensure 2D view is visible
            self.view_2d.fitInView(scene_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.logger.debug("Fit 2D view to new PDF background.")

        except Exception as e:
            error_msg = f"Error rendering/displaying PDF page {page_number} with PyMuPDF: {e}"
            self.logger.error(error_msg, exc_info=True)
            QMessageBox.warning(self, "PDF Display Error", error_msg)
            # Clear potentially corrupted background item
            if self._pdf_bg_item and self._pdf_bg_item in self.scene_2d.items():
                try:
                    self.scene_2d.removeItem(self._pdf_bg_item)
                except RuntimeError as remove_err:
                     self.logger.warning(f"Error removing background item during error handling: {remove_err}")
            self._pdf_bg_item = None

    def set_pdf_page(self, page_number: int, dpi: int = 150):
        """Renders and displays the specified page of the currently loaded PDF.

        Args:
            page_number (int): The 1-based page number to display.
            dpi (int): The target resolution for rendering.
        """
        if not self._pymupdf_doc:
            self.logger.warning("set_pdf_page called but no PyMuPDF document is loaded.")
            return

        if page_number == self.current_pdf_page:
            self.logger.debug(f"Page {page_number} is already displayed. Skipping re-render.")
            # Optionally force re-render if needed, e.g., if DPI changed
            # self._render_and_display_page(page_number, dpi)
            return

        self._render_and_display_page(page_number, dpi)

    # --- Cut/Fill Map Methods --- NEW SECTION ---

    def set_cutfill_visible(self, on: bool):
        """Toggle the visibility of the cut/fill map in both views."""
        if on == self._cutfill_visible:
            return
        self._cutfill_visible = on
        self.logger.debug(f"Setting cut/fill visibility to: {on}")

        if self._dz_image_item:
            self._dz_image_item.setVisible(on)
            self.logger.debug(f"2D cut/fill item visibility set to: {self._dz_image_item.isVisible()}")

        if HAS_3D and self._dz_mesh_item:
            self._dz_mesh_item.setVisible(on)
            # Log the action, not the state (as isVisible() is missing)
            self.logger.debug(f"Called 3D cut/fill item setVisible({on})")

        # Force redraw/update of the views
        if self.view_2d:
            self.view_2d.viewport().update()
        if HAS_3D and isinstance(self.view_3d, gl.GLViewWidget):
             self.view_3d.update()

    def update_cutfill_map(self, dz: np.ndarray, gx: np.ndarray, gy: np.ndarray):
        """
        Update or create the cut/fill map visualization.

        Args:
            dz (np.ndarray): 2D numpy array (height, width) of elevation differences.
            gx (np.ndarray): 1D numpy array of X coordinates for the grid.
            gy (np.ndarray): 1D numpy array of Y coordinates for the grid.
        """
        if dz is None or gx is None or gy is None or dz.size == 0 or gx.size == 0 or gy.size == 0:
            self.logger.warning("update_cutfill_map called with invalid data. Clearing map.")
            self.clear_cutfill_map()
            return

        self.logger.info(f"Updating cut/fill map. dz shape: {dz.shape}, gx size: {gx.size}, gy size: {gy.size}")

        try:
            # --- 2D Heatmap (QGraphicsPixmapItem) ---
            rgba_image = dz_to_rgba(dz) # Get (H, W, 4) uint8 RGBA data
            if rgba_image is None or rgba_image.size == 0:
                 raise ValueError("dz_to_rgba returned invalid data")

            h, w = rgba_image.shape[:2]
            # Create QImage with correct stride if necessary, ensure data buffer isn't garbage collected
            # For numpy arrays in C-contiguous order (default), stride is usually fine.
            qimage = QImage(rgba_image.data, w, h, QImage.Format.Format_RGBA8888).copy() # Use copy to be safe
            pixmap = QPixmap.fromImage(qimage)

            if not self.scene_2d:
                 self.logger.error("Cannot add 2D cut/fill map: scene_2d is not initialized.")
                 return # Cannot proceed without a scene

            if not self._dz_image_item:
                self._dz_image_item = self.scene_2d.addPixmap(pixmap)
                self._dz_image_item.setZValue(-5) # Ensure it's below traced lines
                self.logger.debug("Created new 2D cut/fill pixmap item.")
            else:
                self._dz_image_item.setPixmap(pixmap)
                self.logger.debug("Updated existing 2D cut/fill pixmap item.")

            # Calculate position and scale for the pixmap
            x_min, x_max = gx.min(), gx.max()
            y_min, y_max = gy.min(), gy.max()
            scene_width = x_max - x_min
            scene_height = y_max - y_min

            # Basic check for valid dimensions
            if w <= 0 or h <= 0 or scene_width <= 0 or scene_height <= 0:
                 self.logger.warning(f"Invalid dimensions for scaling pixmap: w={w}, h={h}, scene_width={scene_width}, scene_height={scene_height}. Skipping 2D map positioning.")
            else:
                # Create a transform: scale then translate
                transform = QTransform()
                transform.translate(x_min, y_min) # Translate to the top-left corner
                transform.scale(scene_width / w, scene_height / h) # Scale to fit bounds
                self._dz_image_item.setTransform(transform)
                self.logger.debug(f"2D map positioned at ({x_min},{y_min}), scaled ({scene_width / w:.2f}, {scene_height / h:.2f})")

            self._dz_image_item.setVisible(self._cutfill_visible)

            # --- 3D Colored Mesh (pyqtgraph.opengl.GLMeshItem) ---
            if HAS_3D and isinstance(self.view_3d, gl.GLViewWidget):
                # Create mesh vertices (X, Y, Z) on Z=0 plane
                xx, yy = np.meshgrid(gx, gy)
                zz = np.zeros_like(xx)

                # Ensure shapes match for vertices and colors
                if xx.shape[0] != dz.shape[0] or xx.shape[1] != dz.shape[1]:
                     self.logger.warning(f"Shape mismatch: meshgrid ({xx.shape}), dz ({dz.shape}). Cannot create 3D mesh.")
                else:
                    verts = np.vstack([xx.ravel(), yy.ravel(), zz.ravel()]).T

                    # Create faces (triangles) for the grid
                    rows, cols = dz.shape
                    faces = []
                    for r in range(rows - 1):
                        for c in range(cols - 1):
                            p1 = r * cols + c
                            p2 = p1 + 1
                            p3 = (r + 1) * cols + c
                            p4 = p3 + 1
                            faces.append([p1, p2, p4])
                            faces.append([p1, p4, p3])
                    faces = np.array(faces, dtype=np.uint32)

                    # Create vertex colors from dz_to_rgba
                    vertex_colors_uint8 = dz_to_rgba(dz)
                    if vertex_colors_uint8.shape[0] != rows or vertex_colors_uint8.shape[1] != cols:
                         raise ValueError("Color array shape does not match dz grid shape after processing")
                    vertex_colors_float = vertex_colors_uint8.reshape(-1, 4) / 255.0

                    if verts.shape[0] != vertex_colors_float.shape[0]:
                        raise ValueError(f"Vertex count ({verts.shape[0]}) does not match color count ({vertex_colors_float.shape[0]}) for 3D mesh")

                    # Create or update the GLMeshItem
                    if not self._dz_mesh_item:
                        self._dz_mesh_item = gl.GLMeshItem(
                            vertexes=verts,
                            faces=faces,
                            vertexColors=vertex_colors_float,
                            smooth=False, # Flat shading for grid cells
                            shader='shaded',
                            glOptions='translucent' # Use translucent for potential blending
                        )
                        self.view_3d.addItem(self._dz_mesh_item)
                        self.logger.debug("Created new 3D cut/fill mesh item.")
                    else:
                        self._dz_mesh_item.setMeshData(
                            vertexes=verts,
                            faces=faces,
                            vertexColors=vertex_colors_float
                        )
                        self.logger.debug("Updated existing 3D cut/fill mesh item.")

                    self._dz_mesh_item.setVisible(self._cutfill_visible)
            elif HAS_3D and not isinstance(self.view_3d, gl.GLViewWidget):
                 self.logger.warning("Cannot create 3D cut/fill mesh: view_3d is not a GLViewWidget.")
            # No warning if HAS_3D is False

            self.logger.info("Cut/fill map updated successfully.")

        except Exception as e:
            self.logger.error(f"Failed to update cut/fill map: {e}", exc_info=True)
            QMessageBox.warning(self, "Cut/Fill Map Error", f"Could not generate or display the cut/fill map:\n{e}")
            self.clear_cutfill_map() # Clear any partial state

    def clear_cutfill_map(self):
        """Remove the cut/fill map visualizations from both views."""
        self.logger.debug("Clearing cut/fill map visualization.")
        if self._dz_image_item:
            if self.scene_2d and self._dz_image_item in self.scene_2d.items():
                 try:
                     self.scene_2d.removeItem(self._dz_image_item)
                 except RuntimeError as e:
                     self.logger.warning(f"Error removing 2D map item (might be deleted): {e}")
            self._dz_image_item = None

        if HAS_3D and self._dz_mesh_item:
            if isinstance(self.view_3d, gl.GLViewWidget) and self._dz_mesh_item in self.view_3d.items:
                 try:
                      self.view_3d.removeItem(self._dz_mesh_item)
                 except Exception as e:
                      self.logger.warning(f"Error removing 3D mesh item: {e}")
            self._dz_mesh_item = None
        # Visibility state (_cutfill_visible) is managed by the action/MainWindow

    # --- End Cut/Fill Map Methods ---

    # --- Update clear_all --- 
    def clear_all(self):
        """Clears surfaces, PDF background, traced lines, and cut/fill map."""
        self.logger.info("Clearing all visualization data.")
        self.clear_pdf_background()
        self.clear_polylines_from_scene()
        self.clear_cutfill_map() # Added call to clear cut/fill map

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
                 self.view_3d.update()
            except Exception as cam_e:
                 self.logger.warning(f"Could not reset camera position: {cam_e}")

        # Clear project reference
        self.current_project = None 

        # Reset camera/view
        if hasattr(self, 'view_2d'):
            self.view_2d.viewport().update()

    # --- Add is_surface_visible method --- 
    def is_surface_visible(self, surface_name: str) -> bool:
        """
        Checks if the mesh item for a given surface name exists and is visible.

        Args:
            surface_name: The name of the surface to check.

        Returns:
            True if the surface mesh exists and is visible, False otherwise.
        """
        mesh_item = self.surface_mesh_items.get(surface_name)
        if mesh_item:
            # Check if the item has isVisible method, default to True if not (should exist)
            is_visible = getattr(mesh_item, 'isVisible', lambda: True)()
            self.logger.debug(f"Checking visibility for surface '{surface_name}': {is_visible}")
            return is_visible
        else:
            self.logger.debug(f"Checking visibility for non-existent surface '{surface_name}': False")
            return False # Surface mesh doesn't exist
    # --- End Add --- 

    # --- NEW: Helper to adjust view to a list of Point3D objects ---
    def _adjust_view_to_points(self, points: List[Point3D]):
        """Adjusts the 3D camera view to encompass a list of Point3D objects."""
        if not HAS_3D or not isinstance(self.view_3d, gl.GLViewWidget) or not points:
            return
        
        try:
            x_coords = [p.x for p in points]
            y_coords = [p.y for p in points]
            z_coords = [p.z for p in points]

            if not x_coords: # Handle case where points might be empty after filtering
                self.logger.warning("_adjust_view_to_points called with empty point list after filtering.")
                return

            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            min_z, max_z = min(z_coords), max(z_coords)

            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            center_z = (min_z + max_z) / 2

            # Calculate max dimension for distance scaling
            size_x = max_x - min_x
            size_y = max_y - min_y
            size_z = max_z - min_z
            max_dim = max(size_x, size_y, size_z, 1.0) # Ensure at least 1.0
            distance = max_dim * 2.0 # Adjust multiplier as needed

            center_vec = pyqtgraph.Vector(center_x, center_y, center_z)

            self.view_3d.setCameraPosition(
                pos=center_vec,      # Set the center point the camera looks at
                distance=distance,   # Set the distance from the center point
                elevation=30,        # Keep default elevation angle
                azimuth=45           # Keep default azimuth angle
            )
            self.logger.debug(f"Adjusted 3D view to combined bounds: Center={center_vec}, ApproxDistance={distance:.2f}")
        except Exception as e:
            self.logger.error(f"Error adjusting 3D view to points: {e}", exc_info=True)
    # --- END NEW HELPER --- 