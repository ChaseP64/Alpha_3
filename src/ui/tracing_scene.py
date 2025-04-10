# src/ui/tracing_scene.py

import logging
from typing import List, Optional

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QKeyEvent,
)


class TracingScene(QGraphicsScene):
    """
    A custom QGraphicsScene for interactive polyline tracing over a background image.

    Handles mouse events to draw polylines vertex by vertex and manages
    temporary visual feedback during the drawing process. Finalized polylines
    are added as permanent items.
    """

    # Signal emitted when a polyline is finalized (e.g., by double-click or Enter)
    # Sends the list of QPointF vertices of the completed polyline.
    polyline_finalized = Signal(list)

    def __init__(self, parent=None):
        """Initialize the TracingScene."""
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self._background_item: Optional[QGraphicsPixmapItem] = None
        self._is_drawing: bool = False
        self._current_polyline_points: List[QPointF] = []
        self._current_vertices_items: List[QGraphicsEllipseItem] = []
        self._temporary_line_item: Optional[QGraphicsLineItem] = None

        # --- Styling ---
        # Style for the background image item
        self._background_opacity = 0.7

        # Style for vertices during drawing
        self._vertex_pen = QPen(QColor("cyan"), 1)
        self._vertex_brush = QBrush(QColor("cyan"))
        self._vertex_radius = 3.0  # Screen pixels for vertex marker size

        # Style for the rubber-band line during drawing
        self._rubber_band_pen = QPen(QColor("yellow"), 1, Qt.DashLine)

        # Style for finalized polylines
        self._finalized_polyline_pen = QPen(QColor("lime"), 2)

    def set_background_image(self, image: Optional[QImage]):
        """
        Sets or clears the background image of the scene.

        Args:
            image: The QImage to set as the background. If None, removes the background.
        """
        # Remove existing background if it exists
        if self._background_item and self._background_item in self.items():
            self.removeItem(self._background_item)
            self._background_item = None
            self.setSceneRect(self.itemsBoundingRect()) # Adjust scene rect

        if image and not image.isNull():
            pixmap = QPixmap.fromImage(image)
            self._background_item = QGraphicsPixmapItem(pixmap)
            # Make background non-interactive and place it behind other items
            self._background_item.setZValue(-1)
            self._background_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self._background_item.setFlag(QGraphicsItem.ItemIsMovable, False)
            self._background_item.setOpacity(self._background_opacity)
            self.addItem(self._background_item)
            # Set the scene rect to match the background image size
            self.setSceneRect(self._background_item.boundingRect())
            self.logger.info(f"Background image set with size: {image.width()}x{image.height()}")
        else:
            # If clearing, reset scene rect potentially
            self.setSceneRect(self.itemsBoundingRect())
            self.logger.info("Background image cleared.")

    def start_drawing(self):
        """Explicitly enables drawing mode."""
        # Potentially useful if triggered by a button in the UI
        self.logger.debug("Drawing mode explicitly enabled.")
        # Could add visual cues if needed

    def stop_drawing(self):
        """Explicitly disables drawing mode and cancels any current polyline."""
        if self._is_drawing:
            self._cancel_current_polyline()
            self.logger.debug("Drawing mode explicitly disabled, current polyline cancelled.")

    # --- Event Handling for Drawing ---

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles mouse press events to add vertices to the polyline."""
        if event.button() == Qt.LeftButton:
            # Only start drawing if mouse press is within the background bounds
            # or if no background is set (allow drawing anywhere)
            pos = event.scenePos()
            can_draw = True
            if self._background_item:
                 can_draw = self._background_item.sceneBoundingRect().contains(pos)

            if can_draw:
                if not self._is_drawing:
                    # Start a new polyline
                    self._is_drawing = True
                    self._current_polyline_points = [pos]
                    self._add_vertex_marker(pos)
                    self.logger.debug(f"Started new polyline at: {pos.x():.2f}, {pos.y():.2f}")
                else:
                    # Add vertex to the existing polyline
                    self._current_polyline_points.append(pos)
                    self._add_vertex_marker(pos)
                    # Update temporary line to start from the *new* last point
                    self._update_temporary_line(pos)
                    self.logger.debug(f"Added vertex at: {pos.x():.2f}, {pos.y():.2f}")
            else:
                 # Click outside background, pass event to base class (might be needed for panning/zooming later)
                 super().mousePressEvent(event)
        else:
            # Pass other button presses to the base class
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles mouse move events to update the temporary rubber-band line."""
        if self._is_drawing and self._current_polyline_points:
            pos = event.scenePos()
            self._update_temporary_line(pos)
        else:
            super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles double-click events to finalize the current polyline."""
        if event.button() == Qt.LeftButton and self._is_drawing:
            if len(self._current_polyline_points) >= 2:
                # Add the double-clicked point as the last vertex
                final_pos = event.scenePos()
                # Optional: Check if final_pos is within background bounds?
                self._current_polyline_points.append(final_pos)
                # No need to add a marker here, finalizing immediately
                self._finalize_current_polyline()
            else:
                # Not enough points, cancel drawing
                self._cancel_current_polyline()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key press events (Enter to finalize, Backspace to undo, Esc to cancel)."""
        if not self._is_drawing:
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if len(self._current_polyline_points) >= 2:
                self._finalize_current_polyline()
            else:
                # Not enough points, cancel drawing
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
        # Create marker centered on the position
        marker = QGraphicsEllipseItem(
            pos.x() - radius, pos.y() - radius, radius * 2, radius * 2
        )
        marker.setPen(self._vertex_pen)
        marker.setBrush(self._vertex_brush)
        marker.setZValue(1) # Ensure markers are above background
        self.addItem(marker)
        self._current_vertices_items.append(marker)

    def _update_temporary_line(self, current_pos: QPointF):
        """Updates the position of the temporary rubber-band line."""
        if not self._current_polyline_points:
            return

        last_vertex_pos = self._current_polyline_points[-1]

        # Remove the old temporary line if it exists
        if self._temporary_line_item and self._temporary_line_item in self.items():
            self.removeItem(self._temporary_line_item)
            self._temporary_line_item = None

        # Create and add the new temporary line
        self._temporary_line_item = QGraphicsLineItem(
            last_vertex_pos.x(), last_vertex_pos.y(),
            current_pos.x(), current_pos.y()
        )
        self._temporary_line_item.setPen(self._rubber_band_pen)
        self._temporary_line_item.setZValue(0) # Below markers but above background
        self.addItem(self._temporary_line_item)

    def _finalize_current_polyline(self):
        """Converts the current points into a permanent polyline item."""
        if len(self._current_polyline_points) < 2:
            self.logger.warning("Cannot finalize polyline with less than 2 points.")
            self._cancel_current_polyline() # Cancel if not enough points
            return

        path = QPainterPath()
        path.moveTo(self._current_polyline_points[0])
        for point in self._current_polyline_points[1:]:
            path.lineTo(point)

        polyline_item = QGraphicsPathItem(path)
        polyline_item.setPen(self._finalized_polyline_pen)
        polyline_item.setZValue(0.5) # Above temp line, below markers maybe?
        polyline_item.setFlag(QGraphicsItem.ItemIsSelectable, True) # Make finalized lines selectable
        polyline_item.setFlag(QGraphicsItem.ItemIsMovable, True) # Allow moving lines later if needed
        self.addItem(polyline_item)

        final_points = list(self._current_polyline_points) # Copy list
        self.logger.info(f"Polyline finalized with {len(final_points)} vertices.")

        # Clean up temporary items
        self._reset_drawing_state()

        # Emit signal with the finalized points
        self.polyline_finalized.emit(final_points)


    def _cancel_current_polyline(self):
        """Removes temporary items and resets the drawing state without finalizing."""
        self.logger.debug("Cancelling current polyline drawing.")
        self._reset_drawing_state()


    def _undo_last_vertex(self):
        """Removes the last added vertex and its marker."""
        if not self._is_drawing or not self._current_polyline_points:
            return # Nothing to undo

        # Remove the last point
        removed_point = self._current_polyline_points.pop()
        self.logger.debug(f"Undoing last vertex: {removed_point.x():.2f}, {removed_point.y():.2f}")

        # Remove the corresponding marker
        if self._current_vertices_items:
            last_marker = self._current_vertices_items.pop()
            if last_marker in self.items():
                self.removeItem(last_marker)

        # If no points left, stop drawing and clear temp line
        if not self._current_polyline_points:
            self._is_drawing = False
            if self._temporary_line_item and self._temporary_line_item in self.items():
                self.removeItem(self._temporary_line_item)
                self._temporary_line_item = None
        else:
            # Update the temporary line to the *new* last point (needs mouse pos)
            # We can't perfectly restore the temp line without current mouse pos,
            # but we can remove the old one. It will redraw on next mouse move.
            if self._temporary_line_item and self._temporary_line_item in self.items():
                self.removeItem(self._temporary_line_item)
                self._temporary_line_item = None


    def _reset_drawing_state(self):
        """Clears all temporary drawing items and resets state variables."""
        # Remove temporary line
        if self._temporary_line_item and self._temporary_line_item in self.items():
            self.removeItem(self._temporary_line_item)
            self._temporary_line_item = None

        # Remove vertex markers
        for marker in self._current_vertices_items:
            if marker in self.items():
                self.removeItem(marker)
        self._current_vertices_items.clear()

        # Reset state
        self._current_polyline_points.clear()
        self._is_drawing = False
        self.logger.debug("Drawing state reset.") 