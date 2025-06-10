#!/usr/bin/env python3
"""Visualization panel for the DigCalc application.

This module defines the 3D visualization panel for displaying surfaces and calculations.
It also manages the 2D view for PDF rendering and tracing (currently using QGraphicsView,
planned migration to QML via QQuickWidget).
"""

import enum  # Add import
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import os

import numpy as np
from PySide6 import QtWidgets

# PySide6 imports
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal, Slot
from PySide6.QtGui import (  # Added QPainter, QSize
    QImage,
    QMouseEvent,
    QPainter,
    QPixmap,
    QTransform,
    QWheelEvent,
)

# Import QQuickWidget if we were fully integrating QML here
# from PySide6.QtQuickWidgets import QQuickWidget
# Import QJSValue for type hinting if needed
from PySide6.QtQml import QJSValue  # Use for type hint if receiving from QML
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QToolBar,
)

# Removed: from PySide6.QtPdf import QPdfDocument

# ---------------------------------------------------------------------------
# Switch to PyVista-only rendering (pyqtgraph removed – Phase-B cleanup)
# ---------------------------------------------------------------------------
# All legacy ``pyqtgraph``/OpenGL widgets have been migrated to a shared
# PyVista ``BackgroundPlotter`` accessed via ``get_plotter``.  We therefore
# no longer import ``pyqtgraph`` or refer to ``gl.`` items inside this file.

# NOTE: ``surface_to_polydata`` handles conversion from the project ``Surface``
# datamodel into a VTK-compatible mesh.  All actor management now targets the
# PyVista plotter.

from digcalc_project.src.ui.pv_plotter_singleton import get_plotter  # singleton accessor
from digcalc_project.src.utils.surface_to_polydata import surface_to_polydata
from digcalc_project.src.utils.array_cache import load_grid

# Stubs retained for minimal compile impact on any yet-to-be-refactored helpers.
# GLViewWidget = QWidget  # type: ignore # Removed

# ---------------------------------------------------------------------------

# Local imports - Use relative paths
from ..models.project import Project
from ..models.surface import Point3D, Surface
from ..utils.color_maps import dz_to_rgba  # Import the new color utility
from ..visualization.pdf_renderer import PDFRenderer, PDFRendererError

# Import the new dialog
from .dialogs.elevation_dialog import ElevationDialog
from .interactive_graphics_view import InteractiveGraphicsView  # Import the custom view
from .tracing_scene import TracingScene  # Relative within ui package

# --- Logger ---
logger = logging.getLogger(__name__)

# --- Enums ---
class DrawingMode(enum.Enum):
    SELECT = 0
    TRACE = 1
    BOREHOLE = 2
    # Add other modes as needed

class InteractiveGraphicsView(QGraphicsView):
    """A custom QGraphicsView that adds interactive zooming with Ctrl+Wheel
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
    """Panel for 3D visualization of surfaces and calculation results.
    Also includes components for 2D PDF viewing and tracing.
    """

    # Signals
    surface_visualization_failed = Signal(str, str)  # (surface name, error message)
    # Signal to indicate polyline data needs to be sent TO QML
    request_polylines_load_to_qml = Signal()
    # Borehole picking signal
    boreholePointPicked = Signal(float, float)  # x, y world coords

    def __init__(self, parent=None):
        """Initialize the visualization panel.
        
        Args:
            parent: Parent widget

        """
        super().__init__(parent)

        self.logger = logging.getLogger(__name__)
        # self.surfaces: Dict[str, Dict[str, Any]] = {} # Old storage
        # Legacy dict kept for backward compatibility – values no longer use "gl.GLMeshItem"
        # Replace type hint with Any to avoid mypy/runtime errors now that *gl* is a stub.
        # self.surface_mesh_items: Dict[str, Any] = {} # Removed
        self.pdf_renderer: Optional[PDFRenderer] = None
        # --- REMOVE: _pymupdf_doc is managed by PDFRenderer ---
        # self._pymupdf_doc: Optional[fitz.Document] = None
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
        # self._dz_mesh_item: Optional[gl.GLMeshItem] = None # For 3D pyqtgraph mesh # Removed
        self._cutfill_visible: bool = False
        # --- End Cut/Fill Map Attributes ---

        # --- Strata Heatmap Attributes ---
        self.heatmap_items: Dict[int, QGraphicsPixmapItem] = {}
        self.strata_heatmap_action: Optional[QtWidgets.QAction] = None

        # Initialize UI components
        self._init_ui()

        # Connect signals
        self.surface_visualization_failed.connect(self._on_visualization_failed)
        # Connect the request signal to the actual loading method
        self.request_polylines_load_to_qml.connect(self.load_polylines_into_qml)
        self._connect_strata_signals()

        self.logger.debug("VisualizationPanel initialized")

        self.drawing_mode = DrawingMode.SELECT
        self.surface_colors: Dict[str, str] = {}
        # --- Auto-switch flag for first surface ---
        self._auto_switched_to_3d_tab: bool = False

        # Map surface name → PyVista actor
        self._surface_actors: Dict[str, Any] = {}
        # 3-D cut/fill mesh no longer rendered here (handled in PvDock if needed)
        # self._dz_mesh_item = None  # deprecated placeholder # Removed

        # gl = _LegacyGLStub()  # type: ignore # Removed
        # Legacy conditional constant (always True now that PyVista is required)
        # HAS_3D = True # Removed

    @Slot(str)
    def _on_layer_changed(self, layer: str) -> None:
        """Update the active layer when the combo-box changes.
        """
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
        self.view_2d.setObjectName("pdf_view")  # Allows ScaleCalibrationDialog global picking
        self.scene_2d = TracingScene(self.view_2d, self, self)
        # Ensure tracing starts DISABLED to match the unchecked toolbar action.
        # It can be enabled later via set_tracing_mode(True) when the user
        # actively toggles the action.  This prevents accidental drawing when
        # the application first opens a PDF.
        self.scene_2d.set_tracing_enabled(False)
        self.view_2d.setScene(self.scene_2d)
        # Add render hints for better quality rendering
        self.view_2d.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        # Ensure the default scene rect (set by TracingScene) is fully visible so
        # small scene coordinates like (10,10) map to *positive* viewport
        # positions even before any items/backgrounds are added.  This is
        # critical for headless unit-tests that immediately simulate
        # ``qtbot.mouseClick(view.viewport(), pos=mapFromScene(10,10))``.
        if not self.view_2d.transform().isScaling():
            self.view_2d.fitInView(self.scene_2d.sceneRect(), Qt.KeepAspectRatio)
            # Explicitly pan so a 20×20 rect anchored at origin is visible –
            # this guarantees that tests clicking at (10,10) land inside the
            # viewport even on platforms where the initial scroll position is
            # centred to the scene middle.
            self.view_2d.ensureVisible(QRectF(0, 0, 20, 20))
        # self.view_2d.setVisible(False) # Visibility managed by stack
        self.stacked_widget.addWidget(self.view_2d)

        # --- NEW: PyVista 3-D Tab Container -----------------------------------
        self.tab_3d_container = QWidget()
        self.tab_3d_layout = QVBoxLayout(self.tab_3d_container)
        self.tab_3d_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_widget.addWidget(self.tab_3d_container)
        # Alias kept so other modules referring to ``view_3d`` do not crash.
        self.view_3d = self.tab_3d_container  # legacy compatibility
        # ---------------------------------------------------------------------

        # Start in 2-D view by default
        self.stacked_widget.setCurrentWidget(self.view_2d)

        # --- Toolbar ---
        toolbar = QtWidgets.QToolBar("Visualization")
        self.strata_heatmap_action = toolbar.addAction("Show Strata Heatmap")
        self.strata_heatmap_action.setCheckable(True)
        self.strata_heatmap_action.toggled.connect(self._toggle_strata_heatmap)
        layout.addWidget(toolbar)

        self.logger.debug("VisualizationPanel UI initialized with QStackedWidget")

    def _connect_strata_signals(self):
        """Connect to signals from the StrataManagerDock."""
        # This assumes main_window has a reference to strata_manager_dock
        main_window = self.parent()
        while main_window and not hasattr(main_window, 'strata_manager_dock'):
            main_window = main_window.parent()

        if hasattr(main_window, 'strata_manager_dock'):
            strata_dock = main_window.strata_manager_dock
            strata_dock.materialColorChanged.connect(self._on_strata_color_changed)
            strata_dock.materialVisibilityChanged.connect(self._on_strata_visibility_changed)

    def set_project(self, project: Optional[Project]):
        """Sets the current project for the visualization panel and updates the display.

        Args:
            project: The Project object to visualize, or None to clear.

        """
        self.logger.info(
            "Setting project in VisualizationPanel: %s",
            project.name if project else "None",
        )

        # Clear existing visuals *before* assigning so that clear_all() does not
        # immediately overwrite `self.current_project`.  clear_all() resets
        # various visuals but should not dictate which project is active.
        self.clear_all()

        # Now store the reference to the selected project (may be None).
        self.current_project = project

        # Keep the TracingScene aware of the active project for scale checks
        if hasattr(self, "scene_2d") and self.scene_2d:
            self.scene_2d.project = project
            # Log the project and scale after setting
            if self.scene_2d.project:
                # If the project has a PDF background, load it
                if project.pdf_background_path:
                    self.load_pdf_background(
                        project.pdf_background_path,
                        initial_page=project.pdf_background_page,
                        dpi=project.pdf_background_dpi,
                    )
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

        if self.strata_heatmap_action.isChecked():
            self._toggle_strata_heatmap(True)

    def display_surface(self, surface: Surface) -> bool:
        """Display a surface in the 3D view. This now calls update_surface_mesh.
        Args: surface: Surface to display
        Returns: bool: True if update was initiated, False otherwise
        """
        # Rely exclusively on PyVista – no legacy 3-D widget requirements

        try:
            # Obtain the singleton plotter instance once and reuse it throughout the method
            plotter = get_plotter()
        except Exception as e_plot:
            error_msg = f"PyVista BackgroundPlotter unavailable: {e_plot}"
            self.logger.warning(error_msg)
            self.surface_visualization_failed.emit(surface.name, error_msg)
            return False

        name = surface.name or "Unnamed"

        # Remove existing actor if present
        if name in self._surface_actors:
            try:
                plotter.remove_actor(self._surface_actors[name])  # type: ignore[attr-defined]
            except Exception:
                pass
            del self._surface_actors[name]

        # Build PolyData
        try:
            poly = surface_to_polydata(surface)
        except Exception as exc:
            self.logger.error("surface_to_polydata failed for '%s': %s", name, exc)
            self.surface_visualization_failed.emit(name, str(exc))
            return False

        # Add mesh to plotter
        try:
            actor = plotter.add_mesh(poly, name=name)
            self._surface_actors[name] = actor
        except Exception as exc:
            self.logger.error("Failed to add mesh for '%s': %s", name, exc)
            self.surface_visualization_failed.emit(name, str(exc))
            return False

        # Optionally reset camera when first actor added
        if len(self._surface_actors) == 1:
            try:
                plotter.camera_position = "iso"
                plotter.reset_camera()
            except Exception:
                pass
        # Success logged implicitly by plotter
        return True

    def _remove_surface_visualization(self, surface_name: str):
        """Remove a surface's mesh item."""
        actor = self._surface_actors.pop(surface_name, None)
        if actor is None:
            self.logger.debug("No actor to remove for surface '%s'", surface_name)
            return
        try:
            plotter = get_plotter()
            plotter.remove_actor(actor)  # type: ignore[attr-defined]
            self.logger.debug("Removed PyVista actor for '%s'", surface_name)
        except Exception as exc:
            self.logger.warning("Failed removing actor for '%s': %s", surface_name, exc)

    @Slot(Surface, bool)
    def set_surface_visibility(self, surface: Surface, visible: bool):
        """Set the visibility of a surface's mesh."""
        actor = self._surface_actors.get(surface.name)
        if actor is None:
            self.logger.debug("set_surface_visibility – no actor for '%s'", surface.name)
            return
        try:
            actor.SetVisibility(visible)
        except Exception:
            try:
                # fallback for PyVista-wrapped actor API
                actor.visible = visible  # type: ignore[attr-defined]
            except Exception as exc:
                self.logger.error("Could not toggle visibility for '%s': %s", surface.name, exc)

    def clear_all(self):
        """Clears all visual elements from both 2D and 3D views."""
        self.logger.info("Clearing all visualization data.")
        self.clear_pdf_background()
        self.clear_polylines_from_scene()
        self.clear_cutfill_map()
        self._toggle_strata_heatmap(False) # Clear heatmaps

        # Clear PyVista actors
        try:
            plotter = get_plotter()
            plotter.clear_actors()
        except Exception:
            pass
        self._surface_actors.clear()
        # remove legacy mesh item dict if exists
        # if hasattr(self, "surface_mesh_items"): # Removed
        #     self.surface_mesh_items.clear() # Removed

        # Reset the view camera position if 3D view exists
        # Removed legacy pyqtgraph camera reset:
        # if hasattr(self, "view_3d") and isinstance(self.view_3d, gl.GLViewWidget):
        #     try:
        #          self.view_3d.setCameraPosition(distance=100, elevation=30, azimuth=45)
        #          self.view_3d.update()
        #     except Exception as cam_e:
        #          self.logger.warning(f"Could not reset camera position: {cam_e}")

        # Clear project reference
        self.current_project = None

        # Reset camera/view
        if hasattr(self, "view_2d"):
            self.view_2d.viewport().update()

        # Reset auto-switch so a new project triggers it again
        self._auto_switched_to_3d_tab = False

    def has_surfaces(self) -> bool:
        """Check if any surfaces are currently loaded and visualized."""
        return bool(self._surface_actors)

    def set_tracing_mode(self, enabled: bool):
        """Enable or disable tracing mode for the 2D view (TracingScene).

        Args:
            enabled (bool): True to enable tracing, False to disable.
        """
        self.logger.info(f"Setting tracing mode to: {'Enabled' if enabled else 'Disabled'}")

        if not self.scene_2d:
            self.logger.error("Cannot set tracing mode: scene_2d is not initialized.")
            return

        # Pass to TracingScene to handle cursor, state, etc.
        self.scene_2d.set_tracing_enabled(enabled)

        if enabled:
            # Ensure 2D view is active when tracing is enabled
            self.show_2d_view()

            # Check if scale is set when enabling tracing
            # The TracingScene itself will show a warning if scale is not set
            # when the user tries to place a point.
            if self.current_project and (
                self.current_project.scale is None
                or not self.current_project.scale.world_per_paper_in
                or self.current_project.scale.render_dpi_at_cal <= 0
            ):
                self.logger.warning(
                    "Tracing enabled, but project scale is not set or invalid."
                )
                # TracingScene._show_scale_warning() will be triggered on mouse press if still invalid
            else:
                self.logger.info("Tracing enabled with valid project scale.")

            # Set the cursor for the viewport of the QGraphicsView if desired
            # self.view_2d.viewport().setCursor(Qt.CrossCursor)

        else:
            # Restore default cursor if needed
            # self.view_2d.viewport().setCursor(Qt.ArrowCursor)
            pass

        # Update UI elements related to tracing mode if necessary (e.g., toolbar buttons)
        # This might be handled by signals/slots connected to the MainWindow's action

    def load_and_display_polylines(self, polylines_by_layer: Dict[str, List[List[Tuple[float, float]]]]):
        """Loads polylines from a dictionary (grouped by layer) into the 2D scene.

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
        """Retrieves layered polyline data from the current project
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
        """Slot to receive finalized polyline data from QML.
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

        length = polyline_data_qjs.property("length").toInt() # QJSValue arrays need length property
        for i in range(length):
            qml_point = polyline_data_qjs.property(i) # Get the QJSValue for the point object
            if qml_point and qml_point.isObject():
                x = qml_point.property("x").toNumber()
                y = qml_point.property("y").toNumber()
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
            z,
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
        """Handles polyline finalization from the TracingScene (legacy path).

        Args:
            points_qpointf (List[QPointF]): List of QPointF vertices from the scene.
        """
        if not self.current_project:
            self.logger.warning("Polyline finalized but no current project to add it to.")
            return

        # Convert QPointF to a list of (float, float) tuples
        polyline_coords: List[Tuple[float, float]] = [(pt.x(), pt.y()) for pt in points_qpointf]

        # Determine the active layer (e.g., from a layer selector ComboBox)
        # For now, using a placeholder or a default layer name
        active_layer_name = self.active_layer_name # Using the attribute set by layer_selector

        self.logger.info(f"Legacy polyline finalized on layer '{active_layer_name}' with {len(polyline_coords)} points.")

        # Add to project model (ProjectController should handle this)
        # This is a simplified placeholder. The ProjectController should be responsible
        # for managing the current project and adding data to it.
        # self.current_project.add_polyline_to_layer(active_layer_name, polyline_coords)

        # Emit a signal that MainWindow can connect to, to pass to ProjectController
        # Example: self.polyline_added_to_project.emit(active_layer_name, polyline_coords)

        # For now, directly log. Proper handling would involve ProjectController.
        # In a more robust setup, VisualizationPanel would emit a signal, and MainWindow
        # would connect that signal to a slot in ProjectController.
        # Or, ProjectController could be passed to VisualizationPanel, though this can increase coupling.

    # --- NEW: Helper Methods ---
    def has_pdf(self) -> bool:
        """Checks if a PDF background is currently loaded."""
        return self.pdf_renderer is not None

    def current_view(self) -> str:
        """Returns the currently visible view mode ("2d" or "3d")."""
        current = self.stacked_widget.currentWidget()
        if current == self.view_2d:
            return "2d"
        if current == self.view_3d:
            # Return "3d" even if it's the placeholder Label
            return "3d"
        # Should not happen if stack contains only view_2d and view_3d
        logger.warning("Current widget in stacked_widget is unexpected!")
        return "unknown"

    # --- NEW: View Switching Methods ---
    def show_2d_view(self):
        """Switch to the 2-D (PDF / tracing) view and release the PyVista interactor."""
        self.logger.debug("Switching to 2-D view.")
        # If the PyVista interactor is currently embedded in our 3-D tab, detach it so PvDock can re-use it.
        try:
            from digcalc_project.src.ui.pv_plotter_singleton import get_plotter
            plotter = get_plotter()
            if plotter and plotter.interactor.parent() is self.tab_3d_container:
                self.tab_3d_layout.removeWidget(plotter.interactor)
                plotter.interactor.setParent(None)
        except Exception as exc:  # pragma: no cover – defensive stub
            self.logger.debug("No plotter to detach when switching to 2-D: %s", exc)

        self.stacked_widget.setCurrentWidget(self.view_2d)

    def show_pyvista_in_tab(self):
        """Embed the singleton PyVista interactor into the dedicated 3-D tab and show it."""
        self.logger.debug("Activating PyVista 3-D tab view.")
        try:
            from digcalc_project.src.ui.pv_plotter_singleton import get_plotter
            plotter = get_plotter()
        except Exception as exc:  # pragma: no cover
            self.logger.error("Unable to obtain PyVista BackgroundPlotter: %s", exc)
            QMessageBox.critical(self, "3-D Viewer Error", f"PyVista plotter not available:\n{exc}")
            return

        # Detach from previous parent (PvDock or other)
        if plotter.interactor.parent() is not None:
            old_parent = plotter.interactor.parent()
            try:
                old_parent.layout().removeWidget(plotter.interactor)  # type: ignore[attr-defined]
            except Exception:
                pass  # Non-critical
            plotter.interactor.setParent(None)

        # Re-parent into our tab and show
        self.tab_3d_layout.addWidget(plotter.interactor)
        plotter.interactor.show()
        self.stacked_widget.setCurrentWidget(self.tab_3d_container)

    # Keep legacy API working by forwarding show_3d_view → show_pyvista_in_tab
    def show_3d_view(self):
        """Backward-compat wrapper that now shows the PyVista tab."""
        self.show_pyvista_in_tab()

    # --- Update Existing Methods ---
    # Removed deprecated method _adjust_view_to_surface
    # def _adjust_view_to_surface(self, surface: Surface):  # noqa: D401 – deprecated
    #     """No-op shim retained for backward compatibility (pyqtgraph era)."""
    #     return  # Camera handled by PyVista

    # Removed deprecated method _create_mesh_data
    # def _create_mesh_data(self, surface: Surface) -> Optional[Dict[str, Any]]:
    #     """Deprecated stub – pyqtgraph mesh-building removed."""
    #     return None

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
        self.logger.debug("Clearing PDF background and related items.")
        # --- FIX: Close the renderer, which handles the doc ---
        if self.pdf_renderer:
            # Some unit-tests stub pdf_renderer with a simple object lacking .close()
            if hasattr(self.pdf_renderer, "close"):
                try:
                    self.pdf_renderer.close()
                except Exception as e:
                    self.logger.error(f"Error closing PDF renderer: {e}", exc_info=True)
            else:
                # Gracefully skip when the stub has no close method
                self.logger.debug("pdf_renderer stub has no 'close' attribute; skipping cleanup.")
        self.pdf_renderer = None
        # --- REMOVE: Doc managed by renderer ---
        # self._pymupdf_doc = None

        # --- FIX: Use TracingScene API ---
        # Clear previous layers (assuming page change replaces, not stacks)
        # Need to access internal list as there's no public clear method yet
        while getattr(self.scene_2d, "_background_items", []):
            try:
                self.scene_2d.removeBackgroundLayer(0)
            except IndexError:
                break # Should not happen if list check is correct

        # --- END FIX ---

        self.current_pdf_page = 1

    def load_pdf_background(self, pdf_path: str, initial_page: int = 1, dpi: int = 150) -> bool:
        """Loads a PDF document, renders the initial page, and displays it.

        Args:
            pdf_path: Path to the PDF file.
            initial_page: The 1-based page number to display initially.
            dpi: The resolution for rendering the PDF page.
            
        Returns:
            bool: True if the PDF was loaded and the initial page rendered successfully, False otherwise.

        """
        self.logger.info(f"Loading PDF background: {pdf_path}, initial page: {initial_page}, dpi: {dpi}")

        # Clear any existing background first
        self.clear_pdf_background()

        try:
            # Initialize or reuse the renderer
            if not self.pdf_renderer: # Should always be None after clear_pdf_background
                self.pdf_renderer = PDFRenderer(pdf_path=pdf_path, dpi=dpi)

            # --- FIX: Get page count after successful init ---
            page_count = self.pdf_renderer.get_original_page_count() # Use original count from doc
            self.logger.info(f"PDF document opened successfully via renderer. Page count: {page_count}")

            # Validate initial page number
            if not (1 <= initial_page <= page_count):
                self.logger.warning(f"Initial page {initial_page} is out of range (1-{page_count}). Defaulting to page 1.")
                initial_page = 1

            # Render and display the initial page
            self._render_and_display_page(initial_page, dpi)

            self.current_pdf_page = initial_page
            self.logger.info(f"Successfully rendered and displayed page {initial_page} of '{Path(pdf_path).name}'")
            return True # Indicate success

        except PDFRendererError as e:
            self.logger.error(f"Failed to load or render PDF background: {e}")
            # Ensure renderer is cleared on any failure during this process
            self.clear_pdf_background()
            return False # Indicate failure
        except Exception as e: # Catch any other unexpected errors
            self.logger.exception(f"Unexpected error loading PDF background: {e}")
            self.clear_pdf_background()
            return False # Indicate failure

    def _render_and_display_page(self, page_number: int, dpi: int):
        """Internal helper to render a specific page using PyMuPDF and display it."""
        # --- FIX: Check renderer, get image from renderer ---
        if not self.pdf_renderer:
            self.logger.error("_render_and_display_page called but PDFRenderer is not initialized.")
            return

        page_index = page_number - 1 # Still need 0-based for internal logic if any remains
        if not (1 <= page_number <= self.pdf_renderer.get_original_page_count()):
            self.logger.error(f"Invalid page number {page_number} requested for rendering (Max: {self.pdf_renderer.get_original_page_count()}).")
            return

        self.logger.debug(f"Getting pre-rendered image for page {page_number} (Index {page_index})...")
        try:
            # Get the pre-rendered QImage from the renderer
            qimage = self.pdf_renderer.get_page_image(page_number)

            if qimage is None or qimage.isNull():
                 # This might happen if rendering failed for this specific page during init
                 raise PDFRendererError(f"Failed to retrieve valid QImage for page {page_number} from renderer.")

            qpixmap = QPixmap.fromImage(qimage) # No copy needed here, QPixmap shares image data
            self.logger.debug(f"Retrieved rendered image for page {page_number} (Size: {qimage.width()}x{qimage.height()}).")
            # --- END FIX ---

            # --- FIX: Use TracingScene API ---
            # Clear previous layers (assuming page change replaces, not stacks)
            # Need to access internal list as there's no public clear method yet
            while getattr(self.scene_2d, "_background_items", []):
                try:
                    self.scene_2d.removeBackgroundLayer(0)
                except IndexError:
                    break # Should not happen if list check is correct

            # Add the new page using the scene's method
            self.scene_2d.addBackgroundLayer(qpixmap)
            # self._pdf_bg_item is no longer needed here
            self.logger.debug("Added new PDF background via TracingScene API.")
            # --- END FIX ---

            # Update scene rect to match the pixel dimensions of the rendered page
            scene_rect = self.scene_2d.sceneRect() # Get the updated rect
            self.logger.debug(f"Scene rect updated by addBackgroundLayer: {scene_rect}")

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
            # --- FIX: Use TracingScene API ---
            while getattr(self.scene_2d, "_background_items", []):
                try:
                    self.scene_2d.removeBackgroundLayer(0)
                except IndexError:
                    break
            # --- END FIX ---

    def set_pdf_page(self, page_number: int, dpi: int = 150):
        """Renders and displays the specified page of the currently loaded PDF.

        Args:
            page_number (int): The 1-based page number to display.
            dpi (int): The target resolution for rendering.

        """
        # --- FIX: Check pdf_renderer ---
        if not self.pdf_renderer:
            self.logger.warning("set_pdf_page called but no PDFRenderer is available.")
            return
        # --- END FIX ---

        if page_number == self.current_pdf_page:
            self.logger.debug(f"Page {page_number} is already displayed. Checking DPI.")
            # Re-render only if DPI has changed (though current renderer stores DPI...)
            # Let's assume the renderer's DPI is fixed for now. If DPI needs changing,
            # the renderer itself would need to be recreated or have a re-render method.
            # For now, if page number is same, do nothing.
            return

        # --- FIX: Call _render_and_display_page which now gets pre-rendered image ---
        # The 'dpi' argument here is currently unused by the modified _render_and_display_page
        # as rendering happens in the renderer's __init__. Keep it for now in case of future refactoring.
        self._render_and_display_page(page_number, dpi)
        # --- END FIX ---

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

        # Force redraw/update of the views
        if self.view_2d:
            self.view_2d.viewport().update()

    def update_cutfill_map(self, dz: np.ndarray, gx: np.ndarray, gy: np.ndarray):
        """Update or create the cut/fill map visualization.

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

            # 3-D cut/fill visualisation removed in PyVista refactor – handled elsewhere if needed.

            self.logger.info("Cut/fill map updated successfully.")

        except Exception as e:
            self.logger.error(f"Failed to update cut/fill map: {e}", exc_info=True)
            QMessageBox.warning(self, "Cut/Fill Map Error", f"Could not generate or display the cut/fill map:\n{e}")
            self.clear_cutfill_map() # Clear any partial state

    def clear_cutfill_map(self):
        """Removes the cut/fill map from the 2D and 3D views."""
        self.logger.debug("Clearing cut/fill map visualization.")
        if self._dz_image_item:
            if self.scene_2d and self._dz_image_item in self.scene_2d.items():
                 try:
                     self.scene_2d.removeItem(self._dz_image_item)
                 except RuntimeError as e:
                     self.logger.warning(f"Error removing 2D map item (might be deleted): {e}")
            self._dz_image_item = None

        # Visibility state (_cutfill_visible) is managed by the action/MainWindow

    # --- End Cut/Fill Map Methods ---

    # --- NEW: Helper to adjust view to a list of Point3D objects ---
    # Removed deprecated method _adjust_view_to_points
    # def _adjust_view_to_points(self, points: List[Point3D]):  # noqa: D401 – deprecated
    #     """No-op (legacy). Camera bounding now handled by PyVista plotter."""
    #     return

    # ------------------------------------------------------------------
    # Borehole mode helpers
    # ------------------------------------------------------------------

    def set_borehole_mode(self, enabled: bool) -> None:
        """Enable or disable Borehole placement mode."""
        if enabled:
            self.drawing_mode = DrawingMode.BOREHOLE
            self.view_2d.setCursor(Qt.CrossCursor)
        else:
            self.drawing_mode = DrawingMode.SELECT
            self.view_2d.setCursor(Qt.ArrowCursor)

    def _toggle_strata_heatmap(self, enabled: bool):
        """Shows or hides the strata heat-map overlays in the 2D view."""
        # First, clear any existing items
        for item in self.heatmap_items.values():
            if item.scene():
                self.scene_2d.removeItem(item)
        self.heatmap_items.clear()

        if not enabled or not self.current_project or not self.current_project.strata:
            return

        cache_dir = os.path.join(self.current_project.get_cache_dir(), "strata")
        
        for surface in sorted(self.current_project.strata.surfaces, key=lambda s: s.id, reverse=True):
            material = self.current_project.strata.get_material(surface.material_id)
            if not material:
                continue

            mat_name = material.name.replace(" ", "_")
            filename = f"strata_cache_{self.current_project.id}_{mat_name}.npz"
            path = os.path.join(cache_dir, filename)

            if not os.path.exists(path):
                continue
            
            try:
                grid_data, meta = load_grid(path)
                q_image = self._create_heatmap_image(grid_data, material.colour)
                pixmap = QPixmap.fromImage(q_image)
                
                item = QGraphicsPixmapItem(pixmap)
                item.setPos(meta['x_min'], meta['y_min'])
                
                # Use a transform to scale the pixmap correctly based on cell size
                transform = QTransform().scale(meta['cell_size'], meta['cell_size'])
                item.setTransform(transform)

                item.setZValue(-2) # Below breaklines (Z=-1) and other items
                item.setOpacity(0.3) # As per task spec

                self.scene_2d.addItem(item)
                self.heatmap_items[material.id] = item
                
            except Exception as e:
                logger.exception(f"Failed to create heatmap for material '{material.name}': {e}")
    
    def _create_heatmap_image(self, grid_data: np.ndarray, color_hex: str) -> QImage:
        """Creates a QImage from grid data, coloring valid data points."""
        from PySide6.QtGui import QColor

        color = QColor(color_hex)
        r, g, b = color.red(), color.green(), color.blue()
        
        height, width = grid_data.shape
        # Create an RGBA image buffer, initialized to fully transparent
        buffer = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Find where grid data is valid (not NaN)
        valid_mask = ~np.isnan(grid_data)
        
        # Set the color for valid data points
        buffer[valid_mask] = [r, g, b, 255] # Full opacity within the image itself
        
        # QImage expects (height, width, 4) data for RGBA
        return QImage(buffer.data, width, height, QImage.Format.Format_RGBA8888)

    def _on_strata_color_changed(self, material_id: int, new_hex: str):
        """Updates the color of a specific heatmap item."""
        item = self.heatmap_items.get(material_id)
        # This is inefficient as it re-reads from disk. A better way would be to just
        # update the pixmap, but that requires re-applying the color to the image data.
        # For now, we just re-create it.
        if item and self.strata_heatmap_action.isChecked():
            self._toggle_strata_heatmap(True) # Just refresh all heatmaps

    def _on_strata_visibility_changed(self, material_id: int, visible: bool):
        """Updates the visibility of a specific heatmap item."""
        item = self.heatmap_items.get(material_id)
        if item:
            item.setVisible(visible)
