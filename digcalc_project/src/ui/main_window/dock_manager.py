from __future__ import annotations

"""Dock widget construction for DigCalc *MainWindow*.

This helper centralises creation / placement of every *QDockWidget*
previously instantiated inside ``MainWindow._init_ui``.  All attributes are
attached back onto the owning ``MainWindow`` instance under the same names so
existing code and tests remain unchanged.
"""

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QTreeWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class DockManager:  # noqa: D101 – thin wrapper
    def __init__(self, mw: "MainWindow") -> None:
        self.mw = mw
        self._build()

    # ------------------------------------------------------------------
    def _attach(self, name: str, obj: Any) -> None:  # noqa: D401
        setattr(self.mw, name, obj)
        setattr(self, name, obj)

    # ------------------------------------------------------------------
    def _build(self) -> None:  # noqa: C901 – long but isolated
        mw = self.mw

        # ----------------------- Project Dock -------------------------
        from ...ui.project_panel import ProjectPanel  # local import to avoid cycles

        proj_dock = QDockWidget("Project", mw)
        proj_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        proj_panel = ProjectPanel(main_window=mw, parent=mw)
        proj_dock.setWidget(proj_panel)
        mw.addDockWidget(Qt.LeftDockWidgetArea, proj_dock)
        self._attach("project_dock", proj_dock)
        self._attach("project_panel", proj_panel)

        # ----------------------- Layer Dock ---------------------------
        layer_dock = QDockWidget("Layers", mw)
        layer_dock.setObjectName("LayerDock")
        layer_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        layer_tree = QTreeWidget(layer_dock)
        layer_tree.setHeaderHidden(True)
        layer_dock.setWidget(layer_tree)
        mw.addDockWidget(Qt.LeftDockWidgetArea, layer_dock)
        self._attach("layer_dock", layer_dock)
        self._attach("layer_tree", layer_tree)

        # ----------------------- Properties Dock ----------------------
        from ...ui.properties_dock import PropertiesDock  # lazy import

        prop_dock = PropertiesDock(mw)
        mw.addDockWidget(Qt.RightDockWidgetArea, prop_dock)
        prop_dock.hide()
        self._attach("prop_dock", prop_dock)

        # ----------------------- PDF Thumbnail Dock -------------------
        from ...ui.docks.pdf_thumbnail_dock import PdfThumbnailDock

        pdf_thumb = PdfThumbnailDock(mw)
        mw.addDockWidget(Qt.LeftDockWidgetArea, pdf_thumb)
        pdf_thumb.hide()
        self._attach("pdf_thumbnail_dock", pdf_thumb)

        # ----------------------- Strata Manager Dock ------------------
        try:
            from digcalc_project.src.ui.docks.strata_manager_dock import (  # noqa: E501
                StrataManagerDock,
            )

            strata_dock = StrataManagerDock(mw)  # type: ignore[attr-defined]
            mw.addDockWidget(Qt.RightDockWidgetArea, strata_dock)
            self._attach("strata_manager_dock", strata_dock)
        except Exception as exc:  # pragma: no cover – headless tests
            logger.warning("StrataManagerDock unavailable – using stub (%s)", exc)

            from PySide6.QtGui import QUndoStack

            class _StubStrataDock:  # pylint: disable=too-few-public-methods
                def __init__(self, parent):  # noqa: D401
                    self.undo_stack = QUndoStack(parent)

                def refresh_boreholes(self):
                    """Placeholder for tests."""

            self._attach("strata_manager_dock", _StubStrataDock(mw))
