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
                                    surface2: Surface) -> Dict[str, float]:
        """
        Calculate volume between two surfaces.
        
        Args:
            surface1: First surface
            surface2: Second surface
            
        Returns:
            Dict with 'cut', 'fill', and 'net' volumes
        """
        self.logger.info(f"Calculating volume between '{surface1.name}' and '{surface2.name}'")
        
        # This is a simplified implementation for the skeleton
        # In a real implementation, this would handle both TIN and grid surfaces appropriately
        
        # If both surfaces are grids, use grid differencing
        if (surface1.surface_type == Surface.SURFACE_TYPE_GRID and 
            surface2.surface_type == Surface.SURFACE_TYPE_GRID and
            surface1.grid_data is not None and
            surface2.grid_data is not None):
            return self._calculate_grid_to_grid(surface1, surface2)
            
        # Otherwise, for the skeleton, just return dummy values
        self.logger.warning("Surface-to-surface volume calculation not fully implemented")
        return {
            'cut': 1000.0,
            'fill': 500.0,
            'net': 500.0
        }
    
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
    
    def _calculate_grid_to_grid(self, grid1: Surface, grid2: Surface) -> Dict[str, float]:
        """
        Calculate volume between two grid surfaces.
        
        Args:
            grid1: First grid surface
            grid2: Second grid surface
            
        Returns:
            Dict with 'cut', 'fill', and 'net' volumes
        """
        # This would perform a more sophisticated calculation in a real implementation
        # For now, we'll just create a simple implementation for the skeleton
        
        if None in (grid1.grid_data, grid2.grid_data):
            self.logger.error("Grid data not available")
            return {'cut': 0.0, 'fill': 0.0, 'net': 0.0}
            
        # Check if grids are compatible
        if (grid1.grid_spacing != grid2.grid_spacing or
            grid1.grid_origin != grid2.grid_origin or
            grid1.grid_data.shape != grid2.grid_data.shape):
            self.logger.warning("Incompatible grids, results may be inaccurate")
            # In a real implementation, we would resample one grid to match the other
            
        # Calculate volume based on grid difference
        # For the skeleton, we'll assume the grids are compatible
        try:
            cell_area = grid1.grid_spacing * grid1.grid_spacing
            diff = grid1.grid_data - grid2.grid_data
            
            # Remove NaN values
            diff = np.nan_to_num(diff, nan=0.0)
            
            # Calculate volumes
            cut_mask = diff > 0  # grid1 is above grid2
            fill_mask = diff < 0  # grid1 is below grid2
            
            cut_volume = np.sum(diff[cut_mask]) * cell_area
            fill_volume = -np.sum(diff[fill_mask]) * cell_area
            net_volume = cut_volume - fill_volume
            
            return {
                'cut': float(cut_volume),
                'fill': float(fill_volume),
                'net': float(net_volume)
            }
            
        except Exception as e:
            self.logger.exception(f"Error calculating grid volume: {e}")
            return {'cut': 0.0, 'fill': 0.0, 'net': 0.0} 