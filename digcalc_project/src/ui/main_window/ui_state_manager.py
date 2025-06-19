from __future__ import annotations

"""UIStateManager – thin wrapper around UI state update helpers.

Phase-2 refactor goal: move bulky UI-state helpers out of ``main_window.py``
into a dedicated, testable helper.  For the first migration step we keep the
original implementations inside ``MainWindow`` but route all public calls
through this manager.  In later steps the implementations will be relocated
here and the private helpers deleted from ``MainWindow``.
"""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtGui import QColor

if TYPE_CHECKING:
    # Forward-decl to avoid circular import at runtime.
    from .main_window import MainWindow  # pragma: no cover
    from ...models.project import Project

logger = logging.getLogger(__name__)


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
        self.logger = getattr(mw, "logger", logger)

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
        project = self._mw.project_controller.get_current_project()
        can_calculate = bool(project and len(project.surfaces) >= 2)
        self._mw.calculate_volume_action.setEnabled(can_calculate)
        has_req_surfaces = False
        if project:
            has_req_surfaces = (
                getattr(project, "existing_surface", None) is not None
                and getattr(project, "design_surface", None) is not None
            )
        self._mw.masshaul_action.setEnabled(can_calculate and has_req_surfaces)
        self.logger.debug(f"Calculate Volume action enabled state: {can_calculate}")

    # PDF controls ------------------------------------------------------------
    def update_pdf_controls(self) -> None:
        """Updates the state of PDF-related controls (spinbox, labels, actions)."""
        panel = self._mw.visualization_panel
        has_pdf = panel.has_pdf()
        page_count = panel.pdf_renderer.get_page_count() if panel.pdf_renderer else 0
        current_page_1_based = panel.current_pdf_page if has_pdf else 1

        if self._mw.pdf_page_spinbox:
            self._mw.pdf_page_spinbox.setEnabled(has_pdf and page_count > 1)
            self._mw.pdf_page_spinbox.setRange(1, max(1, page_count))
            self._mw.pdf_page_spinbox.blockSignals(True)
            self._mw.pdf_page_spinbox.setValue(current_page_1_based)
            self._mw.pdf_page_spinbox.blockSignals(False)
        else:
            self.logger.warning("Cannot update missing pdf_page_spinbox")

        if self._mw.pdf_page_label:
            if has_pdf:
                self._mw.pdf_page_label.setText(f"Page: {current_page_1_based} / {page_count}")
            else:
                self._mw.pdf_page_label.setText("Page: N/A")
        else:
            self.logger.warning("Cannot update missing pdf_page_label")

        if hasattr(self._mw, "prev_pdf_page_action"):
            self._mw.prev_pdf_page_action.setEnabled(has_pdf and current_page_1_based > 1)
        if hasattr(self._mw, "next_pdf_page_action"):
            self._mw.next_pdf_page_action.setEnabled(has_pdf and current_page_1_based < page_count)

        self._mw.pdf_thumbnail_dock.setVisible(has_pdf)

        if hasattr(self._mw, "pdf_toolbar"):
            self._mw.pdf_toolbar.setVisible(has_pdf)
            self.logger.debug(f"Setting PDF toolbar visibility to: {has_pdf}")
        else:
            self.logger.warning("Cannot set PDF toolbar visibility: pdf_toolbar attribute not found.")

        self.logger.debug(f"PDF controls updated: has_pdf={has_pdf}, page_count={page_count}, current_page={current_page_1_based}")
        self.update_scale_action_enabled(has_pdf)
        try:
            self.update_scale_pill()
        except Exception as exc:
            self.logger.warning("Failed to refresh scale pill in update_pdf_controls: %s", exc)

    # View actions ------------------------------------------------------------
    def update_view_actions_state(self) -> None:
        """Updates the enabled and checked state of the view toggle actions (2D/3D)."""
        if not hasattr(self._mw, "view_2d_action") or not hasattr(self._mw, "view_3d_action") or not hasattr(self._mw, "visualization_panel"):
            logger.warning("update_view_actions_state called before actions/panel were created.")
            return

        has_pdf = self._mw.visualization_panel.has_pdf()
        has_surfaces = self._mw.visualization_panel.has_surfaces()
        is_2d_current = self._mw.visualization_panel.stacked_widget.currentWidget() == self._mw.visualization_panel.view_2d
        is_3d_current = self._mw.visualization_panel.stacked_widget.currentWidget() == self._mw.visualization_panel.view_3d

        logger.debug(f"Updating view actions: has_pdf={has_pdf}, has_surfaces={has_surfaces}, is_2d_current={is_2d_current}, is_3d_current={is_3d_current}")

        self._mw.view_2d_action.setEnabled(has_pdf)
        self._mw.view_3d_action.setEnabled(has_surfaces)

        can_trace = is_2d_current and has_pdf
        if hasattr(self._mw, "toggle_trace_mode_action"):
            self._mw.toggle_trace_mode_action.setEnabled(can_trace)
            logger.debug(f"Set toggle_trace_mode_action enabled state: {can_trace}")
        else:
            logger.warning("Cannot update toggle_trace_mode_action state: action not found.")

        self._mw.view_2d_action.blockSignals(True)
        self._mw.view_3d_action.blockSignals(True)
        self._mw.view_2d_action.setChecked(is_2d_current and has_pdf)
        self._mw.view_3d_action.setChecked(is_3d_current and has_surfaces)
        self._mw.view_2d_action.blockSignals(False)
        self._mw.view_3d_action.blockSignals(False)
        logger.debug("View actions state updated.")

    # Project-level UI refresh -----------------------------------------------
    def update_ui_for_project(self, project: Optional[Project]) -> None:
        """Update all relevant UI components based on the (new) project state."""
        self.logger.info(f"[update_ui_for_project] Called with project: {project.name if project else 'None'}")
        self.update_window_title()
        self._mw._update_layer_tree()
        if hasattr(self._mw, "project_panel"): self._mw.project_panel.set_project(project)
        self.update_analysis_actions_state()
        self.update_pdf_controls()
        self.update_window_title()
        if hasattr(self._mw, "prop_dock"):
            self._mw.prop_dock.clear_selection()
            if self._mw._selected_scene_item is None:
                self._mw.prop_dock.hide()
        self._mw._clear_cutfill_state()
        self.update_view_actions_state()
        self.update_build_surface_action_state()
        try:
            self.update_scale_pill()
        except Exception as exc:
            self.logger.warning("Failed to refresh scale pill in update_ui_for_project: %s", exc)
        self.logger.debug("UI update complete.")
        if hasattr(self._mw, "legend_dock") and self._mw.legend_dock:
            try:
                self._mw.legend_dock._project = project
                self._mw.legend_dock.refresh()
            except Exception:
                pass
        if hasattr(self._mw, "pdf_thumbnail_dock"):
            if project and project.pdf_background_path:
                self._mw.pdf_thumbnail_dock.show()
            else:
                self._mw.pdf_thumbnail_dock.hide()
        self.logger.info(f"[update_ui_for_project] About to call self._mw.visualization_panel.set_project with: {project.name if project else 'None'}")
        self._mw.visualization_panel.set_project(project)
        self.update_scale_pill()

    # Window title ------------------------------------------------------------
    def update_window_title(self) -> None:
        """Sets the main window title based on the current project name and dirty state."""
        from pathlib import Path
        if not hasattr(self._mw, "project_controller"):
            self._mw.setWindowTitle("DigCalc")
            return
        project = self._mw.project_controller.get_current_project()
        base_title = "DigCalc"
        if project:
            title = f"{project.name} - {base_title}"
            if project.filepath:
                title += f" [{Path(project.filepath).name}]"
            if project.is_dirty:
                title += " *"
            self._mw.setWindowTitle(title)
        else:
            self._mw.setWindowTitle(base_title)

    # Scale helpers -----------------------------------------------------------
    def update_scale_action_enabled(self, loaded: bool) -> None:
        """Enable/disable the *Calibrate Scale…* action."""
        if hasattr(self._mw, 'scale_calib_act'):
            self._mw.scale_calib_act.setEnabled(loaded)

    def update_scale_pill(self) -> None:
        """Refresh the scale status pill in the status-bar."""
        project = self._mw.project_controller.get_current_project() if hasattr(self._mw, "project_controller") else None
        if not project or project.scale is None:
            text = "Scale: —"
            tooltip = "No scale calibrated. Use Ctrl+K or the 'Scale...' button."
            bg_color = QColor("#555")  # Dark grey
            fg_color = QColor("white")
            self._mw.scale_pill.setToolTip(tooltip)
            self._mw.scale_pill.setStyleSheet(
                f"QLabel#scalePill {{ background-color: {bg_color.name()}; color: {fg_color.name()}; border-radius: 8px; padding: 2px 5px; }}"
            )
            self._mw.scale_pill.setText(text)
            return

        scale = project.scale
        is_valid = scale.is_valid_for_dpi(project.pdf_background_dpi)
        text = scale.to_string_short()

        if is_valid:
            tooltip = f"Scale is calibrated and valid for current PDF DPI ({project.pdf_background_dpi} dpi)."
            bg_color = QColor("#3c9")  # Green
            fg_color = QColor("white")
        else:
            tooltip = (
                f"Scale Inconsistent! Recalibrate needed.\n"
                f"Saved at {scale.px_per_in} px/in; current PDF is {project.pdf_background_dpi} dpi."
            )
            bg_color = QColor("#c33")  # Red
            fg_color = QColor("white")

        self._mw.scale_pill.setToolTip(tooltip)
        self._mw.scale_pill.setStyleSheet(
            f"QLabel#scalePill {{ background-color: {bg_color.name()}; color: {fg_color.name()}; border-radius: 8px; padding: 2px 5px; font-weight: bold; }}"
        )
        self._mw.scale_pill.setText(text)

    # Build-surface action ----------------------------------------------------
    def update_build_surface_action_state(self) -> None:
        """Enable or disable the Build-Surface action based on project data."""
        if not hasattr(self._mw, "build_surface_action"):
            self.logger.warning("build_surface_action attribute not found – cannot update state.")
            return

        enabled = False
        project = None
        if hasattr(self._mw, "project_controller"):
            project = self._mw.project_controller.get_current_project()

        if project and getattr(project, "traced_polylines", None):
            for polys_in_layer in project.traced_polylines.values():
                if not isinstance(polys_in_layer, list):
                    continue
                for pdata in polys_in_layer:
                    if isinstance(pdata, dict):
                        if pdata.get("elevation") is not None:
                            enabled = True
                            break
                        points = pdata.get("points")
                        if isinstance(points, list) and points:
                            first_point = points[0]
                            if isinstance(first_point, (list, tuple)) and len(first_point) == 3:
                                if isinstance(first_point[2], (int, float)):
                                    enabled = True
                                    break
                if enabled:
                    break
        
        self._mw.build_surface_action.setEnabled(enabled)
        self.logger.debug(f"Set build_surface_action enabled state: {enabled}") 