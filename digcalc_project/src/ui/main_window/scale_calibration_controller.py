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

        dlg = ScaleCalibrationDialog(
            parent=mw,
            scene=mw.visualization_panel.scene_2d,
            initial_scale=project.scale,
            pdf_service=mw.pdf_service,
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
            new_scale_data = dlg.get_scale()
            if new_scale_data:
                new_scale = ProjectScale(**new_scale_data)
                project.set_scale(new_scale)
                logger.info(f"Project scale updated to: {new_scale}")
                mw.statusBar().showMessage("Scale updated successfully.", 3000)
            else:
                logger.warning("Scale dialog accepted, but no scale data was returned.")
        else:
            logger.info("Scale calibration was cancelled.")

        mw.ui_state.update_scale_pill()
        mw.ui_state.update_ui_for_project(project) 