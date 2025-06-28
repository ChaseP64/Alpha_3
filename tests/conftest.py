"""Global test fixtures for environments without pytest-mock installed."""
import importlib
import sys
import types
from pathlib import Path
import os
import tempfile
from collections.abc import Generator

import pytest

# ---------------------------------------------------------------------------
# Ensure the repository root is on sys.path so that `import digcalc_project` is
# always resolvable when tests are run from any working directory (e.g., CI).
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Add `digcalc_project` to path to allow `src` imports
project_dir = _repo_root / "digcalc_project"
if project_dir.exists() and str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# Ensure that the legacy top-level import path "src" (which actually lives
# under *digcalc_project/src*) is importable.  Some tests still use
# ``from src.models.XXX import ...``.  We therefore prepend that directory to
# *sys.path* **before** any such import is attempted.
legacy_src_dir = project_dir / "src"
if legacy_src_dir.exists() and str(legacy_src_dir) not in sys.path:
    sys.path.insert(0, str(legacy_src_dir))

# Attempt to set PyVista to off-screen rendering for tests
try:
    import pyvista as pv
    pv.global_vars.off_screen = True
except ImportError:
    pass  # PyVista not installed
except AttributeError: # For older PyVista versions that might use pv.OFF_SCREEN
    try:
        import pyvista as pv
        pv.OFF_SCREEN = True
    except Exception:
        pass
except Exception:
    pass

from digcalc_project.src.models.project import Project


@pytest.fixture
def mocker(monkeypatch):
    """Very small subset of *pytest-mock*'s fixture.

    Only implements :py:meth:`patch` with *return_value* support which is all
    that our current test suite requires.  If *pytest-mock* **is** available we
    simply delegate to the real fixture so developers with the plugin installed
    get the full API.
    """
    try:
        # If pytest-mock is installed, use the real fixture to avoid surprises.
        # pylint: disable=import-error
        import pytest_mock  # noqa: F401
        # Request the real fixture from pytest's fixture store.
        return pytest.MockerFixture(monkeypatch)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover – fall back to tiny stub
        class _StubMocker:
            def __init__(self, _mp):
                self._mp = _mp

            def patch(self, target: str, **kwargs):
                module_name, attr_name = target.rsplit(".", 1)
                module = importlib.import_module(module_name)
                dummy = kwargs.get("return_value")
                if dummy is None:
                    dummy = types.SimpleNamespace()
                self._mp.setattr(module, attr_name, dummy)
                return dummy

        return _StubMocker(monkeypatch)


# ---------------------------------------------------------------------------
# Lightweight *benchmark* fixture (fallback when pytest-benchmark is absent)
# ---------------------------------------------------------------------------


@pytest.fixture
def benchmark():
    """Minimal stand-in for *pytest-benchmark*'s fixture.

    The real plugin provides rich statistical analysis; for our purposes we
    only need to measure *wall-clock* runtime once so that unit-tests can
    assert the algorithm completes within a rough threshold.  We therefore
    implement a simple timer around the supplied callable and return the
    elapsed seconds as a float.
    """

    import time

    def _runner(func, *args, **kwargs):  # type: ignore[override]
        t0 = time.perf_counter()
        func(*args, **kwargs)
        return time.perf_counter() - t0

    return _runner


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

# ---------------------------------------------------------------------------
# Additional fixtures required by UI tests
# ---------------------------------------------------------------------------


@pytest.fixture
def temporary_settings(tmp_path, monkeypatch):
    """Temporary settings.json path used by UI tests.

    Writes an empty JSON config file and points the SettingsService env var so
    the application reads/writes to this isolated location.
    """

    cfg_file = tmp_path / "settings.json"
    cfg_file.write_text("{}")

    monkeypatch.setenv("DIGCALC_SETTINGS_PATH", str(cfg_file))

    yield cfg_file
