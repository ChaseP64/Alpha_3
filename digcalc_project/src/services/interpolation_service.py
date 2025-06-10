"""Interpolation services for generating continuous strata surfaces.

This module provides the core logic for turning discrete borehole depth logs
into continuous 3-D surfaces representing underground material layers.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable, List, Protocol, Tuple

import numpy as np

from ..models.strata_models import StrataSurface
from ..services.settings_service import SettingsService

# --------------------------------------------------------------------------
# Optional SciPy import for performance
# --------------------------------------------------------------------------
try:
    from scipy.spatial import cKDTree

    HAS_SCIPY = True
except ImportError:
    cKDTree = None
    HAS_SCIPY = False


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


class IStrataInterpolator(Protocol):
    """Formal interface for strata-surface interpolation algorithms."""

    def generate_surfaces(
        self,
        project: Project,
        stack: StrataStack,
        existing_surface: Surface,
        progress_cb: ProgressCallback | None = None,
    ) -> List[StrataSurface]:
        ...


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
    ) -> List[StrataSurface]:
        """Generate one interpolated StrataSurface per material layer."""
        if not stack.boreholes or not stack.materials:
            self._logger.warning("Cannot generate strata surfaces: no boreholes or materials.")
            return []

        t0 = time.monotonic()
        total_materials = len(stack.materials)
        surfaces = []

        for i, material in enumerate(stack.materials):
            if progress_cb:
                progress_cb(int(i / total_materials * 100))

            points, values = self._get_points_for_material(stack, material.id)
            if points is None or len(points) < 3:
                self._logger.warning(f"Skipping material '{material.name}': needs at least 3 points.")
                continue

            grid, metadata = self._create_interpolated_grid(project, existing_surface, points, values)
            
            surface = StrataSurface(
                id=i + 1,
                material_id=material.id,
                grid_data=grid,
                grid_metadata=metadata,
            )
            surfaces.append(surface)

        if progress_cb:
            progress_cb(100)
            
        self._logger.info(f"Generated {len(surfaces)} strata surfaces in {time.monotonic() - t0:.2f}s.")
        return surfaces

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
        x_min, y_min, _, x_max, y_max, _ = surface.bounds
        
        grid_x = np.arange(x_min, x_max, cell_size)
        grid_y = np.arange(y_min, y_max, cell_size)
        grid_shape = (len(grid_y), len(grid_x))
        interpolated_grid = np.full(grid_shape, np.nan, dtype=float)

        power = self._settings.strata_idw_power
        radius = self._settings.strata_idw_radius

        tree = cKDTree(points) if HAS_SCIPY else None

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
        
        metadata = {"cell_size": cell_size, "x_min": x_min, "y_min": y_min, "crs": surface.crs}
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
        """Interpolates a chunk of the grid using pure NumPy."""
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