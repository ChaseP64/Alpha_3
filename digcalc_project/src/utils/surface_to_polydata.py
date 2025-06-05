from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyvista as pv

if TYPE_CHECKING: # pragma: no cover
    from digcalc_project.src.models.surface import Surface, Point3D # Assumed path

logger = logging.getLogger(__name__)


def surface_to_polydata(surf: "Surface") -> pv.PolyData:
    """
    Convert DigCalc ``Surface`` (TIN) to a PyVista ``PolyData`` mesh.

    Args:
        surf: The ``Surface`` object to convert.

    Returns:
        A ``pyvista.PolyData`` representation of the surface.

    Raises:
        ValueError: If the surface has no points or if point/triangle
                    data is inconsistent.
    """
    # ------------------------------------------------------------------
    # Determine which data representation the Surface is using.
    # ------------------------------------------------------------------
    use_points_dict = bool(getattr(surf, "points", None))

    if use_points_dict:
        # --------------------------------------------------------------
        # Newer representation – points/triangles are dictionaries with
        # Point3D / Triangle objects.
        # --------------------------------------------------------------
        point_list: list[Point3D] = list(surf.points.values())

        if not point_list:
            logger.error(f"Surface '{surf.name}' has no vertices.")
            raise ValueError(f"Surface '{surf.name}' has no vertices")

        vertex_coordinates = np.array([[p.x, p.y, p.z] for p in point_list], dtype=float)

        if vertex_coordinates.ndim != 2 or vertex_coordinates.shape[1] != 3:
            logger.error(
                f"Surface '{surf.name}' vertex coordinates have incorrect shape: {vertex_coordinates.shape}. Expected (N, 3)."
            )
            raise ValueError(
                "vertices must be a list of (x,y,z) tuples or Nx3 array"
            )

        vertex_coordinates = np.ascontiguousarray(vertex_coordinates)
        point_id_to_index_map = {p.id: i for i, p in enumerate(point_list)}

        face_list: list[int] = []
        if surf.triangles:
            for tri_id, triangle in surf.triangles.items():
                try:
                    idx1 = point_id_to_index_map[triangle.p1.id]
                    idx2 = point_id_to_index_map[triangle.p2.id]
                    idx3 = point_id_to_index_map[triangle.p3.id]
                    face_list.extend([3, idx1, idx2, idx3])
                except KeyError:
                    logger.error(
                        f"Triangle '{tri_id}' in surface '{surf.name}' references a point ID that is not in the surface's points dictionary."
                    )
                    raise ValueError("Triangle index out of bounds")
                except AttributeError as e:
                    logger.error(f"Malformed Triangle object: {e}")
                    raise ValueError("Malformed Triangle object or Point3D reference")

        # Create mesh --------------------------------------------------
        if face_list:
            faces_array = np.array(face_list, dtype=np.int_)
            mesh = pv.PolyData(vertex_coordinates, faces=faces_array)
        else:
            # No triangles – point cloud
            mesh = pv.PolyData(vertex_coordinates)

        return mesh

    # --------------------------------------------------------------
    # Legacy representation – expect .vertices and .triangles lists.
    # --------------------------------------------------------------
    vertices = getattr(surf, "vertices", None)
    if vertices is None or len(vertices) == 0:
        logger.error(f"Surface '{surf.name}' has no vertices.")
        raise ValueError(f"Surface '{surf.name}' has no vertices")

    # Accept list of tuples or numpy array
    vertex_coordinates = np.asarray(vertices, dtype=float)

    if vertex_coordinates.ndim != 2 or vertex_coordinates.shape[1] != 3:
        logger.error(
            f"Surface '{surf.name}' vertex coordinates have incorrect shape: {vertex_coordinates.shape}. Expected (N, 3)."
        )
        raise ValueError(
            "vertices must be a list of (x,y,z) tuples or Nx3 array"
        )

    vertex_coordinates = np.ascontiguousarray(vertex_coordinates)

    triangles = getattr(surf, "triangles", None)

    if triangles:
        # Validate indices are within bounds
        face_list: list[int] = []
        for tri in triangles:
            if len(tri) != 3:
                logger.error(f"Surface '{surf.name}' triangle does not have 3 indices: {tri}")
                raise ValueError("Triangle index out of bounds")
            if max(tri) >= len(vertex_coordinates) or min(tri) < 0:
                logger.error(f"Surface '{surf.name}' triangle index out of bounds: {tri}")
                raise ValueError("Triangle index out of bounds")
            face_list.extend([3, *tri])

        faces_array = np.array(face_list, dtype=np.int_)
        mesh = pv.PolyData(vertex_coordinates, faces=faces_array)
    else:
        # No triangles – point cloud with vertices cells
        mesh = pv.PolyData(vertex_coordinates)

    return mesh 