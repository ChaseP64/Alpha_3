"""Interpolation services for generating continuous strata surfaces.

This module provides the core logic for turning discrete borehole depth logs
into continuous 3-D surfaces representing underground material layers.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable, List, Tuple
import os
import math

import numpy as np
from PySide6.QtCore import QThread, Signal

from ..models.strata_models import StrataSurface
from ..services.settings_service import SettingsService
from ..utils.array_cache import save_grid

# --------------------------------------------------------------------------
# Optional SciPy import for performance
# --------------------------------------------------------------------------
try:
    from scipy.spatial import cKDTree

    HAS_SCIPY = True
except ImportError:
    cKDTree = None
    HAS_SCIPY = False

# --------------------------------------------------------------------------
# Optional Shapely import for contour triangulation
# --------------------------------------------------------------------------
try:
    from shapely.geometry import Polygon, Point
    from shapely.ops import triangulate as shp_triangulate
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

# Optional numba for JIT hot-paths -------------------------------------------------
try:
    from numba import njit, prange  # type: ignore
    HAS_NUMBA = True
except ImportError:  # pragma: no cover – CI may lack numba
    njit = lambda f: f  # No-op decorator if numba is not available
    HAS_NUMBA = False

# ---------------------------------------------------------------------------
# Lazy import hints
# ---------------------------------------------------------------------------
if TYPE_CHECKING:
    from ..models.project import Project
    from ..models.strata_models import StrataStack
    from ..models.surface import Surface
    from scipy.spatial import cKDTree

ProgressCallback = Callable[[int], None]
logger = logging.getLogger(__name__)


class IDWInterpolator:
    """Inverse-Distance-Weighting (IDW) strata interpolator.

    This implementation uses a chunked approach to keep memory usage low,
    and it leverages ``scipy.spatial.cKDTree`` for fast nearest-neighbor
    searches if available, with a pure-NumPy fallback.
    """

    CHUNK_SIZE = 256  # Process grid in 256x256 tiles

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._settings = SettingsService()
        if not HAS_SCIPY:
            self._logger.warning("SciPy not found. Using pure-NumPy fallback for IDW (slower).")

    def generate_surfaces(
        self,
        project: Project,
        stack: StrataStack,
        existing_surface: Surface,
        progress_cb: ProgressCallback | None = None,
    ) -> GeneratedSurfaces:
        """Generate one interpolated StrataSurface per material layer.

        If contour‐based strata polylines exist for a given material, a grid
        derived from those contours is blended with the borehole‐IDW grid by
        taking the *minimum* Z at each cell (contours represent upper bound).
        """
        if not stack.materials:
            self._logger.warning("Cannot generate strata surfaces: no materials defined.")
            return GeneratedSurfaces([], 0.0)

        # --- Collect contour polylines per material --------------------------------
        contours_by_mat: dict[int, list[list[tuple[float, float, float]]]] = {}
        traced = getattr(project, "traced_polylines", None)
        if traced:
            for layer_polys in traced.values():
                for poly in layer_polys:
                    if not isinstance(poly, dict):
                        continue
                    if not poly.get("is_strata"):
                        continue
                    mat_id = poly.get("material_id")
                    if mat_id is None:
                        continue
                    contours_by_mat.setdefault(int(mat_id), []).append(poly["points"])
        # ---------------------------------------------------------------------------

        t0 = time.monotonic()
        total_materials = len(stack.materials)
        surfaces: list[StrataSurface] = []
        all_squared_errors: list[float] = []

        for i, material in enumerate(stack.materials):
            if progress_cb:
                progress_cb(int(i / total_materials * 100))

            # 1) Borehole points ------------------------------------------------------
            points, values = self._get_points_for_material(stack, material.id)
            idw_grid = None
            idw_meta = None
            if points is not None and len(points) >= 3:
                idw_grid, idw_meta = self._create_interpolated_grid(project, existing_surface, points, values)

            # 2) Contour grid ---------------------------------------------------------
            contour_grid = None
            contour_meta = None
            if HAS_SHAPELY and material.id in contours_by_mat:
                contour_grid, contour_meta = self._create_contour_grid(project, existing_surface, contours_by_mat[material.id])
            elif material.id in contours_by_mat and not HAS_SHAPELY:
                self._logger.warning("Shapely not installed – skipping contour triangulation for material %s", material.name)

            # 3) Merge ---------------------------------------------------------------
            final_grid = None
            final_meta = None
            if idw_grid is not None and contour_grid is not None:
                # Align shapes; if cell_size differs, resample contour_grid via nearest-neighbour
                if idw_meta["cell_size"] != contour_meta["cell_size"]:
                    # Simple fallback: use larger cell size (coarser)
                    cell_size = max(idw_meta["cell_size"], contour_meta["cell_size"])
                    # For brevity, we simply resample both grids onto new grid covering extents.
                    final_grid, final_meta = self._merge_grids([ (idw_grid,idw_meta), (contour_grid,contour_meta) ], cell_size)
                else:
                    # Same resolution, overlap extents? assume same for now
                    final_grid = np.minimum(idw_grid, contour_grid)
                    final_meta = idw_meta
            elif idw_grid is not None:
                final_grid, final_meta = idw_grid, idw_meta
            elif contour_grid is not None:
                final_grid, final_meta = contour_grid, contour_meta

            if final_grid is None:
                self._logger.warning("Skipping material '%s': no valid source data.", material.name)
                continue

            # Calculate RMSE only when borehole data exists
            if idw_grid is not None and points is not None:
                for point, value in zip(points, values):
                    interpolated_z = self._get_value_from_grid(final_grid, final_meta, point[0], point[1])
                    if interpolated_z is not None and np.isfinite(interpolated_z):
                        all_squared_errors.append((interpolated_z - value) ** 2)

            surface = StrataSurface(
                id=i + 1,
                material_id=material.id,
                grid_data=final_grid,
                grid_metadata=final_meta,
            )
            surfaces.append(surface)

        if progress_cb:
            progress_cb(100)

        self._last_rmse = np.sqrt(np.mean(all_squared_errors)) if all_squared_errors else 0.0
        self._logger.info(
            "Generated %d strata surfaces in %.2fs (RMSE %.4f)",
            len(surfaces), time.monotonic() - t0, self._last_rmse,
        )
        return GeneratedSurfaces(surfaces, self._last_rmse)

    def _get_points_for_material(self, stack: StrataStack, material_id: int) -> Tuple[np.ndarray | None, np.ndarray | None]:
        """Extracts XY points and Z values for a given material from boreholes."""
        points, values = [], []
        for borehole in stack.boreholes:
            for layer in borehole.layers:
                if layer.material_id == material_id:
                    # BoreholeLog stores explicit x/y coordinates
                    points.append((borehole.x, borehole.y))
                    # Use the *top* z-elevation of the layer as sample value
                    values.append(layer.top_z)
                    break
        
        if not points:
            return None, None
            
        return np.array(points), np.array(values)

    def _get_value_from_grid(self, grid: np.ndarray, meta: dict, x: float, y: float) -> float | None:
        """Gets an interpolated value from a grid at a given XY coordinate using nearest-neighbor."""
        if 'x_min' not in meta or 'y_min' not in meta or 'cell_size' not in meta or meta['cell_size'] == 0:
            return None

        col = (x - meta['x_min']) / meta['cell_size']
        row = (y - meta['y_min']) / meta['cell_size']

        r_idx, c_idx = int(round(row)), int(round(col))

        if not (0 <= r_idx < grid.shape[0] and 0 <= c_idx < grid.shape[1]):
            return None
            
        return grid[r_idx, c_idx]

    def _calculate_adaptive_cell_size(self, project: Project) -> float:
        """Determines grid cell size."""
        base_grid = getattr(project, "base_grid", 0)
        min_thickness = getattr(project, "min_thickness", 0)
        
        adaptive_size = 0
        if min_thickness > 0:
            adaptive_size = min_thickness / 2
            
        if base_grid > 0:
            return max(base_grid, adaptive_size)
        if adaptive_size > 0:
            return adaptive_size

        return self._settings.strata_default_cell_size

    def _create_interpolated_grid(
        self,
        project: Project,
        surface: Surface,
        points: np.ndarray,
        values: np.ndarray,
    ) -> Tuple[np.ndarray, dict]:
        """Creates a grid by interpolating values across chunks."""
        cell_size = self._calculate_adaptive_cell_size(project)
        x_min, y_min, x_max, y_max = self._surface_xy_bounds(surface)
        
        grid_x = np.arange(x_min, x_max, cell_size)
        grid_y = np.arange(y_min, y_max, cell_size)
        grid_shape = (len(grid_y), len(grid_x))
        interpolated_grid = np.full(grid_shape, np.nan, dtype=float)

        power = self._settings.strata_idw_power
        radius = self._settings.strata_idw_radius

        # SciPy monkey-patch in unit-tests may set *HAS_SCIPY* True even when
        # the library is not actually installed (cKDTree == None).  Guard
        # against this scenario so that fallbacks continue to work.
        tree = cKDTree(points) if HAS_SCIPY and cKDTree is not None else None

        for r in range(0, grid_shape[0], self.CHUNK_SIZE):
            for c in range(0, grid_shape[1], self.CHUNK_SIZE):
                r_end = min(r + self.CHUNK_SIZE, grid_shape[0])
                c_end = min(c + self.CHUNK_SIZE, grid_shape[1])
                
                chunk_coords_x, chunk_coords_y = np.meshgrid(grid_x[c:c_end], grid_y[r:r_end])
                chunk_grid_points = np.vstack([chunk_coords_x.ravel(), chunk_coords_y.ravel()]).T

                if HAS_SCIPY and tree is not None:
                    z_values = self._interpolate_chunk_scipy(tree, chunk_grid_points, values, radius, power)
                else:
                    z_values = self._interpolate_chunk_numpy(points, chunk_grid_points, values, radius, power)
                
                interpolated_grid[r:r_end, c:c_end] = z_values.reshape(r_end - r, c_end - c)
        
        metadata = {"cell_size": cell_size, "x_min": x_min, "y_min": y_min, "crs": getattr(surface,"crs",None)}
        return interpolated_grid, metadata

    def _interpolate_chunk_scipy(self, tree: Any, grid_points: np.ndarray, values: np.ndarray, radius: float, power: int) -> np.ndarray:
        """Interpolates a chunk of the grid using SciPy's cKDTree."""
        # Get lists of neighbor indices for each grid point within the search radius
        neighbour_idx_lists = tree.query_ball_point(grid_points, r=radius)

        z_values = np.full(grid_points.shape[0], np.nan)

        for i, idx_list in enumerate(neighbour_idx_lists):
            if not idx_list:
                # No neighbours – leave as NaN
                continue

            dists = np.linalg.norm(tree.data[idx_list] - grid_points[i], axis=1)

            # If a grid node coincides with a sample point, take its value directly
            if np.any(dists < 1e-10):
                z_values[i] = values[idx_list[np.argmin(dists)]]
                continue

            weights = 1.0 / dists**power
            z_values[i] = float(np.sum(weights * values[idx_list]) / np.sum(weights))

        return z_values

    def _interpolate_chunk_numpy(self, points: np.ndarray, grid_points: np.ndarray, values: np.ndarray, radius: float, power: int) -> np.ndarray:
        """Interpolates a chunk using NumPy or numba-accelerated kernel."""
        if HAS_NUMBA and '_idw_numba' in globals():
            return _idw_numba(points, values, grid_points, radius, power)
        # fallback pure numpy
        z_values = np.full(grid_points.shape[0], np.nan)
        for i, p_grid in enumerate(grid_points):
            distances = np.sqrt(np.sum((points - p_grid)**2, axis=1))
            mask = distances < radius
            if not np.any(mask):
                continue
            d_masked, v_masked = distances[mask], values[mask]
            if np.any(d_masked < 1e-10):
                z_values[i] = v_masked[np.argmin(d_masked)]
                continue
            weights = 1.0 / d_masked**power
            z_values[i] = np.sum(weights * v_masked) / np.sum(weights)
        return z_values

    # ------------------------------------------------------------------
    # Contour helpers
    # ------------------------------------------------------------------
    def _create_contour_grid(self, project: "Project", surface: "Surface", polylines: list[list[tuple[float,float,float]]]):
        """Rasterise closed contour polylines into a constant‐Z grid.

        Assumes each polyline is closed and all vertices share identical Z.
        Cells inside any polygon take that Z; others are NaN.
        If multiple polygons overlap, the *minimum* Z is used per cell.
        """
        if not HAS_SHAPELY:
            raise RuntimeError("Shapely not available")

        cell_size = self._calculate_adaptive_cell_size(project)
        x_min, y_min, x_max, y_max = self._surface_xy_bounds(surface)
        gx = np.arange(x_min, x_max, cell_size)
        gy = np.arange(y_min, y_max, cell_size)
        grid = np.full((len(gy), len(gx)), np.nan, dtype=float)

        for pts in polylines:
            if len(pts) < 3:
                continue
            # Ensure ring closed in 2D
            ring_coords2d = [(p[0], p[1]) for p in pts]
            if ring_coords2d[0] != ring_coords2d[-1]:
                ring_coords2d.append(ring_coords2d[0])
            poly = Polygon(ring_coords2d)
            if not poly.is_valid or poly.area == 0:
                continue
            # Uniform Z assumed
            z_val = pts[0][2] if len(pts[0]) >= 3 else 0.0
            # Fill grid cells whose center falls inside polygon
            for r, y in enumerate(gy):
                for c, x in enumerate(gx):
                    cx = x + cell_size * 0.5
                    cy = y + cell_size * 0.5
                    if poly.contains(Point(cx, cy)):
                        if math.isnan(grid[r, c]) or z_val < grid[r, c]:
                            grid[r, c] = z_val
        meta = {"cell_size": cell_size, "x_min": x_min, "y_min": y_min, "crs": getattr(surface,"crs",None)}
        return grid, meta

    def _merge_grids(self, grids_meta: list[tuple[np.ndarray, dict]], cell_size: float):
        """Resamples provided grids to common resolution & extent taking min Z."""
        # Determine combined extents
        xs = []
        ys = []
        for _, meta in grids_meta:
            xs.extend([meta["x_min"], meta["x_min"] + meta["cell_size"] * _.shape[1]])
            ys.extend([meta["y_min"], meta["y_min"] + meta["cell_size"] * _.shape[0]])
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        gx = np.arange(x_min, x_max, cell_size)
        gy = np.arange(y_min, y_max, cell_size)
        merged = np.full((len(gy), len(gx)), np.nan, dtype=float)
        # Helper to paste grid
        for grid, meta in grids_meta:
            for r_idx in range(grid.shape[0]):
                for c_idx in range(grid.shape[1]):
                    z = grid[r_idx, c_idx]
                    if np.isnan(z):
                        continue
                    x = meta["x_min"] + c_idx * meta["cell_size"]
                    y = meta["y_min"] + r_idx * meta["cell_size"]
                    C = int((x - x_min) / cell_size)
                    R = int((y - y_min) / cell_size)
                    if 0 <= R < merged.shape[0] and 0 <= C < merged.shape[1]:
                        if math.isnan(merged[R, C]) or z < merged[R, C]:
                            merged[R, C] = z
        meta = {"cell_size": cell_size, "x_min": x_min, "y_min": y_min, "crs": grids_meta[0][1].get("crs")}
        return merged, meta

    def _surface_xy_bounds(self, surface: "Surface"):
        """Return (x_min, y_min, x_max, y_max) bounds from Surface or sensible default."""
        if hasattr(surface, "get_bounds"):
            b = surface.get_bounds()
            if b is not None:
                x_min, y_min, x_max, y_max = b
                return x_min, y_min, x_max, y_max
        # Support lightweight mocks that expose a ``bounds`` tuple attribute
        if hasattr(surface, "bounds") and isinstance(surface.bounds, (tuple, list)) and len(surface.bounds) >= 4:
            b = surface.bounds
            return float(b[0]), float(b[1]), float(b[3]), float(b[4]) if len(b) > 4 else float(b[2])
        # Fallback – derive from points if any
        if surface.points:
            xs = [p.x for p in surface.points.values()]
            ys = [p.y for p in surface.points.values()]
            return min(xs), min(ys), max(xs), max(ys)
        # Default 0..100 square
        return 0.0, 0.0, 100.0, 100.0


class StrataJob(QThread):
    """Asynchronous worker for running strata interpolation."""
    progress = Signal(int)
    finished = Signal(list, float)  # surfaces, rmse

    def __init__(self, interpolator: IDWInterpolator, project: 'Project', stack: 'StrataStack', existing_surface: 'Surface', cache_dir: str):
        super().__init__()
        self.interpolator = interpolator
        self.project = project
        self.stack = stack
        self.existing_surface = existing_surface
        self.cache_dir = cache_dir
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def run(self):
        """Execute the interpolation and emit results."""
        self._logger.info("Starting asynchronous strata generation job.")
        try:
            surfaces = self.interpolator.generate_surfaces(
                self.project, self.stack, self.existing_surface, self.progress.emit
            )
            self._write_caches(surfaces)
            rmse_val = getattr(self.interpolator, "_last_rmse", -1.0)
            self.finished.emit(surfaces, rmse_val)
            self._logger.info(
                "Asynchronous strata generation job finished successfully with RMSE: %.4f",
                rmse_val,
            )
        except Exception as e:
            self._logger.exception(f"Strata generation job failed: {e}")
            self.finished.emit([], -1.0)

    def _write_caches(self, surfaces: List[StrataSurface]):
        """Saves generated surface grids to compressed .npz files."""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            self._logger.info(f"Created cache directory: {self.cache_dir}")

        for surface in surfaces:
            # Find the material name for a more descriptive filename
            material = next((m for m in self.stack.materials if m.id == surface.material_id), None)
            mat_name = material.name.replace(" ", "_") if material else f"unknown_mat_{surface.material_id}"
            
            # Using project UUID and material name to ensure unique cache file
            filename = f"strata_cache_{self.project.id}_{mat_name}.npz"
            path = os.path.join(self.cache_dir, filename)
            
            try:
                save_grid(path, surface.grid_data, surface.grid_metadata)
            except Exception as e:
                self._logger.error(f"Failed to write cache file {path}: {e}")

if HAS_NUMBA:
    @njit(parallel=True, fastmath=True)
    def _idw_numba(points: np.ndarray, values: np.ndarray, gp: np.ndarray, radius: float, power: int):
        m = gp.shape[0]
        out = np.empty(m, dtype=np.float64)
        for i in prange(m):
            wsum = 0.0
            vsum = 0.0
            gx = gp[i, 0]
            gy = gp[i, 1]
            for j in range(points.shape[0]):
                dx = points[j, 0] - gx
                dy = points[j, 1] - gy
                d2 = dx * dx + dy * dy
                if d2 >= radius * radius or d2 < 1e-20:
                    if d2 < 1e-20:
                        out[i] = values[j]
                        wsum = -1.0  # mark direct hit
                        break
                    continue
                w = 1.0 / (d2 ** (power / 2.0))
                wsum += w
                vsum += w * values[j]
            if wsum <= 0.0:
                out[i] = np.nan
            else:
                out[i] = vsum / wsum
        return out 

# ---------------------------------------------------------------------------
# Helper wrapper so generate_surfaces returns an object that acts like a list
# *and* can be unpacked into ``(surfaces, rmse)`` for backward-compatibility.
# ---------------------------------------------------------------------------


class GeneratedSurfaces(list):
    """List subclass that also carries RMSE and supports tuple-unpacking."""

    def __init__(self, surfaces: list["StrataSurface"], rmse: float):
        super().__init__(surfaces)
        self.rmse = rmse

    # When users do ``surfaces, rmse = generate_surfaces(...)`` we yield
    # *self* (the list) followed by the rmse value.
    def __iter__(self):
        return iter((self, self.rmse))

    # Optional nice repr
    def __repr__(self):
        return f"GeneratedSurfaces(len={len(self)}, rmse={self.rmse:.4f})" 