"""
Controller for handling scale calibration logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QDialog

from ...models.project_scale import ProjectScale
from ..dialogs.scale_calibration_dialog import ScaleCalibrationDialog

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class ScaleCalibrationController(QObject):
    """Manages the scale calibration workflow."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window

    @Slot()
    def on_scale_calibration(self):
        """Open the scale calibration dialog."""
        mw = self.main_window
        project = mw.project_controller.get_current_project()
        if not project:
            logger.warning("Attempted to open scale dialog with no active project.")
            return

        # Current dialog signature: (parent, project, scene, page_pixmap=None)
        page_pixmap = None
        try:
            # Prefer the live background pixmap so user sees same page context
            page_pixmap = (
                mw.visualization_panel._pdf_bg_item.pixmap()  # type: ignore[attr-defined]
                if getattr(mw.visualization_panel, "_pdf_bg_item", None) is not None
                else None
            )
        except Exception:
            pass  # Fallback to None when view not ready / attribute absent

        dlg = ScaleCalibrationDialog(
            parent=mw,
            project=project,
            scene=mw.visualization_panel.scene_2d,  # type: ignore[attr-defined]
            page_pixmap=page_pixmap,
        )
        dlg.finished.connect(lambda result: self._on_scale_dialog_done(dlg, result))
        dlg.exec()

    def _on_scale_dialog_done(self, dlg: ScaleCalibrationDialog, result: int):
        """Handle the result of the scale calibration dialog."""
        mw = self.main_window
        project = mw.project_controller.get_current_project()
        if not project:
            return

        if result == QDialog.Accepted:
            new_scale = dlg.result_scale()
            if new_scale is not None:
                project.scale = new_scale
                logger.info("Project scale updated to: %s", new_scale)
                try:
                    mw.statusBar().showMessage("Scale updated successfully.", 3000)
                except Exception:
                    pass
            else:
                logger.warning("Scale dialog accepted, but no scale was calculated.")
        else:
            logger.info("Scale calibration was cancelled.")

        mw.ui_state.update_scale_pill()
        mw.ui_state.update_ui_for_project(project)

    # ------------------------------------------------------------------
    # Public facade expected by MainWindow --------------------------------
    # ------------------------------------------------------------------
    def open_dialog(self):  # noqa: D401 – compatibility shim
        """Qt slot wrapper kept for legacy callers.

        Earlier versions of :pyclass:`MainWindow` looked for an *open_dialog*
        attribute on *scale_calibration_controller*.  The new implementation
        exposes :py:meth:`on_scale_calibration` instead, so we alias the call
        here to remain backward-compatible without touching *main_window.py*.
        """
        self.on_scale_calibration()
