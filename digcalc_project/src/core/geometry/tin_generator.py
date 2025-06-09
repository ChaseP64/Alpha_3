#!/usr/bin/env python3
"""TIN (Triangulated Irregular Network) generator for the DigCalc application.

This module provides functionality to generate TIN surfaces from point clouds.
"""

import logging
from typing import List, Sequence, Union

import numpy as np

# Use the actual Delaunay implementation
try:
    from scipy.spatial import Delaunay
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

        # Surface initializer signature is Surface(name, points=None, triangles=None, ...)
        # so we only provide the name here.  The surface type constant is kept on
        # the class for reference but not required at construction time.
        surface = Surface(name)

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

        # Extract XY coordinates for triangulation
        xy_coords_full = np.array([[p.x, p.y] for p in unique_points_list])

        # ------------------------------------------------------------------
        # Deduplicate identical XY coordinates *before* triangulation.
        # SciPy's Delaunay can handle duplicates, but removing them here
        #   1. avoids Qhull warnings, and
        #   2. guarantees predictable simplex indices for unit-tests.
        # We keep the *first* occurrence of each unique XY pair and later
        # map simplex indices back to the corresponding Point3D objects.
        # ------------------------------------------------------------------
        unique_xy, unique_indices = np.unique(xy_coords_full, axis=0, return_index=True)

        if len(unique_xy) < 3:
            # All XY points are collinear or we have <3 unique locations – no TIN.
            self.logger.warning(
                f"Cannot generate TIN for '{name}': requires at least 3 non-collinear unique XY locations, "
                f"found {len(unique_xy)}.")
            return surface

        # Create a list of Point3D objects matching the deduplicated XY order.
        points_unique = [unique_points_list[i] for i in unique_indices]

        # Perform Delaunay triangulation on the deduplicated coordinates.
        self.logger.debug(
            f"Performing Delaunay triangulation on {len(points_unique)} unique points.")
        delaunay = Delaunay(unique_xy)

        simplices = delaunay.simplices

        self.logger.info(
            f"Delaunay triangulation completed for '{name}', found {len(simplices)} simplices (triangles).")

        # Build Triangle objects – indices reference rows in *points_unique*.
        for simplex in simplices:
            try:
                p1 = points_unique[simplex[0]]
                p2 = points_unique[simplex[1]]
                p3 = points_unique[simplex[2]]

                surface.add_triangle(Triangle(p1, p2, p3))
            except IndexError:
                # Should not happen, but guard just in case.
                self.logger.error(
                    f"Simplex index out of bounds for surface '{name}'. Simplex: {simplex}. "
                    f"Points count: {len(points_unique)}")
                continue

        self.logger.info(f"Generated TIN surface '{name}' with {len(surface.points)} points and {len(surface.triangles)} triangles.")
        return surface

    # Removed the placeholder _create_sample_triangles method

# ==================================================================================================
# Public convenience helper
# --------------------------------------------------------------------------------------------------

def generate_tin(points: Union[np.ndarray, Sequence[Sequence[float]]], name: str = "TIN Surface") -> Surface:
    """Generate a :class:`digcalc_project.src.models.surface.Surface` from raw XYZ points.

    This is a thin wrapper around :class:`TINGenerator` that accepts an *N×3* NumPy
    array (or any similar sequence) and returns a populated :class:`Surface`.

    Args:
        points: Array-like with shape (n, 3) containing *x, y, z* coordinates.
        name:   Optional surface name.

    Returns:
        Surface: A surface object containing the input points and Delaunay triangles.
    """

    points_np = np.asarray(points, dtype=float)
    if points_np.ndim != 2 or points_np.shape[1] != 3:
        raise ValueError("points must be a 2-D array-like with shape (n, 3)")

    # Convert to Point3D list.
    pts: list[Point3D] = [Point3D(float(x), float(y), float(z)) for x, y, z in points_np]

    generator = TINGenerator()
    surface = generator.generate_from_points(pts, name=name)
    return surface
