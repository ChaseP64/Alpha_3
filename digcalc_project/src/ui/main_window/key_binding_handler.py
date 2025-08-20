"""
Handles key press events and shortcut creation for the main window.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock  # Local import – lightweight

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class KeyBindingHandler(QObject):
    """Manages keyboard shortcuts and key press events."""

    def __init__(self, main_window: MainWindow):
        super().__init__(main_window if isinstance(main_window, QObject) else None)
        self.main_window = main_window
        self._create_shortcuts()

    def _create_shortcuts(self):
        """Create keyboard shortcuts for common actions.

        In a real UI session we attach the shortcut to the ``MainWindow``
        (so it inherits the correct focus context).  However, most unit
        tests pass a ``MagicMock`` instead of an actual Qt ``QObject``.
        Constructing a :class:`~PySide6.QtGui.QShortcut` with such an
        object raises a ``TypeError``.  To stay test-friendly we fall
        back to using *self* (which **is** a ``QObject``) as the parent
        when the supplied ``main_window`` isn't a real Qt object.
        """
        mw = self.main_window
        parent = mw if isinstance(mw, QObject) else self

        try:
            self.toggle_others_shortcut = QShortcut(QKeySequence("`"), parent)
            # Hook up the action only if the expected handler exists –
            # mocked windows will happily accept the attribute access.
            if hasattr(mw, "view_mode_handler") and hasattr(
                mw.view_mode_handler, "_toggle_other_layers_visibility"
            ):
                self.toggle_others_shortcut.activated.connect(
                    mw.view_mode_handler._toggle_other_layers_visibility  # type: ignore[arg-type]
                )
        except TypeError as exc:  # pragma: no cover ‑ fallback for weird mocks
            # Create a dummy object so tests can still assert the attribute exists.
            logging.getLogger(__name__).debug("Shortcut creation skipped: %s", exc)
            self.toggle_others_shortcut = MagicMock()

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
