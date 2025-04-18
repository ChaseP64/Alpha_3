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
        logger = logging.getLogger(__name__)
        migrated = False # Track if any migration occurred

        try:
            with open(filename, 'r') as f: data = json.load(f)

            project_name = data.get("name")
            if not project_name:
                 # --- FIX: Correct logger f-string syntax --- 
                 logger.error(f"Project file '{filename}' is missing the required 'name' field.")
                 # --- END FIX --- 
                 # Optionally raise an error or return None
                 # raise ValueError(f"Project file 
                 return None # Cannot create project without a name

            # Instantiate using the correct positional arguments
            project = cls(name=project_name, project_file=filename)
            # --- END FIX ---

            schema_version = data.get("project_schema_version", 1) # Default to 1 if missing
            # project = cls(filename=filename) # Incorrect call removed
            project.project_schema_version = schema_version

            # Load other attributes using .get() for safety
            project.description = data.get("description", "")
            project.author = data.get("author", os.environ.get("USERNAME", "Unknown"))

            # Load timestamps safely
            try:
                project.created_at = datetime.datetime.fromisoformat(data["created_at"])
            except (KeyError, ValueError, TypeError): # Added TypeError
                logger.warning("Could not load or parse created_at timestamp. Using current time.")
                project.created_at = datetime.datetime.now() # Fallback
            try:
                 project.modified_at = datetime.datetime.fromisoformat(data["modified_at"])
            except (KeyError, ValueError, TypeError): # Added TypeError
                 logger.warning("Could not load or parse modified_at timestamp. Using created_at/current time.")
                 project.modified_at = project.created_at # Fallback to created_at

            project.metadata = data.get("metadata", {})

            # --- Load and Process Traced Polylines --- 
            raw_polys_data = data.get("traced_polylines", {})
            processed_polylines: TracedPolylinesType = {}

            if isinstance(raw_polys_data, list): # Legacy V1 format
                logger.warning("Found legacy list format for traced_polylines. Migrating to 'Legacy Traces' layer with elevation=None.")
                migrated_layer_polys = []
                for poly_list in raw_polys_data:
                    if isinstance(poly_list, list) and len(poly_list) >= 2:
                        try:
                            # Convert points to tuples, ensure format correctness
                            points_as_tuples = [tuple(map(float, p)) for p in poly_list if isinstance(p, list) and len(p)==2]
                            if len(points_as_tuples) >= 2: # Check if conversion yielded enough valid points
                                # --- FIX: Create the dict structure --- 
                                migrated_layer_polys.append({"points": points_as_tuples, "elevation": None})
                                # --- END FIX --- 
                            else:
                                 logger.warning(f"Skipping invalid points within legacy polyline list: {poly_list}")
                        except (TypeError, ValueError) as conv_err:
                             logger.warning(f"Error converting points in legacy polyline list: {conv_err}. Skipping: {poly_list}")
                    else:
                        logger.warning(f"Skipping invalid item during legacy polyline migration: {poly_list}")
                if migrated_layer_polys:
                     processed_polylines["Legacy Traces"] = migrated_layer_polys
                migrated = True # Mark as modified if V1 data was found

            elif isinstance(raw_polys_data, dict): # V2+ format
                logger.debug("Loading traced polylines in dictionary format. Verifying structure...")
                for layer, polys_in_layer in raw_polys_data.items():
                    if not isinstance(polys_in_layer, list):
                        logger.warning(f"Data for layer '{layer}' is not a list. Skipping layer.")
                        continue

                    verified_polys = []
                    for i, poly_data in enumerate(polys_in_layer):
                        # Check if it's already the correct dict format
                        if isinstance(poly_data, dict) and "points" in poly_data and isinstance(poly_data.get("points"), list):
                             try:
                                 # Convert points to tuples just in case they were saved as lists
                                 points_as_tuples = [tuple(map(float, p)) for p in poly_data["points"] if isinstance(p, (list, tuple)) and len(p)==2]
                                 if len(points_as_tuples) >= 2:
                                     verified_polys.append({
                                         "points": points_as_tuples,
                                         "elevation": poly_data.get("elevation") # Handles None correctly
                                     })
                                 else:
                                      logger.warning(f"Skipping polyline dict with < 2 valid points in layer '{layer}' (index {i}).")
                             except (TypeError, ValueError) as conv_err:
                                  logger.warning(f"Error converting points in polyline dict: {conv_err}. Skipping polyline in layer '{layer}' (index {i}).")

                        # --- FIX: Handle list format found within V2 dict --- 
                        elif isinstance(poly_data, list):
                            logger.warning(f"Found list format polyline within V2 layer '{layer}' (index {i}). Converting with elevation=None.")
                            if len(poly_data) >= 2:
                                try:
                                    points_as_tuples = [tuple(map(float, p)) for p in poly_data if isinstance(p, (list, tuple)) and len(p)==2]
                                    if len(points_as_tuples) >= 2:
                                        verified_polys.append({"points": points_as_tuples, "elevation": None})
                                        migrated = True # Data format changed, needs save
                                    else:
                                         logger.warning(f"Skipping list format polyline with < 2 valid points during V2 load (Layer: {layer}, Index: {i}).")
                                except (TypeError, ValueError) as conv_err:
                                     logger.warning(f"Error converting points in list format polyline during V2 load: {conv_err}. Skipping polyline in layer '{layer}' (index {i}).")
                            else:
                                logger.warning(f"Skipping list format polyline with < 2 points during V2 load (Layer: {layer}, Index: {i}).")
                        # --- END FIX --- 
                        else:
                             logger.warning(f"Skipping invalid polyline data structure in layer '{layer}' (index {i}): {type(poly_data)}")

                    if verified_polys: # Only add layer if it contains valid polylines
                         processed_polylines[layer] = verified_polys
            elif raw_polys_data is not None:
                 logger.warning("Traced polyline data found but is in an unexpected format (%s). No polylines loaded.", type(raw_polys_data))

            # --- Load Surfaces --- 
            raw_surfaces = data.get("surfaces", {})
            if isinstance(raw_surfaces, dict):
                 for name, surface_data in raw_surfaces.items():
                     try:
                         # Reconstruct Surface object
                         surface = Surface.from_dict(surface_data)
                         surface.name = name # Assign the name from the dict key
                         project.surfaces[name] = surface
                     except Exception as e:
                         logger.error(f"Failed to load surface '{name}': {e}", exc_info=True)
            else:
                 logger.warning("Surface data is not in the expected dictionary format. No surfaces loaded.")

            # --- Load Calculations --- 
            raw_calcs = data.get("calculations", [])
            if isinstance(raw_calcs, list):
                 for calc_data in raw_calcs:
                     try:
                         calc = VolumeCalculation.from_dict(calc_data)
                         project.calculations.append(calc)
                     except Exception as e:
                         logger.error(f"Failed to load calculation: {e}", exc_info=True)
            else:
                 logger.warning("Calculation data is not in the expected list format. No calculations loaded.")

            # --- Load PDF Background State --- 
            # Correctly loading the PDF data into the right attributes
            pdf_data = data.get("pdf_background")
            if isinstance(pdf_data, dict):
                project.pdf_background_path = pdf_data.get("path") # Path can be None
                project.pdf_background_page = pdf_data.get("page", 1)
                project.pdf_background_dpi = pdf_data.get("dpi", 150)
            else:
                logger.warning("PDF background data missing or invalid format in project file. Defaults will be used.")
                project.pdf_background_path = None
                project.pdf_background_page = 1
                project.pdf_background_dpi = 150

            # Assign fully processed data last
            project.traced_polylines = processed_polylines
            project.is_modified = migrated # Mark modified only if format changed during load

            logger.info(f"Project loaded from {filename}")
            return project

        except FileNotFoundError:
            logger.error(f"Project file not found: {filename}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from project file {filename}: {e}")
            return None
        except Exception as e:
            logger.exception(f"An unexpected error occurred loading project {filename}: {e}")
            return None

    def __repr__(self) -> str:
        """Returns a string representation of the Project."""
        modified_status = "*" if self.is_modified else ""
        num_polylines = sum(len(polys) for polys in self.traced_polylines.values())
        return f"<Project(name='{self.name}{modified_status}', path='{self.project_file}', layers={len(self.traced_polylines)}, polylines={num_polylines})>" 