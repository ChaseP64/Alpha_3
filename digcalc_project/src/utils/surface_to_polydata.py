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
    if not surf.points:
        logger.error(f"Surface '{surf.name}' has no points.")
        raise ValueError(f"Surface '{surf.name}' has no points")

    # Extract vertices and create a mapping from point ID to index
    point_list: list[Point3D] = list(surf.points.values())
    vertex_coordinates = np.array([[p.x, p.y, p.z] for p in point_list], dtype=float)
    
    if vertex_coordinates.ndim != 2 or vertex_coordinates.shape[1] != 3:
        logger.error(
            f"Surface '{surf.name}' vertex coordinates have incorrect shape: {vertex_coordinates.shape}. Expected (N, 3)."
        )
        raise ValueError(
            f"Surface '{surf.name}' vertex coordinates must be a list of (x,y,z) tuples or Nx3 array"
        )
    
    # Ensure points are C-contiguous for PyVista compatibility
    vertex_coordinates = np.ascontiguousarray(vertex_coordinates)

    point_id_to_index_map = {p.id: i for i, p in enumerate(point_list)}

    if surf.triangles:
        face_list = []
        for tri_id, triangle in surf.triangles.items():
            try:
                idx1 = point_id_to_index_map[triangle.p1.id]
                idx2 = point_id_to_index_map[triangle.p2.id]
                idx3 = point_id_to_index_map[triangle.p3.id]
                face_list.extend([3, idx1, idx2, idx3])
            except KeyError as e:
                logger.error(
                    f"Triangle '{tri_id}' in surface '{surf.name}' references a point ID ('{e.args[0]}') that is not in the surface's points dictionary."
                )
                raise ValueError(f"Inconsistent triangle data: Point ID {e} not found in surface points.")
            except AttributeError as e: # Should not happen if types are correct
                 logger.error(f"Error accessing point IDs for triangle '{tri_id}': {e}", exc_info=True)
                 raise ValueError(f"Malformed Triangle object or Point3D reference: {e}")


        if not face_list:
            logger.warning(f"Surface '{surf.name}' has triangles defined, but no valid faces could be constructed. Creating point cloud.")
            mesh = pv.PolyData(vertex_coordinates)
        else:
            faces_array = np.array(face_list, dtype=np.int_)
            mesh = pv.PolyData(vertex_coordinates, faces=faces_array)
    else:
        logger.info(f"Surface '{surf.name}' has no triangles, creating point cloud.")
        mesh = pv.PolyData(vertex_coordinates)

    return mesh 