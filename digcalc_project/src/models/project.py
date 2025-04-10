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
from typing import List, Dict, Optional, Any, Union, Tuple

from src.models.surface import Surface
from src.models.calculation import VolumeCalculation


class Project:
    """
    Project model representing an excavation takeoff project.
    
    A project contains surfaces, volume calculations, and metadata.
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
        # Store polylines as lists of (x, y) tuples for JSON compatibility
        self.traced_polylines: List[List[Tuple[float, float]]] = [] 
        
        self.logger.debug(f"Project '{name}' initialized")
    
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
        self.logger.info(f"Calculation '{calculation.name}' added to project")
    
    def add_traced_polyline(self, polyline_points: List[Tuple[float, float]]):
        """
        Adds a finalized traced polyline to the project.

        Args:
            polyline_points: List of (x, y) coordinate tuples for the polyline.
        """
        if len(polyline_points) >= 2:
            self.traced_polylines.append(polyline_points)
            self.modified_at = datetime.datetime.now()
            self.logger.debug(f"Added traced polyline with {len(polyline_points)} points.")
        else:
            self.logger.warning("Attempted to add invalid polyline (less than 2 points).")
            
    def clear_traced_polylines(self):
        """
        Removes all traced polylines from the project.
        """
        if self.traced_polylines:
            self.logger.debug(f"Clearing {len(self.traced_polylines)} traced polylines.")
            self.traced_polylines = []
            self.modified_at = datetime.datetime.now()

    def save(self, filename: Optional[str] = None) -> bool:
        """
        Save the project to a file.
        Includes surfaces, calculations, metadata, PDF background state, and traced polylines.
        
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
                "project_schema_version": 1, # Add a version number
                "name": self.name,
                "description": self.description,
                "created_at": self.created_at.isoformat(),
                "modified_at": datetime.datetime.now().isoformat(),
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
                "traced_polylines": self.traced_polylines
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            self.project_file = file_path
            self.modified_at = datetime.datetime.now()
            self.logger.info(f"Project saved to {file_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"Error saving project: {e}")
            return False
    
    @classmethod
    def load(cls, filename: str) -> Optional["Project"]:
        """
        Load a project from a file.
        
        Args:
            filename: Path to project file
            
        Returns:
            Project or None if loading failed
        """
        logger = logging.getLogger(__name__)
        
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # --- Load schema version for potential migrations later ---
            schema_version = data.get("project_schema_version", 0)
            if schema_version > 1:
                logger.warning(f"Loading project with schema version {schema_version}, which is newer than supported (1). Some data may be ignored.")
            
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
                
            traced_data = data.get("traced_polylines")
            if isinstance(traced_data, list):
                # Basic validation: check if items are lists of lists/tuples with numbers
                valid_polylines = []
                for i, poly in enumerate(traced_data):
                    if isinstance(poly, list) and len(poly) >= 2: 
                        is_valid = True
                        converted_poly = []
                        for pt in poly:
                             if isinstance(pt, (list, tuple)) and len(pt) == 2 and all(isinstance(coord, (int, float)) for coord in pt):
                                 converted_poly.append(tuple(pt)) # Ensure tuple format
                             else:
                                 is_valid = False
                                 logger.warning(f"Invalid point data found in traced polyline {i} at index {poly.index(pt)}. Skipping polyline.")
                                 break
                        if is_valid:
                            valid_polylines.append(converted_poly)
                    else:
                        logger.warning(f"Invalid polyline data format at index {i}. Skipping.")
                project.traced_polylines = valid_polylines
            else:
                 logger.warning("Traced polyline data missing or invalid format. No polylines loaded.")
                 project.traced_polylines = []

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