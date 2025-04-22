from __future__ import annotations

"""PDF thumbnail dock widget.

Provides a vertical list of page thumbnails for the currently loaded PDF. Users
can click on a thumbnail to select a page to trace in the main view.
"""

from typing import Dict

from PySide6.QtCore import Qt, QModelIndex, QAbstractListModel, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDockWidget, QListView, QAbstractItemView

__all__ = [
    "PdfThumbnailModel",
    "PdfThumbnailDock",
]


class PdfThumbnailModel(QAbstractListModel):
    """List‑model that exposes one row per PDF page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_count: int = 0
        self._thumbnails: Dict[int, QPixmap] = {}

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: D401
        return 0 if parent.isValid() else self._page_count

    def data(self, index: QModelIndex, role: int):  # noqa: D401
        if not index.isValid():
            return None
        row = index.row()
        if role == Qt.DisplayRole:
            return f"Page {row + 1}"
        if role == Qt.DecorationRole:
            return self._thumbnails.get(row, QPixmap())
        return None

    # ------------------------------------------------------------------
    # Slots / API used by PdfService signals
    # ------------------------------------------------------------------
    def set_page_count(self, count: int) -> None:  # noqa: D401
        """Reset model when a new document is loaded."""
        self.beginResetModel()
        self._page_count = count
        self._thumbnails.clear()
        self.endResetModel()

    def update_thumbnail(self, page: int, pixmap: QPixmap) -> None:  # noqa: D401
        """Cache pixmap and notify view that decoration changed."""
        if page < 0 or page >= self._page_count:
            return
        self._thumbnails[page] = pixmap
        idx = self.index(page)
        self.dataChanged.emit(idx, idx, [Qt.DecorationRole])


class PdfThumbnailDock(QDockWidget):
    """Dock widget embedding a :class:`QListView` of thumbnails."""

    pageClicked = Signal(int)
    pagesClicked = Signal(list)

    def __init__(self, parent=None):
        super().__init__("PDF Pages", parent)

        self.model = PdfThumbnailModel(self)
        self.view = QListView(self)
        self.view.setModel(self.model)
        self.view.setUniformItemSizes(True)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setViewMode(QListView.IconMode)
        self.view.setIconSize(QPixmap(160, 160).size())  # initial; will shrink
        self.view.clicked.connect(lambda idx: self.pageClicked.emit(idx.row()))

        # Emit pagesClicked whenever the selection changes
        self.view.selectionModel().selectionChanged.connect(self._emit_pages_clicked)

        self.setWidget(self.view)

        # Dock default settings
        self.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _emit_pages_clicked(self, *_):  # noqa: D401
        """Collect selected indexes and emit as a list."""
        rows = [idx.row() for idx in self.view.selectionModel().selectedRows()]
        rows.sort()
        self.pagesClicked.emit(rows)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PdfThumbnailDock()
    window.show()
    sys.exit(app.exec()) 