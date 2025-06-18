from __future__ import annotations

"""UIStateManager – thin wrapper around UI state update helpers.

Phase-2 refactor goal: move bulky UI-state helpers out of ``main_window.py``
into a dedicated, testable helper.  For the first migration step we keep the
original implementations inside ``MainWindow`` but route all public calls
through this manager.  In later steps the implementations will be relocated
here and the private helpers deleted from ``MainWindow``.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    # Forward-decl to avoid circular import at runtime.
    from .main_window import MainWindow  # pragma: no cover


class UIStateManager:
    """Centralises UI-state update helpers.

    Parameters
    ----------
    mw : MainWindow
        The *owning* :class:`~ui.main_window.main_window.MainWindow` instance.
    """

    def __init__(self, mw: "MainWindow") -> None:  # noqa: D401 – one-liner acceptable
        self._mw = mw
        # Re-expose the existing logger for convenience so we can keep log lines
        # identical when we move the real implementations.
        self.logger = getattr(mw, "logger", None)

    # ------------------------------------------------------------------
    # Public wrappers – these names intentionally *lack* the leading "_"
    # so external code can call them directly.  For now they delegate to
    # the legacy implementations still living on *MainWindow*.  Subsequent
    # refactor steps will migrate the body of each helper here and turn the
    # MainWindow variants into thin pass-through shims (or delete them).
    # ------------------------------------------------------------------

    # Analysis / calculations -------------------------------------------------
    def update_analysis_actions_state(self) -> None:
        """Enable/disable analysis actions based on project state."""
        if hasattr(self._mw, "_update_analysis_actions_state"):
            self._mw._update_analysis_actions_state()

    # PDF controls ------------------------------------------------------------
    def update_pdf_controls(self) -> None:
        """Refresh spin-box, toolbar, etc. for PDF background handling."""
        if hasattr(self._mw, "_update_pdf_controls"):
            self._mw._update_pdf_controls()

    # View actions ------------------------------------------------------------
    def update_view_actions_state(self) -> None:
        """Synchronise 2-D/3-D view toggle action state."""
        if hasattr(self._mw, "_update_view_actions_state"):
            self._mw._update_view_actions_state()

    # Project-level UI refresh -----------------------------------------------
    def update_ui_for_project(self, project: Optional[object]) -> None:  # type: ignore[arg-type]
        """Refresh all UI parts after a new project is loaded/created."""
        if hasattr(self._mw, "_update_ui_for_project"):
            self._mw._update_ui_for_project(project)  # type: ignore[arg-type]

    # Window title ------------------------------------------------------------
    def update_window_title(self) -> None:
        """Re-calc and set the main window title."""
        if hasattr(self._mw, "_update_window_title"):
            self._mw._update_window_title()

    # Scale helpers -----------------------------------------------------------
    def update_scale_action_enabled(self, loaded: bool) -> None:
        """Enable/disable the *Calibrate Scale…* action."""
        if hasattr(self._mw, "_update_scale_action_enabled"):
            self._mw._update_scale_action_enabled(loaded)

    def update_scale_pill(self) -> None:
        """Refresh the scale status pill in the status-bar."""
        if hasattr(self._mw, "_update_scale_pill"):
            self._mw._update_scale_pill()

    # Build-surface action ----------------------------------------------------
    def update_build_surface_action_state(self) -> None:
        """Enable/disable *Build Surface* based on traced polylines."""
        if hasattr(self._mw, "_update_build_surface_action_state"):
            self._mw._update_build_surface_action_state() 