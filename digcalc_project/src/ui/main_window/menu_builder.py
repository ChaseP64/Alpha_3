from __future__ import annotations

"""Menu construction helper for DigCalc MainWindow.

Encapsulates the bulky logic formerly inside ``MainWindow._create_menus`` so the
window itself stays lean. The builder receives a reference to ``MainWindow`` and
uses the already-created actions (via ``ActionManager``) to populate the menu
bar. All created menus are stored back on the main window under names like
``file_menu`` for backwards-compatibility.
"""

from typing import TYPE_CHECKING
import logging

from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMenuBar, QToolBar, QLabel, QSizePolicy

from ...services.settings_service import SettingsService  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class MenuBuilder:
    """Build the menu-bar for :class:`~digcalc_project.src.ui.main_window.MainWindow`."""

    def __init__(self, main_window: "MainWindow") -> None:  # noqa: D401
        self._mw = main_window
        self._mb: QMenuBar = self._mw.menuBar()
        self.build()

    # ------------------------------------------------------------------
    # Menu helpers
    # ------------------------------------------------------------------
    def _add_attr(self, name: str, obj) -> None:
        setattr(self._mw, name, obj)  # expose on MainWindow
        setattr(self, name, obj)      # also on builder

    # ------------------------------------------------------------------
    # Main build routine (verbatim from old _create_menus)
    # ------------------------------------------------------------------
    def build(self) -> None:  # noqa: C901 – complexity isolated
        mw = self._mw

        # ----------------------------- File ----------------------------
        file_menu = self._mb.addMenu("&File")
        file_menu.addAction(mw.new_project_action)
        file_menu.addAction(mw.open_project_action)
        file_menu.addAction(mw.save_project_action)
        file_menu.addAction(mw.save_project_as_action)
        file_menu.addSeparator()
        file_menu.addAction(mw.trace_pdf_action)
        file_menu.addSeparator()
        file_menu.addAction(mw.exit_action)
        self._add_attr("file_menu", file_menu)

        # ----------------------------- Import --------------------------
        import_menu = self._mb.addMenu("Import")
        import_menu.addAction(mw.import_csv_action)
        import_menu.addAction(mw.import_dxf_action)
        import_menu.addAction(mw.import_landxml_action)
        self._add_attr("import_menu", import_menu)

        # ----------------------------- View ----------------------------
        view_menu = self._mb.addMenu("View")
        view_menu.addAction(mw.load_pdf_background_action)
        view_menu.addAction(mw.clear_pdf_background_action)
        view_menu.addSeparator()
        view_menu.addAction(mw.prev_pdf_page_action)
        view_menu.addAction(mw.next_pdf_page_action)
        view_menu.addSeparator()
        view_menu.addAction(mw.view_2d_action)
        view_menu.addAction(mw.view_3d_action)
        view_menu.addAction(mw.view3d_action)
        view_menu.addSeparator()
        if hasattr(mw, "project_dock"):
            view_menu.addAction(mw.project_dock.toggleViewAction())
        if hasattr(mw, "layer_dock") and mw.layer_dock:
            view_menu.addAction(mw.layer_dock.toggleViewAction())
        if hasattr(mw, "prop_dock"):
            # attempt to insert logically near layer toggle else append
            view_menu.addAction(mw.prop_dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction(mw.toggle_trace_mode_action)
        self._add_attr("view_menu", view_menu)

        # ----------------------------- Surfaces ------------------------
        surfaces_menu = self._mb.addMenu("Surfaces")
        surfaces_menu.addAction(mw.build_surface_action)
        self._add_attr("surfaces_menu", surfaces_menu)

        # ----------------------------- Analysis ------------------------
        analysis_menu = self._mb.addMenu("Analysis")
        analysis_menu.addAction(mw.calculate_volume_action)
        analysis_menu.addAction(mw.build_surface_action)
        analysis_menu.addSeparator()
        analysis_menu.addAction(mw.masshaul_action)
        analysis_menu.addSeparator()
        analysis_menu.addAction(mw.daylight_action)
        self._add_attr("analysis_menu", analysis_menu)

        # ----------------------------- Settings ------------------------
        settings_menu = self._mb.addMenu("Settings")
        mw.strata_settings_action = mw.action_manager.strata_settings_action  # ensure exists
        settings_menu.addAction(mw.strata_settings_action)
        self._add_attr("settings_menu", settings_menu)

        # ----------------------------- Tracing -------------------------
        tracing_menu = self._mb.addMenu("Tracing")
        tracing_menu.addAction(mw.toggle_trace_mode_action)
        tracing_menu.addSeparator()

        # Scale calibration action (new per original logic)
        mw.scale_calib_act = QAction(QIcon.fromTheme("mdi.ruler"), "Scale…", mw)
        mw.scale_calib_act.setToolTip("Calibrate or edit drawing scale (Ctrl+K)")
        mw.scale_calib_act.setShortcut("Ctrl+K")
        mw.scale_calib_act.triggered.connect(mw.on_scale_calibration)
        mw.scale_calib_act.setEnabled(False)
        tracing_menu.addAction(mw.scale_calib_act)
        tracing_menu.addSeparator()

        # Elevation prompt mode radio actions
        mw.trace_point_action = QAction("Point Prompt", mw, checkable=True)
        mw.trace_interpolate_action = QAction("First/Last Prompt (Interpolate)", mw, checkable=True)
        mw.trace_line_action = QAction("Line Elevation", mw, checkable=True)
        mw.trace_mode_group = QActionGroup(mw)
        for act in (
            mw.trace_point_action,
            mw.trace_interpolate_action,
            mw.trace_line_action,
        ):
            mw.trace_mode_group.addAction(act)
            tracing_menu.addAction(act)

        # Initial checked state
        mode_pref = SettingsService().tracing_elev_mode()
        if mode_pref == "interpolate":
            mw.trace_interpolate_action.setChecked(True)
        elif mode_pref == "line":
            mw.trace_line_action.setChecked(True)
        else:
            mw.trace_point_action.setChecked(True)

        self._add_attr("tracing_menu", tracing_menu)

        # ----------------------------- Help ----------------------------
        help_menu = self._mb.addMenu("Help")
        help_menu.addAction(mw.action_manager.docs_action)
        help_menu.addAction(mw.action_manager.report_issue_action)
        help_menu.addSeparator()
        help_menu.addAction(mw.action_manager.check_updates_action)
        help_menu.addSeparator()
        help_menu.addAction(mw.action_manager.about_action)
        self._add_attr("help_menu", help_menu)

        # Expose on MainWindow for testability
        mw.file_menu = file_menu
        mw.import_menu = import_menu
        mw.view_menu = view_menu
        mw.analysis_menu = analysis_menu
        mw.help_menu = help_menu 