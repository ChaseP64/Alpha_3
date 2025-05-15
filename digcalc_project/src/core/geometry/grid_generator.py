#!/usr/bin/env python3
"""Grid generator for the DigCalc application.

This module provides functionality to generate grid surfaces from
TINs, point clouds, and other data sources.
"""

import logging
from typing import List

import numpy as np

# Use relative import
from ...models.surface import Point3D, Surface


class GridGenerator:
    """Generator for grid-based surfaces."""

    def __init__(self):
        """Initialize the grid generator."""
        self.logger = logging.getLogger(__name__)

    def generate_from_points(self, points: List[Point3D],
                           grid_spacing: float,
                           name: str) -> Surface:
        """Generate a grid surface from a list of 3D points.
        
        Args:
            points: List of 3D points
            grid_spacing: Desired grid spacing
            name: Name for the created surface
            
        Returns:
            Generated grid Surface

        """
        self.logger.info(f"Generating grid from {len(points)} points")

        # Determine grid extents from point bounds
        x_min = min(p.x for p in points)
        x_max = max(p.x for p in points)
        y_min = min(p.y for p in points)
        y_max = max(p.y for p in points)

        # Calculate grid dimensions
        cols = int((x_max - x_min) / grid_spacing) + 1
        rows = int((y_max - y_min) / grid_spacing) + 1

        # Create grid data
        grid_data = np.full((rows, cols), np.nan)

        # For the skeleton, create a simple grid with dummy values
        for i in range(rows):
            for j in range(cols):
                x = x_min + j * grid_spacing
                y = y_min + i * grid_spacing
                # Create a dummy surface (paraboloid)
                grid_data[i, j] = ((x - (x_min + x_max) / 2) ** 2 +
                                   (y - (y_min + y_max) / 2) ** 2) / 100

        # Create and return the grid surface
        surface = Surface(name, Surface.SURFACE_TYPE_GRID)
        surface.set_grid_data(grid_data, grid_spacing, (x_min, y_min))

        self.logger.info(f"Generated grid of shape {grid_data.shape}")
        return surface
