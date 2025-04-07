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
from typing import List, Dict, Optional, Any, Union

from models.surface import Surface
from models.calculation import VolumeCalculation


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
        
        # Project data
        self.surfaces: List[Surface] = []
        self.calculations: List[VolumeCalculation] = []
        self.metadata: Dict[str, Any] = {}
        
        self.logger.debug(f"Project '{name}' initialized")
    
    def add_surface(self, surface: Surface) -> None:
        """
        Add a surface to the project.
        
        Args:
            surface: Surface to add
        """
        self.surfaces.append(surface)
        self.modified_at = datetime.datetime.now()
        self.logger.info(f"Surface '{surface.name}' added to project")
    
    def remove_surface(self, surface: Surface) -> bool:
        """
        Remove a surface from the project.
        
        Args:
            surface: Surface to remove
            
        Returns:
            bool: True if surface was removed, False otherwise
        """
        if surface in self.surfaces:
            self.surfaces.remove(surface)
            self.modified_at = datetime.datetime.now()
            self.logger.info(f"Surface '{surface.name}' removed from project")
            return True
        return False
    
    def get_surface_by_name(self, name: str) -> Optional[Surface]:
        """
        Get a surface by name.
        
        Args:
            name: Surface name
            
        Returns:
            Surface or None if not found
        """
        for surface in self.surfaces:
            if surface.name == name:
                return surface
        return None
    
    def add_calculation(self, calculation: VolumeCalculation) -> None:
        """
        Add a volume calculation to the project.
        
        Args:
            calculation: Volume calculation to add
        """
        self.calculations.append(calculation)
        self.modified_at = datetime.datetime.now()
        self.logger.info(f"Calculation '{calculation.name}' added to project")
    
    def save(self, filename: Optional[str] = None) -> bool:
        """
        Save the project to a file.
        
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
            # In a real implementation, this would serialize the project
            # For now, we'll just save a skeleton with metadata
            data = {
                "name": self.name,
                "description": self.description,
                "created_at": self.created_at.isoformat(),
                "modified_at": datetime.datetime.now().isoformat(),
                "author": self.author,
                "surfaces": [s.name for s in self.surfaces],
                "calculations": [c.name for c in self.calculations],
                "metadata": self.metadata
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
            
            project = cls(data.get("name", "Unnamed Project"), filename)
            project.description = data.get("description", "")
            project.author = data.get("author", "Unknown")
            
            if "created_at" in data:
                project.created_at = datetime.datetime.fromisoformat(data["created_at"])
            if "modified_at" in data:
                project.modified_at = datetime.datetime.fromisoformat(data["modified_at"])
            
            project.metadata = data.get("metadata", {})
            
            # In a real implementation, this would also load surfaces and calculations
            
            logger.info(f"Project loaded from {filename}")
            return project
            
        except Exception as e:
            logger.exception(f"Error loading project: {e}")
            return None 