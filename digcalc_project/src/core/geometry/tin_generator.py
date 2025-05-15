#!/usr/bin/env python3
"""TIN (Triangulated Irregular Network) generator for the DigCalc application.

This module provides functionality to generate TIN surfaces from point clouds.
"""

import logging
from typing import List

import numpy as np

# Use the actual Delaunay implementation
try:
    from scipy.spatial import Delaunay, QhullError
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# REMOVED sys.path manipulation
# Use absolute import for models
from digcalc_project.src.models.surface import Point3D, Surface, Triangle


class TINGenerator:
    """Generator for TIN (Triangulated Irregular Network) surfaces.

    Uses scipy.spatial.Delaunay to perform 2D triangulation based on XY coordinates.
    """

    def __init__(self):
        """Initialize the TIN generator."""
        self.logger = logging.getLogger(__name__)
        if not HAS_SCIPY:
             self.logger.error("Scipy library not found. TIN generation will not be possible.")
             # Consider raising an exception or handling this more gracefully depending on application requirements

    def generate_from_points(self, points: List[Point3D], name: str) -> Surface:
        """Generate a TIN surface from a list of 3D points using Delaunay triangulation.

        Args:
            points (List[Point3D]): List of 3D points.
            name (str): Name for the created surface.

        Returns:
            Surface: The generated Surface object, potentially with no triangles if triangulation failed.

        Raises:
            RuntimeError: If SciPy is not installed or if an unexpected error occurs.

        """
        self.logger.info(f"Generating TIN '{name}' from {len(points)} points")

        if not HAS_SCIPY:
            raise RuntimeError("SciPy library is required for TIN generation but is not installed.")

        surface = Surface(name, Surface.SURFACE_TYPE_TIN)

        # Add points to the surface (ensures unique points by ID in the surface dict)
        # We use a temp dict to handle potential duplicates in the input list
        point_dict = {}
        for p in points:
            if p.id not in point_dict:
                 point_dict[p.id] = p
            else:
                 # Optional: Log or handle duplicate point IDs if necessary
                 pass
        surface.points = point_dict

        # Get the unique points list again from the dictionary values for triangulation
        unique_points_list = list(surface.points.values())

        # Need at least 3 unique points for triangulation
        if len(unique_points_list) < 3:
             self.logger.warning(f"Cannot generate TIN for '{name}': requires at least 3 unique points, found {len(unique_points_list)}.")
             # Return surface with points but no triangles
             return surface

        # Prepare unique points for Delaunay (expects 2D array of coordinates)
        try:
            xy_coords = np.array([[p.x, p.y] for p in unique_points_list])

            # --- Check for collinearity or duplicate XYs before triangulation ---
            # Scipy's Delaunay handles duplicates, but explicit check might be informative
            unique_xy, unique_indices = np.unique(xy_coords, axis=0, return_index=True)

            if len(unique_xy) < 3:
                # This condition catches cases where all unique XY points are collinear or fewer than 3 exist
                self.logger.warning(f"Cannot generate TIN for '{name}': requires at least 3 non-collinear unique XY locations, found {len(unique_xy)}.")
                return surface # Return surface with points but no triangles

            # Perform Delaunay triangulation on the full set of unique XY coordinates
            # It's generally safe to use the full unique_points_list XYs here if len >= 3
            self.logger.debug(f"Performing Delaunay triangulation on {len(xy_coords)} unique points.")
            delaunay = Delaunay(xy_coords) # Use xy_coords corresponding to unique_points_list

            # Simplices gives the indices into the *input* points array (xy_coords)
            simplices = delaunay.simplices

            self.logger.info(f"Delaunay triangulation completed for '{name}', found {len(simplices)} simplices (triangles).")

            # Create Triangle objects using the original Point3D objects
            for simplex in simplices:
                # Get the original Point3D objects corresponding to the simplex indices
                try:
                    # Indices from simplex refer to the order in unique_points_list
                    p1 = unique_points_list[simplex[0]]
                    p2 = unique_points_list[simplex[1]]
                    p3 = unique_points_list[simplex[2]]

                    # Add the triangle to the surface (add_triangle also adds points if missing)
                    surface.add_triangle(Triangle(p1, p2, p3))
                except IndexError:
                     self.logger.error(f"Simplex index out of bounds for surface '{name}'. Simplex: {simplex}. Points count: {len(unique_points_list)}")
                     continue # Skip this triangle

        except QhullError as qe:
            # QhullError often occurs for degenerate input (e.g., all points collinear)
            self.logger.error(f"Delaunay triangulation failed for '{name}': {qe}. Input points might be degenerate (e.g., collinear). Surface will have points but no triangles.", exc_info=False) # Set exc_info=False for cleaner logs unless debugging Qhull
            # Return surface with points but no triangles - this is often acceptable
            return surface
        except Exception as e:
             # Catch other potential errors during triangulation or processing
             self.logger.exception(f"An unexpected error occurred during TIN generation for '{name}': {e}")
             # Raise a runtime error to indicate a more serious failure
             raise RuntimeError(f"TIN generation failed unexpectedly: {e}") from e

        self.logger.info(f"Generated TIN surface '{name}' with {len(surface.points)} points and {len(surface.triangles)} triangles.")
        return surface

    # Removed the placeholder _create_sample_triangles method
