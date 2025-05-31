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

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover – only needed for type checkers
    from pyvistaqt import BackgroundPlotter

# Module-private storage for the singleton instance
_plotter: Optional["BackgroundPlotter"] = None


def _create_plotter() -> "BackgroundPlotter":  # pragma: no cover – runtime side-effect
    """Create and configure a new ``BackgroundPlotter`` instance.

    The plotter is created with ``show=False`` so that the caller can decide
    when/if the window should become visible.
    """

    from pyvistaqt import BackgroundPlotter  # local import – see module docstring

    plotter = BackgroundPlotter(show=False)
    # Quality defaults – these can be tweaked by the owning PvDock or Draft
    # Mode logic later.
    plotter.enable_anti_aliasing()
    plotter.enable_trackball_style()
    return plotter


def get_plotter() -> "BackgroundPlotter":
    """Return the shared ``BackgroundPlotter`` instance.

    Creates it on first call, then returns the cached instance thereafter.
    This ensures a singleton across the entire application.
    """

    global _plotter
    if _plotter is None:
        _plotter = _create_plotter()
    return _plotter 