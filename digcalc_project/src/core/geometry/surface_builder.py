# digcalc_project/src/core/geometry/surface_builder.py

import logging
from typing import List, Tuple, Dict, Optional
import numpy as np
from scipy.spatial import Delaunay, QhullError

# Ensure Point3D and Triangle are imported alongside Surface
from ...models.surface import Surface, Point3D, Triangle
from ...models.project import PolylineData

logger = logging.getLogger(__name__)

class SurfaceBuilderError(Exception):
    """Custom exception for surface building errors."""
    pass

class SurfaceBuilder:
    """Builds a triangulated surface (TIN) from geometric data."""

    @staticmethod
    def build_from_polylines(layer_name: str,
                             polylines: List[PolylineData]) -> Surface:
        """
        Builds a TIN Surface from a list of polylines belonging to a single layer.

        Only vertices from polylines with a non-None elevation are used.
        Requires at least 3 unique points with elevation.

        Args:
            layer_name (str): The name of the source layer (used for error messages).
            polylines (List[PolylineData]): A list of polyline data dictionaries,
                                            each containing 'points' and 'elevation'.

        Returns:
            Surface: The generated Surface object.

        Raises:
            SurfaceBuilderError: If fewer than 3 unique points with elevation are found,
                                 or if triangulation fails.
        """
        logger.info(f"Attempting to build surface from layer '{layer_name}' ({len(polylines)} polylines).")
        pts_3d: List[Tuple[float, float, float]] = []
        unique_pts_check = set()

        # --- Extract 3D Points --- 
        for i, poly_data in enumerate(polylines):
            try:
                elevation = poly_data.get("elevation")
                points = poly_data.get("points", [])
                if elevation is None or not points: continue
                added_from_poly = 0
                for x, y in points:
                    point_tuple = (float(x), float(y), float(elevation))
                    if point_tuple not in unique_pts_check:
                        pts_3d.append(point_tuple)
                        unique_pts_check.add(point_tuple)
                        added_from_poly += 1
                if added_from_poly > 0: logger.debug(f"Added {added_from_poly} unique vertices from polyline {i} (Elev: {elevation}).")
            except (TypeError, ValueError, KeyError) as e:
                logger.warning(f"Skipping polyline {i} in layer '{layer_name}' due to data error: {e}", exc_info=True)
                continue

        num_unique_pts = len(pts_3d)
        logger.info(f"Extracted {num_unique_pts} unique 3D points with elevation from layer '{layer_name}'.")

        if num_unique_pts < 3:
            raise SurfaceBuilderError(
                f"Cannot build surface from layer '{layer_name}'. "
                f"Requires at least 3 unique points with elevation, but found only {num_unique_pts}."
            )

        # --- Triangulation --- 
        vertices_np = np.array(pts_3d)
        xy_coords = vertices_np[:, :2]
        faces_np = None # Initialize faces_np
        try:
            logger.debug("Performing Delaunay triangulation...")
            unique_xy, unique_indices = np.unique(xy_coords, axis=0, return_index=True)
            if len(unique_xy) < 3:
                 raise SurfaceBuilderError(
                    f"Cannot build surface from layer '{layer_name}'. "
                    f"Requires at least 3 unique XY locations, but found only {len(unique_xy)}."
                )
            tri = Delaunay(unique_xy)
            original_indices_map = unique_indices[tri.simplices]
            faces_np = original_indices_map.copy()
            logger.debug(f"Triangulation successful: Generated {len(faces_np)} faces.")
        except QhullError as qe:
             logger.error(f"Delaunay triangulation failed for layer '{layer_name}': {qe}", exc_info=True)
             raise SurfaceBuilderError(
                 f"Triangulation failed for layer '{layer_name}'. Points might be collinear or insufficient. Error: {qe}"
             ) from qe
        except Exception as e:
            logger.exception(f"Unexpected error during triangulation for layer '{layer_name}': {e}")
            raise SurfaceBuilderError(f"An unexpected error occurred during triangulation: {e}") from e

        # --- Create Surface Object --- 
        default_surface_name = f"{layer_name}_Surface"
        logger.info(f"Creating Surface object '{default_surface_name}'...")

        # --- FIX: Create Surface and add points/triangles correctly --- 
        # 1. Create empty surface
        surface = Surface(name=default_surface_name, surface_type=Surface.SURFACE_TYPE_TIN)

        # 2. Create Point3D objects and store mapping from original index to Point3D
        index_to_point3d: Dict[int, Point3D] = {}
        for i, vertex in enumerate(vertices_np):
            try:
                 # Use try-except for robust float conversion
                 point = Point3D(x=float(vertex[0]), y=float(vertex[1]), z=float(vertex[2]))
                 surface.add_point(point) # Adds to surface.points dictionary
                 index_to_point3d[i] = point # Map original index to the Point3D object
            except (ValueError, TypeError, IndexError) as p_err:
                 logger.warning(f"Could not create Point3D from vertex data at index {i}: {vertex}. Error: {p_err}. Skipping point.")
                 continue # Skip this point if invalid
        logger.info(f"Added {len(surface.points)} points to surface '{surface.name}'.")

        # 3. Create Triangles using the mapped Point3D objects
        if faces_np is not None:
             num_faces_added = 0
             num_skipped_faces = 0
             for face_indices in faces_np:
                 try:
                     # Use the mapping to get the actual Point3D objects
                     # Check if all indices were successfully mapped in the previous step
                     if any(idx not in index_to_point3d for idx in face_indices):
                         logger.warning(f"Skipping face with invalid vertex index: {face_indices}")
                         num_skipped_faces += 1
                         continue
                     p1 = index_to_point3d[face_indices[0]]
                     p2 = index_to_point3d[face_indices[1]]
                     p3 = index_to_point3d[face_indices[2]]
                     triangle = Triangle(p1=p1, p2=p2, p3=p3)
                     surface.add_triangle(triangle) # Adds to surface.triangles
                     num_faces_added += 1
                 except (KeyError, IndexError) as e:
                      logger.warning(f"Skipping invalid face during surface creation: Indices={face_indices}, Error={e}")
                      num_skipped_faces += 1
                 except Exception as tri_err: # Catch other potential errors during Triangle creation
                      logger.error(f"Unexpected error creating triangle for indices {face_indices}: {tri_err}", exc_info=True)
                      num_skipped_faces += 1
             logger.info(f"Added {num_faces_added} triangles to surface '{surface.name}'. Skipped {num_skipped_faces} faces.")
        else:
             logger.warning(f"No faces generated by triangulation for surface '{surface.name}'. Surface will have points only.")
        # --- END FIX --- 

        logger.info(f"Successfully built surface '{surface.name}' from layer '{layer_name}'.")
        return surface 