#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serialization classes for DigCalc project data.
"""

import logging
import pickle
from typing import Optional
import json

from .project import Project  # Use relative import
from .project_scale import ProjectScale
from .surface import Surface

logger = logging.getLogger(__name__)

class ProjectLoadError(Exception):
    """Custom exception for errors during project loading."""
    pass

class ProjectSerializer:
    """
    Handles saving and loading of the Project object.
    Delegates saving and loading to the Project class methods,
    which handle the actual serialization format (currently JSON).
    """

    def save(self, project: Project, filepath: str):
        """
        Saves the Project object by calling its save method.

        Args:
            project: The Project instance to save.
            filepath: The path to the file where the project should be saved.

        Raises:
            Exception: Any exception raised by Project.save.
        """
        logger.info(f"Delegating save for project '{project.name}' to Project.save({filepath}).")
        try:
            success = project.save(filepath)
            if not success:
                 raise RuntimeError(f"Project.save method returned False for {filepath}.")
            logger.debug(f"Project.save completed for {filepath}.")
        except Exception as e:
            logger.error(f"Error occurred during Project.save for {filepath}: {e}", exc_info=True)
            raise # Re-raise the original exception

    def load(self, filepath: str) -> Project:
        """
        Loads a Project object by calling the Project.load class method.

        Args:
            filepath: The path to the project file to load.

        Returns:
            Project: The loaded Project instance.

        Raises:
            ProjectLoadError: If Project.load fails or returns None.
            Exception: Any other unexpected exception during loading.
        """
        logger.info(f"Delegating load for {filepath} to Project.load.")
        try:
            project = Project.load(filepath)
            
            if project is None:
                logger.error(f"Project.load returned None for file: {filepath}")
                raise ProjectLoadError(f"Failed to load project from {filepath}. File may be invalid, corrupted, or not found.")
            
            logger.debug(f"Project.load successfully returned project '{project.name}' from {filepath}.")
            return project
            
        except FileNotFoundError:
            logger.error(f"Project file not found: {filepath}")
            raise ProjectLoadError(f"Project file not found: {filepath}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {filepath}: {e}", exc_info=True)
            raise ProjectLoadError(f"Failed to load project from {filepath}. Invalid JSON format. Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during Project.load for {filepath}: {e}", exc_info=True)
            raise ProjectLoadError(f"An unexpected error occurred loading {filepath}. Error: {e}")

# ---------------------------------------------------------------------------
# Convenience in-memory (de)serialisers used by unit-tests and API layer.
# They are intentionally *schema-stable* and ignore extraneous keys.
# ---------------------------------------------------------------------------

def _load_surfaces(data: dict | None) -> dict[str, Surface]:
    """Helper to reconstruct *Surface* objects from a mapping."""

    surfaces_dict: dict[str, Surface] = {}
    if not isinstance(data, dict):
        return surfaces_dict

    for name, surf_data in data.items():
        try:
            surfaces_dict[name] = Surface.from_dict(surf_data)
        except Exception as exc:  # pragma: no cover – defensive
            logger.warning("Failed to load surface '%s': %s", name, exc)
    return surfaces_dict

# NOTE: Polyline model is still evolving – keep loader simple / future-proof.
def _load_polylines(data):  # type: ignore[override]
    """Return the raw polylines structure exactly as stored (dict or list).

    The *Project* class owns the heavy lifting of validating and migrating the
    traced-polyline schema, so at this stage we just pass things through.
    """

    return data if data is not None else {}

def to_dict(project: Project) -> dict:
    """Serialise *Project* → `dict` (no file I/O).

    Only a subset of fields is currently required by the API layer and unit
    tests.  This helper deliberately mirrors the schema produced by
    :py:meth:`Project.save`, but it lives here so it can evolve independently
    from on-disk persistence.
    """

    return {
        "name": project.name,
        # ------------------------------------------------------------------
        # Scale (new) – include sub-keys explicitly for clarity
        # ------------------------------------------------------------------
        "scale": (
            {
                "px_per_in": project.scale.px_per_in,
                "world_units": project.scale.world_units,
                "world_per_in": project.scale.world_per_in,
            }
            if project.scale is not None
            else None
        ),
        # Keep other sections minimal for now – can be expanded later.
        "surfaces": {n: s.to_dict() for n, s in project.surfaces.items()},
        "polylines": project._serialisable_polylines(),
    }

def from_dict(data: dict) -> Project:
    """Hydrate a :class:`Project` from an in-memory mapping."""

    # ---------------- Scale (legacy-safe) ------------------------------
    scale_data = data.get("scale")
    scale_obj: ProjectScale | None
    if scale_data is not None:
        try:
            scale_obj = ProjectScale(
                px_per_in=float(scale_data["px_per_in"]),
                world_units=str(scale_data["world_units"]),
                world_per_in=float(scale_data["world_per_in"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Failed to parse scale data – defaulting to None: %s", exc)
            scale_obj = None
    else:
        scale_obj = None

    proj = Project(
        name=data.get("name", "Untitled"),
        scale=scale_obj,
    )

    # Attach surfaces / polylines using the Project API to maintain invariants
    proj.surfaces = _load_surfaces(data.get("surfaces"))
    proj.traced_polylines = _load_polylines(data.get("polylines"))

    return proj 