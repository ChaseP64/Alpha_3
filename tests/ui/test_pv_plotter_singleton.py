from __future__ import annotations

"""Tests for the ``pv_plotter_singleton`` helper module.

These tests patch the heavy ``pyvistaqt`` dependency with a lightweight dummy
class so that they run in headless CI environments.
"""

import importlib
import sys
from types import ModuleType
from typing import Any, Generator

import pytest


class _DummyPlotter:  # pylint: disable=too-few-public-methods
    """Minimal stub for :class:`pyvistaqt.BackgroundPlotter`."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401, ANN401
        self.args = args
        self.kwargs = kwargs
        self.enable_anti_aliasing_called = False
        self.enable_trackball_style_called = False

    # PyVista API we touch in the helper
    def enable_anti_aliasing(self) -> None:  # noqa: D401
        self.enable_anti_aliasing_called = True

    def enable_trackball_style(self) -> None:  # noqa: D401 # Added for Task 4 compatibility
        self.enable_trackball_style_called = True  # noqa: D401

    # Convenience for tests that might call ``close`` later on.
    def close(self) -> None:  # noqa: D401
        self.closed = True


@pytest.fixture(autouse=True)
def _patch_pyvistaqt(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:  # noqa: D401
    """Patch ``sys.modules['pyvistaqt']`` with a dummy module.

    This prevents importing the real VTK/PyVista stack during automated tests.
    """

    dummy_module = ModuleType("pyvistaqt")
    dummy_module.BackgroundPlotter = _DummyPlotter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvistaqt", dummy_module)
    yield
    # Cleanup – not strictly necessary because the fixture is module-scoped and
    # the Python process will exit, but good hygiene.
    sys.modules.pop("pyvistaqt", None)
    # ``pv_plotter_singleton`` keeps a global reference – ensure fresh import in
    # each test to avoid cross-test contamination.
    sys.modules.pop("digcalc_project.src.ui.pv_plotter_singleton", None)


def _import_helper():
    """Import the helper fresh each time so globals reset."""
    return importlib.import_module("digcalc_project.src.ui.pv_plotter_singleton")


def test_singleton_returns_same_instance() -> None:  # noqa: D401
    helper = _import_helper()
    plotter_1 = helper.get_plotter()
    plotter_2 = helper.get_plotter()
    assert plotter_1 is plotter_2, "Expected get_plotter() to return singleton instance"
    assert (
        plotter_1.enable_anti_aliasing_called is True
    ), "Anti-aliasing should be enabled on creation"


def test_singleton_recreates_after_manual_reset() -> None:  # noqa: D401
    helper = _import_helper()
    first = helper.get_plotter()
    # Manually reset the singleton (simulates PvDock cleanup + GC).
    helper._plotter = None  # pylint: disable=protected-access
    second = helper.get_plotter()
    assert first is not second, "A new instance should be created after reset"
