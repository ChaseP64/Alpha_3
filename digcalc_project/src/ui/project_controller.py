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

# --- Add QObject and Signal ---
from PySide6.QtCore import QObject, Signal
# --- End Add ---
from PySide6.QtWidgets import QFileDialog, QMessageBox

# Local imports (use relative paths if within the same package structure)
from ..models.project import Project
from ..models.serializers import ProjectSerializer, ProjectLoadError
from ..models.surface import Surface
from ..core.geometry.surface_builder import lowest_surface

# Use TYPE_CHECKING to avoid circular imports with MainWindow
if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)

# --- Inherit from QObject ---
class ProjectController(QObject):
# --- End Inherit ---
    """
    Manages the lifecycle and state of the DigCalc project.

    Acts as the intermediary between the UI (MainWindow) and the
    Project data model for operations like new, open, save.

    Signals:
        project_loaded (Project): Emitted when a new project is loaded or created.
        project_closed (): Emitted before a project is closed or replaced.
        project_modified (): Emitted when the project's dirty status changes.
        surfaces_rebuilt (): Emitted after surfaces are rebuilt so views can refresh
    """
    # --- Define Signals ---
    project_loaded = Signal(Project)
    project_closed = Signal()
    project_modified = Signal()
    surfaces_rebuilt = Signal()  # Emitted after surfaces are rebuilt so views can refresh
    surfacesChanged = Signal()   # Emitted when lowest/composite surfaces refresh
    # --- End Define ---

    def __init__(self, main_window: 'MainWindow'):
        """
        Initialize the ProjectController.

        Args:
            main_window: The main application window instance.
        """
        # --- Call super().__init__() ---
        super().__init__()
        # --- End Call ---
        self.main_window = main_window
        self.current_project: Optional[Project] = None
        self._serializer = ProjectSerializer()
        self.logger = logging.getLogger(__name__)
        # --- Create default project object but don't trigger UI update yet ---
        default_project = Project(name="Untitled Project")
        self.current_project = default_project
        self.logger.info("ProjectController initialized with default project object.")
        # self._create_default_project() # Moved logic here, removed method call
        # --- Lowest composite surface holder ---
        self._lowest_surface: Surface | None = None

    # --------------------------------------------------------------------------
    # Project State Management
    # --------------------------------------------------------------------------

    def _update_project(self, project: Optional[Project]):
        """
        Sets the current project and updates the UI accordingly.
        Emits project_loaded signal.

        Args:
            project: The project to set as current, or None.
        """
        self.logger.info(f"Setting current project to: {project.name if project else 'None'}")
        self.current_project = project
        # Trigger UI updates in MainWindow through its methods
        # self.main_window._update_ui_for_project(self.current_project) # Let signal handle this
        # --- Emit project_loaded ---
        if self.current_project is not None:
            self.project_loaded.emit(self.current_project)
        else:
            # Optionally handle the case where project becomes None,
            # though project_closed should cover this transition.
            pass
        # --- End Emit ---


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
            # --- Emit project_closed ---
            self.project_closed.emit()
            # --- End Emit ---
            # --- Re-implement default project creation here ---
            self.logger.info("Creating a new default project for New action.")
            default_project = Project(name="Untitled Project")
            self._update_project(default_project) # This will emit project_loaded
            # --- End Re-implement ---

    def on_open_project(self):
        """Handles the 'Open Project' action."""
        self.logger.debug("Open Project action triggered.")
        if not self._confirm_close_project():
            return

        # --- Emit project_closed ---
        self.project_closed.emit()
        # --- End Emit ---

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
                self._update_project(project) # This will emit project_loaded
                self.current_project.is_dirty = False # Mark as clean after load
                # self.main_window.statusBar().showMessage(f"Project '{project.name}' loaded.", 5000) # Handled by MainWindow via signal
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
                self._update_project(default_project) # This will emit project_loaded
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
                 self._update_project(default_project) # This will emit project_loaded
                 # --- End Re-implement ---

    def on_save_project(self, save_as=False) -> bool:
        """
        Handles the 'Save Project' and 'Save Project As...' actions.
        Emits project_modified if the dirty state changes to False.

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

        was_dirty = self.current_project.is_dirty # Check state before potential save
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
                 # self.main_window._update_window_title() # Let signal handle this
                 # Emit modified because name changed (implies dirty state change needed too)
                 if not was_dirty: # If it wasn't dirty before, name change makes it so implicitly
                     self.current_project.is_dirty = True # Mark dirty before save
                     self.project_modified.emit()

        self.logger.info(f"Attempting to save project to: {project_path}")
        try:
            self._serializer.save(self.current_project, project_path)
            save_successful = True
        except Exception as e: # Catch-all for serialization errors
            save_successful = False
            self.logger.exception(f"Failed to save project to {project_path}: {e}")
            QMessageBox.critical(
                self.main_window,
                "Error Saving Project",
                f"""Could not save project file:
{project_path}

Error: {e}"""
            )

        if save_successful:
            if was_dirty: # Only change state and emit if it *was* dirty
                self.current_project.is_dirty = False # Mark as clean
                # --- Emit project_modified ---
                self.project_modified.emit()
                # --- End Emit ---
            # self.main_window.statusBar().showMessage(f"Project '{self.current_project.name}' saved.", 5000) # Let MainWindow handle status
            self.logger.info("Project saved successfully.")
            # self.main_window._update_window_title() # Let signal handle this
            return True
        else:
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

    # --- Renamed to set_project_modified and emit signal ---
    def set_project_modified(self, modified: bool = True):
        """Marks the current project's dirty state and emits project_modified if it changed."""
        if self.current_project and self.current_project.is_dirty != modified:
            self.logger.debug(f"Setting project dirty state to: {modified}")
            self.current_project.is_dirty = modified
            # --- Emit project_modified ---
            self.project_modified.emit()
            # --- End Emit ---
            # self.main_window._update_window_title() # Let signal handle this
    # --- End Rename ---

    # --------------------------------------------------------------------------
    # Surface Rebuild Helpers
    # --------------------------------------------------------------------------
    def rebuild_surfaces(self):
        """Rebuild all derived surfaces based on current traced polylines.

        This method is called when tracing data changes (e.g., pad elevations
        added).  It will:

        1. Clear the MainWindow's cached cut/fill grids.
        2. Iterate over existing surfaces and rebuild them using SurfaceBuilder
           if their source layer still has valid polylines with elevation.
        3. Emit the *surfaces_rebuilt* signal so that views (2-D/3-D) can refresh.
        """
        from digcalc_project.src.core.geometry.surface_builder import SurfaceBuilder, SurfaceBuilderError

        if not self.current_project:
            self.logger.warning("rebuild_surfaces called but there is no active project.")
            return

        project = self.current_project

        # 1. Clear cached dz/cut-fill state in the MainWindow (if attribute exists)
        if hasattr(self.main_window, '_clear_cutfill_state'):
            self.main_window._clear_cutfill_state()

        rebuilt_count = 0
        for surf_name, surf in list(project.surfaces.items()):
            src_layer = getattr(surf, 'source_layer_name', None)
            if not src_layer:
                continue  # Skip surfaces without a source layer

            polylines = project.traced_polylines.get(src_layer, [])
            valid_polys = [p for p in polylines if isinstance(p, dict) and p.get('elevation') is not None]
            if not valid_polys:
                self.logger.info("Layer '%s' has no valid polylines with elevation for rebuilding '%s'.", src_layer, surf_name)
                continue

            try:
                new_surf = SurfaceBuilder.build_from_polylines(src_layer, valid_polys, project.layer_revisions.get(src_layer, 0))
                new_surf.name = surf_name  # Keep original name
                new_surf.source_layer_name = src_layer
                project.surfaces[surf_name] = new_surf
                rebuilt_count += 1

                # Update visualization if possible
                if hasattr(self.main_window, 'visualization_panel') and \
                   hasattr(self.main_window.visualization_panel, 'update_surface_mesh'):
                    self.main_window.visualization_panel.update_surface_mesh(new_surf)
            except SurfaceBuilderError as e:
                self.logger.error("Failed to rebuild surface '%s': %s", surf_name, e)
            except Exception as e:  # Catch-all to avoid crashing the UI loop
                self.logger.exception("Unexpected error rebuilding surface '%s': %s", surf_name, e)

        if rebuilt_count:
            self.logger.info("Rebuilt %d surface(s) successfully.", rebuilt_count)

            # --- Ensure lowest composite surface stays in sync ---
            self._rebuild_lowest()

            # Mark project modified and emit events
            self.set_project_modified(True)

            # Emit signal for external listeners (views/UI) to refresh
            self.surfaces_rebuilt.emit()
        else:
            self.logger.info("No surfaces required rebuilding.")

    # ----------------------------------------------------------------------
    # Lowest composite surface helpers
    # ----------------------------------------------------------------------
    def lowest_surface(self) -> Optional[Surface]:
        """Return the current lowest-elevation composite surface if available."""
        return self._lowest_surface

    def _rebuild_lowest(self):
        """(Re)compute the *Lowest* composite surface.

        This function requires both a *design* and *existing* surface to be
        present on the current project.  When generated, the surface is added
        to ``project.surfaces`` using the key ``"Lowest"`` so downstream UI
        elements can find it by name.
        """
        if (self.current_project
                and self.current_project.get_surface("Design Surface")
                and self.current_project.get_surface("Existing Surface")):
            design = self.current_project.get_surface("Design Surface")
            existing = self.current_project.get_surface("Existing Surface")
            try:
                self._lowest_surface = lowest_surface(design, existing)  # type: ignore[arg-type]
                # Store/update on project for persistence/visualisation
                self.current_project.surfaces[self._lowest_surface.name] = self._lowest_surface
                self.surfacesChanged.emit()
            except Exception as err:
                self.logger.error("Failed to build lowest surface: %s", err, exc_info=True) 