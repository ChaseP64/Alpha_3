from __future__ import annotations

"""Action creation and registration for DigCalc's MainWindow.

This module defines ``ActionManager`` – a helper that encapsulates all
``QAction`` objects previously manufactured inside ``MainWindow._create_actions``.
It attaches each created action back onto the provided ``MainWindow`` instance
so the rest of the code (menus/tool-bars, signal wiring, tests) can continue
referencing attributes like ``main_window.open_project_action`` unchanged.
"""

from typing import TYPE_CHECKING
import logging

from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtWidgets import QStyle

if TYPE_CHECKING:  # pragma: no cover – avoid runtime deps / circulars
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class ActionManager:
    """Create and register all ``QAction`` objects for ``MainWindow``.

    Notes:
        • The constructor immediately invokes :py:meth:`_create_actions` which
          mirrors the former ``MainWindow._create_actions`` implementation.
        • For backwards-compatibility, each action is stored *both* on the
          manager (``self.new_project_action``) **and** on the owning
          ``MainWindow`` (``main_window.new_project_action``).
    """

    # Reason: Keep init minimal; heavy lifting is done in helper method.
    def __init__(self, main_window: "MainWindow") -> None:  # noqa: D401
        self._mw = main_window
        self._create_actions()

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _add_attr(self, name: str, action: QAction) -> None:  # noqa: D401
        """Register *action* on both manager and MainWindow under *name*."""
        setattr(self, name, action)
        setattr(self._mw, name, action)

    # ---------------------------------------------------------------------
    # Action factory – extracted from MainWindow._create_actions verbatim
    # ---------------------------------------------------------------------
    def _create_actions(self) -> None:  # noqa: C901 – long but isolated
        mw = self._mw  # Convenience alias

        # File menu actions -------------------------------------------------
        act = QAction("&New Project", mw)
        act.setShortcut(QKeySequence.StandardKey.New)
        act.setStatusTip("Create a new empty project.")
        self._add_attr("new_project_action", act)

        act = QAction("&Open Project...", mw)
        act.setShortcut(QKeySequence.StandardKey.Open)
        act.setStatusTip("Open an existing project file (.digcalc).")
        self._add_attr("open_project_action", act)

        act = QAction("&Save Project", mw)
        act.setShortcut(QKeySequence.StandardKey.Save)
        act.setStatusTip("Save the current project.")
        act.setEnabled(False)
        self._add_attr("save_project_action", act)

        act = QAction("Save Project &As...", mw)
        act.setShortcut(QKeySequence.StandardKey.SaveAs)
        act.setStatusTip("Save the current project to a new file.")
        act.setEnabled(False)
        self._add_attr("save_project_as_action", act)

        act = QAction("E&xit", mw)
        act.setShortcut(QKeySequence.StandardKey.Quit)
        act.setStatusTip("Exit the application.")
        self._add_attr("exit_action", act)

        # Import menu actions ----------------------------------------------
        act = QAction("Import &CSV...", mw)
        act.setStatusTip("Import points from a CSV file.")
        self._add_attr("import_csv_action", act)

        act = QAction("Import &DXF...", mw)
        act.setStatusTip("Import geometry from a DXF file.")
        self._add_attr("import_dxf_action", act)

        act = QAction("Import &LandXML...", mw)
        act.setStatusTip("Import surfaces or points from a LandXML file.")
        self._add_attr("import_landxml_action", act)

        # Background actions (Load/Clear PDF) ------------------------------
        act = QAction("Load PDF &Background...", mw)
        act.setStatusTip("Load a PDF page as a background for tracing.")
        self._add_attr("load_pdf_background_action", act)

        act = QAction("&Clear PDF Background", mw)
        act.setStatusTip("Remove the current PDF background image.")
        act.setEnabled(False)
        self._add_attr("clear_pdf_background_action", act)

        # PDF Navigation Actions -------------------------------------------
        act = QAction("Previous PDF Page", mw)
        act.setStatusTip("Go to the previous page in the PDF background.")
        act.setEnabled(False)
        self._add_attr("prev_pdf_page_action", act)

        act = QAction("Next PDF Page", mw)
        act.setStatusTip("Go to the next page in the PDF background.")
        act.setEnabled(False)
        self._add_attr("next_pdf_page_action", act)

        # Analysis menu actions -------------------------------------------
        act = QAction("&Calculate Volume...", mw)
        act.setStatusTip("Calculate cut/fill volumes between surfaces.")
        act.setEnabled(False)
        self._add_attr("calculate_volume_action", act)

        act = QAction("&Build Surface...", mw)
        act.setStatusTip("Build a TIN or Grid surface from project layers.")
        act.setEnabled(False)
        self._add_attr("build_surface_action", act)

        act = QAction("Generate &Report...", mw)
        act.setStatusTip("Generate a PDF report of the project.")
        act.setEnabled(False)
        self._add_attr("generate_report_action", act)

        # Export Report Action --------------------------------------------
        act = QAction(mw.style().standardIcon(QStyle.SP_DialogSaveButton),
                      "Export Report…", mw)
        act.setStatusTip("Export PDF report with CSV tables.")
        act.triggered.connect(mw.on_export_report)
        self._add_attr("export_action", act)

        # View menu actions (docks) ----------------------------------------
        if hasattr(mw, "project_dock"):
            act = mw.project_dock.toggleViewAction()
            act.setText("&Project Panel")
            self._add_attr("view_project_panel_action", act)
        else:
            logger.error("Cannot create view_project_panel_action: project_dock missing")

        if hasattr(mw, "layer_dock"):
            act = mw.layer_dock.toggleViewAction()
            act.setText("&Layer Panel")
            self._add_attr("view_layer_panel_action", act)
        else:
            logger.error("Cannot create view_layer_panel_action: layer_dock missing")

        if hasattr(mw, "prop_dock"):
            act = mw.prop_dock.toggleViewAction()
            act.setText("P&roperties Dock")
            self._add_attr("view_properties_dock_action", act)
        else:
            logger.error("Cannot create view_properties_dock_action: prop_dock missing")

        if hasattr(mw, "pdf_thumbnail_dock"):
            act = mw.pdf_thumbnail_dock.toggleViewAction()
            act.setText("PDF T&humbnails")
            act.setEnabled(False)
            self._add_attr("view_pdf_thumbnail_dock_action", act)
        else:
            logger.error("Cannot create view_pdf_thumbnail_dock_action: pdf_thumbnail_dock missing")

        # View mode actions (2D/3D tabs) -----------------------------------
        act2d = QAction("View &2D", mw, checkable=True)
        act3d = QAction("3D View (Tab)", mw, checkable=True)
        grp = QActionGroup(mw)
        grp.addAction(act2d)
        grp.addAction(act3d)
        grp.setExclusive(True)
        act2d.setChecked(True)
        self._add_attr("view_2d_action", act2d)
        self._add_attr("view_3d_action", act3d)
        self._add_attr("view_action_group", grp)

        # 3-D Viewer Dock ---------------------------------------------------
        act = QAction("3-D Viewer", mw)
        act.setStatusTip("Open the 3-D viewer dock.")
        act.triggered.connect(mw.on_open_3d)
        self._add_attr("view3d_action", act)

        # Cut/Fill Map toggle ---------------------------------------------
        act = QAction("Show Cut/Fill Map", mw, checkable=True)
        act.setChecked(False)
        act.setEnabled(False)
        self._add_attr("cutfill_action", act)

        # Tracing / PDF tools ---------------------------------------------
        act = QAction("&Enable Tracing", mw, checkable=True)
        act.setStatusTip("Toggle polyline tracing mode for the 2D view.")
        act.setChecked(False)
        act.setEnabled(False)
        self._add_attr("toggle_trace_mode_action", act)

        act = QAction("Trace from PDF Vectors...", mw)
        act.setStatusTip("Extract vector paths from a PDF page and create layers.")
        act.setEnabled(False)
        self._add_attr("trace_pdf_action", act)

        # Daylight Offset --------------------------------------------------
        act = QAction(QIcon(":/icons/daylight.svg"), "Daylight Offset…", mw)
        act.setStatusTip("Create daylight offset breakline from selected polyline.")
        act.triggered.connect(mw.on_daylight_offset)
        self._add_attr("daylight_action", act)

        # Mass-Haul --------------------------------------------------------
        act = QAction(QIcon(":/icons/masshaul.svg"), "Mass-Haul…", mw)
        act.setStatusTip("Generate mass-haul diagram from Existing and Design surfaces.")
        act.triggered.connect(mw.on_mass_haul)
        act.setEnabled(False)
        self._add_attr("masshaul_action", act)

        # Borehole tool ----------------------------------------------------
        act = QAction(QIcon.fromTheme("mdi.circle"), "Place Borehole", mw)
        act.setCheckable(True)
        act.setStatusTip("Place a borehole log on the plan")
        self._add_attr("borehole_tool_action", act)

        # Help menu --------------------------------------------------------
        act = QAction("&About DigCalc", mw)
        act.setStatusTip("Show information about the DigCalc application.")
        self._add_attr("about_action", act)

        # Settings → Strata -----------------------------------------------
        act = QAction("Strata…", mw)
        act.triggered.connect(mw._on_strata_settings)
        self._add_attr("strata_settings_action", act) 