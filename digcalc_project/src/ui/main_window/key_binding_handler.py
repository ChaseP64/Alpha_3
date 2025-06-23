"""
Handles key press events and shortcut creation for the main window.
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtGui import QKeySequence, QKeyEvent, QShortcut
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class KeyBindingHandler(QObject):
    """Manages keyboard shortcuts and key press events."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window
        self._create_shortcuts()

    def _create_shortcuts(self):
        """Create keyboard shortcuts for common actions."""
        mw = self.main_window
        # Shortcut for toggling other layers
        self.toggle_others_shortcut = QShortcut(QKeySequence("`"), mw)
        self.toggle_others_shortcut.activated.connect(mw.view_mode_handler._toggle_other_layers_visibility)

    def handle_key_press(self, event: QKeyEvent):
        """
        Centralized handler for key press events, delegating to other handlers.
        """
        key = event.key()
        mw = self.main_window

        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            if mw.polyline_handler and mw.polyline_handler._selected_scene_item:
                logger.debug("Delete key pressed, delegating to PolylineInteractionHandler.")
                mw.polyline_handler._delete_selected_polyline()
                event.accept()
                return

        # Fallback to default processing if not handled
        event.ignore() 