from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyvista as pv

if TYPE_CHECKING: # pragma: no cover
    from digcalc_project.src.models.surface import Surface # Assumed path

logger = logging.getLogger(__name__)


def surface_to_polydata(surf: "Surface") -> pv.PolyData:
    """
    Convert DigCalc ``Surface`` (TIN) to a PyVista ``PolyData`` mesh.

    Args:
        surf: The ``Surface`` object to convert.

    Returns:
        A ``pyvista.PolyData`` representation of the surface.

    Raises:
        ValueError: If the surface has no vertices or if vertex/triangle
                    data is inconsistent.
    """
    if surf.vertices is None or len(surf.vertices) == 0:
        logger.error(f"Surface '{surf.name}' has no vertices.")
        raise ValueError(f"Surface '{surf.name}' has no vertices")

    points = np.asarray(surf.vertices, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        logger.error(
            f"Surface '{surf.name}' vertices have incorrect shape: {points.shape}. Expected (N, 3)."
        )
        raise ValueError(
            f"Surface '{surf.name}' vertices must be a list of (x,y,z) tuples or Nx3 array"
        )

    # Ensure points are C-contiguous for PyVista compatibility, especially if coming from odd sources
    points = np.ascontiguousarray(points)

    if surf.triangles:
        try:
            # Each triangle is (idx1, idx2, idx3). Prepend with 3 for PyVista format.
            # Ensure triangles are valid indices into points array
            max_idx = np.max(surf.triangles)
            if max_idx >= len(points):
                logger.error(
                    f"Surface '{surf.name}' has triangle vertex index {max_idx} out of bounds "
                    f"for {len(points)} vertices."
                )
                raise ValueError("Triangle index out of bounds for surface vertices.")
            
            # PyVista expects a 1D array: [3, p0_idx, p1_idx, p2_idx, 3, p3_idx, p4_idx, p5_idx, ...]
            faces = np.hstack([[3, *tri] for tri in surf.triangles]).astype(np.int_)
            mesh = pv.PolyData(points, faces=faces)
        except Exception as e:
            logger.exception(
                f"Error processing triangles for surface '{surf.name}'. Triangles: {surf.triangles[:5]}..."
            ) # Log first few triangles
            raise ValueError(f"Could not construct mesh from triangles: {e}")
    else:
        logger.info(f"Surface '{surf.name}' has no triangles, creating point cloud.")
        mesh = pv.PolyData(points)

    return mesh 