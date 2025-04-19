#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Volume calculator for the DigCalc application.

This module provides functionality to calculate volumes between surfaces.
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple, Any

# Use relative import
from ...models.surface import Surface


class VolumeCalculator:
    """Calculator for volumes between surfaces."""
    
    def __init__(self):
        """Initialize the volume calculator."""
        self.logger = logging.getLogger(__name__)
    
    def calculate_grid_method(self, surface1: Surface,
                              surface2: Surface,
                              grid_resolution: float = 1.0) -> Dict[str, Any]:
        """
        Calculates cut, fill, net volumes, and the difference grid between two surfaces.

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
        self.logger.info(f"Starting grid method volume calculation between '{surface1.name}' and '{surface2.name}'. Grid resolution: {grid_resolution}")

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

        # --- Calculation Steps ---
        # 1. Determine Combined Bounding Box
        try:
            bbox = self._get_combined_bounding_box(surface1, surface2)
        except ValueError as e:
            self.logger.error(f"Error determining bounding box: {e}")
            raise

        # 2. Create Calculation Grid Coordinates (gx, gy) and Points (grid_points_xy)
        # Modify _create_grid to return gx, gy as well
        gx, gy, grid_points_xy = self._create_grid(bbox, grid_resolution)
        if grid_points_xy.shape[0] == 0:
            self.logger.warning("Calculation grid is empty. Returning zero volumes and empty grids.")
            # Return empty/default values for grid data
            return {
                'cut': 0.0, 'fill': 0.0, 'net': 0.0,
                'dz_grid': np.array([[]], dtype=np.float32),
                'grid_x': np.array([], dtype=np.float32),
                'grid_y': np.array([], dtype=np.float32)
            }

        num_x_cells = len(gx)
        num_y_cells = len(gy)
        self.logger.debug(f"Grid created: {num_y_cells} rows (Y), {num_x_cells} columns (X)")

        # 3. Interpolate Elevations onto Grid Points
        self.logger.info(f"Interpolating surface '{surface1.name}'...")
        z1_interp = self._interpolate_surface(surface1, grid_points_xy)
        self.logger.info(f"Interpolating surface '{surface2.name}'...")
        z2_interp = self._interpolate_surface(surface2, grid_points_xy)

        # 4. Calculate Elevation Differences and Create dz_grid
        valid_mask = ~np.isnan(z1_interp) & ~np.isnan(z2_interp)
        num_valid_points = np.sum(valid_mask)

        if num_valid_points == 0:
            self.logger.warning("No overlapping grid points with valid elevations found.")
            return {
                'cut': 0.0, 'fill': 0.0, 'net': 0.0,
                'dz_grid': np.full((num_y_cells, num_x_cells), np.nan, dtype=np.float32),
                'grid_x': gx,
                'grid_y': gy
            }

        self.logger.info(f"Calculating differences for {num_valid_points} valid grid points.")

        # Calculate difference (surface2 - surface1)
        z_diff_flat = np.full_like(z1_interp, np.nan)
        z_diff_flat[valid_mask] = z2_interp[valid_mask] - z1_interp[valid_mask]

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

        self.logger.info(f"Grid Volume Calculation Complete: Cut={cut:.3f}, Fill={fill:.3f}, Net={net:.3f}")

        # --- Return results including grid data ---
        return {
            'cut': float(cut),
            'fill': float(fill),
            'net': float(net),
            'dz_grid': dz_grid.astype(np.float32), # Ensure correct dtype
            'grid_x': gx.astype(np.float32),
            'grid_y': gy.astype(np.float32)
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

    def _create_grid(self, bbox: Tuple[float, float, float, float], resolution: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Creates grid coordinates and flattened points."""
        min_x, min_y, max_x, max_y = bbox
        # Use cell centers for coordinate arrays? Or edges? Let's use edges/arange.
        epsilon = resolution * 1e-6
        # gx corresponds to columns (X), gy corresponds to rows (Y)
        gx = np.arange(min_x, max_x + epsilon, resolution)
        gy = np.arange(min_y, max_y + epsilon, resolution)

        if len(gx) == 0 or len(gy) == 0:
            self.logger.warning(f"Grid dimensions are zero for bbox {bbox} and resolution {resolution}. Returning empty grid.")
            return np.array([]), np.array([]), np.empty((0, 2))

        # Create meshgrid for flattened points (consistent with previous logic)
        grid_x_mesh, grid_y_mesh = np.meshgrid(gx, gy)
        grid_points = np.vstack([grid_x_mesh.ravel(), grid_y_mesh.ravel()]).T
        self.logger.debug(f"Created grid with {len(gy)} Y-coords, {len(gx)} X-coords. Total points: {grid_points.shape[0]}")
        # Return 1D coordinate arrays AND the 2D flattened points
        return gx, gy, grid_points

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

    # Deprecate or rename calculate_surface_to_surface if calculate_grid_method is the primary one
    def calculate_surface_to_surface(self, *args, **kwargs):
         # Keep for backward compatibility if needed, or raise DeprecationWarning
         self.logger.warning("calculate_surface_to_surface is deprecated, use calculate_grid_method")
         # Call the new method but only return the volumes
         results = self.calculate_grid_method(*args, **kwargs)
         return {
             'cut_volume': results['cut'],
             'fill_volume': results['fill'],
             'net_volume': results['net']
         } 