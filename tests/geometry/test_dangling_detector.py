import pytest

from digcalc_project.src.core.geometry.dangling_detector import detect_dangling_edges
from digcalc_project.src.models.surface import Point3D, Surface, Triangle


def _square_surface() -> Surface:
    # Build 4 points making a unit square in XY plane
    p1 = Point3D(0.0, 0.0, 0.0)
    p2 = Point3D(1.0, 0.0, 0.0)
    p3 = Point3D(0.0, 1.0, 0.0)
    p4 = Point3D(1.0, 1.0, 0.0)

    t1 = Triangle(p1, p2, p3)
    t2 = Triangle(p2, p4, p3)

    surf = Surface("square")
    surf.add_triangle(t1)
    surf.add_triangle(t2)
    return surf


def test_detects_expected_boundary_edges():
    surf = _square_surface()
    edges = detect_dangling_edges(surf)

    # There should be 4 boundary edges around the square
    assert len(edges) == 4

    # Each endpoint pair should be unique disregarding order
    sorted_pairs = {tuple(sorted((e[0].id, e[1].id))) for e in edges}
    assert len(sorted_pairs) == 4


def test_watertight_tin_returns_empty():
    # Build a closed tetrahedron (4 triangles, no dangling edges)
    p1 = Point3D(0, 0, 0)
    p2 = Point3D(1, 0, 0)
    p3 = Point3D(0, 1, 0)
    p4 = Point3D(0, 0, 1)

    tris = [
        Triangle(p1, p2, p3),
        Triangle(p1, p2, p4),
        Triangle(p1, p3, p4),
        Triangle(p2, p3, p4),
    ]
    surf = Surface("tetra")
    for t in tris:
        surf.add_triangle(t)

    assert detect_dangling_edges(surf) == []
