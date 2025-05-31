from __future__ import annotations

import numpy as np
import pyvista as pv
import pytest

from digcalc_project.src.models.surface import Surface # Assuming this path is correct
from digcalc_project.src.utils.surface_to_polydata import surface_to_polydata

# Mock Surface class for testing if direct import/instantiation is complex
# If Surface is a simple dataclass, direct instantiation is fine.
# For this example, let's assume Surface can be mocked or is simple enough.

@pytest.fixture
def simple_surface() -> Surface:
    """Return a basic valid Surface object."""
    # This is a simplified representation of your Surface model
    # Adjust fields based on your actual Surface dataclass definition
    s = Surface(name="TestSimple")
    s.vertices = [(0,0,0), (1,0,0), (0,1,0), (1,1,1)] # Added Z variation
    s.triangles = [(0,1,2), (1,3,2)]
    return s

@pytest.fixture
def surface_no_vertices() -> Surface:
    """Return a Surface object with no vertices."""
    s = Surface(name="TestNoVertices")
    s.vertices = []
    s.triangles = []
    return s

@pytest.fixture
def surface_no_triangles() -> Surface:
    """Return a Surface object with vertices but no triangles (point cloud)."""
    s = Surface(name="TestNoTriangles")
    s.vertices = [(0,0,0), (1,1,1), (2,0,0)]
    s.triangles = []
    return s

@pytest.fixture
def surface_bad_triangles() -> Surface:
    """Return a Surface with triangle indices out of bounds."""
    s = Surface(name="TestBadTriangles")
    s.vertices = [(0,0,0), (1,0,0)] # Only 2 vertices
    s.triangles = [(0,1,2)] # Index 2 is out of bounds
    return s


def test_surface_to_polydata_valid(simple_surface: Surface) -> None:
    """Test conversion of a valid Surface to PolyData."""
    mesh = surface_to_polydata(simple_surface)
    assert isinstance(mesh, pv.PolyData)
    assert mesh.n_points == 4
    assert mesh.n_faces == 2
    # Check some point data if necessary
    assert np.allclose(mesh.points[1], [1,0,0])

def test_surface_to_polydata_no_vertices(surface_no_vertices: Surface) -> None:
    """Test conversion raises ValueError if Surface has no vertices."""
    with pytest.raises(ValueError, match="has no vertices"):
        surface_to_polydata(surface_no_vertices)

def test_surface_to_polydata_no_triangles(surface_no_triangles: Surface) -> None:
    """Test conversion creates a point cloud if Surface has no triangles."""
    mesh = surface_to_polydata(surface_no_triangles)
    assert isinstance(mesh, pv.PolyData)
    assert mesh.n_points == 3
    assert mesh.n_cells == 3 # Changed from n_faces == 0
    # assert mesh.n_faces == 0 # Original assertion, incorrect for vertex cells

def test_surface_to_polydata_bad_triangles(surface_bad_triangles: Surface) -> None:
    """Test conversion raises ValueError for bad triangle indices."""
    with pytest.raises(ValueError, match="Triangle index out of bounds"):
        surface_to_polydata(surface_bad_triangles)

def test_surface_vertices_bad_shape() -> None:
    """Test conversion raises ValueError if vertices have incorrect shape."""
    s = Surface(name="TestBadShape")
    s.vertices = [(0,0), (1,0), (0,1)] # 2D points instead of 3D
    s.triangles = [(0,1,2)]
    with pytest.raises(ValueError, match="vertices must be a list of \(x,y,z\) tuples or Nx3 array"):
        surface_to_polydata(s)

    s2 = Surface(name="TestBadShape2")
    s2.vertices = np.array([[0,0,0,0],[1,0,0,0]]) # 4D points
    s2.triangles = []
    with pytest.raises(ValueError, match="vertices must be a list of \(x,y,z\) tuples or Nx3 array"):
        surface_to_polydata(s2) 