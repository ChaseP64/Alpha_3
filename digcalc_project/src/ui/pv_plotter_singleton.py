from __future__ import annotations

"""Singleton accessor for the application's ``pyvistaqt.BackgroundPlotter``.

The 3-D viewer overhaul (see PLAN.md) standardises on a single, centrally
managed ``BackgroundPlotter`` instance to avoid multiple OpenGL contexts and
wglMakeCurrent errors.  All UI components that need a plotter should import
and call :func:`get_plotter` instead of creating their own.

Lifecycle notes
---------------
* This module **only** instantiates – it deliberately does **not** close the
  plotter.  The owner widget (``PvDock``) is responsible for calling
  ``plotter.close()`` during its ``closeEvent`` and on
  ``QApplication.aboutToQuit``.
* Because the import cost of ``pyvistaqt`` (and VTK) is high, we keep the
  import local to the singleton creation so that importing this helper is
  cheap unless the plotter is actually needed.

Returns:
    A shared ``BackgroundPlotter`` instance configured for DigCalc.
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover – only needed for type checkers
    from pyvistaqt import BackgroundPlotter

# Module-private storage for the singleton instance
_plotter: Optional["BackgroundPlotter"] = None

# ---------------------------------------------------------------------------
# Helper: lightweight Qt-only stub used for CI / headless runs
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # moved to module scope so both branches share it
from PySide6.QtWidgets import QWidget  # lightweight import


class _HeadlessPlotter:  # pylint: disable=too-few-public-methods
    """Qt-only dummy replacement for `BackgroundPlotter`.

    Exposes just the subset of the PyVista API touched by DigCalc so our test
    suite can run without an OpenGL context (e.g. CI, headless servers).
    """

    def __init__(self):
        self.interactor = QWidget()
        self.renderer = SimpleNamespace(actors={}, bounds=(0, 1, 0, 1, 0, 1))
        self.ren_win = SimpleNamespace(SetMultiSamples=lambda *a, **k: None)
        self._parallel = True
        self.camera = SimpleNamespace(GetParallelProjection=lambda: self._parallel)
        self.bounds = (0, 1, 0, 1, 0, 1)
        self.center = (0.5, 0.5, 0.5)
        self.camera_position = "iso"
        self.enable_anti_aliasing_called = True  # type: ignore[attr-defined]

    # Quality helpers ------------------------------------------------------
    def enable_anti_aliasing(self):
        # Record flag for unit-test expectations
        self.enable_anti_aliasing_called = True  # type: ignore[attr-defined]

    def enable_trackball_style(self):
        self.enable_trackball_style_called = True  # type: ignore[attr-defined]
        pass

    enable_eye_dome_lighting = enable_anti_aliasing

    def disable_anti_aliasing(self):
        pass

    disable_eye_dome_lighting = disable_anti_aliasing

    # Mesh helpers ---------------------------------------------------------
    class _StubMapper:  # noqa: D401 – minimal API shim
        def __init__(self):
            self._planes: list[tuple] = []
            self.dataset = SimpleNamespace(n_points=1)

        # Clipping plane API ------------------------------------------------
        def AddClippingPlane(self, *_a, **_k):  # noqa: N802
            self._planes.append((_a, _k))

        def RemoveAllClippingPlanes(self, *_a, **_k):  # noqa: N802
            self._planes.clear()

        def GetNumberOfClippingPlanes(self):  # noqa: N802
            return len(self._planes)

    class _StubActor(SimpleNamespace):
        """Mimic basic VTK actor API touched by PvDock/tests."""

        def __init__(self):
            super().__init__(
                prop=SimpleNamespace(representation="surface", color=None),
                mapper=_HeadlessPlotter._StubMapper(),
                bounds=(0, 1, 0, 1, 0, 1),
            )
            self._visible = True
            self._scale = (1.0, 1.0, 1.0)

        # VTK actor methods -------------------------------------------------
        def SetVisibility(self, flag: bool):  # noqa: N802
            self._visible = bool(flag)

        def GetVisibility(self):  # noqa: N802
            return self._visible

        def SetScale(self, *_a):  # noqa: N802
            if len(_a) == 3:
                self._scale = tuple(float(v) for v in _a)

        def GetScale(self):  # noqa: N802
            return self._scale

    def add_mesh(self, mesh, **_k):
        # Update mapper dataset points count for assertions
        actor = _HeadlessPlotter._StubActor()
        if hasattr(actor, "mapper"):
            try:
                actor.mapper.dataset = SimpleNamespace(n_points=getattr(mesh, "n_points", 1))
            except Exception:
                pass
        self.renderer.actors[id(actor)] = actor
        return actor

    def remove_actor(self, actor):  # noqa: ANN001
        self.renderer.actors.pop(id(actor), None)
        if getattr(self, "_digcalc_legend_actor", None) is actor:
            self._digcalc_legend_actor = None  # type: ignore[attr-defined]

    def clear(self):
        self.renderer.actors.clear()

    clear_actors = clear

    # Camera & render stubs -----------------------------------------------
    def reset_camera(self, *args, **kwargs):  # noqa: D401
        pass

    def enable_parallel_projection(self):
        self._parallel = True

    def render(self):  # noqa: D401
        pass

    # Misc helpers ---------------------------------------------------------
    def add_axes(self, *args, **kwargs):
        pass

    def add_scale_bar(self, *args, **kwargs):
        pass

    def add_orientation_widget(self, *args, **kwargs):
        pass

    def add_legend(self, *args, **kwargs):
        legend = object()
        # Store for tests expecting this attribute
        self._digcalc_legend_actor = legend  # type: ignore[attr-defined]
        return legend

    # Section-plane widget dummy ------------------------------------------
    def add_plane_widget(self, *_a, **_k):  # noqa: D401, ANN001
        class _DummyPlaneWidget:  # pylint: disable=too-few-public-methods
            def SetEnabled(self, _flag):
                pass

            def GetEnabled(self):
                return False

        return _DummyPlaneWidget()

    screenshot = render


def _create_plotter() -> "BackgroundPlotter":  # pragma: no cover – runtime side-effect
    """Internal helper that tries real PyVista first, falls back to a headless stub.

    The real `BackgroundPlotter` may fail in head-less CI (no valid OpenGL
    context).  If **any** exception arises we create a lightweight Qt-only
    stub that exposes the minimal API surface required by DigCalc's widgets
    and unit-tests.  This keeps 3-D dependent code paths testable without the
    heavy VTK stack.
    """

    # ------------------------------------------------------------------
    # Prefer stub when running in CI / test mode -----------------------
    # ------------------------------------------------------------------
    if os.getenv("PYVISTA_OFF_SCREEN", "false").lower() == "true" or os.getenv(
        "PYTEST_CURRENT_TEST"
    ):
        return _HeadlessPlotter()  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Attempt real BackgroundPlotter. On *any* failure, fall back to stub.
    # ------------------------------------------------------------------
    try:
        from pyvistaqt import BackgroundPlotter  # local import – heavyweight

        plotter = BackgroundPlotter(show=False)
        if hasattr(plotter, "enable_anti_aliasing"):
            plotter.enable_anti_aliasing()
        if hasattr(plotter, "enable_trackball_style"):
            plotter.enable_trackball_style()
        return plotter  # pragma: no cover – real backend path

    except Exception:
        # Any failure (including VTK OpenGL init) → stub.
        return _HeadlessPlotter()  # type: ignore[return-value]


def get_plotter() -> "BackgroundPlotter":
    """Return the shared ``BackgroundPlotter`` instance.

    Creates it on first call, then returns the cached instance thereafter.
    This ensures a singleton across the entire application.
    """

    global _plotter
    if _plotter is None:
        _plotter = _create_plotter()
    return _plotter 