from __future__ import annotations

"""PDF thumbnail dock widget.

Provides a vertical list of page thumbnails for the currently loaded PDF. Users
can click on a thumbnail to select a page to trace in the main view.
"""

from typing import Dict

from PySide6.QtCore import Qt, QModelIndex, QAbstractListModel, Signal, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QColor, QCursor
from PySide6.QtWidgets import (
    QDockWidget,
    QListView,
    QAbstractItemView,
    QToolTip,
)

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
        self._bg_colors: Dict[int, QColor] = {}

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
        if role == Qt.BackgroundRole:
            return self._bg_colors.get(row)
        return None

    # Allow background role editing
    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole):  # noqa: D401
        if not index.isValid():
            return False
        row = index.row()
        if role == Qt.BackgroundRole:
            if isinstance(value, QColor):
                self._bg_colors[row] = value
            else:
                self._bg_colors.pop(row, None)
            self.dataChanged.emit(index, index, [Qt.BackgroundRole])
            return True
        return False

    def flags(self, index: QModelIndex):  # noqa: D401
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

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
    pageActivated = Signal(int)

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

        # Track current item for background coloring
        self._currentItem: QModelIndex | None = None

        # Handle selection changes to update background
        self.view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Emit pagesClicked whenever the selection changes (after background update)
        self.view.selectionModel().selectionChanged.connect(self._emit_pages_clicked)

        # Double‑click to activate page
        self.view.doubleClicked.connect(lambda idx: self.pageActivated.emit(idx.row()))

        # Hover tooltip for preview
        self.view.setMouseTracking(True)
        self.view.entered.connect(self._show_thumbnail_tooltip)

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

    # ------------------------------------------------------------------
    # Selection / UI helpers
    # ------------------------------------------------------------------

    def _on_selection_changed(self, selected, deselected):  # noqa: D401
        """Update background colours when selection changes."""
        # Clear previous highlight
        if self._currentItem and self._currentItem.isValid():
            self.model.setData(self._currentItem, None, Qt.BackgroundRole)

        # Apply highlight to first newly selected item
        if selected.indexes():
            idx = selected.indexes()[0]
            highlight = QColor("#3399ff")
            highlight.setAlpha(60)
            self.model.setData(idx, highlight, Qt.BackgroundRole)
            self._currentItem = idx
        else:
            self._currentItem = None

    def _show_thumbnail_tooltip(self, index: QModelIndex):  # noqa: D401
        """Show a scaled thumbnail tooltip on hover."""
        if not index.isValid():
            return
        pix: QPixmap = self.model.data(index, Qt.DecorationRole)
        if pix and not pix.isNull():
            scaled = pix.scaled(200, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Convert pixmap to base64 PNG for HTML tooltip
            ba = QByteArray()
            buffer = QBuffer(ba)
            buffer.open(QIODevice.WriteOnly)
            scaled.save(buffer, "PNG")
            b64 = bytes(ba.toBase64()).decode()
            html = f"<img src='data:image/png;base64,{b64}'/>"
            QToolTip.showText(QCursor.pos(), html, self.view)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PdfThumbnailDock()
    window.show()
    sys.exit(app.exec()) 