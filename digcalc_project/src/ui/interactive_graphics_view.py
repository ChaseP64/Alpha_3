# digcalc_project/src/ui/interactive_graphics_view.py

import logging
from typing import Optional

from PySide6.QtCore import Qt, QPoint # Corrected import for QPoint
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QWidget

logger = logging.getLogger(__name__)

class InteractiveGraphicsView(QGraphicsView):
    """
    A custom QGraphicsView that adds interactive zooming with Ctrl+Wheel
    and panning with the middle mouse button drag or Alt + Left Mouse drag.
    """
    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None):
        super().__init__(scene, parent)

        # Set transformation anchor for zooming centered on mouse
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # Start with no drag mode; middle mouse/alt+left will activate manual panning
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.logger = logger # Use module logger
        self._is_manual_panning = False # Flag for middle/alt+left panning
        self._last_pan_pos: Optional[QPoint] = None

    def wheelEvent(self, event: QWheelEvent):
        """Handles mouse wheel events for zooming."""
        if event.modifiers() == Qt.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1.0 / zoom_in_factor

            # Save the scene pos at the cursor
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
            # If not panning manually, pass the event to the base class AND the scene
            # This ensures scene can handle clicks for tracing/selection
            super().mousePressEvent(event)
            # --- Pass event to scene only if not accepted by base view --- 
            if not event.isAccepted() and self.scene():
                 # Re-wrap the event for the scene context if necessary?
                 # Usually direct passing works, but scene might expect QGraphicsSceneMouseEvent
                 # For now, assume direct pass is okay or scene handles QMouseEvent.
                 # If scene clicks stop working, this might need adjustment.
                 pass # Let base class handle it fully for now


    def mouseMoveEvent(self, event: QMouseEvent):
        """Handles mouse move for manual panning or passes to base class."""
        if self._is_manual_panning and self._last_pan_pos is not None:
            delta = event.pos() - self._last_pan_pos
            # Scroll the view\\'s scroll bars
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._last_pan_pos = event.pos() # Update position
            event.accept()
        else:
            # Let the base class handle move events, e.g., for ScrollHandDrag
            super().mouseMoveEvent(event)
            # Also pass to scene if not accepted? Usually not needed for move.


    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handles mouse release events to stop manual panning or passes to base class."""
        # Check using event.button() which triggered the release
        is_middle_release = event.button() == Qt.MiddleButton
        # Alt modifier might not be present on release, so check _is_manual_panning flag
        was_alt_panning = self._is_manual_panning and not is_middle_release
        
        if self._is_manual_panning and (is_middle_release or was_alt_panning):
            self.logger.debug("Manual pan finished.")
            self._is_manual_panning = False
            # Check current dragMode to set appropriate cursor
            cursor = Qt.ArrowCursor # Default
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                 cursor = Qt.OpenHandCursor
            elif self.dragMode() == QGraphicsView.DragMode.NoDrag:
                 # Check if tracing is active (cursor is CrossCursor)
                 if self.viewport().cursor().shape() == Qt.CrossCursor:
                      cursor = Qt.CrossCursor
            self.setCursor(cursor)
            self._last_pan_pos = None
            event.accept()
        else:
            # Let the base class handle release
            super().mouseReleaseEvent(event)
            # Also pass to scene if not accepted by base
            # This allows scene to handle selection release
            if not event.isAccepted() and self.scene():
                 # Re-wrap event if needed, similar to mousePressEvent comment
                 pass # Let base class handle it fully for now 