#!/usr/bin/env python3
from __future__ import annotations

"""
Project model for the DigCalc application.

This module defines the Project model class which represents
an excavation takeoff project.
"""

import datetime
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from .calculation import VolumeCalculation
from .project_scale import ProjectScale  # NEW Pydantic model
from .region import Region

# Use relative imports
from .surface import Surface

# Configure logging for the module
logger = logging.getLogger(__name__)
# Set default level if not configured by caller (e.g., main app)
# Library code shouldn't call basicConfig; configure in main app
# if not logger.hasHandlers():
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def _migrate_v1_to_v2(data: dict) -> dict:
    """Ensures the 'regions' key exists for loading older project versions."""
    if "regions" not in data:
        logger.info("Migrating project data: Adding missing 'regions' field.")
        data["regions"] = []
    return data

# Type alias for clarity on the new polyline data structure
class PolylineData(TypedDict):
    points: List[Tuple[float, float]]
    elevation: Optional[float]

# Type alias for the main storage structure
TracedPolylinesType = Dict[str, List[PolylineData]]

DEFAULT_LAYER = "Default Layer"

@dataclass
class Project:
    """Project model representing an excavation takeoff project.
    
    A project contains surfaces, volume calculations, and metadata.
    `traced_polylines` is now a dict keyed by layer name; see
    add_traced_polyline() for details.
    """

    name: str
    filepath: Optional[str] = None
    description: str = ""
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    modified_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    author: str = field(default_factory=lambda: os.environ.get("USERNAME", "Unknown"))
    surfaces: Dict[str, Surface] = field(default_factory=dict)
    calculations: List[VolumeCalculation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    regions: list[Region] = field(default_factory=list)
    scale: Optional[ProjectScale] = None  # Updated to new ProjectScale
    # Flags for project-level state (e.g., legacy scale invalid)
    flags: List[str] = field(default_factory=list)

    # --- Tracing / PDF Background Data ---
    pdf_background_path: Optional[str] = None
    pdf_background_page: int = 1
    pdf_background_dpi: int = 150
    # Store polylines as dict mapping layer name -> list of polylines
    # where each polyline is a list of (x, y) tuples
    traced_polylines: TracedPolylinesType = field(default_factory=dict)
    is_dirty: bool = False # Track if project has unsaved changes
    # --- NEW: Layer Revisions ---
    # Dictionary to track revisions of layers (used for surface staleness)
    layer_revisions: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    # --- END NEW ---

    def __post_init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Project '{self.name}' initialized")

    @property
    def legacy_traced_polylines(self) -> List[List[Tuple[float, float]]]:
        """Flatten and return all polylines regardless of layer.

        This lets older code that still iterates over
        `project.legacy_traced_polylines` work without change.
        """
        flat_list = []
        for layer_name in self.traced_polylines:
            for polyline_data in self.traced_polylines[layer_name]:
                if "points" in polyline_data: # Check for robustness
                    flat_list.append(polyline_data["points"])
        return flat_list

    def add_surface(self, surface: Surface) -> None:
        """Add a surface to the project using its name as the key.
        Ensures the surface has a unique name before adding.
        
        Args:
            surface: Surface to add

        """
        # Ensure name is unique before adding
        unique_name = self.get_unique_surface_name(surface.name)
        surface.name = unique_name # Update surface name if modified

        self.surfaces[surface.name] = surface # Use name as key
        self.modified_at = datetime.datetime.now()
        self.logger.info(f"Surface '{surface.name}' added to project")

    def remove_surface(self, surface_name: str) -> bool:
        """Remove a surface from the project by name.
        
        Args:
            surface_name: Name of the surface to remove
            
        Returns:
            bool: True if surface was removed, False otherwise

        """
        if surface_name in self.surfaces:
            del self.surfaces[surface_name] # Remove by key
            self.modified_at = datetime.datetime.now()
            self.logger.info(f"Surface '{surface_name}' removed from project")
            return True
        self.logger.warning(f"Attempted to remove non-existent surface: '{surface_name}'")
        return False

    def get_surface(self, name: str) -> Optional[Surface]: # Renamed for clarity
        """Get a surface by name directly from the dictionary.
        
        Args:
            name: Surface name
            
        Returns:
            Surface or None if not found

        """
        return self.surfaces.get(name) # Use dict.get for safety

    def get_unique_surface_name(self, base_name: str) -> str:
        """Generates a unique surface name within the project.
        If base_name already exists, appends (1), (2), etc. until unique.

        Args:
            base_name (str): The desired base name for the surface.

        Returns:
            str: A unique surface name.

        """
        if base_name not in self.surfaces:
            return base_name

        counter = 1
        while True:
            new_name = f"{base_name} ({counter})"
            if new_name not in self.surfaces:
                return new_name
            counter += 1

    def add_calculation(self, calculation: VolumeCalculation) -> None:
        """Add a volume calculation to the project.
        
        Args:
            calculation: Volume calculation to add

        """
        self.calculations.append(calculation)
        self.modified_at = datetime.datetime.now()
        self.is_dirty = True
        self.logger.info(f"Calculation '{calculation.name}' added to project")

    def add_traced_polyline(
        self,
        polyline: PolylineData, # Expect only the dictionary format now
        layer_name: str = "Existing Surface",
    ) -> Optional[int]: # Return index on success, None on failure
        """Adds a traced polyline (as a PolylineData dictionary) to the specified layer.

        Args:
            polyline (PolylineData): The polyline data dictionary containing
                                     'points' (List[Tuple[float, float]]) and
                                     'elevation' (Optional[float]).
            layer_name (str, optional): The name of the layer to add the polyline to.
                                        Defaults to "Existing Surface".

        Returns:
            Optional[int]: The index of the added polyline within its layer list,
                           or None if adding failed.

        """
        # Validate the input dictionary
        if not isinstance(polyline, dict) or "points" not in polyline:
            self.logger.warning(f"Invalid polyline data format provided for layer '{layer_name}'. Expected dict with 'points'. Skipping.")
            return None # Failure

        points_list = polyline.get("points")
        # Ensure points_list is actually a list before checking length
        if not isinstance(points_list, list) or len(points_list) < 2:
            self.logger.warning(f"Attempted to add polyline with invalid or < 2 points to layer '{layer_name}'. Skipping.")
            return None # Failure

        # Ensure elevation key exists, defaulting to None if missing
        polyline_obj: PolylineData = {
            "points": points_list,
            "elevation": polyline.get("elevation"), # Use get for safety
        }

        if layer_name not in self.traced_polylines:
            self.traced_polylines[layer_name] = []

        self.traced_polylines[layer_name].append(polyline_obj)
        self.modified_at = datetime.datetime.now()
        new_index = len(self.traced_polylines[layer_name]) - 1

        # --- Bump Revision ---
        new_revision = self._bump_layer_revision(layer_name)
        # --- End Bump ---

        self.logger.info(f"Added polyline to layer '{layer_name}' (Index: {new_index}, Points: {len(polyline_obj['points'])}, Elevation: {polyline_obj['elevation']}, New Rev: {new_revision}).")
        return new_index # Success, return index

    def remove_polyline(self, layer_name: str, polyline_index: int) -> bool:
        """Removes a polyline from a layer by its index."""
        if layer_name in self.traced_polylines and 0 <= polyline_index < len(self.traced_polylines[layer_name]):
            removed = self.traced_polylines[layer_name].pop(polyline_index)

            # --- Bump Revision ---
            new_revision = self._bump_layer_revision(layer_name)
            # --- End Bump ---

            self.logger.info(f"Removed polyline at index {polyline_index} from layer '{layer_name}' (Elevation: {removed.get('elevation')}, New Rev: {new_revision}).")
            if not self.traced_polylines[layer_name]: # Remove layer if empty
                del self.traced_polylines[layer_name]
                self.logger.info(f"Removed empty layer: '{layer_name}'")
            return True
        self.logger.warning(f"Could not remove polyline: Layer '{layer_name}' or index {polyline_index} not found.")
        return False

    def clear_traced_polylines(self):
        """Removes all traced polylines from the project."""
        if self.traced_polylines:
            self.traced_polylines.clear()
            self.is_dirty = True
            self.logger.info("Cleared all traced polylines.")

    def get_layers(self) -> List[str]:
        """Returns a list of layer names that contain traced polylines."""
        return list(self.traced_polylines.keys())

    def _serialisable_polylines(self) -> TracedPolylinesType:
        """Return a JSON-safe copy (all points as lists)."""
        serializable_data = {}
        for layer, polys in self.traced_polylines.items():
            serializable_polys = []
            if isinstance(polys, list):
                for poly_data in polys:
                    if isinstance(poly_data, dict) and "points" in poly_data and isinstance(poly_data["points"], list):
                        # Ensure points are lists of numbers [x, y]
                        serializable_points = [[pt[0], pt[1]] for pt in poly_data["points"] if isinstance(pt, (list, tuple)) and len(pt) == 2]
                        serializable_polys.append({
                            "points": serializable_points,
                            "elevation": poly_data.get("elevation"),
                        })
            serializable_data[layer] = serializable_polys
        return serializable_data

    def save(self, filename: Optional[str] = None) -> bool:
        """Saves the project data to a file in JSON format."""
        save_path = filename or self.filepath
        if not save_path:
            self.logger.error("Cannot save project: No filename provided and project has no associated file.")
            return False

        self.filepath = save_path
        self.modified_at = datetime.datetime.now()
        self.logger.info(f"Saving project '{self.name}' to {self.filepath}")

        try:
            scale_dict_data = None
            if self.scale:
                scale_dict_data = self.scale.dict(exclude_none=True) # Use Pydantic's .dict()
                # Ensure datetime is ISO format string for JSON
                if "calibrated_at" in scale_dict_data and isinstance(scale_dict_data["calibrated_at"], datetime.datetime):
                    scale_dict_data["calibrated_at"] = scale_dict_data["calibrated_at"].isoformat()

            data_to_save = {
                "version": 2, # Bump version due to scale model change
                "name": self.name,
                "description": self.description,
                "created_at": self.created_at.isoformat(),
                "modified_at": self.modified_at.isoformat(),
                "author": self.author,
                "surfaces": {name: s.to_dict() for name, s in self.surfaces.items()},
                "calculations": [c.to_dict() for c in self.calculations],
                "regions": [r.to_dict() for r in self.regions],
                "metadata": self.metadata,
                "scale": scale_dict_data, # Use the processed dict
                "pdf_background_path": self.pdf_background_path,
                "pdf_background_page": self.pdf_background_page,
                "pdf_background_dpi": self.pdf_background_dpi,
                "traced_polylines": self._serialisable_polylines(),
                "layer_revisions": dict(self.layer_revisions), # Convert defaultdict
                "flags": self.flags,
            }

            with open(self.filepath, "w") as f:
                json.dump(data_to_save, f, indent=4)

            self.is_dirty = False # Mark as saved
            self.logger.info("Project saved successfully.")
            return True

        except Exception:
            self.logger.exception(f"Failed to save project to {self.filepath}")
            return False

    @classmethod
    def load(cls, filename: str, pdf_service: Optional[Any] = None) -> Optional[Project]:
        """Loads a project from a JSON file."""
        logger = logging.getLogger(__name__)
        migrated = False # Track if any migration occurred

        if not Path(filename).is_file():
            logger.error(f"Load failed: Project file not found at '{filename}'")
            return None

        try:
            with open(filename) as f:
                data = json.load(f)

            project_version = data.get("version", 0)

            # --- Migration ---
            if project_version < 2:
                 data = _migrate_project_scale_v1_to_v2(data)
                 migrated = True

            # Convert legacy world_per_in to ProjectScale (v3 shim)
            render_dpi = None
            try:
                render_dpi = pdf_service.current_render_dpi() if pdf_service else None
            except AttributeError:
                render_dpi = None

            data = _migrate_v2_add_scale(data, render_dpi)

            # Other v1→v2 migrations (regions etc.)
            data = _migrate_v1_to_v2(data)

            # Create project instance
            project = cls(name=data.get("name", "Untitled Project"))

            # Load simple attributes
            project.description = data.get("description", "")
            try:
                project.created_at = datetime.datetime.fromisoformat(data.get("created_at", datetime.datetime.now().isoformat()))
                project.modified_at = datetime.datetime.fromisoformat(data.get("modified_at", project.created_at.isoformat()))
            except (ValueError, TypeError):
                logger.warning("Invalid date format in project file, using current time.")
                project.created_at = datetime.datetime.now()
                project.modified_at = project.created_at
            project.author = data.get("author", "Unknown")
            project.metadata = data.get("metadata", {})
            project.flags = data.get("flags", [])

            # --- Load Project Scale (optional) ---  # NEW
            scale_data = data.get("scale")
            if scale_data:
                try:
                    # Pydantic will parse ISO string for calibrated_at to datetime automatically
                    project.scale = ProjectScale(**scale_data)
                except Exception as e_scale:
                    logger.error(f"Failed to load/parse new ProjectScale data: {e_scale}. Scale will be None.", exc_info=True)
                    project.scale = None
            else:
                project.scale = None

            # --- Load Surfaces ---
            surfaces_data = data.get("surfaces", {})
            if isinstance(surfaces_data, dict):
                for name, surface_data in surfaces_data.items():
                    try:
                        surface = Surface.from_dict(surface_data)
                        project.surfaces[name] = surface # Add directly to dict
                    except Exception as e_surf:
                        logger.error(f"Failed to load surface '{name}': {e_surf}", exc_info=True)
            else:
                logger.warning("Surface data in project file is not a dictionary. Skipping surface load.")

            # --- Load PDF Background Info (Directly from top level) ---
            project.pdf_background_path = data.get("pdf_background_path") # Can be None
            project.pdf_background_page = data.get("pdf_background_page", 1)
            project.pdf_background_dpi = data.get("pdf_background_dpi", 150)
            if project.pdf_background_path:
                if not Path(project.pdf_background_path).is_file():
                     logger.warning(f"PDF background path '{project.pdf_background_path}' in project file does not exist or is not accessible.")
                else:
                     logger.info(f"Found PDF background path in project file: {project.pdf_background_path}")
            else:
                 logger.info("No PDF background path found in project file.")

            # --- Load Traced Polylines (Handle legacy list and new format) ---
            polylines_raw = data.get("traced_polylines", {})
            loaded_polylines_dict: TracedPolylinesType = {}
            if isinstance(polylines_raw, list):
                # Handle legacy format: list of polylines (list of points)
                migrated = True
                logger.warning("Migrating legacy traced polylines (list) to new dictionary format under 'Legacy Traces' layer.")
                legacy_polys_as_dicts = []
                for poly_points in polylines_raw:
                    if isinstance(poly_points, list) and len(poly_points) >= 2:
                        try:
                            points_tuples = [tuple(map(float, pt)) if isinstance(pt, list) and len(pt)==2 else tuple(pt) for pt in poly_points]
                            if len(points_tuples) >= 2: # Check if conversion yielded enough valid points
                                legacy_polys_as_dicts.append({"points": points_tuples, "elevation": None})
                            else:
                                logger.warning(f"Skipping invalid points within legacy polyline list: {poly_points}")
                        except (TypeError, ValueError) as conv_err:
                             logger.warning(f"Error converting points in legacy polyline list: {conv_err}. Skipping: {poly_points}")
                    else:
                         logger.warning(f"Skipping invalid item during legacy polyline migration: {poly_points}")
                if legacy_polys_as_dicts:
                    loaded_polylines_dict["Legacy Traces"] = legacy_polys_as_dicts
            elif isinstance(polylines_raw, dict):
                # New format: dict of layer -> list of PolylineData dicts
                logger.debug("Loading traced polylines in dictionary format.")
                for layer, polys in polylines_raw.items():
                    if isinstance(polys, list):
                        valid_polys = []
                        for p_data in polys:
                            if isinstance(p_data, dict) and "points" in p_data and isinstance(p_data["points"], list):
                                try:
                                    p_data["points"] = [tuple(map(float, pt)) if isinstance(pt, list) and len(pt)==2 else tuple(pt) for pt in p_data["points"]]
                                    # Ensure elevation key exists
                                    p_data["elevation"] = p_data.get("elevation")
                                    if len(p_data["points"]) >= 2: # Ensure enough valid points after conversion
                                         valid_polys.append(p_data)
                                    else:
                                         logger.warning(f"Skipping polyline dict with < 2 valid points in layer '{layer}'. Data: {p_data}")
                                except (TypeError, ValueError) as conv_err:
                                      logger.warning(f"Error converting points in polyline dict: {conv_err}. Skipping polyline in layer '{layer}'. Data: {p_data}")
                            else:
                                logger.warning(f"Skipping invalid polyline data structure in layer '{layer}': {p_data}")
                        if valid_polys:
                             loaded_polylines_dict[layer] = valid_polys
                    else:
                         logger.warning(f"Invalid data type for layer '{layer}' polylines: {type(polys)}. Skipping layer.")
            else:
                 logger.warning(f"Traced polyline data found but is in an unexpected format: {type(polylines_raw)}")

            project.traced_polylines = loaded_polylines_dict

            # --- Load Layer Revisions ---
            project.layer_revisions = defaultdict(int, data.get("layer_revisions", {}))

            # --- Check Surface Staleness ---
            for surface_name, surface in project.surfaces.items():
                if surface.source_layer_name:
                    current_rev = project.layer_revisions.get(surface.source_layer_name, 0)
                    saved_rev = surface.source_layer_revision
                    if saved_rev is None or saved_rev != current_rev:
                        surface.is_stale = True
                        logger.info(f"Marking loaded surface '{surface_name}' as stale (SavedRev={saved_rev}, CurrentRev={current_rev}).")
                    else:
                        surface.is_stale = False
                else:
                    surface.is_stale = False

            # --- Load Regions ---
            project.regions = [Region.from_dict(r) for r in data.get("regions", [])]

            project.is_dirty = migrated # Mark modified if migration happened
            logger.info(f"Project loaded from {filename}")
            return project

        except json.JSONDecodeError as e:
            logger.error(f"Load failed: Invalid JSON format in '{filename}': {e}")
            return None
        except Exception as e:
            logger.exception(f"Load failed: Unexpected error reading project file '{filename}': {e}")
            return None

    def __repr__(self) -> str:
        """Returns a string representation of the Project."""
        modified_status = "*" if self.is_dirty else ""
        num_polylines = sum(len(polys) for polys in self.traced_polylines.values())
        return f"<Project(name='{self.name}{modified_status}', path='{self.filepath}', layers={len(self.traced_polylines)}, polylines={num_polylines})>"

    # --- NEW: Layer Revision Helper ---
    def _bump_layer_revision(self, layer_name: str) -> int:
        """Increments the revision number for the specified layer and marks
        the project as modified.

        Args:
            layer_name (str): The name of the layer to bump the revision for.

        Returns:
            int: The new revision number for the layer.

        """
        self.layer_revisions[layer_name] += 1
        new_revision = self.layer_revisions[layer_name]
        self.is_dirty = True # Bumping revision counts as modification
        logger.debug(f"Bumped layer '{layer_name}' revision to {new_revision}")
        return new_revision
    # --- END NEW ---

# --- NEW: Migration helper for ProjectScale v1 (dataclass) to v2 (Pydantic) ---
# This should be defined at the module level in project.py

def _migrate_project_scale_v1_to_v2(data: dict) -> dict:
    """Migrates old ProjectScale (dataclass-like dict) to new Pydantic ProjectScale structure."""
    logger.info("Attempting to migrate ProjectScale from v1 to v2 format.")
    scale_data_v1 = data.get("scale")
    if not scale_data_v1 or not isinstance(scale_data_v1, dict):
        logger.debug("No v1 scale data found or not a dict, skipping migration.")
        return data # No old scale data to migrate

    # Old fields: px_per_in, world_units, world_per_in
    # New fields: input_method, world_units, world_per_paper_in, ratio_numer, ratio_denom, render_dpi_at_cal, calibrated_at
    try:
        px_per_in = float(scale_data_v1.get("px_per_in", 96.0)) # Default if missing
        world_units = str(scale_data_v1.get("world_units", "ft"))
        world_per_in = float(scale_data_v1.get("world_per_in", 0.0))

        # For old data, assume it came from two-point calibration or was set directly
        # We don't have ratio_numer/denom for old data.
        # calibrated_at will be set to now by Pydantic default_factory if not provided.
        new_scale_data = {
            "input_method": "two_point", # Assume old scales were effectively two-point or direct
            "world_units": world_units,
            "world_per_paper_in": world_per_in,
            "render_dpi_at_cal": px_per_in,
            "ratio_numer": None, # Not available in old format
            "ratio_denom": None, # Not available in old format
            # "calibrated_at": datetime.datetime.utcnow().isoformat() # Or let Pydantic handle default
        }
        data["scale"] = new_scale_data
        logger.info(f"Successfully migrated scale data for project. New scale dict: {new_scale_data}")
    except Exception as e:
        logger.error(f"Error migrating old scale data: {e}. Old scale data: {scale_data_v1}. Scale will be discarded.", exc_info=True)
        data["scale"] = None # Discard problematic old scale data
    return data

# Ensure existing migration functions are compatible or updated if they also touch 'scale'
# def _migrate_v2_add_scale(st: dict) -> dict: ...
# def _migrate_v1_to_v2(data: dict) -> dict: ... # This one was for regions, should be fine

def _migrate_v2_add_scale(data: dict, project_render_dpi: float | None) -> dict:
    """Legacy projects (≤ v0.3) stored a bare `world_per_in` float.
    Convert it into a full ProjectScale object or mark as invalid.
    """
    # If already contains proper scale or no legacy key → nothing to do.
    if "scale" in data or "world_per_in" not in data:
        return data

    world_per_in = data.pop("world_per_in")

    # Could not determine DPI → flag invalid scale
    if project_render_dpi is None or project_render_dpi <= 0:
        data["scale"] = None
        data["flags"] = data.get("flags", []) + ["scale-invalid"]
        return data

    from .project_scale import ProjectScale

    try:
        scale_obj = ProjectScale.from_direct(
            value=world_per_in,
            units=data.get("world_units", "ft"),
            render_dpi=project_render_dpi,
        )
        data["scale"] = scale_obj.dict(exclude_none=True)
    except Exception as exc:
        logger.warning("Failed to convert legacy scale: %s", exc, exc_info=True)
        data["scale"] = None
        data["flags"] = data.get("flags", []) + ["scale-invalid"]

    # Clean up legacy key 'world_units' if not used elsewhere (optional)
    return data
