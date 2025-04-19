import json
from pathlib import Path
import pytest
from typing import List, Tuple, Optional, Dict

# Adjust the import based on your project structure and how pytest discovers it
# If running pytest from the workspace root 'digcalc_project':
try:
    from src.models.project import Project, PolylineData
    from src.models.surface import Surface, Point3D
except ImportError:
    # If running pytest in a way that requires the full path:
    from digcalc_project.src.models.project import Project, PolylineData
    from digcalc_project.src.models.surface import Surface, Point3D

# Type alias for clarity
TracedPolylinesType = Dict[str, List[PolylineData]]


def _poly(*points: Tuple[float, float], elevation: Optional[float] = None) -> PolylineData:
    """Helper to create PolylineData dict for tests."""
    return {"points": list(points), "elevation": elevation}


def test_layer_storage_basic(caplog):
    """Test that polylines are added to the correct layers."""
    pr = Project(name="test_proj_layers")
    # Add valid polylines using the new helper
    pr.add_traced_polyline(_poly((0, 0), (1, 1), elevation=10.0), "Existing Surface")
    pr.add_traced_polyline(_poly((2, 0), (2, 2), elevation=10.5), "Existing Surface")
    pr.add_traced_polyline(_poly((10, 0), (10, 1), elevation=20.0), "Proposed Surface")

    # Test adding a polyline with fewer than 2 points (should be ignored)
    pr.add_traced_polyline(_poly((5, 5), elevation=5.5), "Should Be Ignored") # This will be ignored by add_traced_polyline

    assert set(pr.traced_polylines.keys()) == {
        "Existing Surface",
        "Proposed Surface",
    }, "Only layers with valid polylines should exist"

    assert len(pr.traced_polylines["Existing Surface"]) == 2
    assert len(pr.traced_polylines["Proposed Surface"]) == 1
    assert "Should Be Ignored" not in pr.traced_polylines # Verify invalid polyline wasn't added

    # Check structure of added data
    assert pr.traced_polylines["Existing Surface"][0]["points"] == [(0.0, 0.0), (1.0, 1.0)]
    assert pr.traced_polylines["Existing Surface"][0]["elevation"] == 10.0
    assert pr.traced_polylines["Proposed Surface"][0]["elevation"] == 20.0


def test_save_and_load_roundtrip(tmp_path: Path):
    """Test saving and loading the project preserves the traced_polylines dict."""
    pr = Project(name="test_proj_roundtrip")

    # Setup using the NEW format: Dict[str, List[PolylineData]]
    polyline_data_new_format: TracedPolylinesType = {
        "Test Layer 1": [
            _poly((5, 5), (6, 6), elevation=10.0),
            _poly((7, 7), (8, 8), elevation=None)
        ],
        "Test Layer 2": [
            _poly((10, 10), (11, 11), elevation=20.5)
        ]
    }
    # Assign the correctly structured data
    pr.traced_polylines = polyline_data_new_format
    pr.is_modified = True

    file = tmp_path / "proj.json"
    save_success = pr.save(file)
    assert save_success, "Project save should succeed"
    assert not pr.is_modified, "is_modified should be False after save"

    # Now load it back
    pr2 = Project.load(file)
    assert pr2 is not None, "Project load should succeed"
    assert not pr2.is_modified, "is_modified should be False after load"

    # Compare loaded Python object structure against original Python structure
    assert pr2.traced_polylines == polyline_data_new_format, \
        "Loaded polylines structure should match the original input structure"


def test_legacy_migration(tmp_path: Path, caplog):
    """Test loading an old project file with a list migrates polylines."""
    # Simulate an old file that stored a simple list of lists of points
    legacy_poly_points_list = [
        [(0.0, 0.0), (1.0, 1.0)],
        [(2.0, 2.0), (3.0, 3.0)]
    ]
    legacy_data = {
        "name": "legacy_project",
        "created_at": "2023-01-01T12:00:00",
        "modified_at": "2023-01-01T13:00:00",
        "traced_polylines": legacy_poly_points_list # The old list format
    }
    file = tmp_path / "legacy.json"
    file.write_text(json.dumps(legacy_data))

    # Load the legacy project
    pr = Project.load(file)
    assert pr is not None, "Legacy project load should succeed"

    # Check migration results
    assert list(pr.traced_polylines.keys()) == ["Legacy Traces"], "Only 'Legacy Traces' layer should exist"
    migrated_layer = pr.traced_polylines["Legacy Traces"]
    assert len(migrated_layer) == 2, "Both polylines should be migrated"
    
    # Verify structure of migrated items
    assert isinstance(migrated_layer[0], dict)
    assert "points" in migrated_layer[0]
    assert "elevation" in migrated_layer[0]
    assert migrated_layer[0]["elevation"] is None, "Migrated elevation should be None"
    assert isinstance(migrated_layer[0]["points"], list)
    # Ensure points are tuples after load
    assert all(isinstance(pt, tuple) for pt in migrated_layer[0]["points"])
    assert migrated_layer[0]["points"] == [(0.0, 0.0), (1.0, 1.0)] # Compare points (now tuples)

    assert isinstance(migrated_layer[1], dict)
    assert migrated_layer[1]["elevation"] is None
    assert migrated_layer[1]["points"] == [(2.0, 2.0), (3.0, 3.0)]

    assert pr.is_modified, "Project should be marked modified after migration"
    assert "Migrating to 'Legacy Traces' layer" in caplog.text


def test_load_invalid_polyline_format(tmp_path: Path, caplog):
    """Test loading a project where traced_polylines has an invalid format."""
    # Simulate a file where traced_polylines is neither a list nor a dict
    invalid_data = {
        "name": "invalid_format_project",
        "created_at": "2023-01-01T12:00:00",
        "modified_at": "2023-01-01T13:00:00",
        "traced_polylines": "this is not valid data"
    }
    file = tmp_path / "invalid.json"
    file.write_text(json.dumps(invalid_data))

    # Load the project
    pr = Project.load(file)
    assert pr is not None, "Project load should still succeed (but ignore invalid data)"

    # Check that traced_polylines is empty
    assert not pr.traced_polylines, "traced_polylines should be empty after loading invalid format"
    
    # Check that the project is not marked as modified
    assert not pr.is_modified, "Project should not be marked as modified"
    
    # Check logger warning for invalid format
    assert "Traced polyline data found but is in an unexpected format" in caplog.text
    assert "<class 'str'>" in caplog.text # Check that the type was logged


def test_load_missing_polylines_key(tmp_path: Path, caplog):
    """Test loading a project file where traced_polylines key is missing."""
    # Simulate a file without the traced_polylines key
    missing_key_data = {
        "name": "missing_key_project",
        "created_at": "2023-01-01T12:00:00",
        "modified_at": "2023-01-01T13:00:00"
    }
    file = tmp_path / "missing_key.json"
    file.write_text(json.dumps(missing_key_data))

    # Load the project
    pr = Project.load(file)
    assert pr is not None, "Project load should succeed"

    # Check that traced_polylines is empty
    assert not pr.traced_polylines, "traced_polylines should be empty when key is missing"
    
    # Check that the project is not marked as modified
    assert not pr.is_modified, "Project should not be marked as modified"
    
    # Ensure no error/warning about missing key specifically (it should default safely)
    assert "Migrated legacy" not in caplog.text
    assert "unexpected format" not in caplog.text 