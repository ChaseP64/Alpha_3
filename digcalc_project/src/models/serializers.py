#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serialization classes for DigCalc project data.
"""

import logging
import pickle
from typing import Optional
import json

from .project import Project # Use relative import

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