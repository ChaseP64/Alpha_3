import pytest

from digcalc_project.src.models.project import PolylineData, Project


def test_traced_polyline_serializes_strata_flag():
    project = Project(name="Test Project")

    polyline: PolylineData = {
        "points": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
        "elevation": None,
        "is_strata": True,
        "material_id": 1,
    }

    idx = project.add_traced_polyline(polyline, layer_name="Layer1")
    assert idx == 0, "Polyline should be added at index 0"

    ser = project._serialisable_polylines()
    assert "Layer1" in ser
    saved = ser["Layer1"][0]
    assert saved["is_strata"] is True
    assert saved["material_id"] == 1
