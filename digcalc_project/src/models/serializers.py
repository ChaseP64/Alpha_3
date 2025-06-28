#!/usr/bin/env python3
"""Serialization classes for DigCalc project data.
"""

import json
import logging
from typing import Optional, TYPE_CHECKING

from .project import Project  # Use relative import
from .project_scale import ProjectScale
from .surface import Surface
from .strata_models import StrataStack

logger = logging.getLogger(__name__)

class ProjectLoadError(Exception):
    """Custom exception for errors during project loading."""


class ProjectSerializer:
    """Handles saving and loading of the Project object.
    Delegates saving and loading to the Project class methods,
    which handle the actual serialization format (currently JSON).
    """

    def save(self, project: Project, filepath: str):
        """Saves the Project object by calling its save method.

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
        """Loads a Project object by calling the Project.load class method.

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

def scale_to_dict(scale: Optional[ProjectScale]) -> Optional[dict]:
    """Serialize ProjectScale to dict, excluding None values."""
    return scale.model_dump(exclude_none=True) if scale else None

def scale_from_dict(d: Optional[dict]) -> Optional[ProjectScale]:
    """Deserialize dict to ProjectScale."""
    # This will only work if 'd' perfectly matches ProjectScale fields.
    # Migration for old formats needs to happen before this point if 'd' is from an old file.
    if d is None:
        return None
    try:
        scale = ProjectScale.model_validate(d)
        # If critical calibration fields are missing (no direct value & no ratio)
        if scale.world_per_paper_in is None and (scale.ratio_numer is None or scale.ratio_denom is None):
            return None
        return scale
    except Exception as e:
        logger.warning(f"Failed to create ProjectScale from dict: {d}. Error: {e}. Returning None.")
        return None

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
    data = project.model_dump(mode="json", exclude_none=True)

    # Always include scale key – even when None so downstream tests can assert
    # presence of the field.
    if "scale" not in data:
        data["scale"] = None

    return data

def from_dict(data: dict) -> Project:
    """Hydrate a :class:`Project` from an in-memory mapping."""
    try:
        if "scale" in data:
            data["scale"] = scale_from_dict(data["scale"])
        # Ensure 'layers' is an instance of _LayerDict
        from digcalc_project.src.models.project import _LayerDict as _LD
        if "layers" not in data or not isinstance(data["layers"], _LD):
            data["layers"] = _LD(data.get("layers", {}))
        return Project.model_validate(data)
    except Exception as exc:
        # Attempt graceful fallback for invalid ProjectScale etc.
        if isinstance(data, dict):
            data = data.copy()
            if "scale" in data:
                data["scale"] = scale_from_dict(data["scale"])
            # Ensure 'layers' is an instance of _LayerDict
            if "layers" not in data or not isinstance(data["layers"], _LD):
                data["layers"] = _LD(data.get("layers", {}))
            return Project.model_validate(data)
        raise

# ---------------------------------------------------------------------------
# Layer (de)serialisation helpers
# ---------------------------------------------------------------------------

if TYPE_CHECKING:  # pragma: no cover
    # Avoid runtime import cycle; only needed for type checkers.
    from .layer import Layer  # noqa: F401


def layer_to_dict(layer: "Layer") -> dict:
    """Serialize a :class:`Layer` to a plain dictionary.

    Only the minimal stable fields are included so we can evolve the model
    without breaking on-disk schema unnecessarily.
    """
    return {
        "id": layer.id,
        "name": layer.name,
        "mode": layer.mode,
        "line_color": layer.line_color,
        "point_color": layer.point_color,
        "visible": layer.visible,
    }


def layer_from_dict(data: dict) -> "Layer":
    """Deserialize *data* into a :class:`Layer`.

    Missing colour keys are tolerated for backwards compatibility with legacy
    project files that pre-date coloured layers.
    """
    from .layer import Layer  # local import to avoid cycle at module import time

    return Layer(
        id=data["id"],
        name=data["name"],
        mode=data.get("mode", "entered"),
        line_color=data.get("line_color", "#4DBBD5"),
        point_color=data.get("point_color", data.get("line_color", "#4DBBD5")),
        visible=data.get("visible", True),
    )

# ---------------------------------------------------------------------------
# Strata (de)serialisation helpers
# ---------------------------------------------------------------------------

def strata_to_dict(stack: "StrataStack | None") -> dict | None:
    """Return mapping suitable for JSON output or *None* if no stack."""
    return stack.to_dict() if stack else None

def strata_from_dict(d: dict | None) -> "StrataStack | None":
    """Inverse of :pyfunc:`strata_to_dict` with best-effort legacy tolerance."""
    if d is None:
        return None

    # Legacy fallback – if *d* is a list we assume it contains *BoreholeLog*
    # dictionaries only (pre-stack schema).  Wrap in a minimal StrataStack.
    if isinstance(d, list):
        try:
            from .strata_models import BoreholeLog, StrataStack  # local import

            boreholes = [BoreholeLog.from_dict(bd) for bd in d]
            return StrataStack(id=0, boreholes=boreholes)
        except Exception as exc:  # pragma: no cover – corrupt legacy data
            logger.warning("Failed to migrate legacy borehole list to StrataStack: %s", exc)
            return None

    # Standard path – defer to StrataStack factory.
    try:
        return StrataStack.from_dict(d)
    except Exception as exc:
        logger.warning("Invalid strata payload – ignored. Error: %s", exc)
        return None
