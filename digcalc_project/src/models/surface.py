#!/usr/bin/env python3
"""Surface data models for the DigCalc application.

This module defines the core data models for representing 3D surfaces
including points, triangles, and surfaces.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# Define logger at module level
logger = logging.getLogger(__name__)

class Point3D:
    """Represents a 3D point with x, y, z coordinates.
    
    Attributes:
        x: X coordinate (East)
        y: Y coordinate (North)
        z: Z coordinate (Elevation)
        id: Unique identifier for the point

    """

    def __init__(self, x: float, y: float, z: float, point_id: Optional[str] = None):
        """Initialize a 3D point.
        
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
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Point3D":
        """Create point from dictionary representation."""
        return cls(
            x=data["x"],
            y=data["y"],
            z=data["z"],
            point_id=data.get("id"),
        )


class Triangle:
    """Represents a triangle in 3D space, defined by three points.
    
    Attributes:
        p1, p2, p3: The three points defining the triangle
        id: Unique identifier for the triangle

    """

    logger = logging.getLogger(__name__) # Add logger instance

    def __init__(self, p1: Point3D, p2: Point3D, p3: Point3D, triangle_id: Optional[str] = None):
        """Initialize a triangle.
        
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
            "p1": self.p1.to_dict(),
            "p2": self.p2.to_dict(),
            "p3": self.p3.to_dict(),
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], points_map: Optional[Dict[str, Point3D]] = None) -> "Triangle":
        """Create triangle from dictionary representation.
        
        Args:
            data: Dictionary representation of triangle
            points_map: Optional map of point IDs to Point3D objects for linking
        
        Returns:
            Triangle object

        """
        if points_map:
            # Use points from the provided map if available
            # Extract the point ID from the dictionary to use as the key
            p1_id = data["p1"].get("id") if isinstance(data.get("p1"), dict) else None
            p2_id = data["p2"].get("id") if isinstance(data.get("p2"), dict) else None
            p3_id = data["p3"].get("id") if isinstance(data.get("p3"), dict) else None

            if p1_id and p2_id and p3_id: # Ensure we got IDs
                 # Use the ID as the key, fallback to creating from dict if ID not in map (shouldn't happen)
                 p1 = points_map.get(p1_id, Point3D.from_dict(data["p1"]))
                 p2 = points_map.get(p2_id, Point3D.from_dict(data["p2"]))
                 p3 = points_map.get(p3_id, Point3D.from_dict(data["p3"]))
            else:
                 # Fallback if point data doesn't look like expected dicts with IDs
                 cls.logger.warning("Could not extract point IDs from triangle data during deserialization. Creating new points.")
                 p1 = Point3D.from_dict(data["p1"])
                 p2 = Point3D.from_dict(data["p2"])
                 p3 = Point3D.from_dict(data["p3"])

        else:
            # Create new points if no map provided
            p1 = Point3D.from_dict(data["p1"])
            p2 = Point3D.from_dict(data["p2"])
            p3 = Point3D.from_dict(data["p3"])

        return cls(p1, p2, p3, data.get("id"))


class Surface:
    """Represents a 3D surface composed of points and triangles.
    
    Attributes:
        name: Name of the surface
        points: Dictionary of points in the surface
        triangles: Dictionary of triangles in the surface
        metadata: Additional metadata about the surface
        source_layer_name: Optional source layer name
        source_layer_revision: Optional source layer revision
        is_stale: Boolean indicating if the surface is stale

    """

    # Surface type constants
    SURFACE_TYPE_TIN = "TIN"
    SURFACE_TYPE_GRID = "GRID"

    def __init__(
        self,
        name: str,
        points: Optional[Dict[str, Point3D]] = None,
        triangles: Optional[Dict[str, Triangle]] = None,
        source_layer_name: Optional[str] = None,
        source_layer_revision: Optional[int] = None,
    ):
        """Initialize a surface.
        
        Args:
            name: Name of the surface
            points: Dictionary of points in the surface
            triangles: Dictionary of triangles in the surface
            source_layer_name: Optional source layer name
            source_layer_revision: Optional source layer revision

        """
        self.name = name
        self.points: Dict[str, Point3D] = points if points is not None else {}
        self.triangles: Dict[str, Triangle] = triangles if triangles is not None else {}
        self.id = str(uuid.uuid4())
        self.metadata: Dict[str, Any] = {}
        self.source_layer_name = source_layer_name
        self.source_layer_revision = source_layer_revision
        self.is_stale = False

    def __str__(self) -> str:
        """String representation of the surface."""
        return f"Surface({self.name}, {len(self.points)} points, {len(self.triangles)} triangles)"

    def add_point(self, point: Point3D) -> None:
        """Add a point to the surface.
        
        Args:
            point: Point to add

        """
        self.points[point.id] = point

    def add_triangle(self, triangle: Triangle) -> None:
        """Add a triangle to the surface.
        
        Args:
            triangle: Triangle to add

        """
        # Make sure all points are in the surface
        for point in triangle.get_points():
            if point.id not in self.points:
                self.add_point(point)

        self.triangles[triangle.id] = triangle

    # ------------------------------------------------------------------
    # Grid-surface helpers
    # ------------------------------------------------------------------

    grid_data: Optional["np.ndarray"] = None  # lazily imported type hint – see methods
    grid_spacing: Optional[float] = None
    grid_origin: Optional[Tuple[float, float]] = None  # (x0, y0)

    def set_grid_data(self, grid_data: "np.ndarray", spacing: float, origin: Tuple[float, float]) -> None:
        """Attach a numpy *grid_data* array to this Surface.

        The grid is assumed to be regularly spaced at *spacing* in both the X and
        Y directions, with the *origin* tuple giving the lower-left (x, y)
        coordinate of the [0, 0] grid cell.

        The method populates ``self.points`` so that grid-based Surfaces can be
        used interchangeably with TIN-based ones elsewhere in the application.

        Args:
            grid_data: 2-D ``numpy.ndarray`` of elevations. ``np.nan`` values are
                ignored (no Point3D generated).
            spacing:  Grid spacing in same X/Y units as the coordinates.
            origin:   Tuple ``(x0, y0)`` for the gridʼs south-west corner.

        """
        # Import here to avoid mandatory numpy dependency for all modules.
        # import numpy as np # Removed import from here

        self.grid_data = grid_data
        self.grid_spacing = float(spacing)
        self.grid_origin = origin

        # Rebuild the points dict so that existing algorithms that iterate over
        # :pyattr:`points` continue to function.
        self.points.clear()
        rows, cols = grid_data.shape
        x0, y0 = origin
        for r in range(rows):
            for c in range(cols):
                z = grid_data[r, c]
                if np.isnan(z):
                    continue  # Skip empty cells
                x = x0 + c * spacing
                y = y0 + r * spacing
                p = Point3D(x=x, y=y, z=float(z))
                self.points[p.id] = p

    # ------------------------------------------------------------------
    # Alternate constructors
    # ------------------------------------------------------------------
    @classmethod
    def from_point_list(
        cls,
        name: str,
        points: List[Tuple[float, float, float]],
        spacing: Optional[float] = None,
        color: Optional[str] = None,
    ) -> "Surface":
        """Convenience constructor for grid or scatter point collections.

        Args:
            name:    Name for the new surface.
            points:  Iterable of ``(x, y, z)`` tuples.
            spacing: Optional grid spacing.  If provided the attribute
                     ``grid_spacing`` will be set so that downstream code can
                     treat this Surface as grid-based.
            color:   Arbitrary colour name stored in :pyattr:`metadata` for UI
                     hinting.

        """
        pts_dict: Dict[str, Point3D] = {}
        for x, y, z in points:
            p = Point3D(x=float(x), y=float(y), z=float(z))
            pts_dict[p.id] = p

        surf = cls(name=name, points=pts_dict)
        if spacing is not None:
            surf.grid_spacing = float(spacing)
        if color is not None:
            surf.metadata["color"] = color
        return surf

    def get_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """Get the bounds of the surface.
        
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
        """Get the elevation range of the surface.
        
        Returns:
            Tuple (zmin, zmax) or None if surface is empty

        """
        if not self.points:
            return None

        points_list = list(self.points.values())
        zmin = min(p.z for p in points_list)
        zmax = max(p.z for p in points_list)

        return (zmin, zmax)

    # --- Convenience elevation properties ---------------------------------
    @property
    def min_z(self) -> float:
        """Return minimum elevation of the surface or 0.0 if no points."""
        rng = self.get_elevation_range()
        return rng[0] if rng else 0.0

    @property
    def max_z(self) -> float:
        """Return maximum elevation of the surface or 0.0 if no points."""
        rng = self.get_elevation_range()
        return rng[1] if rng else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the surface to a dictionary."""
        surface_dict = {
            "name": self.name,
            "surface_type": self.SURFACE_TYPE_TIN,
            "id": self.id,
            "points": {pid: p.to_dict() for pid, p in self.points.items()},
            "triangles": {tid: t.to_dict() for tid, t in self.triangles.items()},
            "metadata": self.metadata,
            "source_layer_name": self.source_layer_name,
            "source_layer_revision": self.source_layer_revision,
        }
        return surface_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Surface":
        """Deserializes a surface from a dictionary, handling legacy list format for points."""
        # Deserialize points first
        points_dict: Dict[str, Point3D] = {}
        points_data = data.get("points", {})

        # --- Handle legacy list format for points ---
        if isinstance(points_data, list):
            logger.warning(f"Loading legacy surface '{data.get('name', 'Unknown')}' with list of points.")
            # Assume list contains point data dicts, generate IDs if missing
            for i, p_data in enumerate(points_data):
                if isinstance(p_data, dict):
                    # Point3D.from_dict should handle potentially missing 'id'
                    point = Point3D.from_dict(p_data)
                    # Use point's internal ID if generated, otherwise use index as fallback key
                    pid = point.id if point.id else str(i)
                    points_dict[pid] = point
                else:
                    logger.warning(f"Skipping invalid point data in list at index {i}: {p_data}")
        elif isinstance(points_data, dict):
             # --- Standard dictionary format ---
             for pid, p_data in points_data.items():
                  points_dict[pid] = Point3D.from_dict(p_data)
        else:
             logger.error(f"Invalid format for points data in surface '{data.get('name', 'Unknown')}': {type(points_data)}")
             # Proceed with empty points dict? Or raise error?
             # Let's proceed with empty for now.

        # Deserialize triangles, linking to points
        triangles_dict: Dict[str, Triangle] = {}
        triangles_data = data.get("triangles", {})

        # --- Handle legacy list format for triangles ---
        if isinstance(triangles_data, list):
            logger.warning(f"Loading legacy surface '{data.get('name', 'Unknown')}' with list of triangles.")
            # Assume list contains triangle data dicts
            for i, t_data in enumerate(triangles_data):
                if isinstance(t_data, dict):
                    # Triangle.from_dict should handle potentially missing 'id' and use points_dict
                    triangle = Triangle.from_dict(t_data, points_dict)
                    # Use triangle's internal ID if generated, otherwise use index as fallback key
                    tid = triangle.id if triangle.id else str(i)
                    triangles_dict[tid] = triangle
                else:
                    logger.warning(f"Skipping invalid triangle data in list at index {i}: {t_data}")
        elif isinstance(triangles_data, dict):
             # --- Standard dictionary format ---
             for tid, t_data in triangles_data.items():
                  triangles_dict[tid] = Triangle.from_dict(t_data, points_dict)
        else:
             logger.error(f"Invalid format for triangles data in surface '{data.get('name', 'Unknown')}': {type(triangles_data)}")
             # Proceed with empty triangles dict.

        # Create the Surface instance
        surface = cls(
            name=data.get("name", "Unnamed Surface"),
            points=points_dict,
            triangles=triangles_dict,
            source_layer_name=data.get("source_layer_name"),
            source_layer_revision=data.get("source_layer_revision"),
        )
        # is_stale is handled during project load
        return surface
