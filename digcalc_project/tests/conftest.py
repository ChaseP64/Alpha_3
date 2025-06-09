#!/usr/bin/env python3
"""Pytest configuration for DigCalc tests.

This module contains shared fixtures and configuration for
all test modules in the DigCalc application.
"""

import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Add the project root to the Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# If src directory exists, add it too
src_dir = root_dir / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

print(f"Python path: {sys.path}")

# Attempt to set PyVista to off-screen rendering for tests
try:
    import pyvista as pv
    pv.global_vars.off_screen = True
    print("PyVista off_screen mode set to True for tests.")
except ImportError:
    print("PyVista not found, off_screen mode not set.")
except AttributeError: # For older PyVista versions that might use pv.OFF_SCREEN
    try:
        import pyvista as pv
        pv.OFF_SCREEN = True
        print("PyVista OFF_SCREEN mode set to True for tests (older API).")
    except Exception as e:
        print(f"Could not set PyVista off-screen mode (older API): {e}")
except Exception as e:
    print(f"Could not set PyVista off-screen mode: {e}")

@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test files.
    
    Returns:
        Path to a temporary directory

    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir

# ---------------------------------------------------------------------------
# Fixture helpers – sample boreholes / project (Phase 0-5)
# ---------------------------------------------------------------------------

from digcalc_project.src.models.project import Project  # local import after sys.path tweaks


@pytest.fixture
def sample_boreholes_csv_path() -> Path:
    """Absolute path to *sample_boreholes.csv* test fixture."""
    return Path(__file__).parent / "fixtures" / "sample_boreholes.csv"


@pytest.fixture
def sample_project_json_path() -> Path:
    """Absolute path to *sample_project.json* test fixture."""
    return Path(__file__).parent / "fixtures" / "sample_project.json"


@pytest.fixture
def sample_project(sample_project_json_path: Path) -> Project:
    """Loaded :class:`Project` object from sample JSON fixture."""
    proj = Project.load(str(sample_project_json_path))
    assert proj is not None, "Failed to load sample project fixture"
    return proj
