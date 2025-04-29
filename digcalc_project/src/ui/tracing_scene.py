from __future__ import annotations

# src/ui/tracing_scene.py

import logging
import math
from typing import List, Optional, Tuple, Dict, Sequence, Any, TypeAlias, TYPE_CHECKING

from PySide6.QtCore import Qt, QPointF, Signal, QLineF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainterPath,
    QPen,
    QPixmap,
    QKeyEvent,
    QMouseEvent,
    QUndoCommand,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsItemGroup,
    QGraphicsView
)

# --- MODIFIED: Use TYPE_CHECKING for PolylineData --- 
if TYPE_CHECKING:
    from ..models.project import PolylineData
    from .visualization_panel import VisualizationPanel
else:
    # Provide a runtime fallback (e.g., dict or Any)
    PolylineData = Any # Or Dict[str, Any] if it's always a dict structure
    VisualizationPanel = Any # <<< Add fallback for runtime
# --- END MODIFIED ---

# --- NEW: Define Type Alias --- 
LayerPolylineDict: TypeAlias = Dict[str, List[List[Tuple[float, float]]]]
# --- END NEW ---

class TracingScene(QGraphicsScene):
    """
    A custom QGraphicsScene for interactive polyline tracing over a background image,
    with support for basic layer management.
    """

    # --- MODIFIED: Update signal definition ---
    # Signal emitted when a polyline is finalized (e.g., by double-click or Enter)
    # Sends the list of QPointF vertices AND the created QGraphicsPathItem.
    polyline_finalized = Signal(list, QGraphicsPathItem)
    # --- END MODIFIED ---

    # --- NEW: Signal for item selection ---
    # Emits the selected QGraphicsItem when selection changes.
    # In this context, it will be the QGraphicsPathItem representing a polyline.
    selectionChanged = Signal(QGraphicsItem)
    # --- END NEW ---

    # --- NEW: Signal for page bounding rect ---
    pageRectChanged = Signal()
    # --- END NEW ---

    # --- NEW: Signal when a closed pad polyline is drawn ---
    padDrawn = Signal(list)  # Emits list[tuple[float, float]] representing 2-D vertices
    # --- END NEW ---

    # --- MODIFIED: Accept and store panel reference --- 
    def __init__(self, view: QGraphicsView, panel: VisualizationPanel, parent=None):
        """Initialize the TracingScene.

        Args:
            view (QGraphicsView): The view that displays this scene.
            panel (VisualizationPanel): The parent visualization panel.
            parent (QObject, optional): Parent object. Defaults to None.
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.parent_view = view # Store reference to the parent view
        self.panel = panel # Store reference to the panel
    # --- END MODIFIED --- 

        # Allow multiple stacked background layers (one per PDF page)
        self._background_items: List[QGraphicsPixmapItem] = []
        self._tracing_enabled: bool = False
        self._is_drawing: bool = False
        self._current_polyline_points: List[QPointF] = []
        self._current_vertices_items: List[QGraphicsEllipseItem] = []
        self._temporary_line_item: Optional[QGraphicsLineItem] = None

        # --- Styling ---
        # TODO: Consider layer-specific styling later
        self._background_opacity = 0.7
        self._vertex_pen = QPen(QColor("cyan"), 1)
        self._vertex_brush = QBrush(QColor("cyan"))
        self._vertex_radius = 3.0
        self._rubber_band_pen = QPen(QColor("yellow"), 1, Qt.DashLine)
        self._finalized_polyline_pen = QPen(QColor("lime"), 4)
        self._selected_polyline_pen = QPen(QColor("yellow"), 5, Qt.DotLine)

    # --- Background Image ---

    # ------------------------------------------------------------------
    # Background layer helpers (multi‑page stacking)
    # ------------------------------------------------------------------

    def addBackgroundLayer(self, pixmap: QPixmap, z: float | None = None) -> None: # noqa: N802
        """Add a new PDF page pixmap as a background layer."""
        item = QGraphicsPixmapItem(pixmap)
        if z is None:
            z = -(len(self._background_items) + 1) # stack downwards
        item.setZValue(z)
        item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        item.setFlag(QGraphicsItem.ItemIsMovable, False)
        item.setOpacity(self._background_opacity)
        self.addItem(item)
        self._background_items.append(item)
        # Expand scene rect to fit all layers (use combined bounds)
        self.setSceneRect(self.itemsBoundingRect())
        self.pageRectChanged.emit()

    def removeBackgroundLayer(self, index: int) -> None: # noqa: N802
        """Remove a background layer by its index in the stack."""
        if 0 <= index < len(self._background_items):
            item = self._background_items.pop(index)
            if item in self.items():
                self.removeItem(item)
            # Update Z‑values to keep ordering compact
            for i, it in enumerate(self._background_items, start=1):
                it.setZValue(-i)
            self.setSceneRect(self.itemsBoundingRect())
            self.pageRectChanged.emit()
        else:
            self.logger.warning("removeBackgroundLayer: index out of range (%s)", index)

    # Legacy single‑image API retained for compatibility -----------------------------------\
    def set_background_image(self, image: Optional[QImage]): # noqa: N802
        """Maintain old API: clear layers then add one."""
        # clear existing
        for item in list(self._background_items):
            if item in self.items():
                self.removeItem(item)
        self._background_items.clear()
        if image and not image.isNull():
            self.addBackgroundLayer(QPixmap.fromImage(image))
        else:
            # If image is None, clear scene rect or set to default
            self.setSceneRect(self.itemsBoundingRect()) # Update rect even if empty
            self.pageRectChanged.emit() # Emit signal

    # ------------------------------------------------------------------
    # Backward‑compat helper – some code paths call *setBackgroundImage*.
    # ------------------------------------------------------------------
    def setBackgroundImage(self, pixmap: QPixmap): # camelCase alias
        """Qt slot‑style camel‑case alias for :py:meth:`set_background_image`."""
        img = pixmap.toImage() if isinstance(pixmap, QPixmap) else None
        self.set_background_image(img)

    # --- NEW: Fit View ---
    def fit_current_page(self):
        """
        Emits the pageRectChanged signal, indicating the view should refit the scene contents.
        The actual fitting is handled by the connected slot in the MainWindow/VisualizationPanel.
        """
        self.logger.debug("fit_current_page called, emitting pageRectChanged.")
        self.pageRectChanged.emit()
    # --- END NEW ---

    # --- Drawing Control ---

    def start_drawing(self):
        """Explicitly enables drawing mode."""
        self._tracing_enabled = True
        self.logger.debug("Drawing mode explicitly enabled.")
        # Change cursor when tracing starts
        if self.parent_view:
            self.parent_view.setCursor(Qt.CrossCursor)

    def stop_drawing(self):
        """Explicitly disables drawing mode and cancels any current polyline."""
        self._tracing_enabled = False
        if self._is_drawing:
            self._cancel_current_polyline()
            self.logger.debug("Drawing mode explicitly disabled, current polyline cancelled.")
        # Reset cursor when tracing stops
        if self.parent_view:
             # Restore appropriate cursor based on view's drag mode
            cursor = Qt.ArrowCursor
            if self.parent_view.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                cursor = Qt.OpenHandCursor
            self.parent_view.setCursor(cursor)

    # --- Event Handling for Drawing ---

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles mouse press events to add vertices to the polyline."""
        # Check if the parent view is currently performing manual panning
        if self.parent_view and hasattr(self.parent_view, '_panning') and self.parent_view._panning:
            self.logger.debug("Scene mousePress ignored: View is manually panning.")
            return

        if not self._tracing_enabled:
            # If tracing is disabled, allow the base class/view to handle selection/panning etc.
            super().mousePressEvent(event)
            return

        # --- Tracing is Enabled ---
        if event.button() == Qt.LeftButton:
            pos = self._constrained_pos(event.scenePos(), event.modifiers()) # Apply constraints on press

            # Check if click is within any background item bounds (if backgrounds exist)
            can_draw = True
            if self._background_items:
                can_draw = any(bg.sceneBoundingRect().contains(pos) for bg in self._background_items)

            if can_draw:
                if not self._is_drawing:
                    self._is_drawing = True
                    self._current_polyline_points = [pos]
                    self._add_vertex_marker(pos)
                    self.logger.debug(f"Started new polyline at: {pos.x():.2f}, {pos.y():.2f}")
                else:
                    # Add the constrained position
                    self._current_polyline_points.append(pos)
                    self._add_vertex_marker(pos)
                    self._update_temporary_line(pos) # Update rubber band to this new point
                    self.logger.debug(f"Added vertex at: {pos.x():.2f}, {pos.y():.2f}")
                event.accept() # We handled the click for drawing
            else:
                 # If click is outside drawable area when tracing, let view handle pan/etc.
                 super().mousePressEvent(event)
        else:
            # Pass non-left clicks (e.g., right-click for context menu) to base scene
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles mouse move events to update the temporary rubber-band line with constraints."""
        if not self._tracing_enabled or not self._is_drawing or not self._current_polyline_points:
            super().mouseMoveEvent(event)
            return

        constrained_pos = self._constrained_pos(event.scenePos(), event.modifiers())
        self._update_temporary_line(constrained_pos)
        event.accept() # We are handling the move for the rubber band

    def _constrained_pos(self, current_pos: QPointF, modifiers: Qt.KeyboardModifiers) -> QPointF:
        """
        Calculates the constrained position based on the last point and modifier keys.

        Args:
            current_pos (QPointF): The current mouse position in scene coordinates.
            modifiers (Qt.KeyboardModifiers): Keyboard modifiers (Shift, Ctrl).

        Returns:
            QPointF: The potentially constrained position.
        """
        if not self._current_polyline_points:
            return current_pos # No previous point to constrain relative to

        last_point = self._current_polyline_points[-1]
        dx = current_pos.x() - last_point.x()
        dy = current_pos.y() - last_point.y()

        if modifiers == Qt.ShiftModifier:
            # Constrain to horizontal or vertical
            if abs(dx) > abs(dy):
                return QPointF(current_pos.x(), last_point.y()) # Horizontal
            else:
                return QPointF(last_point.x(), current_pos.y()) # Vertical
        elif modifiers == Qt.ControlModifier:
            # Constrain to 45-degree increments
            angle = math.atan2(dy, dx)
            snapped_angle = round(angle / (math.pi / 4)) * (math.pi / 4)
            dist = math.hypot(dx, dy)
            snapped_x = last_point.x() + dist * math.cos(snapped_angle)
            snapped_y = last_point.y() + dist * math.sin(snapped_angle)
            return QPointF(snapped_x, snapped_y)
        else:
            # No constraint
            return current_pos

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles double-click events to finalize the current polyline."""
        if not self._tracing_enabled or not self._is_drawing:
            super().mouseDoubleClickEvent(event)
            return

        if event.button() == Qt.LeftButton:
            if len(self._current_polyline_points) >= 2:
                # Use the position from the second click of the double-click
                # Apply constraints to the final point as well
                final_pos = self._constrained_pos(event.scenePos(), event.modifiers())
                self._current_polyline_points.append(final_pos)
                self._add_vertex_marker(final_pos) # Add marker for the final point

                # Get active layer name from parent (VisualizationPanel)
                active_layer = self._get_active_layer_name()
                self._finalize_current_polyline(active_layer)
            else:
                # Not enough points, cancel
                self._cancel_current_polyline()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key press events (Enter to finalize, Backspace to undo, Esc to cancel)."""
        if not self._tracing_enabled or not self._is_drawing:
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if len(self._current_polyline_points) >= 2:
                active_layer = self._get_active_layer_name()
                self._finalize_current_polyline(active_layer)
            else:
                self._cancel_current_polyline()
            event.accept()
        elif event.key() == Qt.Key_Backspace:
            self._undo_last_vertex()
            event.accept()
        elif event.key() == Qt.Key_Escape:
             self._cancel_current_polyline()
             event.accept()
        else:
            # Allow other keys (like modifiers) to pass through
            super().keyPressEvent(event)

    # --- Helper to get active layer ---
    def _get_active_layer_name(self) -> str:
        """Safely gets the active layer name from the parent panel."""
        active_layer = "Default" # Fallback
        # --- MODIFIED: Use stored panel reference --- 
        if self.panel and hasattr(self.panel, 'active_layer_name'):
            active_layer = self.panel.active_layer_name
            self.logger.debug(f"Retrieved active layer: {active_layer}")
        else:
            self.logger.warning("Could not get active_layer_name: Panel reference or attribute missing.")
        # --- END MODIFIED --- 
        return active_layer

    # --- NEW: Override mouseReleaseEvent to detect selection ---
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | QMouseEvent): # Allow QMouseEvent from view
        """
        Overrides mouseReleaseEvent to emit selectionChanged signal
        when a selectable item (polyline) is clicked.
        """
        # Check if the parent view handled panning
        if self.parent_view and hasattr(self.parent_view, '_panning') and self.parent_view._panning:
             # If view was panning, don't process release for selection in scene
             # The view's release handler should reset state
             return

        # Important: Call super implementation to handle standard selection behavior first!
        super().mouseReleaseEvent(event)

        # After base class handled it, check selection and emit signal
        selected_items = self.selectedItems()
        if selected_items:
            # Emit the first selected item (assuming single selection for now)
            # Filter for QGraphicsPathItem specifically if needed
            selected_item = selected_items[0]
            if isinstance(selected_item, QGraphicsPathItem): # Ensure it's a polyline
                 self.logger.debug(f"Selection changed, emitting signal for item: {selected_item}")
                 self.selectionChanged.emit(selected_item)
            else:
                 self.logger.debug(f"Selection changed, but item is not a QGraphicsPathItem: {type(selected_item)}")
                 self.selectionChanged.emit(None) # Emit None if selection is not a polyline path

        elif not selected_items:
            # Emit None if selection is cleared
            self.logger.debug("Selection cleared, emitting None.")
            self.selectionChanged.emit(None)

    # --- Polyline Drawing Helpers ---

    def _add_vertex_marker(self, pos: QPointF):
        """Adds a visual marker for a vertex."""
        radius = self._vertex_radius
        # Adjust position to center the ellipse on the point
        ellipse = QGraphicsEllipseItem(pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)
        ellipse.setPen(self._vertex_pen)
        ellipse.setBrush(self._vertex_brush)
        ellipse.setZValue(10) # Ensure vertices are drawn above lines/background
        self.addItem(ellipse)
        self._current_vertices_items.append(ellipse)

    def _update_temporary_line(self, current_pos: QPointF):
        """Updates the rubber-band line from the last vertex to the current mouse position."""
        if not self._current_polyline_points:
            return

        last_point = self._current_polyline_points[-1]
        constrained_pos = self._constrained_pos(current_pos, Qt.NoModifier) # Apply constraints for display only? No, apply in move event.

        # Use the already constrained position from mouseMoveEvent
        pos_to_draw_to = current_pos # Use the position passed in (already constrained)

        if self._temporary_line_item:
            # Update existing line
            self._temporary_line_item.setLine(QLineF(last_point, pos_to_draw_to))
        else:
            # Create new line
            self._temporary_line_item = QGraphicsLineItem(QLineF(last_point, pos_to_draw_to))
            self._temporary_line_item.setPen(self._rubber_band_pen)
            self._temporary_line_item.setZValue(5) # Draw rubber band above background but below vertices
            self.addItem(self._temporary_line_item)

    def _finalize_current_polyline(self, layer_name: str):
        """Finalizes the current polyline, creates a QGraphicsPathItem, and resets state."""
        if len(self._current_polyline_points) < 2:
            self._cancel_current_polyline()
            return

        path = QPainterPath()
        path.moveTo(self._current_polyline_points[0])
        for point in self._current_polyline_points[1:]:
            path.lineTo(point)

        polyline_item = QGraphicsPathItem(path)
        polyline_item.setPen(self._finalized_polyline_pen)
        polyline_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        polyline_item.setFlag(QGraphicsItem.ItemIsMovable, True) # Allow moving later
        polyline_item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True) # For updates if moved
        polyline_item.setZValue(1) # Ensure finalized lines are above background

        # --- Store layer name and original points in the item ---
        polyline_item.setData(Qt.UserRole + 1, layer_name)
        # Store points as list of tuples for easier serialization/retrieval
        points_data = [(p.x(), p.y()) for p in self._current_polyline_points]
        polyline_item.setData(Qt.UserRole + 2, points_data)
        # --- END Store ---

        # Push undo command to MainWindow's stack if available
        main_win = self.parent_view.window() if self.parent_view else None
        if main_win and hasattr(main_win, 'undoStack'):
            cmd = AddPolylineCommand(self, polyline_item)
            main_win.undoStack.push(cmd)
        else:
            # Fallback: directly add item if no undo stack
            if polyline_item not in self.items():
                self.addItem(polyline_item)

        self.logger.info(
            f"Finalized polyline with {len(self._current_polyline_points)} points on layer '{layer_name}'."
        )

        # Emit finalized signal (item is already in scene via undo command redo)
        self.polyline_finalized.emit(self._current_polyline_points, polyline_item)

        # --- NEW: Emit padDrawn if polyline belongs to "pads" layer and is closed ---
        try:
            # Convert QPointF list to plain tuples for emission
            points_2d = [(p.x(), p.y()) for p in self._current_polyline_points]
            if layer_name.lower() == "pads" and self._path_is_closed(points_2d):
                self.logger.debug("padDrawn emitted for closed pad on 'pads' layer with %d vertices", len(points_2d))
                self.padDrawn.emit(points_2d)
        except Exception as e:
            self.logger.error("Failed to evaluate/emit padDrawn: %s", e, exc_info=True)
        # --- END NEW ---

        self._reset_drawing_state()

    def _cancel_current_polyline(self):
        """Cancels the current polyline drawing."""
        self.logger.debug("Cancelling current polyline.")
        self._reset_drawing_state()

    def _undo_last_vertex(self):
        """Removes the last added vertex and its marker."""
        if len(self._current_polyline_points) > 1 and self._current_vertices_items:
            removed_point = self._current_polyline_points.pop()
            removed_marker = self._current_vertices_items.pop()
            if removed_marker in self.items():
                self.removeItem(removed_marker)
            self.logger.debug(f"Undid last vertex at: {removed_point.x():.2f}, {removed_point.y():.2f}")
            # Update the temporary line to the new last point
            if self._current_polyline_points:
                 # Need current mouse pos - tricky. Get from view? Or just remove temp line?
                 # For now, just remove it until next mouse move.
                 if self._temporary_line_item:
                     if self._temporary_line_item in self.items():
                         self.removeItem(self._temporary_line_item)
                     self._temporary_line_item = None
            else:
                 # If only one point was left after undo, cancel drawing
                 self._cancel_current_polyline()

        elif len(self._current_polyline_points) == 1:
             # If only the starting point remains, cancel the whole line
             self._cancel_current_polyline()

    def _reset_drawing_state(self):
        """Resets all temporary items and flags related to the current drawing operation."""
        # Remove temporary line
        if self._temporary_line_item and self._temporary_line_item in self.items():
            self.removeItem(self._temporary_line_item)
        self._temporary_line_item = None

        # Remove vertex markers
        for item in self._current_vertices_items:
            if item in self.items():
                self.removeItem(item)
        self._current_vertices_items.clear()

        # Reset state variables
        self._is_drawing = False
        self._current_polyline_points = []
        # Don't disable tracing mode here, only reset the current polyline state

    # --- Loading / Saving / Layer Management ---

    def clear_finalized_polylines(self):
        """Removes all finalized QGraphicsPathItems from the scene."""
        items_to_remove = [item for item in self.items() if isinstance(item, QGraphicsPathItem)]
        for item in items_to_remove:
            self.removeItem(item)
        self.logger.info("Cleared all finalized polylines.")

    def load_polylines_with_layers(self, polylines_by_layer: Dict[str, Sequence[PolylineData]]):
        """
        Loads polylines from a dictionary structure, creating QGraphicsPathItems
        and assigning layer information.

        Args:
            polylines_by_layer (Dict[str, Sequence[PolylineData]]):
                A dictionary where keys are layer names and values are sequences of
                polyline data (e.g., lists of point tuples or dicts).
                Example:
                {
                    "Existing": [ [(10, 10), (50, 10)], [(20, 30), (60, 30)] ],
                    "Proposed": [ [(15, 45), (55, 45), (55, 65)] ]
                }
                PolylineData format assumes a list/tuple of (x, y) tuples/lists.
        """
        self.clear_finalized_polylines() # Clear existing before loading

        for layer_name, polylines in polylines_by_layer.items():
            self.logger.debug(f"Loading {len(polylines)} polylines for layer '{layer_name}'")
            for poly_data in polylines:
                if not poly_data or len(poly_data) < 2:
                    self.logger.warning(f"Skipping invalid polyline data for layer '{layer_name}': {poly_data}")
                    continue

                try:
                    path = QPainterPath()
                    start_point = QPointF(poly_data[0][0], poly_data[0][1])
                    path.moveTo(start_point)
                    for point_data in poly_data[1:]:
                        path.lineTo(QPointF(point_data[0], point_data[1]))

                    polyline_item = QGraphicsPathItem(path)
                    polyline_item.setPen(self._finalized_polyline_pen)
                    polyline_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                    polyline_item.setFlag(QGraphicsItem.ItemIsMovable, True)
                    polyline_item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
                    polyline_item.setZValue(1)

                    # Store layer name and original points
                    polyline_item.setData(Qt.UserRole + 1, layer_name)
                    # Re-store points data as list of tuples
                    points_data = [(p[0], p[1]) for p in poly_data]
                    polyline_item.setData(Qt.UserRole + 2, points_data)

                    self.addItem(polyline_item)
                except (TypeError, IndexError, ValueError) as e:
                    self.logger.error(f"Error processing polyline data for layer '{layer_name}': {poly_data}. Error: {e}")

        self.logger.info(f"Finished loading polylines for {len(polylines_by_layer)} layers.")
        # Update scene rect after loading all items
        self.setSceneRect(self.itemsBoundingRect())
        self.pageRectChanged.emit() # Emit signal after loading

    def dump_scene_state(self) -> LayerPolylineDict:
        """
        Extracts finalized polylines and groups them by layer name.

        Returns:
            LayerPolylineDict:
                A dictionary where keys are layer names and values are lists of
                polylines, each represented as a list of (x, y) tuples.
        """
        polylines_by_layer: LayerPolylineDict = {}
        for item in self.items():
            if isinstance(item, QGraphicsPathItem):
                layer_name = item.data(Qt.UserRole + 1)
                points_data = item.data(Qt.UserRole + 2)
                if isinstance(layer_name, str) and isinstance(points_data, list):
                    if layer_name not in polylines_by_layer:
                        polylines_by_layer[layer_name] = []
                    # Ensure points_data contains tuples (it should from load/finalize)
                    polyline_tuples = [(float(p[0]), float(p[1])) for p in points_data if len(p) == 2]
                    polylines_by_layer[layer_name].append(polyline_tuples)
        self.logger.info(f"Dumped scene state: {len(polylines_by_layer)} layers found.")
        return polylines_by_layer

    def setLayerVisible(self, layer_name: str, visible: bool) -> None: # noqa: N802
        """Sets the visibility of all polyline items associated with a layer."""
        count = 0
        for item in self.items():
            if isinstance(item, QGraphicsPathItem):
                item_layer = item.data(Qt.UserRole + 1)
                if item_layer == layer_name:
                    item.setVisible(visible)
                    count += 1
        self.logger.debug(f"Set visibility for {count} items on layer '{layer_name}' to {visible}.")

    # --- Debugging ---
    def dump_scene_state(self):
        """Logs the current state of items in the scene for debugging."""
        self.logger.debug(f"Tracing Enabled: {self._tracing_enabled}")
        self.logger.debug(f"Is Drawing: {self._is_drawing}")
        self.logger.debug(f"Current Points: {len(self._current_polyline_points)}")
        if self._background_items:
            self.logger.debug(f"Background Item: {self._background_items[0].boundingRect()}")
        else:
            self.logger.debug("Background Item: None")
        self.logger.debug(f"Item Count: {len(self.items())}")

    # --- Helper to get current selected polyline ---
    def current_polyline(self):
        """Return the currently selected QGraphicsPathItem (polyline), if any."""
        sel = [itm for itm in self.selectedItems() if isinstance(itm, QGraphicsPathItem)]
        return sel[0] if sel else None

    def current_polyline_points(self) -> list[tuple[float, float]]:
        """Return the 2-D points of the currently selected polyline."""
        item = self.current_polyline()
        if not item:
            return []
        path: QPainterPath = item.path()
        return [(path.elementAt(i).x, path.elementAt(i).y) for i in range(path.elementCount())]

    def add_offset_breakline(self, pts3d: list[tuple[float, float, float]], *, push_to_undo: bool = True):
        """Add a 3-D aware offset breakline to the scene.

        If *push_to_undo* is True (default), an AddPolylineCommand is pushed onto the
        application's undo stack.  When False, the caller is responsible for
        managing undo/redo behaviour.  The created QGraphicsPathItem is returned
        in all cases.
        """
        if not pts3d or len(pts3d) < 2:
            self.logger.warning("add_offset_breakline called with insufficient points.")
            return

        # Create a 2-D path (ignore z for screen representation)
        path = QPainterPath()
        path.moveTo(QPointF(pts3d[0][0], pts3d[0][1]))
        for x, y, _ in pts3d[1:]:
            path.lineTo(QPointF(x, y))

        item = QGraphicsPathItem(path)
        # Use dashed magenta pen to visually distinguish offset lines
        pen = self._finalized_polyline_pen
        pen.setStyle(Qt.DashLine)
        pen.setColor(Qt.magenta)
        item.setPen(pen)
        item.setZValue(1)
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        # Store layer and both 2D & 3D pts
        item.setData(Qt.UserRole + 1, "Offsets")
        item.setData(Qt.UserRole + 2, [(x, y) for x, y, *_ in pts3d])
        item.setData(Qt.UserRole + 3, pts3d)  # Full 3-D points

        main_win = self.parent_view.window() if self.parent_view else None
        if push_to_undo and main_win and hasattr(main_win, 'undoStack'):
            cmd = AddPolylineCommand(self, item)
            main_win.undoStack.push(cmd)
        else:
            if item not in self.items():
                self.addItem(item)

        return item

# ------------------------------------------------------------------
# Undo/Redo Command
# ------------------------------------------------------------------

class AddPolylineCommand(QUndoCommand):
    """QUndoCommand to add/remove a polyline item from the scene."""

    def __init__(self, scene: 'TracingScene', item_or_pts, layer: str | None = None):  # noqa: D401
        super().__init__("Add Polyline")
        self._scene = scene
        if isinstance(item_or_pts, QGraphicsPathItem):
            self._item = item_or_pts
        else:
            # Assume iterable of (x,y,?) tuples – create path (ignore z)
            from PySide6.QtCore import QPointF
            path = QPainterPath()
            pts = list(item_or_pts)
            if not pts:
                raise ValueError("No points supplied for AddPolylineCommand")
            path.moveTo(QPointF(pts[0][0], pts[0][1]))
            for x, y, *_ in pts[1:]:
                path.lineTo(QPointF(x, y))
            self._item = QGraphicsPathItem(path)
            pen = QPen(Qt.magenta, 1, Qt.DashLine)
            self._item.setPen(pen)
            self._item.setZValue(1)
            # Store metadata
            self._item.setData(Qt.UserRole + 1, layer or "Offsets")
            self._item.setData(Qt.UserRole + 2, [(x, y) for x, y, *_ in pts])
            self._item.setData(Qt.UserRole + 3, pts)

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------

    def redo(self):  # noqa: D401
        if self._item not in self._scene.items():
            self._scene.addItem(self._item)

    def undo(self):  # noqa: D401
        if self._item in self._scene.items():
            self._scene.removeItem(self._item)

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _path_is_closed(pts: list[tuple[float, float]], tol: float = 1e-6) -> bool:
        """Return True if path is closed (first & last vertices coincide within *tol*)."""
        return len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < tol and abs(pts[0][1] - pts[-1][1]) < tol

class SetPadElevationCommand(QUndoCommand):
    """QUndoCommand to add/remove a *pad* polyline (closed polygon) with constant elevation."""

    def __init__(self, scene: 'TracingScene', pts3d: list[tuple[float, float, float]]):  # noqa: D401
        super().__init__("Add Pad")
        if not pts3d or len(pts3d) < 3:
            raise ValueError("Pad requires at least 3 vertices.")
        self._scene = scene
        self._pts3d = pts3d
        self._item: Optional[QGraphicsPathItem] = None

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------
    def redo(self):  # noqa: D401
        # Build the graphics item on first redo
        if self._item is None:
            path = QPainterPath()
            path.moveTo(QPointF(self._pts3d[0][0], self._pts3d[0][1]))
            for x, y, *_ in self._pts3d[1:]:
                path.lineTo(QPointF(x, y))
            # Close the path visually
            path.closeSubpath()

            self._item = QGraphicsPathItem(path)
            pen = QPen(QColor("orange"), 3)
            self._item.setPen(pen)
            self._item.setZValue(1)
            self._item.setFlag(QGraphicsItem.ItemIsSelectable, True)

            # Store metadata
            self._item.setData(Qt.UserRole + 1, "Pads")
            self._item.setData(Qt.UserRole + 2, [(x, y) for x, y, *_ in self._pts3d])
            self._item.setData(Qt.UserRole + 3, self._pts3d)  # 3-D vertices

        if self._item not in self._scene.items():
            self._scene.addItem(self._item)

    def undo(self):  # noqa: D401
        if self._item and self._item in self._scene.items():
            self._scene.removeItem(self._item)