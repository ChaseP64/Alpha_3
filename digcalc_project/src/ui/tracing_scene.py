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

# Define default layers
DEFAULT_LAYERS = [
    "Existing Surface",
    "Proposed Surface",
    "Subgrade",
    "Annotations",
    "Report Regions",
]

class TracingScene(QGraphicsScene):
    """
    A custom QGraphicsScene for interactive polyline tracing over a background image,
    with support for basic layer management.
    """

    # Signal emitted when a polyline is finalized (e.g., by double-click or Enter)
    # Sends the list of QPointF vertices and the layer name it was added to.
    polyline_finalized = Signal(list, str)

    def __init__(self, parent=None, layers: Sequence[str] = DEFAULT_LAYERS):
        """Initialize the TracingScene."""
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self._background_item: Optional[QGraphicsPixmapItem] = None
        self._tracing_enabled: bool = False
        self._is_drawing: bool = False
        self._current_polyline_points: List[QPointF] = []
        self._current_vertices_items: List[QGraphicsEllipseItem] = []
        self._temporary_line_item: Optional[QGraphicsLineItem] = None

        # --- Layer Management ---
        self._layer_names: List[str] = list(layers)
        self._layer_groups: Dict[str, QGraphicsItemGroup] = {}
        self._active_layer_name: str = self._layer_names[0] if self._layer_names else "Default"
        self._init_layers()

        # --- Styling ---
        # TODO: Consider layer-specific styling later
        self._background_opacity = 0.7
        self._vertex_pen = QPen(QColor("cyan"), 1)
        self._vertex_brush = QBrush(QColor("cyan"))
        self._vertex_radius = 3.0
        self._rubber_band_pen = QPen(QColor("yellow"), 1, Qt.DashLine)
        self._finalized_polyline_pen = QPen(QColor("lime"), 2)

    def _init_layers(self):
        """Create QGraphicsItemGroup for each defined layer."""
        # Ensure a default layer exists if none provided
        if not self._layer_names:
             self._layer_names.append("Default")
             self._active_layer_name = "Default"

        for name in self._layer_names:
            group = QGraphicsItemGroup()
            group.setHandlesChildEvents(False) # Let scene handle clicks initially
            self.addItem(group)
            self._layer_groups[name] = group
            self.logger.debug(f"Initialized layer group: {name}")

        # Ensure active layer exists
        if self._active_layer_name not in self._layer_groups:
             self._active_layer_name = self._layer_names[0]

    # --- Public Layer Methods ---

    def get_layers(self) -> List[str]:
        """Returns the list of defined layer names."""
        return list(self._layer_names) # Return a copy

    def set_active_layer(self, layer_name: str):
        """Sets the layer to which new drawings will be added."""
        if layer_name in self._layer_groups:
            if self._active_layer_name != layer_name:
                self._active_layer_name = layer_name
                self.logger.info(f"Active layer set to: {layer_name}")
        else:
            self.logger.warning(f"Attempted to set invalid active layer: {layer_name}")

    def get_active_layer(self) -> str:
         """Gets the name of the currently active layer."""
         return self._active_layer_name

    def set_layer_visibility(self, layer_name: str, visible: bool):
        """Sets the visibility of all items within a specific layer."""
        if layer_name in self._layer_groups:
            self._layer_groups[layer_name].setVisible(visible)
            self.logger.debug(f"Layer '{layer_name}' visibility set to {visible}")
        else:
            self.logger.warning(f"Cannot set visibility for unknown layer: {layer_name}")

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
                    self.logger.debug(f"Started new polyline at: {pos.x():.2f}, {pos.y():.2f} on layer '{self._active_layer_name}'")
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

        # Ensure the active layer exists
        if self._active_layer_name not in self._layer_groups:
             self.logger.error(f"Cannot finalize polyline: Active layer '{self._active_layer_name}' not found. Defaulting to first layer.")
             # Fallback to the first available layer
             if self._layer_names:
                 self._active_layer_name = self._layer_names[0]
             else: # Should not happen if _init_layers worked
                  self._cancel_current_polyline()
                  return

        path = QPainterPath()
        path.moveTo(self._current_polyline_points[0])
        for point in self._current_polyline_points[1:]:
            path.lineTo(point)

        polyline_item = QGraphicsPathItem(path)
        polyline_item.setPen(self._finalized_polyline_pen)
        # ZValue relative to the group? Set to 0 for now.
        # polyline_item.setZValue(0.5)
        polyline_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        polyline_item.setFlag(QGraphicsItem.ItemIsMovable, True)

        # Add the item to the *active layer group*
        self._layer_groups[self._active_layer_name].addToGroup(polyline_item)

        final_points = list(self._current_polyline_points)
        final_layer = self._active_layer_name
        self.logger.info(f"Polyline finalized with {len(final_points)} vertices on layer '{final_layer}'.")

        self._reset_drawing_state()

        # Emit signal with the finalized points AND layer name
        self.polyline_finalized.emit(final_points, final_layer)
        # Note: _finalized_polyline_items list is removed, item is now owned by the group

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
        """Removes all permanently drawn (finalized) polylines from all layers."""
        self.logger.debug(f"Clearing finalized polyline items from all layers.")
        count = 0
        for layer_name, group in self._layer_groups.items():
            items_in_group = group.childItems()
            count += len(items_in_group)
            for item in items_in_group:
                # Items are owned by the group, removing from group removes from scene
                group.removeFromGroup(item)
                # Explicitly delete item to be safe? Usually handled by Qt ownership
                # item.deleteLater()
        self.logger.debug(f"Cleared {count} items.")

    def load_polylines(self, polylines_data: List[List[Tuple[float, float]]]):
        """
        Clears existing finalized polylines and loads new ones from data.
        NOTE: This version loads all lines into the DEFAULT layer, as layer
        information is not yet saved/loaded in the project file.

        Args:
            polylines_data: A list where each item is a list of (x, y) tuples representing a polyline.
        """
        self.clear_finalized_polylines()

        # TODO: Update this when project save/load includes layer info per polyline
        # For now, load all into the first default layer
        target_layer_name = self._layer_names[0] if self._layer_names else "Default"
        if target_layer_name not in self._layer_groups:
             self.logger.error(f"Cannot load polylines: Default layer '{target_layer_name}' group not found.")
             return

        self.logger.warning(f"Loading {len(polylines_data)} polylines into default layer '{target_layer_name}' (Layer association not loaded).")
        target_group = self._layer_groups[target_layer_name]

        for poly_points in polylines_data:
            if len(poly_points) >= 2:
                try:
                    path = QPainterPath()
                    start_point = QPointF(poly_points[0][0], poly_points[0][1])
                    path.moveTo(start_point)
                    for point_tuple in poly_points[1:]:
                        path.lineTo(QPointF(point_tuple[0], point_tuple[1]))

                    polyline_item = QGraphicsPathItem(path)
                    polyline_item.setPen(self._finalized_polyline_pen)
                    polyline_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                    polyline_item.setFlag(QGraphicsItem.ItemIsMovable, True)
                    # Add item to the target group instead of directly to scene
                    target_group.addToGroup(polyline_item)
                except Exception as e:
                    self.logger.error(f"Error creating QGraphicsPathItem for loaded polyline: {e}", exc_info=True)
            else:
                 self.logger.warning(f"Skipping loaded polyline with less than 2 points: {poly_points}") 