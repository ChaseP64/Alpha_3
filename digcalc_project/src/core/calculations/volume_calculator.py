#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Volume calculator for the DigCalc application.

This module provides functionality to calculate volumes between surfaces.
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple

from models.surface import Surface


class VolumeCalculator:
    """Calculator for volumes between surfaces."""
    
    def __init__(self):
        """Initialize the volume calculator."""
        self.logger = logging.getLogger(__name__)
    
    def calculate_surface_to_surface(self, surface1: Surface, 
                                    surface2: Surface, 
                                    grid_resolution: float = 1.0) -> Dict[str, float]:
        """
        Calculates cut, fill, and net volumes between two surfaces using a grid method.

        This method creates a grid over the combined area of both surfaces, interpolates
        the elevation of each surface at the grid points, calculates the difference,
        and sums the volume contributions for cut and fill based on the sign of the difference.

        Args:
            surface1 (Surface): The existing terrain surface model (or first surface).
            surface2 (Surface): The proposed design surface model (or second surface).
            grid_resolution (float): The side length of the square grid cells used for
                                     calculation. Smaller values yield higher accuracy but
                                     increase computation time. Defaults to 1.0.

        Returns:
            Dict[str, float]: A dictionary containing calculated volumes:
                - 'cut_volume': Total volume where surface1 > surface2 (material to remove). Positive value.
                - 'fill_volume': Total volume where surface2 > surface1 (material to add). Positive value.
                - 'net_volume': fill_volume - cut_volume. Can be positive (net fill) or negative (net cut).
                Units are cubic units corresponding to the input surface coordinates.

        Raises:
            TypeError: If inputs are not Surface objects (or compatible).
            ValueError: If both input surfaces are empty, or if grid_resolution is non-positive.
        """
        self.logger.info(f"Starting volume calculation between '{surface1.name}' and '{surface2.name}'. Grid resolution: {grid_resolution}")

        # --- Input Validation ---
        if not hasattr(surface1, 'points') or not hasattr(surface2, 'points'):
            self.logger.error("Input objects must be Surface-like with a 'points' attribute.")
            raise TypeError("Inputs must be Surface objects.")
        
        # Check if surfaces have data using the points dictionary
        has_data1 = bool(surface1.points)
        has_data2 = bool(surface2.points)

        if not has_data1 and not has_data2:
            self.logger.error("Calculation failed: Both input surfaces are empty.")
            raise ValueError("Both input surfaces are empty. Cannot calculate volumes.")
            
        if grid_resolution <= 0:
             self.logger.error(f"Calculation failed: Invalid grid resolution '{grid_resolution}'. Must be positive.")
             raise ValueError("Grid resolution must be positive.")

        # --- Calculation Steps (Using helper methods assumed to exist) ---
        # 1. Determine Combined Bounding Box
        try:
            # Pass the actual Surface objects to the helper
            bbox = self._get_combined_bounding_box(surface1, surface2)
        except ValueError as e:
             self.logger.error(f"Error determining bounding box: {e}")
             raise # Re-raise the specific error

        # 2. Create Calculation Grid
        grid_points_xy = self._create_grid(bbox, grid_resolution)
        if grid_points_xy.shape[0] == 0:
            self.logger.warning("Calculation grid is empty. Returning zero volumes.")
            return {'cut_volume': 0.0, 'fill_volume': 0.0, 'net_volume': 0.0}

        # 3. Interpolate Elevations onto Grid Points for Both Surfaces
        self.logger.info(f"Interpolating surface '{surface1.name}' onto {grid_points_xy.shape[0]} grid points...")
        z1_interp = self._interpolate_surface(surface1, grid_points_xy)
        
        self.logger.info(f"Interpolating surface '{surface2.name}' onto {grid_points_xy.shape[0]} grid points...")
        z2_interp = self._interpolate_surface(surface2, grid_points_xy)

        # 4. Calculate Elevation Differences and Filter Invalid Points
        valid_mask = ~np.isnan(z1_interp) & ~np.isnan(z2_interp)
        
        num_valid_points = np.sum(valid_mask)
        if num_valid_points == 0:
             self.logger.warning("No overlapping grid points with valid elevations found. Check if surfaces overlap.")
             return {'cut_volume': 0.0, 'fill_volume': 0.0, 'net_volume': 0.0}
        
        self.logger.info(f"Calculating differences for {num_valid_points} valid overlapping grid points.")
        
        # Calculate difference only for valid points (surface2 - surface1)
        z_diff = np.full_like(z1_interp, np.nan)
        z_diff[valid_mask] = z2_interp[valid_mask] - z1_interp[valid_mask]

        # 5. Calculate Cell Volumes and Sum Cut/Fill
        cell_area = grid_resolution * grid_resolution
        cell_volumes = z_diff[valid_mask] * cell_area 

        # Fill volume: where surface2 > surface1 (positive difference)
        fill_volume = np.sum(cell_volumes[cell_volumes > 0])
        
        # Cut volume: where surface1 > surface2 (negative difference)
        cut_volume = np.abs(np.sum(cell_volumes[cell_volumes < 0])) 

        net_volume = fill_volume - cut_volume

        self.logger.info(f"Volume Calculation Complete: Cut={cut_volume:.3f}, Fill={fill_volume:.3f}, Net={net_volume:.3f}")

        # Return results using the keys expected by MainWindow
        return {
            'cut_volume': float(cut_volume),
            'fill_volume': float(fill_volume),
            'net_volume': float(net_volume)
        }

    # Ensure helper methods _get_combined_bounding_box, _create_grid, 
    # and _interpolate_surface exist below this method.
    # These were defined when we first created the calculator.

    def calculate_surface_to_elevation(self, surface: Surface, 
                                      elevation: float) -> Dict[str, float]:
        """
        Calculate volume between a surface and a flat plane.
        
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
            'cut': cut_volume,
            'fill': fill_volume,
            'net': volume
        }
    
    # --- Helper Methods (Should already exist from previous steps) --- 
    def _get_combined_bounding_box(self, surface1: Surface, surface2: Surface) -> Tuple[float, float, float, float]:
        # ... (Implementation from previous steps) ...
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
        
        self.logger.debug(f"Calculated combined bounding box: ({min_x}, {min_y}) to ({max_x}, {max_y})")
        return min_x, min_y, max_x, max_y

    def _create_grid(self, bbox: Tuple[float, float, float, float], resolution: float) -> np.ndarray:
        # ... (Implementation from previous steps) ...
        min_x, min_y, max_x, max_y = bbox
        epsilon = resolution * 1e-6 
        x_coords = np.arange(min_x, max_x + epsilon, resolution)
        y_coords = np.arange(min_y, max_y + epsilon, resolution)
        if len(x_coords) == 0 or len(y_coords) == 0:
             self.logger.warning(f"Grid dimensions are zero for bbox {bbox} and resolution {resolution}. Returning empty grid.")
             return np.empty((0,2))
        grid_x, grid_y = np.meshgrid(x_coords, y_coords)
        grid_points = np.vstack([grid_x.ravel(), grid_y.ravel()]).T
        self.logger.debug(f"Created grid with {grid_points.shape[0]} points. Resolution: {resolution}. BBox: {bbox}")
        return grid_points

    def _interpolate_surface(self, surface: Surface, grid_points: np.ndarray) -> np.ndarray:
        # ... (Implementation from previous steps, requires scipy) ...
        from scipy.interpolate import LinearNDInterpolator # Import locally if needed
        
        if not surface.points:
            self.logger.warning(f"Interpolation skipped for '{surface.name}': Surface has no data points.")
            return np.full(grid_points.shape[0], np.nan)
        
        surface_points_list = list(surface.points.values())
        if len(surface_points_list) < 3:
             self.logger.warning(f"Interpolation skipped for '{surface.name}': Has only {len(surface_points_list)} points. Linear interpolation requires at least 3.")
             return np.full(grid_points.shape[0], np.nan)

        try:
            xy_coords = np.array([[p.x, p.y] for p in surface_points_list])
            z_values = np.array([p.z for p in surface_points_list])
            interpolator = LinearNDInterpolator(xy_coords, z_values)
            interpolated_z = interpolator(grid_points)
            num_valid = np.sum(~np.isnan(interpolated_z))
            self.logger.debug(f"Interpolation for '{surface.name}' successful for {num_valid} / {grid_points.shape[0]} grid points.")
            return interpolated_z
        except Exception as e:
            self.logger.error(f"Linear interpolation failed for '{surface.name}': {e}", exc_info=True)
            return np.full(grid_points.shape[0], np.nan) 