"""Clickable QLabel helper.

A QLabel that emits a *clicked* Qt signal when the user releases the
left mouse button.  Extracted from *main_window.py* so it can be reused
across the UI without bloating the main-window module.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel

__all__ = ["ClickableLabel"]


class ClickableLabel(QLabel):
    """A QLabel that behaves like a hyperlink/button."""

    clicked = Signal()

    def __init__(self, parent=None):  # noqa: D401 – trivial init
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    # ------------------------------------------------------------------
    # Qt events
    # ------------------------------------------------------------------
    def mouseReleaseEvent(self, event):  # noqa: D401 – Qt override
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
