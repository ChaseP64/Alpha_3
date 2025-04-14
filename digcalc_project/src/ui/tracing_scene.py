# src/ui/tracing_scene.py

import logging
from typing import List, Optional, Tuple, Dict, Sequence

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainterPath, QPen, QPixmap, QKeyEvent
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsItemGroup,
)

class TracingScene(QGraphicsScene):
    """
    A custom QGraphicsScene for interactive polyline tracing over a background image,
    with support for basic layer management.
    """

    # Signal emitted when a polyline is finalized (e.g., by double-click or Enter)
    # Sends the list of QPointF vertices and the layer name it was added to.
    polyline_finalized = Signal(list)

    def __init__(self, parent=None):
        """Initialize the TracingScene."""
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self._background_item: Optional[QGraphicsPixmapItem] = None
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
        self._finalized_polyline_pen = QPen(QColor("lime"), 2)

    # --- Background Image ---

    def set_background_image(self, image: Optional[QImage]):
        """Sets or clears the background image of the scene."""
        # Remove existing background if it exists
        if self._background_item and self._background_item in self.items():
            self.removeItem(self._background_item)
            self._background_item = None
            self.setSceneRect(self.itemsBoundingRect())

        if image and not image.isNull():
            pixmap = QPixmap.fromImage(image)
            self._background_item = QGraphicsPixmapItem(pixmap)
            self._background_item.setZValue(-1) # Background is always at the bottom
            self._background_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self._background_item.setFlag(QGraphicsItem.ItemIsMovable, False)
            self._background_item.setOpacity(self._background_opacity)
            self.addItem(self._background_item)
            self.setSceneRect(self._background_item.boundingRect())
            self.logger.info(f"Background image set with size: {image.width()}x{image.height()}")
        else:
            self.setSceneRect(self.itemsBoundingRect())
            self.logger.info("Background image cleared.")

    # --- Drawing Control ---

    def start_drawing(self):
        """Explicitly enables drawing mode."""
        self._tracing_enabled = True
        self.logger.debug("Drawing mode explicitly enabled.")

    def stop_drawing(self):
        """Explicitly disables drawing mode and cancels any current polyline."""
        self._tracing_enabled = False
        if self._is_drawing:
            self._cancel_current_polyline()
            self.logger.debug("Drawing mode explicitly disabled, current polyline cancelled.")

    # --- Event Handling for Drawing ---

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles mouse press events to add vertices to the polyline."""
        if not self._tracing_enabled:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            pos = event.scenePos()
            can_draw = True
            if self._background_item:
                 can_draw = self._background_item.sceneBoundingRect().contains(pos)

            if can_draw:
                if not self._is_drawing:
                    self._is_drawing = True
                    self._current_polyline_points = [pos]
                    self._add_vertex_marker(pos)
                    self.logger.debug(f"Started new polyline at: {pos.x():.2f}, {pos.y():.2f}")
                else:
                    self._current_polyline_points.append(pos)
                    self._add_vertex_marker(pos)
                    self._update_temporary_line(pos)
                    self.logger.debug(f"Added vertex at: {pos.x():.2f}, {pos.y():.2f}")
            else:
                 super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles mouse move events to update the temporary rubber-band line."""
        if not self._tracing_enabled or not self._is_drawing or not self._current_polyline_points:
            super().mouseMoveEvent(event)
            return

        pos = event.scenePos()
        self._update_temporary_line(pos)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles double-click events to finalize the current polyline."""
        if not self._tracing_enabled or not self._is_drawing:
            super().mouseDoubleClickEvent(event)
            return

        if event.button() == Qt.LeftButton:
            if len(self._current_polyline_points) >= 2:
                final_pos = event.scenePos()
                self._current_polyline_points.append(final_pos)
                self._finalize_current_polyline()
            else:
                self._cancel_current_polyline()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key press events (Enter to finalize, Backspace to undo, Esc to cancel)."""
        if not self._tracing_enabled or not self._is_drawing:
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if len(self._current_polyline_points) >= 2:
                self._finalize_current_polyline()
            else:
                self._cancel_current_polyline()
        elif event.key() == Qt.Key_Backspace:
            self._undo_last_vertex()
        elif event.key() == Qt.Key_Escape:
             self._cancel_current_polyline()
        else:
            super().keyPressEvent(event)

    # --- Helper Methods for Drawing ---

    def _add_vertex_marker(self, pos: QPointF):
        """Adds a visual marker (ellipse) for a vertex."""
        radius = self._vertex_radius
        marker = QGraphicsEllipseItem(
            pos.x() - radius, pos.y() - radius, radius * 2, radius * 2
        )
        marker.setPen(self._vertex_pen)
        marker.setBrush(self._vertex_brush)
        marker.setZValue(1) # Above background/finalized lines
        self.addItem(marker)
        self._current_vertices_items.append(marker)

    def _update_temporary_line(self, current_pos: QPointF):
        """Updates the position of the temporary rubber-band line."""
        if not self._current_polyline_points:
            return

        last_vertex_pos = self._current_polyline_points[-1]

        if self._temporary_line_item and self._temporary_line_item in self.items():
            self.removeItem(self._temporary_line_item)
            self._temporary_line_item = None

        self._temporary_line_item = QGraphicsLineItem(
            last_vertex_pos.x(), last_vertex_pos.y(),
            current_pos.x(), current_pos.y()
        )
        self._temporary_line_item.setPen(self._rubber_band_pen)
        self._temporary_line_item.setZValue(0) # Below markers but above background
        self.addItem(self._temporary_line_item)

    def _finalize_current_polyline(self):
        """Converts the current points into a permanent polyline item in the active layer."""
        if len(self._current_polyline_points) < 2:
            self.logger.warning("Cannot finalize polyline with less than 2 points.")
            self._cancel_current_polyline()
            return

        path = QPainterPath()
        path.moveTo(self._current_polyline_points[0])
        for point in self._current_polyline_points[1:]:
            path.lineTo(point)

        polyline_item = QGraphicsPathItem(path)
        polyline_item.setPen(self._finalized_polyline_pen)
        polyline_item.setZValue(0) # Render below vertices but above background
        self.addItem(polyline_item)

        self.logger.info(f"Finalized polyline with {len(self._current_polyline_points)} vertices.")

        # --- FIX: Emit signal *before* resetting state --- 
        # Store points before reset, as reset clears the list
        points_to_emit = list(self._current_polyline_points) 
        # Emit signal with finalized points
        self.polyline_finalized.emit(points_to_emit)
        # ----------------------------------------------

        self._reset_drawing_state()

    def _cancel_current_polyline(self):
        """Removes temporary items and resets the drawing state without finalizing."""
        self.logger.debug("Cancelling current polyline drawing.")
        self._reset_drawing_state()

    def _undo_last_vertex(self):
        """Removes the last added vertex and its marker."""
        if not self._is_drawing or not self._current_polyline_points:
            return

        removed_point = self._current_polyline_points.pop()
        self.logger.debug(f"Undoing last vertex: {removed_point.x():.2f}, {removed_point.y():.2f}")

        if self._current_vertices_items:
            last_marker = self._current_vertices_items.pop()
            if last_marker in self.items():
                self.removeItem(last_marker)

        if not self._current_polyline_points:
            self._is_drawing = False
            if self._temporary_line_item and self._temporary_line_item in self.items():
                self.removeItem(self._temporary_line_item)
                self._temporary_line_item = None
        else:
            if self._temporary_line_item and self._temporary_line_item in self.items():
                self.removeItem(self._temporary_line_item)
                self._temporary_line_item = None

    def _reset_drawing_state(self):
        """Clears all temporary drawing items and resets state variables."""
        if self._temporary_line_item and self._temporary_line_item in self.items():
            self.removeItem(self._temporary_line_item)
            self._temporary_line_item = None

        for marker in self._current_vertices_items:
            if marker in self.items():
                self.removeItem(marker)
        self._current_vertices_items.clear()

        self._current_polyline_points.clear()
        self._is_drawing = False
        self.logger.debug("Drawing state reset.")

    # --- Methods for Loading/Clearing Finalized Lines ---

    def clear_finalized_polylines(self):
        """Removes all finalized QGraphicsPathItems (polylines) from the scene."""
        items_to_remove = []
        # Iterate directly over scene items
        for item in self.items():
            if isinstance(item, QGraphicsPathItem):
                items_to_remove.append(item)

        for item in items_to_remove:
            self.removeItem(item)
        self.logger.info(f"Cleared {len(items_to_remove)} finalized polyline(s).")

    def load_polylines(self, polylines_data: List[List[Tuple[float, float]]]):
        """
        Clears existing finalized polylines and loads new ones from data.
        NOTE: This version loads all lines into the DEFAULT layer, as layer
        information is not yet saved/loaded in the project file.

        Args:
            polylines_data: A list where each item is a list of (x, y) tuples representing a polyline.
        """
        # self.clear_finalized_polylines() # REMOVED - Clearing should be handled before calling this

        # REMOVED Incorrect check for a layer item named "Default"
        # The scene is assumed to be clear, and we just add the items back.
        # target_layer_name = "Default"
        # if target_layer_name not in self.items():
        #     self.logger.error(f"Cannot load polylines: Default layer '{target_layer_name}' not found.")
        #     return

        self.logger.info(f"Loading {len(polylines_data)} polylines onto the scene.")

        added_count = 0

        for poly_points in polylines_data:
            if len(poly_points) >= 2:
                try:
                    path = QPainterPath()
                    start_point = QPointF(poly_points[0][0], poly_points[0][1])
                    path.moveTo(start_point)
                    for point_tuple in poly_points[1:]:
                        path.lineTo(QPointF(point_tuple[0], point_tuple[1]))

                    path_item = QGraphicsPathItem(path)
                    path_item.setPen(self._finalized_polyline_pen)
                    path_item.setZValue(0)
                    self.addItem(path_item)
                    added_count += 1
                except Exception as e:
                    self.logger.error(f"Error creating QGraphicsPathItem for loaded polyline: {e}", exc_info=True)
            else:
                 self.logger.warning(f"Skipping loaded polyline with less than 2 points: {poly_points}")

        self.logger.info(f"Loaded and displayed {added_count} polylines.")

    # --- View Interaction (Future) ---
    # Zooming, panning etc. could be handled here or in the QGraphicsView

    # --- Debugging ---
    def dump_scene_state(self):
        """Logs the current state of the scene for debugging."""
        self.logger.debug(f"Tracing Enabled: {self._tracing_enabled}")
        self.logger.debug(f"Is Drawing: {self._is_drawing}")
        self.logger.debug(f"Current Points: {len(self._current_polyline_points)}")
        if self._background_item:
            self.logger.debug(f"Background Item: {self._background_item.boundingRect()}")
        else:
            self.logger.debug("Background Item: None")
        self.logger.debug(f"Item Count: {len(self.items())}") 