# digcalc_project/src/core/geometry/surface_builder.py

import logging
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.spatial import Delaunay, QhullError

# Ensure Point3D and Triangle are imported alongside Surface
from ...models.surface import Point3D, Surface, Triangle

logger = logging.getLogger(__name__)

class SurfaceBuilderError(Exception):
    """Custom exception for surface building errors."""


class SurfaceBuilder:
    """Builds a triangulated surface (TIN) from geometric data."""

    @staticmethod
    def build_from_polylines(
        layer_name: str,
        polylines_data: List[Dict[str, Any]], # Expect list of PolylineData dicts
        revision: int, # New argument
    ) -> Surface:
        """Builds a TIN surface from a list of polylines with elevation data.

        Args:
            layer_name: The name of the source layer.
            polylines_data: List of PolylineData dictionaries (must have 'points' and 'elevation').
            revision: The revision number of the source layer data.

        Returns:
            A new Surface object.

        Raises:
            SurfaceBuilderError: If input data is invalid or triangulation fails.

        """
        logger.info(f"Attempting to build surface from layer '{layer_name}' ({len(polylines_data)} polylines).")
        points_3d: List[Tuple[float, float, float]] = []
        unique_pts_check = set()

        # --- Extract 3D Points ---
        for i, poly_dict in enumerate(polylines_data):
            try:
                elevation = poly_dict.get("elevation")
                points_2d = poly_dict.get("points")
                if elevation is None or not points_2d:
                    logger.warning(f"Skipping polyline {i} in layer '{layer_name}' due to missing elevation or points.")
                    continue
                added_from_poly = 0
                for x, y in points_2d:
                    point_tuple = (float(x), float(y), float(elevation))
                    if point_tuple not in unique_pts_check:
                        points_3d.append(point_tuple)
                        unique_pts_check.add(point_tuple)
                        added_from_poly += 1
                if added_from_poly > 0: logger.debug(f"Added {added_from_poly} unique vertices from polyline {i} (Elev: {elevation}).")
            except (TypeError, ValueError, KeyError) as e:
                logger.warning(f"Skipping polyline {i} in layer '{layer_name}' due to data error: {e}", exc_info=True)
                continue

        num_unique_pts = len(points_3d)
        logger.info(f"Extracted {num_unique_pts} unique 3D points with elevation from layer '{layer_name}'.")

        if num_unique_pts < 3:
            raise SurfaceBuilderError(
                f"Cannot build surface from layer '{layer_name}'. "
                f"Requires at least 3 unique points with elevation, but found only {num_unique_pts}.",
            )

        # --- Triangulation ---
        points_array = np.array(points_3d)
        xy_coords = points_array[:, :2]
        faces_np = None # Initialize faces_np
        try:
            logger.debug("Performing Delaunay triangulation...")
            unique_xy, unique_indices = np.unique(xy_coords, axis=0, return_index=True)
            if len(unique_xy) < 3:
                 raise SurfaceBuilderError(
                    f"Cannot build surface from layer '{layer_name}'. "
                    f"Requires at least 3 unique XY locations, but found only {len(unique_xy)}.",
                )
            tri = Delaunay(unique_xy)
            original_indices_map = unique_indices[tri.simplices]
            faces_np = original_indices_map.copy()
            logger.debug(f"Triangulation successful: Generated {len(faces_np)} faces.")
        except QhullError as qe:
             logger.error(f"Delaunay triangulation failed for layer '{layer_name}': {qe}", exc_info=True)
             raise SurfaceBuilderError(
                 f"Triangulation failed for layer '{layer_name}'. Points might be collinear or insufficient. Error: {qe}",
             ) from qe
        except Exception as e:
            logger.exception(f"Unexpected error during triangulation for layer '{layer_name}': {e}")
            raise SurfaceBuilderError(f"An unexpected error occurred during triangulation: {e}") from e

        # --- Create Surface Object ---
        default_surface_name = f"{layer_name}_Surface"
        logger.info(f"Creating Surface object '{default_surface_name}'...")

        # Convert points_array into the required dictionary format with Point3D objects
        surface_points_dict: Dict[str, Point3D] = {}
        for i, (x, y, z) in enumerate(points_array):
            # Create Point3D object (ID will be generated automatically)
            point_obj = Point3D(x=float(x), y=float(y), z=float(z))
            surface_points_dict[point_obj.id] = point_obj # Use point ID as the key

        # Convert faces_np into the required dictionary formats using the NEW point IDs
        # We need a map from the original point index (0, 1, 2...) to the new Point3D ID
        point_id_list = [p.id for p in surface_points_dict.values()] # Assumes order is preserved from enumerate
        # Or more robustly create the list alongside the dict:
        # point_id_list = []
        # surface_points_dict: Dict[str, Point3D] = {}
        # for i, (x, y, z) in enumerate(points_array):
        #     point_obj = Point3D(x=float(x), y=float(y), z=float(z))
        #     surface_points_dict[point_obj.id] = point_obj
        #     point_id_list.append(point_obj.id)

        surface_triangles_dict: Dict[str, Triangle] = {}
        # Assuming faces_np contains indices corresponding to the original points_array order
        for i, face_indices in enumerate(faces_np):
            try:
                # Map original indices to Point3D objects using the points dictionary
                p1_id = point_id_list[face_indices[0]]
                p2_id = point_id_list[face_indices[1]]
                p3_id = point_id_list[face_indices[2]]
                # Create Triangle object using the actual Point3D objects
                triangle = Triangle(p1=surface_points_dict[p1_id],
                                    p2=surface_points_dict[p2_id],
                                    p3=surface_points_dict[p3_id])
                surface_triangles_dict[triangle.id] = triangle # Use triangle ID as key
            except IndexError as e_idx:
                 logger.error(f"Index error creating triangle {i} from face {face_indices}: {e_idx}. Point ID list length: {len(point_id_list)}")
                 continue # Skip this triangle
            except KeyError as e_key:
                 logger.error(f"Key error creating triangle {i} (likely missing point ID): {e_key}. Face indices: {face_indices}")
                 continue # Skip this triangle

        # --- Create Surface object ---
        surface = Surface(
            name=default_surface_name,
            points=surface_points_dict, # Pass dict of Point3D objects
            triangles=surface_triangles_dict, # Pass dict of Triangle objects
            source_layer_name=layer_name,
            source_layer_revision=revision,
        )

        logger.info(f"Successfully built surface '{surface.name}' from layer '{layer_name}' (Rev: {revision}).")
        return surface

def lowest_surface(design: Surface, existing: Surface) -> Surface:
    """Return a Surface whose Z at each (x,y) is the lower of *design* or
    *existing*.

    This helper assumes both Surfaces originate from the **same raster or point
    cloud** so they share identical X/Y coordinates *and* the same
    ``grid_spacing`` value.  That means we can simply iterate over the points
    in parallel and pick the minimum Z without any spatial searching.

    Args:
        design:   The proposed/design surface.
        existing: The existing‐ground surface.

    Returns:
        A new :class:`~digcalc_project.models.surface.Surface` instance called
        "Lowest" coloured yellow for UI visibility.

    """
    assert design.grid_spacing == existing.grid_spacing, "mismatch spacing"

    # Points are stored in dictionaries keyed by UUIDs so the ordering is not
    # guaranteed.  We'll therefore sort them deterministically by coordinate so
    # that *zip()* pairs matching locations together.
    def _sorted(surface: Surface):
        return sorted(
            [(p.x, p.y, p.z) for p in surface.points.values()], key=lambda t: (t[0], t[1]),
        )

    design_pts = _sorted(design)
    existing_pts = _sorted(existing)

    assert len(design_pts) == len(existing_pts), "point count mismatch"

    new_pts = []
    for (x, y, z_d), (_, _, z_e) in zip(design_pts, existing_pts):
        new_pts.append((x, y, min(z_d, z_e)))

    return Surface.from_point_list(
        name="Lowest",
        points=new_pts,
        spacing=design.grid_spacing,
        color="yellow",
    )

# ------------------------------------------------------------------
# Utility helpers for testing / quick-build surfaces
# ------------------------------------------------------------------

def flat_surface(z: float, size: int = 10, name: str = "Flat", spacing: float = 1.0) -> Surface:
    """Generate a simple flat grid :class:`Surface` for tests.

    A square grid of *size* × *size* points (inclusive) is created at the given
    elevation *z*.  The grid spacing defaults to ``1.0`` unit.
    """
    pts = []
    for i in range(size + 1):
        for j in range(size + 1):
            x = i * spacing
            y = j * spacing
            pts.append((x, y, z))

    return Surface.from_point_list(name=name, points=pts, spacing=spacing)
