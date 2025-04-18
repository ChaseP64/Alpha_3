#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project model for the DigCalc application.

This module defines the Project model class which represents
an excavation takeoff project.
"""

import os
import logging
import json
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Union, Tuple, TypedDict

# Use relative imports
from .surface import Surface
from .calculation import VolumeCalculation

# Configure logging for the module
logger = logging.getLogger(__name__)
# Set default level if not configured by caller (e.g., main app)
# Library code shouldn't call basicConfig; configure in main app
# if not logger.hasHandlers():
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Type alias for clarity on the new polyline data structure
class PolylineData(TypedDict):
    points: List[Tuple[float, float]]
    elevation: Optional[float]

# Type alias for the main storage structure
TracedPolylinesType = Dict[str, List[PolylineData]]

DEFAULT_LAYER = "Default Layer"

class Project:
    """
    Project model representing an excavation takeoff project.
    
    A project contains surfaces, volume calculations, and metadata.
    `traced_polylines` is now a dict keyed by layer name; see
    add_traced_polyline() for details.
    """
    
    def __init__(self, name: str, project_file: Optional[str] = None):
        """
        Initialize a new project.
        
        Args:
            name: Project name
            project_file: Optional path to project file
        """
        self.logger = logging.getLogger(__name__)
        self.name = name
        self.project_file = project_file
        
        # Project properties
        self.description: str = ""
        self.created_at: datetime.datetime = datetime.datetime.now()
        self.modified_at: datetime.datetime = self.created_at
        self.author: str = os.environ.get("USERNAME", "Unknown")
        
        # Project data - Use Dict for surfaces for easier name lookup
        self.surfaces: Dict[str, Surface] = {} # Changed from List to Dict
        self.calculations: List[VolumeCalculation] = [] # Keep as list for now
        self.metadata: Dict[str, Any] = {}
        
        # --- Tracing / PDF Background Data ---
        self.pdf_background_path: Optional[str] = None
        self.pdf_background_page: int = 1
        self.pdf_background_dpi: int = 150
        # Store polylines as dict mapping layer name -> list of polylines
        # where each polyline is a list of (x, y) tuples
        self.traced_polylines: TracedPolylinesType = {}
        self.is_modified: bool = False # Track if project has unsaved changes
        
        self.logger.debug(f"Project '{name}' initialized")
    
    @property
    def legacy_traced_polylines(self) -> List[List[Tuple[float, float]]]:
        """ Flatten and return all polylines regardless of layer.

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
        """
        Add a surface to the project using its name as the key.
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
        """
        Remove a surface from the project by name.
        
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
        """
        Get a surface by name directly from the dictionary.
        
        Args:
            name: Surface name
            
        Returns:
            Surface or None if not found
        """
        return self.surfaces.get(name) # Use dict.get for safety

    def get_unique_surface_name(self, base_name: str) -> str:
        """
        Generates a unique surface name within the project.
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
        """
        Add a volume calculation to the project.
        
        Args:
            calculation: Volume calculation to add
        """
        self.calculations.append(calculation)
        self.modified_at = datetime.datetime.now()
        self.is_modified = True
        self.logger.info(f"Calculation '{calculation.name}' added to project")
    
    def add_traced_polyline(
        self,
        polyline: PolylineData, # Expect only the dictionary format now
        layer_name: str = "Existing Surface",
    ) -> Optional[int]: # Return index on success, None on failure
        """
        Adds a traced polyline (as a PolylineData dictionary) to the specified layer.

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
            "elevation": polyline.get("elevation") # Use get for safety
        }

        if layer_name not in self.traced_polylines:
            self.traced_polylines[layer_name] = []

        self.traced_polylines[layer_name].append(polyline_obj)
        self.modified_at = datetime.datetime.now()
        self.is_modified = True
        # Calculate index *after* appending
        new_index = len(self.traced_polylines[layer_name]) - 1
        self.logger.info(f"Added polyline to layer '{layer_name}' (Index: {new_index}, Points: {len(polyline_obj['points'])}, Elevation: {polyline_obj['elevation']}).")
        # Return the calculated index
        return new_index # Success, return index

    def remove_polyline(self, layer_name: str, polyline_index: int) -> bool:
        """Removes a polyline from a layer by its index."""
        if layer_name in self.traced_polylines and 0 <= polyline_index < len(self.traced_polylines[layer_name]):
            removed = self.traced_polylines[layer_name].pop(polyline_index)
            self.logger.info(f"Removed polyline at index {polyline_index} from layer '{layer_name}' (Elevation: {removed.get('elevation')}).")
            if not self.traced_polylines[layer_name]: # Remove layer if empty
                del self.traced_polylines[layer_name]
                self.logger.info(f"Removed empty layer: '{layer_name}'")
            self.is_modified = True
            return True
        self.logger.warning(f"Could not remove polyline: Layer '{layer_name}' or index {polyline_index} not found.")
        return False

    def clear_traced_polylines(self):
        """Removes all traced polylines from the project."""
        if self.traced_polylines:
            self.traced_polylines.clear()
            self.is_modified = True
            self.logger.info("Cleared all traced polylines.")

    def get_layers(self) -> List[str]:
        """Returns a list of layer names that contain traced polylines."""
        return list(self.traced_polylines.keys())

    def _serialisable_polylines(self) -> TracedPolylinesType:
        """Return a JSON-safe copy (all points as lists)."""
        # Note: While TypedDict implies structure, JSON will save as dict.
        # The TracedPolylinesType helps internally but output is standard dict.
        def tup2list(pt: Tuple[float, float]) -> List[float]:
            # Convert tuple to list for JSON compatibility
            return list(pt)

        out: TracedPolylinesType = {}
        for layer, polys in self.traced_polylines.items():
            serialised_polys = []
            for poly_data in polys:
                # Ensure points are lists
                serialised_points = [tup2list(p) for p in poly_data["points"]]
                serialised_polys.append({
                    "points": serialised_points,
                    "elevation": poly_data["elevation"],
                })
            out[layer] = serialised_polys
        return out

    def save(self, filename: Optional[str] = None) -> bool:
        """
        Save the project to a file.
        Includes surfaces, calculations, metadata, PDF background state, 
        and the layered traced polylines dictionary.
        
        Args:
            filename: Optional filename to save to
            
        Returns:
            bool: True if successful, False otherwise
        """
        file_path = filename or self.project_file
        if not file_path:
            self.logger.error("No project file specified for save operation")
            return False
        
        try:
            # Prepare data for serialization
            data = {
                "project_schema_version": 2, # Increment schema version for the new format
                "name": self.name,
                "description": self.description,
                "created_at": self.created_at.isoformat(),
                "modified_at": datetime.datetime.now().isoformat(), # Update modified time on save
                "author": self.author,
                # Store surface data (replace with full serialization later)
                "surfaces": {name: s.to_dict() for name, s in self.surfaces.items()},
                # Store calculation data (replace with full serialization later)
                "calculations": [c.to_dict() for c in self.calculations],
                "metadata": self.metadata,
                
                # --- Save Tracing / PDF State ---
                "pdf_background": {
                    "path": self.pdf_background_path,
                    "page": self.pdf_background_page,
                    "dpi": self.pdf_background_dpi
                },
                # Save the entire dictionary, ensuring points are lists
                "traced_polylines": self._serialisable_polylines() 
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            self.project_file = file_path
            self.modified_at = datetime.datetime.fromisoformat(data["modified_at"]) # Store the saved time
            self.is_modified = False # Mark as saved
            self.logger.info(f"Project saved to {file_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"Error saving project: {e}")
            return False
    
    @classmethod
    def load(cls, filename: str) -> Optional["Project"]:
        """
        Load a project from a file. Handles both new (v2) and old (v1) 
        formats for traced_polylines.
        
        Args:
            filename: Path to project file
            
        Returns:
            Project or None if loading failed
        """
        logger = logging.getLogger(__name__)
        
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # --- Load and handle traced_polylines first (handles migration) ---
            raw_polys = data.get("traced_polylines", {}) # Default to empty dict
            temp_traced_polylines = {}
            migrated = False
            if isinstance(raw_polys, list):
                # Legacy file: single list => migrate to default layer
                temp_traced_polylines = {"Legacy Traces": raw_polys}
                logger.warning(
                    "Migrated legacy polyline list to 'Legacy Traces' layer " 
                    "(%d polylines). Please save the project to keep these changes.",
                    len(raw_polys)
                )
                migrated = True
            elif isinstance(raw_polys, dict):
                # Standard v2 format
                temp_traced_polylines = raw_polys
                logger.debug("Loaded traced polylines in dictionary format.")
            elif raw_polys is not None:
                 # Handle cases where data exists but is neither dict nor list
                 logger.warning("Traced polyline data found but is in an unexpected format (%s). No polylines loaded.", type(raw_polys))
            # If raw_polys is None or {}, temp_traced_polylines remains {}

            # --- Load schema version for potential migrations --- 
            # (Keep this for other potential future migrations, though not used for polylines now)
            schema_version = data.get("project_schema_version", 0)
            if schema_version == 0 and isinstance(data.get("traced_polylines"), list):
                 schema_version = 1 # Infer version 1 if key exists as list

            if schema_version > 2:
                logger.warning(f"Loading project with schema version {schema_version}, which is newer than supported (2). Some data may be ignored.")
            
            # Basic validation
            if "name" not in data:
                raise ValueError("Project file missing 'name' attribute.")
                
            project = cls(data["name"], filename)
            project.description = data.get("description", "")
            project.author = data.get("author", "Unknown")
            
            # Load timestamps safely
            try:
                project.created_at = datetime.datetime.fromisoformat(data["created_at"])
            except (KeyError, ValueError):
                logger.warning("Could not load or parse created_at timestamp.")
                project.created_at = datetime.datetime.now() # Fallback
            try:
                project.modified_at = datetime.datetime.fromisoformat(data["modified_at"])
            except (KeyError, ValueError):
                 logger.warning("Could not load or parse modified_at timestamp.")
                 project.modified_at = project.created_at # Fallback
            
            project.metadata = data.get("metadata", {})
            
            # Load surfaces (replace with full deserialization later)
            surfaces_data = data.get("surfaces", {})
            if isinstance(surfaces_data, dict):
                 for name, surface_dict in surfaces_data.items():
                     try:
                         # Assuming Surface.from_dict exists and works
                         surface = Surface.from_dict(surface_dict)
                         project.surfaces[surface.name] = surface # Add directly to dict
                     except Exception as surf_e:
                         logger.error(f"Failed to load surface '{name}' from project data: {surf_e}")
            else:
                 logger.warning("Surface data in project file is not a dictionary. Skipping surfaces.")
            
            # Load calculations (replace with full deserialization later)
            calculations_data = data.get("calculations", [])
            if isinstance(calculations_data, list):
                 for calc_dict in calculations_data:
                     try:
                         # Assuming VolumeCalculation.from_dict exists and works
                         calc = VolumeCalculation.from_dict(calc_dict)
                         project.calculations.append(calc)
                     except Exception as calc_e:
                          logger.error(f"Failed to load calculation from project data: {calc_e}")
            else:
                 logger.warning("Calculation data in project file is not a list. Skipping calculations.")

            # --- Load Tracing / PDF State ---
            pdf_data = data.get("pdf_background")
            if isinstance(pdf_data, dict):
                project.pdf_background_path = pdf_data.get("path") # Path can be None
                project.pdf_background_page = pdf_data.get("page", 1)
                project.pdf_background_dpi = pdf_data.get("dpi", 150)
            else:
                logger.warning("PDF background data missing or invalid format. Defaults will be used.")
                project.pdf_background_path = None
                project.pdf_background_page = 1
                project.pdf_background_dpi = 150
                
            # Assign the processed/migrated polylines
            project.traced_polylines = temp_traced_polylines
            
            # Set modified status based ONLY on migration having occurred
            project.is_modified = migrated 
            
            logger.info(f"Project loaded from {filename}")
            return project
            
        except FileNotFoundError:
             logger.error(f"Project file not found: {filename}")
             return None
        except json.JSONDecodeError as json_e:
             logger.error(f"Error decoding project file (invalid JSON): {filename} - {json_e}")
             return None
        except Exception as e:
            logger.exception(f"Unexpected error loading project: {e}")
            return None 

    def __repr__(self) -> str:
        """Returns a string representation of the Project."""
        modified_status = "*" if self.is_modified else ""
        num_polylines = sum(len(polys) for polys in self.traced_polylines.values())
        return f"<Project(name='{self.name}{modified_status}', path='{self.project_file}', layers={len(self.traced_polylines)}, polylines={num_polylines})>" 