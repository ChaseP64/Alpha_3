#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Volume calculation model for the DigCalc application.

This module defines the VolumeCalculation class for representing
and handling volume calculations between surfaces.
"""

import logging
import uuid
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Use relative import
from .surface import Surface

@dataclass(slots=True)
class SliceResult:
    """Result of a single elevation slice volume calculation."""
    z_bottom: float
    z_top: float
    cut: float
    fill: float

class VolumeCalculation:
    """
    Represents a volume calculation between surfaces.
    """
    
    # Calculation types
    TYPE_SURFACE_TO_SURFACE = "surface_to_surface"
    TYPE_SURFACE_TO_ELEVATION = "surface_to_elevation"
    TYPE_GRID_DIFFERENCING = "grid_differencing"
    TYPE_TIN_DIFFERENCING = "tin_differencing"
    
    def __init__(self, name: str, calc_type: str, base_surface: Surface):
        """
        Initialize a volume calculation.
        
        Args:
            name: Calculation name
            calc_type: Calculation type (one of the TYPE_* constants)
            base_surface: Base surface for the calculation
        """
        self.logger = logging.getLogger(__name__)
        self.name = name
        self.calc_type = calc_type
        self.base_surface = base_surface
        self.calculation_id = str(uuid.uuid4())
        
        # For surface to surface calculations
        self.comparison_surface: Optional[Surface] = None
        
        # For surface to elevation calculations
        self.reference_elevation: Optional[float] = None
        
        # Results
        self.results: Dict[str, Any] = {}
        self.created_at = datetime.datetime.now()
        self.calculated_at: Optional[datetime.datetime] = None
        
        # Optional parameters
        self.grid_spacing: Optional[float] = None
        self.calc_region_bounds: Optional[tuple] = None  # (xmin, ymin, xmax, ymax)
        self.metadata: Dict[str, Any] = {}
        
        self.logger.debug(f"Volume calculation '{name}' initialized with type {calc_type}")
    
    def set_comparison_surface(self, surface: Surface) -> None:
        """
        Set the comparison surface for surface-to-surface calculations.
        
        Args:
            surface: Comparison surface
        """
        self.comparison_surface = surface
        self.logger.debug(f"Comparison surface set to '{surface.name}'")
    
    def set_reference_elevation(self, elevation: float) -> None:
        """
        Set the reference elevation for surface-to-elevation calculations.
        
        Args:
            elevation: Reference elevation
        """
        self.reference_elevation = elevation
        self.logger.debug(f"Reference elevation set to {elevation}")
    
    def calculate(self) -> Dict[str, Any]:
        """
        Perform the volume calculation.
        
        Returns:
            Dictionary of calculation results
        """
        self.logger.info(f"Performing calculation: {self.name}")
        
        try:
            if self.calc_type == self.TYPE_SURFACE_TO_ELEVATION:
                self._calculate_surface_to_elevation()
                
            elif self.calc_type == self.TYPE_SURFACE_TO_SURFACE:
                self._calculate_surface_to_surface()
                
            elif self.calc_type == self.TYPE_GRID_DIFFERENCING:
                self._calculate_grid_differencing()
                
            elif self.calc_type == self.TYPE_TIN_DIFFERENCING:
                self._calculate_tin_differencing()
                
            else:
                raise ValueError(f"Unsupported calculation type: {self.calc_type}")
            
            # Update calculation timestamp
            self.calculated_at = datetime.datetime.now()
            self.logger.info(f"Calculation completed: {self.name}")
            
            return self.results
            
        except Exception as e:
            self.logger.exception(f"Error during calculation: {e}")
            self.results = {"error": str(e)}
            return self.results
    
    def _calculate_surface_to_elevation(self) -> None:
        """Calculate volume between surface and flat reference elevation."""
        if self.reference_elevation is None:
            raise ValueError("Reference elevation not set")
        
        volume = self.base_surface.calculate_volume_to_elevation(self.reference_elevation)
        
        # Positive volume means the surface is above the reference (cut)
        # Negative volume means the surface is below the reference (fill)
        cut_volume = max(0.0, volume)
        fill_volume = max(0.0, -volume)
        
        self.results = {
            "total_area": self._calculate_area(),
            "cut_volume": cut_volume,
            "fill_volume": fill_volume,
            "net_volume": volume,
            "reference_elevation": self.reference_elevation
        }
    
    def _calculate_surface_to_surface(self) -> None:
        """Calculate volume between two surfaces."""
        if self.comparison_surface is None:
            raise ValueError("Comparison surface not set")
        
        # Calculate volume using the base surface method
        volumes = self.base_surface.calculate_volume_to_surface(self.comparison_surface)
        
        self.results = {
            "total_area": self._calculate_area(),
            "cut_volume": volumes["cut"],
            "fill_volume": volumes["fill"],
            "net_volume": volumes["net"],
            "base_surface": self.base_surface.name,
            "comparison_surface": self.comparison_surface.name
        }
    
    def _calculate_grid_differencing(self) -> None:
        """
        Calculate volume using grid differencing.
        
        This method converts TIN surfaces to grids if necessary,
        then performs grid-based volume calculations.
        """
        # This would be implemented in a real application
        self.logger.warning("Grid differencing calculation not implemented")
        self._calculate_surface_to_surface()  # Fallback
    
    def _calculate_tin_differencing(self) -> None:
        """
        Calculate volume using TIN differencing.
        
        This method performs triangle-based volumetric calculations.
        """
        # This would be implemented in a real application
        self.logger.warning("TIN differencing calculation not implemented")
        self._calculate_surface_to_surface()  # Fallback
    
    def _calculate_area(self) -> float:
        """
        Calculate the area of the calculation region.
        
        Returns:
            Area in square units
        """
        if self.calc_region_bounds:
            xmin, ymin, xmax, ymax = self.calc_region_bounds
            width = xmax - xmin
            height = ymax - ymin
            return width * height
        else:
            # Use surface bounds
            surface = self.base_surface
            if None in (surface.x_min, surface.x_max, surface.y_min, surface.y_max):
                return 0.0
                
            width = surface.x_max - surface.x_min
            height = surface.y_max - surface.y_min
            return width * height
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a detailed report of the calculation.
        
        Returns:
            Report data dictionary
        """
        if not self.results or self.calculated_at is None:
            self.logger.warning("Cannot generate report - calculation not performed")
            return {"error": "Calculation not performed"}
        
        report = {
            "name": self.name,
            "id": self.calculation_id,
            "type": self.calc_type,
            "calculated_at": self.calculated_at.isoformat(),
            "base_surface": self.base_surface.name,
            "results": self.results
        }
        
        if self.comparison_surface:
            report["comparison_surface"] = self.comparison_surface.name
            
        if self.reference_elevation is not None:
            report["reference_elevation"] = self.reference_elevation
            
        return report 