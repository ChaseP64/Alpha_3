from __future__ import annotations

"""pdf_controller.py

Controller that mediates between the PDF thumbnail dock and the rest of the UI.
It simply re‑emits a signal when the user selects a page from the thumbnail
sidebar.  The indirection allows us to keep *MainWindow* free from excessive
signal wiring and makes the page‑selection flow easier to unit‑test.
"""

from PySide6.QtCore import QObject, Signal, Slot

__all__ = ["PdfController"]


class PdfController(QObject):
    """Thin QObject re‑emitting the *pageSelected* signal."""

    pageSelected: Signal = Signal(int)  # 1‑based page index

    # ---------------------------------------------------------------------
    # QObject life‑cycle helpers
    # ---------------------------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    @Slot(int)
    def on_page_clicked(self, page: int) -> None:  # noqa: D401
        """Handle *pageClicked* from :class:`PdfThumbnailDock`.

        The dock emits *zero‑based* page numbers – we convert them to *one‑based*
        to match the rest of the application API before re‑emitting.
        """
        # Convert to 1‑based index expected elsewhere in the codebase.
        self.pageSelected.emit(page + 1) 