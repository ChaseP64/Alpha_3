from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QStatusBar

if TYPE_CHECKING:
    from .main_window import MainWindow


class StatusBarManager:
    """
    Owns the QStatusBar, the coloured 'scale-pill', and transient
    message helpers so the rest of the app never touches the bar directly.
    """

    def __init__(self, mw: "MainWindow") -> None:
        self.mw = mw
        self.bar: QStatusBar = QStatusBar(mw)
        mw.setStatusBar(self.bar)

        # --- widgets ------------
        self._scale_pill = QLabel("No Scale", self.bar)
        self._scale_pill.setObjectName("scalePill")
        self._scale_pill.setAlignment(Qt.AlignCenter)
        self._scale_pill.setStyleSheet(
            "QLabel#scalePill {"
            " border-radius:8px; padding:2px 6px;"
            " background:#AAA; color:white; }"
        )
        self.bar.addPermanentWidget(self._scale_pill)

        # transient message timer
        self._msg_timer = QTimer(self.bar)
        self._msg_timer.setInterval(4000)
        self._msg_timer.setSingleShot(True)
        self._msg_timer.timeout.connect(self.bar.clearMessage)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def show_message(self, text: str, timeout_ms: int = 4000) -> None:
        self.bar.showMessage(text, timeout_ms)
        # The QStatusBar itself has a timer, so we don't need our own for this.

    def set_scale_state(self, *, value: str | None, valid: bool) -> None:
        """
        Update the pill text & colour.

        value = e.g. "50 ft/in"  |  None → 'No Scale'
        valid = False if DPI mismatch / invalidated
        """
        if value:
            self._scale_pill.setText(value)
        else:
            self._scale_pill.setText("No Scale")

        if not value:
            colour = "#AAA"  # grey
        elif valid:
            colour = "#4CAF50"  # green
        else:
            colour = "#F44336"  # red

        self._scale_pill.setStyleSheet(
            f"QLabel#scalePill {{border-radius:8px; padding:2px 6px;"
            f"background:{colour}; color:white; }}"
        )

    # Convenience hook used by UIStateManager -------------------------- #
    def update_from_project(self) -> None:
        project = self.mw.project_controller.get_current_project()
        if not project or not project.scale:
            self.set_scale_state(value=None, valid=False)
        else:
            scale = project.scale
            txt = f"{scale.world_per_in:g} {scale.world_units}/in"

            current_dpi = (
                self.mw.visualization_panel.get_current_dpi()
                if self.mw.visualization_panel
                else 150
            )

            dpi_ok = abs(scale.render_dpi_at_cal - current_dpi) < 0.5
            self.set_scale_state(value=txt, valid=dpi_ok)
