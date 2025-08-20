"""
This module contains the ProjectFileController class.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ...models.project import Project
from ...models.serializers import ProjectLoadError, ProjectSerializer

if TYPE_CHECKING:
    from .main_window import MainWindow


class ProjectFileController:
    """Handles project file operations like new, open, save."""

    def __init__(self, mw: "MainWindow"):
        """
        Initializes the ProjectFileController.

        Args:
            mw (MainWindow): The main window instance.
        """
        self.mw = mw
        self.logger = logging.getLogger(__name__)
        self._serializer = ProjectSerializer()

    def on_new_project(self):
        """Handles the 'New Project' action."""
        self.logger.debug("New Project action triggered.")
        if self.mw.project_controller._confirm_close_project():
            self.mw.project_controller.project_closed.emit()
            self.logger.info("Creating a new default project for New action.")
            default_project = Project(name="Untitled Project")
            self.mw.project_controller._update_project(default_project)

    def on_open_project(self):
        """Handles the 'Open Project' action."""
        self.logger.debug("Open Project action triggered.")
        if not self.mw.project_controller._confirm_close_project():
            return

        self.mw.project_controller.project_closed.emit()

        filename, _ = QFileDialog.getOpenFileName(
            self.mw,
            "Open Project",
            "",
            "DigCalc Projects (*.digcalc);;All Files (*)",
        )

        if filename:
            self._open_project_from_path(filename)

    def _open_project_from_path(self, filename: str):
        """Opens a project from a given file path."""
        self.logger.info(f"Attempting to open project file: {filename}")
        try:
            project = self._serializer.load(filename)
            self.mw.project_controller._update_project(project)
            if self.mw.project_controller.current_project:
                self.mw.project_controller.current_project.is_dirty = False
        except ProjectLoadError as e:
            self.logger.error(f"Failed to load project: {e}", exc_info=True)
            QMessageBox.critical(
                self.mw,
                "Error Loading Project",
                f"Could not load project file:\n{filename}\n\nError: {e}",
            )
            self._create_default_project_after_error()
        except Exception as e:
            self.logger.exception(f"Unexpected error loading project {filename}: {e}")
            QMessageBox.critical(
                self.mw,
                "Error Loading Project",
                f"An unexpected error occurred while loading:\n{filename}\n\nError: {e}",
            )
            self._create_default_project_after_error()

    def _create_default_project_after_error(self):
        """Creates a default project after a file load error."""
        self.logger.info("Creating default project after failed load.")
        default_project = Project(name="Untitled Project")
        self.mw.project_controller._update_project(default_project)

    def on_save_project(self, save_as=False) -> bool:
        """Handles the 'Save Project' and 'Save Project As...' actions."""
        self.logger.debug(f"Save Project action triggered (save_as={save_as}).")
        project = self.mw.project_controller.get_current_project()
        if not project:
            self.logger.warning("Save requested but no current project exists.")
            return True

        was_dirty = project.is_dirty
        project_path = project.filepath

        if save_as or not project_path:
            filename, _ = self._save_file_dialog(project)
            if not filename:
                self.logger.info("Save As cancelled by user.")
                return False
            project_path = filename
            project.filepath = project_path
            if project.name == "Untitled Project":
                project.name = Path(project_path).stem
                if not was_dirty:
                    project.is_dirty = True
                    self.mw.project_controller.project_modified.emit()

        if not project_path:
            return False

        self.logger.info(f"Attempting to save project to: {project_path}")
        try:
            self._serializer.save(project, project_path)
            save_successful = True
        except Exception as e:
            save_successful = False
            self.logger.exception(f"Failed to save project to {project_path}: {e}")
            QMessageBox.critical(
                self.mw,
                "Error Saving Project",
                f"Could not save project file:\n{project_path}\n\nError: {e}",
            )

        if save_successful:
            if was_dirty:
                project.is_dirty = False
                self.mw.project_controller.project_modified.emit()
            self.logger.info("Project saved successfully.")
            return True
        return False

    def _save_file_dialog(self, project: Project) -> tuple[str, str]:
        """Shows the save file dialog and returns the selected filename."""
        project_path = project.filepath
        suggested_name = project_path or f"{project.name}.digcalc"
        return QFileDialog.getSaveFileName(
            self.mw,
            "Save Project As",
            suggested_name,
            "DigCalc Projects (*.digcalc);;All Files (*)",
        )

    def dragEnterEvent(self, event):
        """Handles drag enter events for file drops."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(".digcalc"):
                event.acceptProposedAction()

    def dropEvent(self, event):
        """Handles drop events for file drops."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                filepath = urls[0].toLocalFile()
                if filepath.lower().endswith(".digcalc"):
                    self.logger.info(f"Project file dropped: {filepath}")
                    if self.mw.project_controller._confirm_close_project():
                        self.mw.project_controller.project_closed.emit()
                        self._open_project_from_path(filepath)

    def _update_recent_files(self):
        """Updates the recent files menu."""
        self.logger.info("Updating recent files.")
