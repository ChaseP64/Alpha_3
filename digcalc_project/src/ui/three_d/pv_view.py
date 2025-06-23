import numpy as np
import pyvista as pv


# TODO: Add type hint for 'surface' after confirming its type
def surface_to_polydata(surface):
    """Converts Surface (TIN/grid) to PyVista PolyData with 'dz' scalar
    if surface has cut/fill map in surface.dz_grid, else just elevation.

    Args:
        surface: The Surface object to convert (likely from src.models.surface.Surface).

    Returns:
        pyvista.PolyData: A PyVista mesh representation of the surface.

    """
    # ------------------------------------------------------------------
    # Build point array (handle both list-of-tuples and dict-of-Point3D)
    # ------------------------------------------------------------------
    if isinstance(surface.points, dict):
        # Assume dict of Point3D instances
        point_items = list(surface.points.values())
        pts = np.array([[p.x, p.y, p.z] for p in point_items], dtype=float)
        id_to_index = {p.id: idx for idx, p in enumerate(point_items)}
    else:
        # Assume iterable of (x, y, z) tuples
        pts = np.array([[x, y, z] for x, y, z in surface.points], dtype=float)
        id_to_index = None  # Not needed for tuple-based triangles

    # ------------------------------------------------------------------
    # Build faces array if triangles are present and reference by objects or indices
    # ------------------------------------------------------------------
    faces = None
    if hasattr(surface, "triangles") and surface.triangles:
        # If triangles is a dict of Triangle objects
        first = next(iter(surface.triangles.values()))
        if hasattr(first, "p1"):
            # Triangle object path
            face_list = []
            for tri in surface.triangles.values():
                if id_to_index is None:
                    continue  # Should not happen
                face_list.extend([3,
                                  id_to_index.get(tri.p1.id, -1),
                                  id_to_index.get(tri.p2.id, -1),
                                  id_to_index.get(tri.p3.id, -1)])
            faces = np.array(face_list, dtype=int)
        else:
            # Assume list/iterable of index triplets
            faces = np.hstack([np.full((len(surface.triangles), 1), 3),
                               np.array(list(surface.triangles))]).ravel()

    if faces is not None and faces.size > 0:
        mesh = pv.PolyData(pts, faces=faces)
    else:                                                # grid => surf
        # Reason: If no triangles, assume it's a point grid and use Delaunay 2D
        # to create a surface mesh.
        mesh = pv.PolyData(pts)
        mesh = mesh.delaunay_2d() # Apply Delaunay triangulation

    # Reason: Check for cut/fill data (dz_grid) and add it as scalars 'dz'.
    # Otherwise, use the Z elevation as the default 'dz' scalar.
    if getattr(surface, "dz_grid", None) is not None:
        # Ensure dz_grid is iterable and has the expected structure
        try:
            dz = np.array([d for _, _, d in surface.dz_grid])
            # Basic check: Ensure dz array has the same size as the number of points
            if dz.shape[0] == pts.shape[0]:
                 mesh["dz"] = dz
            else:
                 # Fallback or raise error if dimensions mismatch
                 print(f"Warning: dz_grid size ({dz.shape[0]}) mismatch with points ({pts.shape[0]}). Using elevation.")
                 mesh["dz"] = pts[:, 2] # Fallback to elevation
        except (TypeError, ValueError) as e:
            print(f"Warning: Could not process dz_grid: {e}. Using elevation.")
            mesh["dz"] = pts[:, 2] # Fallback to elevation

    else:
        mesh["dz"] = pts[:, 2] # Use Z coordinate if no dz_grid

    return mesh
