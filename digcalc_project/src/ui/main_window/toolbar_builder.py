from __future__ import annotations

"""Toolbar construction helper for DigCalc MainWindow."""

from typing import TYPE_CHECKING
import logging

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QToolBar,
    QLabel,
    QSpinBox,
)

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class ToolbarBuilder:  # noqa: D101 – simple helper
    def __init__(self, mw: "MainWindow") -> None:
        self.mw = mw
        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:  # noqa: C901 – long but isolated
        mw = self.mw

        # -------------------------- Main --------------------------------
        main_tb = QToolBar("Main Toolbar")
        main_tb.setIconSize(QSize(24, 24))
        mw.addToolBar(main_tb)
        main_tb.addAction(mw.new_project_action)
        main_tb.addAction(mw.open_project_action)
        main_tb.addAction(mw.save_project_action)
        main_tb.addAction(mw.save_project_as_action)
        # Edit actions
        main_tb.addSeparator()
        main_tb.addAction(mw.undo_action)
        main_tb.addAction(mw.redo_action)
        main_tb.addSeparator()

        # Layer selector (optional)
        if hasattr(mw, "visualization_panel") and hasattr(mw.visualization_panel, "layer_selector"):
            main_tb.addSeparator()
            main_tb.addWidget(QLabel(" Layer:"))
            main_tb.addWidget(mw.visualization_panel.layer_selector)  # type: ignore[arg-type]
        else:
            logger.warning("Layer selector not available for toolbar")

        # ------------------------ Import --------------------------------
        imp_tb = QToolBar("Import Toolbar")
        imp_tb.setIconSize(QSize(24, 24))
        mw.addToolBar(imp_tb)
        imp_tb.addAction(mw.import_csv_action)
        imp_tb.addAction(mw.import_dxf_action)
        imp_tb.addAction(mw.import_landxml_action)

        # Add calculate volume into main toolbar after import set
        main_tb.addSeparator()
        main_tb.addAction(mw.calculate_volume_action)

        # ------------------------- PDF ----------------------------------
        pdf_tb = QToolBar("PDF Toolbar")
        pdf_tb.setIconSize(QSize(24, 24))
        mw.addToolBar(Qt.ToolBarArea.TopToolBarArea, pdf_tb)

        pdf_tb.addAction(mw.load_pdf_background_action)
        pdf_tb.addAction(mw.scale_calib_act)
        pdf_tb.addAction(mw.clear_pdf_background_action)
        pdf_tb.addSeparator()
        pdf_tb.addAction(mw.prev_pdf_page_action)

        mw.pdf_page_label = QLabel(" Page: ")
        mw.pdf_page_spinbox = QSpinBox()
        mw.pdf_page_spinbox.setRange(0, 0)
        mw.pdf_page_spinbox.setEnabled(False)
        # mw.pdf_page_spinbox.valueChanged.connect(mw.on_set_pdf_page_from_spinbox)
        pdf_tb.addWidget(mw.pdf_page_label)
        pdf_tb.addWidget(mw.pdf_page_spinbox)
        pdf_tb.addAction(mw.next_pdf_page_action)
        pdf_tb.setVisible(False)

        # Tracing toggle in PDF toolbar
        pdf_tb.addSeparator()
        pdf_tb.addAction(mw.toggle_trace_mode_action)

        # ------------------------- View ---------------------------------
        view_tb = QToolBar("View Toolbar")
        view_tb.setIconSize(QSize(24, 24))
        mw.addToolBar(Qt.ToolBarArea.TopToolBarArea, view_tb)
        view_tb.addAction(mw.view_2d_action)
        view_tb.addAction(mw.view_3d_action)
        view_tb.addAction(mw.view3d_action)

        # ------------------------- Tools --------------------------------
        tools_tb = QToolBar("Tools Toolbar")
        tools_tb.setIconSize(QSize(24, 24))
        mw.addToolBar(Qt.ToolBarArea.TopToolBarArea, tools_tb)
        tools_tb.addAction(mw.daylight_action)
        tools_tb.addAction(mw.masshaul_action)
        tools_tb.addAction(mw.borehole_tool_action)
        tools_tb.addAction(mw.smart_clean_action)

        # Expose on MainWindow for compatibility
        mw.main_toolbar = main_tb
        mw.import_toolbar = imp_tb
        mw.pdf_toolbar = pdf_tb
        mw.view_toolbar = view_tb
        mw.tools_toolbar = tools_tb 