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

import logging

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover – only needed for type checkers
    from pyvistaqt import BackgroundPlotter

# Module-private storage for the singleton instance
_plotter: Optional["BackgroundPlotter"] = None

# ---------------------------------------------------------------------------
# Helper: lightweight Qt-only stub used for CI / headless runs
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # moved to module scope so both branches share it

from PySide6.QtWidgets import QApplication, QWidget  # lightweight import


class _HeadlessPlotter:  # pylint: disable=too-few-public-methods
    """Qt-only dummy replacement for `BackgroundPlotter`.

    Exposes just the subset of the PyVista API touched by DigCalc so our test
    suite can run without an OpenGL context (e.g. CI, headless servers).
    """

    def __init__(self):
        # ------------------------------------------------------------------
        # Public flags ------------------------------------------------------
        # ------------------------------------------------------------------
        # Consumers (PvDock tests) may check this to branch behaviour.
        self.is_headless = True  # Distinguish the stub from real plotters
        # ------------------------------------------------------------------
        # Qt widget & basic scene scaffolding -------------------------------
        # ------------------------------------------------------------------
        self.interactor = QWidget()
        self.renderer = SimpleNamespace(actors={}, bounds=(0, 1, 0, 1, 0, 1))
        self.ren_win = SimpleNamespace(SetMultiSamples=lambda *a, **k: None)
        self.bounds = (0, 1, 0, 1, 0, 1)
        self.center = (0.5, 0.5, 0.5)

        # Camera stub mirrors the minimal API surface used in tests
        self._parallel = True
        self.camera = SimpleNamespace(GetParallelProjection=lambda: self._parallel)
        self.camera_position = "iso"

        # Quality-mode helpers (AA / EDL) -----------------------------------
        self._aa_on = True  # AA is considered ON by default for high-quality mode
        self.enable_anti_aliasing_called = True  # type: ignore[attr-defined]
        self.enable_trackball_style_called = False  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Quality helpers --------------------------------------------------
    # ------------------------------------------------------------------
    def enable_anti_aliasing(self):
        self._aa_on = True
        self.enable_anti_aliasing_called = True  # type: ignore[attr-defined]

    def enable_trackball_style(self):
        self.enable_trackball_style_called = True  # type: ignore[attr-defined]

    # EDL helpers share AA flag for simplicity
    enable_eye_dome_lighting = enable_anti_aliasing

    def disable_anti_aliasing(self):
        self._aa_on = False

    disable_eye_dome_lighting = disable_anti_aliasing

    # ------------------------------------------------------------------
    # Mesh helpers -----------------------------------------------------
    # ------------------------------------------------------------------
    class _StubMapper:  # noqa: D401 – minimal API shim
        def __init__(self):
            from types import SimpleNamespace as _SN

            self._planes: list[object] = []
            # Provide dataset with point-count attr for assertions
            self.dataset = _SN(n_points=1)

        # Clipping plane API subset -------------------------------------
        def AddClippingPlane(self, plane):  # noqa: N802, ANN001
            self._planes.append(plane)

        def RemoveAllClippingPlanes(self):  # noqa: N802
            self._planes.clear()

        def GetNumberOfClippingPlanes(self):  # noqa: N802
            return len(self._planes)

    class _StubActor(SimpleNamespace):
        """Mimic basic VTK actor API touched by PvDock and tests."""

        def __init__(self):
            super().__init__(
                prop=SimpleNamespace(representation="surface", color=None),
                mapper=_HeadlessPlotter._StubMapper(),
                bounds=(0, 1, 0, 1, 0, 1),
            )
            self._visible = True
            self._scale = (1.0, 1.0, 1.0)

        # VTK-actor-like helpers ---------------------------------------
        def SetVisibility(self, flag: bool):  # noqa: N802
            self._visible = bool(flag)

        def GetVisibility(self):  # noqa: N802
            return self._visible

        # Scale helpers -------------------------------------------------
        def SetScale(self, sx: float, sy: float, sz: float):  # noqa: N802
            self._scale = (float(sx), float(sy), float(sz))

        def GetScale(self):  # noqa: N802
            return self._scale

    def add_mesh(self, mesh, **_k):
        """Add a mesh and return a stub actor while tracking it internally."""
        actor = _HeadlessPlotter._StubActor()
        # Propagate point-count to mapper.dataset for assertions
        try:
            npts = getattr(mesh, "n_points", 1)
            actor.mapper.dataset.n_points = npts
        except Exception:
            pass
        self.renderer.actors[id(actor)] = actor
        return actor

    # ------------------------------------------------------------------
    # Legend helpers ---------------------------------------------------
    # ------------------------------------------------------------------
    def add_legend(self, entries, **kwargs):  # noqa: D401, ANN001
        """Create a test-friendly legend actor stored in renderer.actors."""
        legend_actor = {"entries": entries, "_is_legend": True}
        self.renderer.actors["legend"] = legend_actor
        self._digcalc_legend_actor = legend_actor  # type: ignore[attr-defined]
        return legend_actor

    def remove_actor(self, actor):  # noqa: ANN001
        """Remove *actor* from registry and clear legend handle if matching."""
        self.renderer.actors.pop(id(actor), None)
        if getattr(self, "_digcalc_legend_actor", None) is actor:  # type: ignore[attr-defined]
            self._digcalc_legend_actor = None  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Scene helpers ----------------------------------------------------
    # ------------------------------------------------------------------
    def clear(self):
        self.renderer.actors.clear()

    clear_actors = clear  # Alias common PyVista method

    def reset_camera(self, *args, **kwargs):  # noqa: D401
        pass  # No-op for stub

    def enable_parallel_projection(self):  # noqa: D401
        self._parallel = True

    def render(self):  # noqa: D401
        pass  # Intentionally blank

    # Misc helpers -----------------------------------------------------
    def add_axes(self, *args, **kwargs):
        pass

    def add_scale_bar(self, *args, **kwargs):
        pass

    def add_orientation_widget(self, *args, **kwargs):
        pass

    # ------------------------------------------------------------------
    # Section-plane widget ---------------------------------------------
    # ------------------------------------------------------------------
    def add_plane_widget(self, *_a, callback=None, **_k):  # noqa: D401, ANN001
        """Return a minimal stub with the subset of API used by PvDock."""

        class _DummyPlaneWidget:  # pylint: disable=too-few-public-methods
            def __init__(self, cb):
                self._enabled = True
                self._origin = (0, 0, 0)
                self._normal = (0, 0, 1)
                self._cb = cb
                # Initial callback (mimic creation trigger)
                if self._cb:
                    self._cb((0, 0, 1), (0, 0, 0))

            def SetEnabled(self, flag: bool):  # noqa: N802
                self._enabled = bool(flag)
                if flag and self._cb:
                    self._cb((0, 0, 1), (0, 0, 0))

            def GetEnabled(self):  # noqa: N802
                return self._enabled

            enabled = property(GetEnabled, SetEnabled)

            def SetOrigin(self, origin):  # noqa: N802
                self._origin = origin

            def SetNormal(self, normal):  # noqa: N802
                self._normal = normal

        return _DummyPlaneWidget(callback)

    # Screenshot stub (used by screenshot feature) ---------------------
    def screenshot(self, *_a, **_k):  # noqa: D401
        pass


def _create_plotter() -> "BackgroundPlotter":  # pragma: no cover – runtime side-effect
    """Internal helper that tries real PyVista first, falls back to a headless stub.

    The real `BackgroundPlotter` may fail in head-less CI (no valid OpenGL
    context).  If **any** exception arises we create a lightweight Qt-only
    stub that exposes the minimal API surface required by DigCalc's widgets
    and unit-tests.  This keeps 3-D dependent code paths testable without the
    heavy VTK stack.
    """
    logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Prefer stub when running in CI / test mode -----------------------
    # ------------------------------------------------------------------
    if os.getenv("PYVISTA_OFF_SCREEN", "false").lower() == "true" or os.getenv(
        "PYTEST_CURRENT_TEST"
    ):
        logger.info("CI/Test environment detected. Using HeadlessPlotter.")
        return _HeadlessPlotter()  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Attempt real BackgroundPlotter. On *any* failure, fall back to stub.
    # ------------------------------------------------------------------
    plotter: Optional["BackgroundPlotter"] = None

    try:
        from PySide6.QtWidgets import QApplication  # ADD THIS IMPORT
        from pyvistaqt import BackgroundPlotter  # local import – heavyweight

        logger.debug("Attempting to create real pyvistaqt.BackgroundPlotter...")

        # --- EXPLICITLY GET APP INSTANCE ---
        app_instance = QApplication.instance()
        if app_instance is None:
            logger.warning(
                "QApplication.instance() is None during _create_plotter. "
                "This is unexpected when the main application is running."
            )
            # Fallback or raise, but BackgroundPlotter(app=None) might still work
            # if an app is later created or if it can operate headlessly before attaching.
        # --- END EXPLICIT GET ---

        plotter = BackgroundPlotter(show=False, app=app_instance)  # MODIFY THIS LINE
        logger.debug("Real BackgroundPlotter created. Configuring...")

        if hasattr(plotter, "enable_anti_aliasing"):
            plotter.enable_anti_aliasing()
        if hasattr(plotter, "enable_trackball_style"):
            plotter.enable_trackball_style()
        logger.info("Real BackgroundPlotter configured and returning.")
        return plotter  # pragma: no cover – real backend path

    except Exception as e:
        logger.error(f"Failed to initialize real PyVista BackgroundPlotter: {e}", exc_info=True)
        logger.warning("Falling back to HeadlessPlotter due to PyVista initialization error.")
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
