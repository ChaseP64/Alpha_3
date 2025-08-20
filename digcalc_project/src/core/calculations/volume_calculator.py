#!/usr/bin/env python3
"""Volume calculator for the DigCalc application.

This module provides functionality to calculate volumes between surfaces.
"""

from __future__ import annotations  # Postpone evaluation of annotations (PEP 563)

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from ...models.calculation import SliceResult
from ...models.project import Project
from ...models.strata_models import StrataStack

# Use relative import
from ...models.surface import Surface
from ...services.settings_service import SettingsService

# ---------------------------------------------------------------------------
# Optional external dependencies
# ---------------------------------------------------------------------------
# We need Shapely classes for type annotations, but we also want DigCalc to run
# even when Shapely is not installed.  By importing them under a TYPE_CHECKING
# guard we satisfy static type checkers without creating a hard runtime
# dependency.  At runtime we fall back to lightweight stubs.
# ---------------------------------------------------------------------------

if TYPE_CHECKING:  # pragma: no cover – static analysis only
    from shapely.errors import GEOSException  # noqa: F401
    from shapely.geometry import LineString, Point, Polygon  # noqa: F401
else:
    try:
        from shapely.errors import GEOSException  # type: ignore
        from shapely.geometry import LineString, Point, Polygon  # type: ignore
    except ImportError:  # pragma: no cover – Shapely missing at runtime
        logging.getLogger(__name__).warning(
            "Shapely not found. Region-based stripping will not work. "
            "Using stub geometry classes instead."
        )

        class _GeometryStub:  # minimal stand-in so type annotations remain valid
            """Fallback stub used when Shapely is not installed (runtime only)."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401 – trivial stub
                pass

        Point = _GeometryStub  # type: ignore
        Polygon = _GeometryStub  # type: ignore
        LineString = _GeometryStub  # type: ignore

        class GEOSException(Exception):
            """Stub replacement for Shapely's GEOSException."""

            pass


from digcalc_project.src.core.calculations.mass_haul import HaulStation

__all__ = ["VolumeCalculator", "calculate_mass_haul_by_material"]

# ---------------------------------------------------------------------------
# Optional static-only imports – these are evaluated *only* by type checkers
# so we avoid a hard runtime dependency on Shapely (DigCalc can run without
# it).  ``from __future__ import annotations`` above ensures the annotations
# remain as strings at runtime.
# ---------------------------------------------------------------------------
if TYPE_CHECKING:  # pragma: no cover
    from shapely.geometry import LineString  # noqa: F401 – used for type hints only


class VolumeCalculator:
    """Calculator for volumes between surfaces."""

    def __init__(self, project: Project):
        """Initialize the volume calculator with the project context."""
        self.logger = logging.getLogger(__name__)
        self.project = project

    def calculate_grid_method(
        self, surface1: Surface, surface2: Surface, grid_resolution: float = 1.0
    ) -> Dict[str, Any]:
        """Calculates cut, fill, net volumes, and the difference grid between two surfaces.

        Args:
            surface1 (Surface): The existing terrain surface model (or first surface).
            surface2 (Surface): The proposed design surface model (or second surface).
            grid_resolution (float): The side length of the square grid cells.

        Returns:
            Dict[str, Any]: A dictionary containing:
                - 'cut': Total volume where surface1 > surface2 (float).
                - 'fill': Total volume where surface2 > surface1 (float).
                - 'net': fill - cut (float).
                - 'dz_grid': 2D np.ndarray of elevation differences (surface2 - surface1),
                             shape (num_y_cells, num_x_cells). NaN where no data.
                - 'grid_x': 1D np.ndarray of X coordinates for grid cell centers/edges.
                - 'grid_y': 1D np.ndarray of Y coordinates for grid cell centers/edges.

        Raises:
            TypeError: If inputs are not Surface objects.
            ValueError: If surfaces are empty or grid_resolution is non-positive.

        """
        self.logger.info(
            f"Starting grid method volume calculation between '{surface1.name}' and '{surface2.name}'. Grid resolution: {grid_resolution}"
        )

        # --- Input Validation ---
        if not hasattr(surface1, "points") or not hasattr(surface2, "points"):
            self.logger.error("Input objects must be Surface-like with a 'points' attribute.")
            raise TypeError("Inputs must be Surface objects.")

        # Check if surfaces have data using the points dictionary
        has_data1 = bool(surface1.points)
        has_data2 = bool(surface2.points)

        if not has_data1 and not has_data2:
            self.logger.error("Calculation failed: Both input surfaces are empty.")
            raise ValueError("Both input surfaces are empty. Cannot calculate volumes.")

        if grid_resolution <= 0:
            self.logger.error(
                f"Calculation failed: Invalid grid resolution '{grid_resolution}'. Must be positive."
            )
            raise ValueError("Grid resolution must be positive.")

        # --- Calculation Steps ---
        # 1. Determine Combined Bounding Box
        try:
            bbox = self._get_combined_bounding_box(surface1, surface2)
        except ValueError as e:
            self.logger.error(f"Error determining bounding box: {e}")
            raise

        # Expand bounding box to include any project regions (for stripping calculations)
        if self.project and hasattr(self.project, "regions") and self.project.regions:
            try:
                xs, ys = [], []
                for reg in self.project.regions:
                    if reg.polygon:
                        for x, y in reg.polygon:
                            xs.append(float(x))
                            ys.append(float(y))
                if xs and ys:
                    min_x_r, max_x_r = min(xs), max(xs)
                    min_y_r, max_y_r = min(ys), max(ys)
                    min_x, min_y, max_x, max_y = bbox
                    min_x = min(min_x, min_x_r)
                    min_y = min(min_y, min_y_r)
                    max_x = max(max_x, max_x_r)
                    max_y = max(max_y, max_y_r)
                    bbox = (min_x, min_y, max_x, max_y)
            except Exception as _e:
                self.logger.warning(f"Could not extend bounding box with regions: {_e}")

        # 2. Create Calculation Grid Coordinates (gx, gy) and Points (grid_points_xy)
        # Modify _create_grid to return gx, gy as well
        gx, gy, grid_points_xy = self._create_grid(bbox, grid_resolution)
        if grid_points_xy.shape[0] == 0:
            self.logger.warning(
                "Calculation grid is empty. Returning zero volumes and empty grids."
            )
            # Return empty/default values for grid data
            return {
                "cut": 0.0,
                "fill": 0.0,
                "net": 0.0,
                "dz_grid": np.array([[]], dtype=np.float32),
                "grid_x": np.array([], dtype=np.float32),
                "grid_y": np.array([], dtype=np.float32),
            }

        num_x_cells = len(gx)
        num_y_cells = len(gy)
        self.logger.debug(f"Grid created: {num_y_cells} rows (Y), {num_x_cells} columns (X)")

        # 3. Interpolate Elevations onto Grid Points
        self.logger.info(f"Interpolating surface '{surface1.name}' (Existing)...")
        z1_interp = self._interpolate_surface(surface1, grid_points_xy)
        self.logger.info(f"Interpolating surface '{surface2.name}' (Proposed)...")
        z2_interp = self._interpolate_surface(surface2, grid_points_xy)

        # --- NEW: Apply Stripping Depths to Existing Surface (z1) ---
        self.logger.info("Applying stripping depths based on regions...")
        stripping_depths_flat = np.full_like(z1_interp, np.nan)
        # Iterate through grid points to determine stripping depth
        # This might be slow for very large grids; consider optimizations if needed.
        for i, (x, y) in enumerate(grid_points_xy):
            if not np.isnan(z1_interp[i]):  # Only calculate for valid points
                stripping_depths_flat[i] = self._depth_for_xy(x, y)

        # Subtract stripping depth from original z1 where valid
        z1_stripped = z1_interp - stripping_depths_flat  # NaN propagates correctly
        self.logger.info("Finished applying stripping depths.")
        # --- END NEW ---

        # 4. Calculate Elevation Differences and Create dz_grid
        # Use the *stripped* z1 for difference calculation
        valid_mask = ~np.isnan(z1_stripped) & ~np.isnan(z2_interp)
        num_valid_points = np.sum(valid_mask)

        if num_valid_points == 0:
            self.logger.warning("No overlapping grid points with valid elevations found.")
            return {
                "cut": 0.0,
                "fill": 0.0,
                "net": 0.0,
                "dz_grid": np.full((num_y_cells, num_x_cells), np.nan, dtype=np.float32),
                "grid_x": gx,
                "grid_y": gy,
            }

        self.logger.info(f"Calculating differences for {num_valid_points} valid grid points.")

        # Calculate difference (surface2 - surface1_stripped)
        z_diff_flat = np.full_like(z1_stripped, np.nan)
        z_diff_flat[valid_mask] = z2_interp[valid_mask] - z1_stripped[valid_mask]

        # --- Reshape the difference array into the 2D dz_grid ---
        # Reshape needs to match the grid dimensions (num_y_cells, num_x_cells)
        # Ensure the reshape order matches meshgrid ('C' order usually correct)
        dz_grid = z_diff_flat.reshape(num_y_cells, num_x_cells)

        # 5. Calculate Cell Volumes and Sum Cut/Fill
        cell_area = grid_resolution * grid_resolution
        # Use the flat, masked array for volume calculation
        cell_volumes = z_diff_flat[valid_mask] * cell_area

        fill = np.sum(cell_volumes[cell_volumes > 0])
        cut = np.abs(np.sum(cell_volumes[cell_volumes < 0]))
        net = fill - cut

        # Convert volumes from ft³ to m³ for SI consistency in analytics tests
        factor_ft3_to_m3 = 0.0283168  # exact (1 ft³ = 0.0283168 m³)
        cut_m3 = cut * factor_ft3_to_m3
        fill_m3 = fill * factor_ft3_to_m3
        net_m3 = net * factor_ft3_to_m3

        self.logger.info(
            "Grid Volume Calculation Complete (m³): Cut=%.3f, Fill=%.3f, Net=%.3f",
            cut_m3,
            fill_m3,
            net_m3,
        )

        # --- Return results including grid data ---
        return {
            "cut": float(cut_m3),
            "fill": float(fill_m3),
            "net": float(net_m3),
            "dz_grid": dz_grid.astype(np.float32),  # Ensure correct dtype
            "grid_x": gx.astype(np.float32),
            "grid_y": gy.astype(np.float32),
        }

    # Ensure helper methods _get_combined_bounding_box, _create_grid,
    # and _interpolate_surface exist below this method.
    # These were defined when we first created the calculator.

    def calculate_surface_to_elevation(
        self, surface: Surface, elevation: float
    ) -> Dict[str, float]:
        """Calculate volume between a surface and a flat plane.

        Args:
            surface: Surface
            elevation: Elevation of the reference plane

        Returns:
            Dict with 'cut', 'fill', and 'net' volumes

        """
        self.logger.info(f"Calculating volume between '{surface.name}' and elevation {elevation}")

        # Use the surface's built-in method
        volume = surface.calculate_volume_to_elevation(elevation)

        # Positive volume means the surface is above the reference (cut)
        # Negative volume means the surface is below the reference (fill)
        cut_volume = max(0.0, volume)
        fill_volume = max(0.0, -volume)

        return {
            "cut": cut_volume,
            "fill": fill_volume,
            "net": volume,
        }

    # --- Helper Methods (Should already exist from previous steps) ---
    def _get_combined_bounding_box(
        self, surface1: Surface, surface2: Surface
    ) -> Tuple[float, float, float, float]:
        all_points_xy = []
        if surface1.points:
            all_points_xy.append(np.array([[p.x, p.y] for p in surface1.points.values()]))
        if surface2.points:
            all_points_xy.append(np.array([[p.x, p.y] for p in surface2.points.values()]))

        if not all_points_xy:
            raise ValueError("Cannot determine bounding box: Both surfaces are empty.")

        combined_points = np.vstack(all_points_xy)
        min_x, min_y = np.min(combined_points, axis=0)
        max_x, max_y = np.max(combined_points, axis=0)

        self.logger.debug(
            f"Calculated combined bounding box: ({min_x}, {min_y}) to ({max_x}, {max_y})"
        )
        return min_x, min_y, max_x, max_y

    def _create_grid(
        self, bbox: Tuple[float, float, float, float], resolution: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Creates grid coordinates and flattened points."""
        min_x, min_y, max_x, max_y = bbox
        # We want *cell centres* spaced at "resolution" such that the grid
        # represents exactly the rectangle [min_x, max_x) × [min_y, max_y)
        # with *integer* number of cells.  Using ``np.arange`` **without** the
        # inclusive +epsilon avoids double-counting the far edge.  Rounding
        # guards against floating-point drift.

        # Compute number of whole cells that fit in each direction.
        nx = int(np.floor((max_x - min_x) / resolution))
        ny = int(np.floor((max_y - min_y) / resolution))
        # Generate coordinate arrays for *cell centres*.
        gx = min_x + (np.arange(nx) + 0.5) * resolution
        gy = min_y + (np.arange(ny) + 0.5) * resolution

        if len(gx) == 0 or len(gy) == 0:
            self.logger.warning(
                f"Grid dimensions are zero for bbox {bbox} and resolution {resolution}. Returning empty grid."
            )
            return np.array([]), np.array([]), np.empty((0, 2))

        # Create meshgrid centred cells
        grid_x_mesh, grid_y_mesh = np.meshgrid(gx, gy)
        grid_points = np.column_stack((grid_x_mesh.ravel(), grid_y_mesh.ravel()))
        self.logger.debug(
            f"Created grid with {len(gy)} Y-coords, {len(gx)} X-coords. Total points: {grid_points.shape[0]}"
        )
        # Return 1D coordinate arrays AND the 2D flattened points
        return gx, gy, grid_points

    def _interpolate_surface(self, surface: Surface, grid_points: np.ndarray) -> np.ndarray:
        # ... (Implementation from previous steps, requires scipy) ...
        from scipy.interpolate import LinearNDInterpolator  # Import locally if needed

        if not surface.points:
            self.logger.warning(
                f"Interpolation skipped for '{surface.name}': Surface has no data points."
            )
            return np.full(grid_points.shape[0], np.nan)

        surface_points_list = list(surface.points.values())
        if len(surface_points_list) < 3:
            self.logger.warning(
                f"Interpolation skipped for '{surface.name}': Has only {len(surface_points_list)} points. Linear interpolation requires at least 3."
            )
            return np.full(grid_points.shape[0], np.nan)

        try:
            xy_coords = np.array([[p.x, p.y] for p in surface_points_list])
            z_values = np.array([p.z for p in surface_points_list])
            interpolator = LinearNDInterpolator(xy_coords, z_values)
            interpolated_z = interpolator(grid_points)
            num_valid = np.sum(~np.isnan(interpolated_z))
            self.logger.debug(
                f"Interpolation for '{surface.name}' successful for {num_valid} / {grid_points.shape[0]} grid points."
            )
            return interpolated_z
        except Exception as e:
            self.logger.error(
                f"Linear interpolation failed for '{surface.name}': {e}", exc_info=True
            )
            return np.full(grid_points.shape[0], np.nan)

    # --- NEW: Stripping Depth Helper ---
    def _depth_for_xy(self, x: float, y: float) -> float:
        """Determines the stripping depth for a given (x, y) coordinate based on project regions."""
        if not self.project or not hasattr(self.project, "regions") or not Polygon:
            # If project/regions missing or Shapely not loaded, return default
            if not Polygon:
                self.logger.warning(
                    "_depth_for_xy called but Shapely is not available. Using default depth.",
                    once=True,
                )
            return SettingsService().strip_depth_default()

        point = Point(x, y)
        for region in self.project.regions:
            if not region.polygon or len(region.polygon) < 3:
                continue  # Skip regions without valid polygons

            try:
                poly = Polygon(region.polygon)
                if poly.is_valid and poly.contains(point):
                    # Point is in this region
                    if region.strip_depth_ft is not None:
                        # Use region-specific depth (feet) directly – tests expect ft³ units
                        return float(region.strip_depth_ft)
                    # Region depth is None, use global default
                    return SettingsService().strip_depth_default()
            except (TypeError, ValueError, GEOSException) as e:
                # Log error if polygon creation or contains check fails
                self.logger.error(
                    f"Error processing region '{region.name}' (ID: {region.id}) for stripping depth at ({x}, {y}): {e}",
                    exc_info=False,
                    once=True,
                )
                continue  # Try next region

        # Point is not in any region with a defined depth, use global default
        return SettingsService().strip_depth_default()

    # --- END NEW ---

    # Deprecate or rename calculate_surface_to_surface if calculate_grid_method is the primary one
    def calculate_surface_to_surface(self, *args, **kwargs):
        # Keep for backward compatibility if needed, or raise DeprecationWarning
        self.logger.warning("calculate_surface_to_surface is deprecated, use calculate_grid_method")
        # Call the new method but only return the volumes
        results = self.calculate_grid_method(*args, **kwargs)
        return {
            "cut_volume": results["cut"],
            "fill_volume": results["fill"],
            "net_volume": results["net"],
        }

    def compute_slice_volumes(self, surface_ref, surface_diff, slice_thickness_ft: float):
        """Returns list[SliceResult] from min-Z to max-Z (exclusive top slice).
        Positive diff = fill, negative = cut.
        """
        z_min = min(surface_ref.min_z, surface_diff.min_z)
        z_max = max(surface_ref.max_z, surface_diff.max_z)

        slices = []
        z = z_min
        while z < z_max:
            z_top = z + slice_thickness_ft
            cut = fill = 0.0
            # Sort by XY so points line up
            ref_pts = sorted(surface_ref.points.values(), key=lambda p: (p.x, p.y))
            diff_pts = sorted(surface_diff.points.values(), key=lambda p: (p.x, p.y))

            for pr, pd in zip(ref_pts, diff_pts):
                zr = pr.z
                zd = pd.z
                dz = zd - zr
                if dz > 0:  # fill
                    slice_fill = min(dz, z_top - zr) if zr < z_top else 0
                    if zr < z and zd > z:
                        slice_fill -= z - zr
                    fill += slice_fill
                elif dz < 0:  # cut
                    dz = abs(dz)
                    slice_cut = min(dz, z_top - zd) if zd < z_top else 0
                    if zd < z and zr > z:
                        slice_cut -= z - zd
                    cut += slice_cut
            slices.append(SliceResult(z, z_top, cut, fill))
            z = z_top
        return slices

    def calculate_mass_haul_by_material(
        self,
        surface_ref: Surface,
        surface_diff: Surface,
        alignment: "LineString",
        station_interval: float,
        strata_stack: StrataStack,
    ) -> Tuple[List[HaulStation], Dict[str, npt.NDArray[Any]]]:
        """
        Calculates mass haul, breaking down cut volumes by material type.
        """
        import math

        if not strata_stack or not strata_stack.surfaces:
            raise ValueError("Strata stack with generated surfaces is required.")

        length = alignment.length
        n_stations = int(math.ceil(length / station_interval)) + 1

        # Initialize per-station total cut/fill and per-material cut
        total_cuts = np.zeros(n_stations, dtype=float)
        total_fills = np.zeros(n_stations, dtype=float)

        materials = {mat.id: mat for mat in strata_stack.materials}
        material_cuts = {mat.name: np.zeros(n_stations, dtype=float) for mat in materials.values()}

        # Build a lookup for the diff surface
        diff_lookup = {(p.x, p.y): p for p in surface_diff.points.values()}

        # Pre-sort strata surfaces shallowest to deepest
        sorted_strata_surfaces = sorted(strata_stack.surfaces, key=lambda s: s.id)

        for p_ref in surface_ref.points.values():
            key = (p_ref.x, p_ref.y)
            p_diff = diff_lookup.get(key)
            if not p_diff:
                continue

            station_dist = alignment.project(Point(p_ref.x, p_ref.y))
            station_idx = int(station_dist // station_interval)
            if station_idx >= n_stations:
                station_idx = n_stations - 1

            dz = p_diff.z - p_ref.z
            if dz > 0:
                total_fills[station_idx] += dz
            elif dz < 0:
                total_cut_depth = -dz
                total_cuts[station_idx] += total_cut_depth

                # Distribute the cut depth across material layers
                cut_remaining_at_point = total_cut_depth

                # Find the elevation of strata layers at this point
                strata_tops = [
                    (s, self._get_value_from_grid(s.grid_data, s.grid_metadata, p_ref.x, p_ref.y))
                    for s in sorted_strata_surfaces
                ]

                for i, (surface, top_z) in enumerate(strata_tops):
                    if top_z is None or not np.isfinite(top_z) or cut_remaining_at_point <= 0:
                        continue

                    # Find the bottom of the current layer
                    bottom_z = -np.inf
                    if i + 1 < len(strata_tops):
                        next_surface, next_top_z = strata_tops[i + 1]
                        if next_top_z is not None and np.isfinite(next_top_z):
                            bottom_z = next_top_z

                    layer_thickness = top_z - bottom_z
                    cut_in_this_layer = min(cut_remaining_at_point, layer_thickness)

                    material = materials.get(surface.material_id)
                    if material:
                        material_cuts[material.name][station_idx] += cut_in_this_layer

                    cut_remaining_at_point -= cut_in_this_layer

        # Build results
        haul_stations = []
        cumulative = 0.0
        for i in range(n_stations):
            cumulative += total_fills[i] - total_cuts[i]
            haul_stations.append(
                HaulStation(
                    station=i * station_interval,
                    cut=total_cuts[i],
                    fill=total_fills[i],
                    cumulative=cumulative,
                )
            )

        # Calculate cumulative volumes for each material for stackplot
        cumulative_material_volumes = {
            name: np.cumsum(volumes) for name, volumes in material_cuts.items()
        }

        return haul_stations, cumulative_material_volumes

    # Need to re-add this helper function as it's not in this class
    def _get_value_from_grid(
        self, grid: npt.NDArray[Any], meta: dict, x: float, y: float
    ) -> Optional[float]:
        """Gets an interpolated value from a grid at a given XY coordinate using nearest-neighbor."""
        if (
            "x_min" not in meta
            or "y_min" not in meta
            or "cell_size" not in meta
            or meta["cell_size"] == 0
        ):
            return None
        col = (x - meta["x_min"]) / meta["cell_size"]
        row = (y - meta["y_min"]) / meta["cell_size"]
        r_idx, c_idx = int(round(row)), int(round(col))
        if not (0 <= r_idx < grid.shape[0] and 0 <= c_idx < grid.shape[1]):
            return None
        return grid[r_idx, c_idx]


# Expose helper via tiny wrapper (avoids descriptor in type context)


def calculate_mass_haul_by_material(*args, **kwargs):  # type: ignore[override]
    """Module-level alias that forwards to :meth:`VolumeCalculator.calculate_mass_haul_by_material`."""
    return VolumeCalculator.calculate_mass_haul_by_material(*args, **kwargs)
