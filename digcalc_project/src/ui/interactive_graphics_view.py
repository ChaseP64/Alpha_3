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
    centered on the mouse cursor, and panning with the middle mouse button drag.
    """
    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None):
        super().__init__(scene, parent)

        # Settings for zoom and pan behavior
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag) # Default drag mode

        self.logger = logger # Use module logger

        # Panning state variables
        self._panning: bool = False
        self._last_pan_pos: QPoint | None = None

    def wheelEvent(self, event: QWheelEvent):
        """Handles mouse wheel events for zooming centered on the cursor."""
        # Check if Ctrl is pressed for zooming (optional, can remove for always zoom)
        # if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
        zoom_in_factor = 1.25 # Zoom in step
        zoom_out_factor = 1.0 / zoom_in_factor # Zoom out step

        # Save the scene pos at the cursor before zoom
        old_pos = self.mapToScene(event.position().toPoint())

        # Determine zoom factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
            self.logger.debug("Zooming in")
        else:
            zoom_factor = zoom_out_factor
            self.logger.debug("Zooming out")

        # Apply scaling
        self.scale(zoom_factor, zoom_factor)

        # Get the new scene position under the cursor after zoom
        new_pos = self.mapToScene(event.position().toPoint())

        # Move scene to keep cursor positioned over the same scene point
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

        event.accept() # Indicate we handled this event
        # else:
        #     # Allow default scroll behavior if Ctrl is not pressed
        #     super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handles mouse press events to initiate panning with the middle button."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self.logger.debug("Middle mouse pressed: Initiating pan.")
            self._panning = True
            # Use globalPos() if screen coordinates are needed, else pos() for widget coords
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            self.logger.debug("Non-middle mouse press. Passing to base class.")
            # Ensure the base class handles other buttons (e.g., left click for selection)
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handles mouse move events for panning when the middle button is held down."""
        if self._panning and self._last_pan_pos is not None:
            # Calculate the difference in position
            delta: QPoint = event.pos() - self._last_pan_pos

            # Adjust the scroll bars based on the delta
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

            # Update the last position for the next move event
            self._last_pan_pos = event.pos()
            event.accept()
        else:
            # Pass other move events to the base class
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handles mouse release events to stop panning when the middle button is released."""
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self.logger.debug("Middle mouse released: Stopping pan.")
            self._panning = False
            self._last_pan_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor) # Reset cursor to default
            event.accept()
        else:
            # Pass other release events to the base class
            super().mouseReleaseEvent(event) 