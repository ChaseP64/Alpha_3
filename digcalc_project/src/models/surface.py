#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Surface data models for the DigCalc application.

This module defines the core data models for representing 3D surfaces
including points, triangles, and surfaces.
"""

import uuid
from typing import Dict, List, Optional, Tuple, Set, Union, Any


class Point3D:
    """
    Represents a 3D point with x, y, z coordinates.
    
    Attributes:
        x: X coordinate (East)
        y: Y coordinate (North)
        z: Z coordinate (Elevation)
        id: Unique identifier for the point
    """
    
    def __init__(self, x: float, y: float, z: float, point_id: Optional[str] = None):
        """
        Initialize a 3D point.
        
        Args:
            x: X coordinate (East)
            y: Y coordinate (North)
            z: Z coordinate (Elevation)
            point_id: Optional unique identifier for the point
        """
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.id = point_id or str(uuid.uuid4())
    
    def __str__(self) -> str:
        """String representation of the point."""
        return f"Point3D({self.x:.3f}, {self.y:.3f}, {self.z:.3f})"
    
    def __repr__(self) -> str:
        """Detailed representation of the point."""
        return f"Point3D(x={self.x}, y={self.y}, z={self.z}, id='{self.id}')"
    
    def __eq__(self, other) -> bool:
        """Check if points are equal (based on coordinates)."""
        if not isinstance(other, Point3D):
            return False
        return (
            abs(self.x - other.x) < 1e-6 and 
            abs(self.y - other.y) < 1e-6 and 
            abs(self.z - other.z) < 1e-6
        )
    
    def __hash__(self) -> int:
        """Hash for point (based on ID)."""
        return hash(self.id)
    
    def to_dict(self) -> Dict[str, Union[float, str]]:
        """Convert point to dictionary for serialization."""
        return {
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'id': self.id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Point3D':
        """Create point from dictionary representation."""
        return cls(
            x=data['x'],
            y=data['y'],
            z=data['z'],
            point_id=data.get('id')
        )


class Triangle:
    """
    Represents a triangle in 3D space, defined by three points.
    
    Attributes:
        p1, p2, p3: The three points defining the triangle
        id: Unique identifier for the triangle
    """
    
    def __init__(self, p1: Point3D, p2: Point3D, p3: Point3D, triangle_id: Optional[str] = None):
        """
        Initialize a triangle.
        
        Args:
            p1, p2, p3: The three points defining the triangle
            triangle_id: Optional unique identifier for the triangle
        """
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.id = triangle_id or str(uuid.uuid4())
    
    def __str__(self) -> str:
        """String representation of the triangle."""
        return f"Triangle({self.p1}, {self.p2}, {self.p3})"
    
    def __repr__(self) -> str:
        """Detailed representation of the triangle."""
        return f"Triangle(p1={self.p1}, p2={self.p2}, p3={self.p3}, id='{self.id}')"
    
    def __eq__(self, other) -> bool:
        """Check if triangles are equal (based on having the same points regardless of order)."""
        if not isinstance(other, Triangle):
            return False
        
        # Get sets of points from both triangles
        self_points = {self.p1, self.p2, self.p3}
        other_points = {other.p1, other.p2, other.p3}
        
        # Check if they have the same set of points
        return self_points == other_points
    
    def __hash__(self) -> int:
        """Hash for triangle (based on ID)."""
        return hash(self.id)
    
    def get_points(self) -> List[Point3D]:
        """Get list of the triangle's points."""
        return [self.p1, self.p2, self.p3]
    
    @property
    def center(self) -> Point3D:
        """Get the center point of the triangle."""
        x = (self.p1.x + self.p2.x + self.p3.x) / 3
        y = (self.p1.y + self.p2.y + self.p3.y) / 3
        z = (self.p1.z + self.p2.z + self.p3.z) / 3
        return Point3D(x, y, z)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert triangle to dictionary for serialization."""
        return {
            'p1': self.p1.to_dict(),
            'p2': self.p2.to_dict(),
            'p3': self.p3.to_dict(),
            'id': self.id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], points_map: Optional[Dict[str, Point3D]] = None) -> 'Triangle':
        """
        Create triangle from dictionary representation.
        
        Args:
            data: Dictionary representation of triangle
            points_map: Optional map of point IDs to Point3D objects for linking
        
        Returns:
            Triangle object
        """
        if points_map:
            # Use points from the provided map if available
            p1 = points_map.get(data['p1'], Point3D.from_dict(data['p1']))
            p2 = points_map.get(data['p2'], Point3D.from_dict(data['p2']))
            p3 = points_map.get(data['p3'], Point3D.from_dict(data['p3']))
        else:
            # Create new points
            p1 = Point3D.from_dict(data['p1'])
            p2 = Point3D.from_dict(data['p2'])
            p3 = Point3D.from_dict(data['p3'])
        
        return cls(p1, p2, p3, data.get('id'))


class Surface:
    """
    Represents a 3D surface composed of points and triangles.
    
    Attributes:
        name: Name of the surface
        points: Dictionary of points in the surface
        triangles: Dictionary of triangles in the surface
        metadata: Additional metadata about the surface
    """
    
    # Surface type constants
    SURFACE_TYPE_TIN = "TIN"
    SURFACE_TYPE_GRID = "GRID"
    
    def __init__(self, name: str, surface_type: str = None):
        """
        Initialize a surface.
        
        Args:
            name: Name of the surface
            surface_type: Type of surface (TIN, GRID, etc.)
        """
        self.name = name
        self.surface_type = surface_type or self.SURFACE_TYPE_TIN
        self.id = str(uuid.uuid4())
        self.points: Dict[str, Point3D] = {}
        self.triangles: Dict[str, Triangle] = {}
        self.metadata: Dict[str, Any] = {}
    
    def __str__(self) -> str:
        """String representation of the surface."""
        return f"Surface({self.name}, {len(self.points)} points, {len(self.triangles)} triangles)"
    
    def add_point(self, point: Point3D) -> None:
        """
        Add a point to the surface.
        
        Args:
            point: Point to add
        """
        self.points[point.id] = point
    
    def add_triangle(self, triangle: Triangle) -> None:
        """
        Add a triangle to the surface.
        
        Args:
            triangle: Triangle to add
        """
        # Make sure all points are in the surface
        for point in triangle.get_points():
            if point.id not in self.points:
                self.add_point(point)
        
        self.triangles[triangle.id] = triangle
    
    def get_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Get the bounds of the surface.
        
        Returns:
            Tuple (xmin, ymin, xmax, ymax) or None if surface is empty
        """
        if not self.points:
            return None
            
        # Get min/max x and y values
        points_list = list(self.points.values())
        xmin = min(p.x for p in points_list)
        ymin = min(p.y for p in points_list)
        xmax = max(p.x for p in points_list)
        ymax = max(p.y for p in points_list)
        
        return (xmin, ymin, xmax, ymax)
    
    def get_elevation_range(self) -> Optional[Tuple[float, float]]:
        """
        Get the elevation range of the surface.
        
        Returns:
            Tuple (zmin, zmax) or None if surface is empty
        """
        if not self.points:
            return None
            
        points_list = list(self.points.values())
        zmin = min(p.z for p in points_list)
        zmax = max(p.z for p in points_list)
        
        return (zmin, zmax)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert surface to dictionary for serialization."""
        return {
            'name': self.name,
            'surface_type': self.surface_type,
            'id': self.id,
            'points': [p.to_dict() for p in self.points.values()],
            'triangles': [t.to_dict() for t in self.triangles.values()],
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Surface':
        """Create surface from dictionary representation."""
        surface = cls(data['name'], data.get('surface_type', cls.SURFACE_TYPE_TIN))
        
        # Add metadata
        surface.metadata = data.get('metadata', {})
        
        # Add points
        points_map = {}
        for point_data in data.get('points', []):
            point = Point3D.from_dict(point_data)
            surface.add_point(point)
            points_map[point.id] = point
        
        # Add triangles, using the points map for referencing
        for triangle_data in data.get('triangles', []):
            triangle = Triangle.from_dict(triangle_data, points_map)
            surface.add_triangle(triangle)
        
        return surface 