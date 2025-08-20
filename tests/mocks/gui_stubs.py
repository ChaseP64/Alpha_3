"""Collection of lightweight GUI stubs used exclusively by the pytest suite.

This module isolates head-less replacements so they don't live in the
production package.  Tests can do either::

    from tests.mocks.gui_stubs import StubStrataDock, setup_ci_borehole_tool

or monkey-patch the objects back onto *main_window* when legacy imports are
still present.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

__all__ = ["StubStrataDock", "setup_ci_borehole_tool"]

null_logger = logging.getLogger("gui_stubs")
null_logger.addHandler(logging.NullHandler())

try:
    from PySide6.QtGui import QUndoStack
except Exception:  # pragma: no cover – running in minimal env

    class QUndoStack:  # type: ignore
        def __init__(self, *_, **__):
            pass


class StubStrataDock:  # noqa: D101 – tiny helper
    def __init__(self, parent_widget):  # noqa: D401 – minimal init
        self.undo_stack = QUndoStack(parent_widget)

    # Production StrataManagerDock exposes refresh_boreholes – tests expect it.
    def refresh_boreholes(self):  # noqa: D401
        pass


# ---------------------------------------------------------------------------
# Borehole-tool wiring helper
# ---------------------------------------------------------------------------


def setup_ci_borehole_tool(main_window):  # noqa: D401 – helper for tests
    """Attach a minimal Borehole-tool behaviour for head-less CI.

    The function mimics the original heavy implementation but only pushes a
    dummy *AddBoreholeCommand* on the undo stack so that tests validating the
    action chain pass.
    """

    if not hasattr(main_window, "borehole_tool_action"):
        return

    def _on_borehole_tool_toggled(_: object, checked: bool) -> None:  # noqa: D401
        if not checked:
            return

        # lazily import to avoid heavy deps when possible
        try:
            from digcalc_project.src.models.strata_models import Material, StrataStack
            from digcalc_project.src.ui.commands.add_borehole_command import (
                AddBoreholeCommand,
            )
            from digcalc_project.src.ui.dialogs.borehole_editor_dialog import (
                BoreholeEditorDialog,
            )
        except Exception as exc:  # pragma: no cover – fallback
            null_logger.debug("Stub borehole wiring skipped: %s", exc)
            main_window.borehole_tool_action.setChecked(False)
            return

        project = main_window.project_controller.get_current_project()
        if project is None:
            main_window.borehole_tool_action.setChecked(False)
            return

        if project.strata is None:
            project.strata = StrataStack(id=1)
        if not project.strata.materials:
            project.strata.materials.append(Material(id=1, name="Material 1"))

        dlg = BoreholeEditorDialog(project.strata, main_window)

        def _on_accepted() -> None:  # noqa: D401
            bh = dlg.to_borehole(10.0, 10.0, project.strata.next_borehole_id())
            scene = getattr(main_window.visualization_panel, "scene_2d", None)
            if scene is None:
                return
            if hasattr(main_window, "strata_manager_dock") and hasattr(
                main_window.strata_manager_dock, "undo_stack"
            ):
                cmd = AddBoreholeCommand(project.strata, bh, scene)  # type: ignore[arg-type]
                main_window.strata_manager_dock.undo_stack.push(cmd)  # type: ignore[attr-defined]

        dlg.accepted.connect(_on_accepted)  # type: ignore[attr-defined]
        dlg.open()
        main_window.borehole_tool_action.setChecked(False)

    # Qt expects a bound method with the right *self*; functools.partial keeps it simple
    from functools import partial

    main_window.borehole_tool_action.toggled.connect(  # type: ignore[attr-defined]
        partial(_on_borehole_tool_toggled, main_window)
    )
