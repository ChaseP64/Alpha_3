import json
from pathlib import Path
import pytest

# Adjust the import based on your project structure and how pytest discovers it
# If running pytest from the workspace root 'digcalc_project':
try:
    from src.models.project import Project
except ImportError:
    # If running pytest in a way that requires the full path:
    from digcalc_project.src.models.project import Project


def _poly(*pts):
    """Helper to build a list of (x, y) tuples quickly."""
    # Ensure points are tuples of floats/ints
    return [tuple(float(c) for c in p) for p in pts]


def test_layer_storage_basic(caplog):
    """Test that polylines are added to the correct layers."""
    pr = Project(name="test_proj_layers")
    # Add valid polylines
    pr.add_traced_polyline(_poly((0, 0), (1, 1)), "Existing Surface")
    pr.add_traced_polyline(_poly((2, 0), (2, 2)), "Existing Surface")
    pr.add_traced_polyline(_poly((10, 0), (10, 1)), "Proposed Surface")
    
    # Test adding a polyline with fewer than 2 points (should be ignored)
    pr.add_traced_polyline(_poly((5, 5)), "Should Be Ignored")

    assert set(pr.traced_polylines.keys()) == {
        "Existing Surface",
        "Proposed Surface",
    }, "Only layers with valid polylines should exist"
    assert len(pr.traced_polylines["Existing Surface"]) == 2, "Two polylines should be in Existing Surface"
    assert len(pr.traced_polylines["Proposed Surface"]) == 1, "One polyline should be in Proposed Surface"
    assert "Should Be Ignored" not in pr.traced_polylines, "Layer for ignored polyline should not be created"
    
    # Check logger warning for ignored polyline
    assert "Ignoring polyline with fewer than 2 points." in caplog.text


def test_save_and_load_roundtrip(tmp_path: Path):
    """Test saving and loading the project preserves the traced_polylines dict."""
    pr = Project(name="test_proj_roundtrip")
    polyline_data = {
        "Test Layer 1": [_poly((5, 5), (6, 6)), _poly((7, 7), (8, 8))],
        "Test Layer 2": [_poly((10, 10), (11, 11))]
    }
    # Add polylines using the dictionary directly for setup
    pr.traced_polylines = polyline_data
    pr.is_modified = True # Simulate modification before save
    
    file = tmp_path / "proj.json"
    save_success = pr.save(file)
    assert save_success, "Project save should succeed"
    assert not pr.is_modified, "is_modified should be False after save"

    # Ensure the file content is JSON and contains the dictionary structure
    content = file.read_text()
    saved_data = json.loads(content)
    assert "traced_polylines" in saved_data
    assert isinstance(saved_data["traced_polylines"], dict)
    
    # Compare saved JSON data (lists) against the expected list structure
    expected_polylines_in_json = {
        layer: [[list(pt) for pt in poly] for poly in polys]
        for layer, polys in polyline_data.items()
    }
    assert saved_data["traced_polylines"] == expected_polylines_in_json, "Saved JSON data should match expected list structure"

    # Now load it back
    pr2 = Project.load(file)
    assert pr2 is not None, "Project load should succeed"
    assert not pr2.is_modified, "is_modified should be False after load"

    # Convert original tuples to lists for comparison after JSON load
    expected_polylines_after_load = {
        layer: [[list(pt) for pt in poly] for poly in polys]
        for layer, polys in pr.traced_polylines.items()
    }
    assert pr2.traced_polylines == expected_polylines_after_load, "Loaded polylines dict should match original (with tuples converted to lists)"


def test_legacy_migration(tmp_path: Path, caplog):
    """Test loading an old project file with a list migrates polylines."""
    # Simulate an old file that stored a simple list
    # Include required fields for basic project loading
    legacy_polys = [_poly((0, 0), (1, 1)), _poly((2, 2), (3, 3))]
    legacy_data = {
        "name": "legacy_project",
        "created_at": "2023-01-01T12:00:00",
        "modified_at": "2023-01-01T13:00:00",
        # Simulate the list structure directly as it would be in old JSON
        "traced_polylines": [[list(pt) for pt in poly] for poly in legacy_polys] 
    }
    file = tmp_path / "legacy.json"
    file.write_text(json.dumps(legacy_data))

    # Load the legacy project
    pr = Project.load(file)
    assert pr is not None, "Legacy project load should succeed"

    # Check migration results
    assert list(pr.traced_polylines.keys()) == ["Legacy Traces"], "Only 'Legacy Traces' layer should exist"
    assert len(pr.traced_polylines["Legacy Traces"]) == 2, "Both polylines should be migrated"
    # The migrated layer should contain the original polyline points, converted to lists by JSON
    # Compare against the list structure that was saved in the legacy JSON
    assert pr.traced_polylines["Legacy Traces"] == legacy_data["traced_polylines"], "Migrated polylines should match original list data (as lists)"
    
    # Check that the project is marked as modified due to migration
    assert pr.is_modified, "Project should be marked as modified after migration"
    
    # Check logger warning for migration
    assert "Migrated legacy polyline list to 'Legacy Traces' layer" in caplog.text
    assert f"({len(legacy_polys)} polylines)" in caplog.text

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