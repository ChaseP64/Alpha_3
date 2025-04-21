#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Controller Module for DigCalc.

Handles project lifecycle management (new, open, save, close)
and maintains the current project state.
"""

import logging
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

# Local imports (use relative paths if within the same package structure)
from ..models.project import Project
from ..models.serializers import ProjectSerializer, ProjectLoadError

# Use TYPE_CHECKING to avoid circular imports with MainWindow
if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)

class ProjectController:
    """
    Manages the lifecycle and state of the DigCalc project.

    Acts as the intermediary between the UI (MainWindow) and the
    Project data model for operations like new, open, save.
    """
    def __init__(self, main_window: 'MainWindow'):
        """
        Initialize the ProjectController.

        Args:
            main_window: The main application window instance.
        """
        self.main_window = main_window
        self.current_project: Optional[Project] = None
        self._serializer = ProjectSerializer()
        self.logger = logging.getLogger(__name__)
        # --- Create default project object but don't trigger UI update yet ---
        default_project = Project(name="Untitled Project")
        self.current_project = default_project
        self.logger.info("ProjectController initialized with default project object.")
        # self._create_default_project() # Moved logic here, removed method call

    # --------------------------------------------------------------------------
    # Project State Management
    # --------------------------------------------------------------------------

    def _update_project(self, project: Optional[Project]):
        """
        Sets the current project and updates the UI accordingly.

        Args:
            project: The project to set as current, or None.
        """
        self.logger.info(f"Setting current project to: {project.name if project else 'None'}")
        self.current_project = project
        # Trigger UI updates in MainWindow through its methods
        self.main_window._update_ui_for_project(self.current_project)


    def get_current_project(self) -> Optional[Project]:
         """Returns the currently active project."""
         return self.current_project

    # --------------------------------------------------------------------------
    # Project Actions (Slots for MainWindow signals)
    # --------------------------------------------------------------------------

    def on_new_project(self):
        """Handles the 'New Project' action."""
        self.logger.debug("New Project action triggered.")
        if self._confirm_close_project():
            # --- Re-implement default project creation here ---
            self.logger.info("Creating a new default project for New action.")
            default_project = Project(name="Untitled Project")
            self._update_project(default_project)
            # --- End Re-implement ---

    def on_open_project(self):
        """Handles the 'Open Project' action."""
        self.logger.debug("Open Project action triggered.")
        if not self._confirm_close_project():
            return

        # Use QFileDialog to select a project file
        filename, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Open Project",
            "", # Start directory (can be improved)
            "DigCalc Projects (*.digcalc);;All Files (*)"
        )

        if filename:
            self.logger.info(f"Attempting to open project file: {filename}")
            try:
                project = self._serializer.load(filename)
                self._update_project(project)
                self.current_project.is_dirty = False # Mark as clean after load
                self.main_window.statusBar().showMessage(f"Project '{project.name}' loaded.", 5000)
            except ProjectLoadError as e:
                self.logger.error(f"Failed to load project: {e}", exc_info=True)
                QMessageBox.critical(
                    self.main_window,
                    "Error Loading Project",
                    f"""Could not load project file:
{filename}

Error: {e}"""
                )
                # --- Re-implement default project creation on error ---
                self.logger.info("Creating default project after failed load.")
                default_project = Project(name="Untitled Project")
                self._update_project(default_project)
                # --- End Re-implement ---
            except Exception as e: # Catch unexpected errors during load
                 self.logger.exception(f"Unexpected error loading project {filename}: {e}")
                 QMessageBox.critical(
                     self.main_window,
                     "Error Loading Project",
                     f"""An unexpected error occurred while loading:
{filename}

Error: {e}"""
                 )
                 # --- Re-implement default project creation on error ---
                 self.logger.info("Creating default project after failed load.")
                 default_project = Project(name="Untitled Project")
                 self._update_project(default_project)
                 # --- End Re-implement ---

    def on_save_project(self, save_as=False) -> bool:
        """
        Handles the 'Save Project' and 'Save Project As...' actions.

        Args:
            save_as: If True, forces the 'Save As' dialog even if a path exists.

        Returns:
            bool: True if the project was saved successfully or save was cancelled,
                  False if the save operation failed or was aborted by the user
                  in a critical way (e.g., closing dialog without saving when required).
        """
        self.logger.debug(f"Save Project action triggered (save_as={save_as}).")
        if not self.current_project:
            self.logger.warning("Save requested but no current project exists.")
            return True # Nothing to save

        project_path = self.current_project.filepath

        if save_as or not project_path:
            # Prompt for a filename using QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Save Project As",
                project_path or f"{self.current_project.name}.digcalc", # Suggest name/path
                "DigCalc Projects (*.digcalc);;All Files (*)"
            )
            if not filename:
                self.logger.info("Save As cancelled by user.")
                return False # User cancelled the Save As dialog
            project_path = filename
            self.current_project.filepath = project_path
            # Update project name based on filename if it was 'Untitled'
            if self.current_project.name == "Untitled Project":
                 self.current_project.name = Path(project_path).stem
                 self.main_window._update_window_title() # Update window title

        self.logger.info(f"Attempting to save project to: {project_path}")
        try:
            self._serializer.save(self.current_project, project_path)
            self.current_project.is_dirty = False # Mark as clean
            self.main_window.statusBar().showMessage(f"Project '{self.current_project.name}' saved.", 5000)
            self.logger.info("Project saved successfully.")
            self.main_window._update_window_title() # Ensure title reflects saved state
            return True
        except Exception as e: # Catch-all for serialization errors
            self.logger.exception(f"Failed to save project to {project_path}: {e}")
            QMessageBox.critical(
                self.main_window,
                "Error Saving Project",
                f"""Could not save project file:
{project_path}

Error: {e}"""
            )
            return False # Save failed

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------

    def _should_save_project(self) -> bool:
        """
        Checks if the current project is dirty (has unsaved changes).

        Returns:
            bool: True if the project has unsaved changes, False otherwise.
        """
        return self.current_project is not None and self.current_project.is_dirty

    def _confirm_close_project(self) -> bool:
        """
        Checks if the current project needs saving and prompts the user if necessary.
        Called before opening a new project or closing the application.

        Returns:
            bool: True if it's safe to proceed (project saved or user chose not to),
                  False if the user cancelled the operation.
        """
        if not self._should_save_project():
            return True # No unsaved changes, safe to proceed

        self.logger.debug("Project has unsaved changes. Prompting user.")
        reply = QMessageBox.question(
            self.main_window,
            "Unsaved Changes",
            f"""Project '{self.current_project.name}' has unsaved changes.
Do you want to save them?""",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save # Default button
        )

        if reply == QMessageBox.Save:
            self.logger.debug("User chose to Save.")
            return self.on_save_project() # Returns True if save successful/cancelled, False if failed critically
        elif reply == QMessageBox.Discard:
            self.logger.debug("User chose to Discard changes.")
            return True # Safe to proceed without saving
        else: # reply == QMessageBox.Cancel
            self.logger.debug("User chose to Cancel.")
            return False # Operation cancelled, do not proceed

    def mark_dirty(self):
        """Marks the current project as having unsaved changes."""
        if self.current_project and not self.current_project.is_dirty:
            self.logger.debug("Marking project as dirty.")
            self.current_project.is_dirty = True
            self.main_window._update_window_title() # Reflect dirty state in title 