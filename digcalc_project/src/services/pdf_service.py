from __future__ import annotations

"""digcalc_project.services.pdf_service

Singleton‑style service that owns the current PdfDocument instance and provides
thumbnail caching with Qt signals for UI binding.
"""

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from ..models.pdf_document import PdfDocument

__all__ = ["PdfService"]


class PdfService(QObject):
    """Qt object emitting signals when PDF pages/thumbnails become available."""

    # Signals -----------------------------------------------------------------------------------
    documentLoaded: Signal = Signal(int)           # page_count
    thumbnailReady: Signal = Signal(int, QPixmap)  # (page, pixmap)

    # -----------------------------------------------------------------------------------------
    # Construction / singleton helper
    # -----------------------------------------------------------------------------------------
    _instance: Optional[PdfService] = None

    def __new__(cls) -> PdfService:  # ensure singleton
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # -----------------------------------------------------------------------------------------
    # Qt init
    # -----------------------------------------------------------------------------------------
    def __init__(self) -> None:
        # Guard against double‑init when singleton is requested multiple times.
        if hasattr(self, "_initialized") and self._initialized:  # type: ignore[attr-defined]
            return
        super().__init__()
        self._current: Optional[PdfDocument] = None
        # Cache key is tuple(page, width)
        self._thumb_cache: Dict[tuple[int, int], QPixmap] = {}
        self._initialized = True  # type: ignore[attr-defined]

    # -----------------------------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------------------------
    def load_pdf(self, path: str | Path) -> Optional[PdfDocument]:
        """Load the *PDF* synchronously and emit :pyattr:`documentLoaded`.

        Returns the loaded :class:`digcalc_project.models.pdf_document.PdfDocument` or *None* on
        failure. If the load succeeds all previous thumbnail cache entries are cleared.
        """
        pdf = PdfDocument()
        if not pdf.load(str(path)):
            return None

        # Replace current doc & clear cache.
        self._current = pdf
        self._thumb_cache.clear()

        # Emit Qt signal – listeners can request thumbnails afterwards.
        self.documentLoaded.emit(pdf.page_count)
        return pdf

    # -------------------------------------------------------------------------------------
    def request_thumbnail(self, page: int, width: int = 160) -> None:
        """Ensure that a thumbnail exists and emit :pyattr:`thumbnailReady`.

        The function is synchronous (rendering happens in the calling thread)
        since :pymeth:`~digcalc_project.models.pdf_document.PdfDocument.render_page` blocks.
        """
        if self._current is None:
            return  # nothing loaded – silently ignore

        cache_key = (page, width)
        if cache_key in self._thumb_cache:
            self.thumbnailReady.emit(page, self._thumb_cache[cache_key])
            return

        pix = self._current.render_page(page, width)
        self._thumb_cache[cache_key] = pix
        self.thumbnailReady.emit(page, pix)
