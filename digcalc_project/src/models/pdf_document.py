from __future__ import annotations

"""digcalc_project.models.pdf_document

Utility wrapper around Qt Pdf classes providing synchronous PDF loading and
thumbnail generation.

This class intentionally avoids any threading – it relies on ``QPdfDocument``
which already offers blocking ``load`` and ``render`` calls.  The model is kept
UI‑agnostic so that it can be used from both the services layer (for signal
emission) as well as unit‑tests (where no QApplication GUI is required – a
``QCoreApplication`` created by ``pytest‑qt`` is sufficient).
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtPdf import QPdfDocument

__all__ = ["PdfDocument"]


class PdfDocument(QObject):
    """Synchronous PDF helper built on top of :class:`QPdfDocument`.

    The class hides *most* of the Qt‑specific API and presents a light‑weight
    Pythonic façade used by the higher‑level :class:`digcalc_project.services.
    pdf_service.PdfService`.

    Note that the class derives from :class:`~PySide6.QtCore.QObject` so that
    the internal ``QPdfDocument`` can safely take *this* as its parent – that
    way Qt manages its lifetime automatically.
    """

    def __init__(self) -> None:  # noqa: D401 (imperative mood is fine here)
        super().__init__()
        # ``self`` is passed as parent so the wrapped object follows our
        # lifetime.
        self._doc: QPdfDocument = QPdfDocument(self)
        self._path: Optional[Path] = None
        self._is_loaded: bool = False

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def load(self, path: str | Path) -> bool:
        """Load *path* synchronously.

        Parameters
        ----------
        path
            A path‑like object pointing to a *PDF* file.

        Returns
        -------
        bool
            *True* on success, *False* otherwise.
        """
        # Ensure we work with a Path instance.
        pdf_path = Path(path)
        if not pdf_path.is_file():
            # Early exit – avoid creating a dangling QPdfDocument state.
            self._reset()
            return False

        # Close any previously opened document first to keep the internal
        # state consistent.
        self._doc.close()

        load_result = self._doc.load(str(pdf_path))

        # The Qt enum value for "no error" is *None_* (note the trailing
        # underscore to avoid the Python keyword).
        ok = load_result == QPdfDocument.Error.None_
        self._is_loaded = ok
        self._path = pdf_path if ok else None
        return ok

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def page_count(self) -> int:  # noqa: D401
        """The number of pages in the current document.

        Raises
        ------
        RuntimeError
            If called before :pymeth:`load` succeeds.
        """
        if not self._is_loaded:
            raise RuntimeError("PDF not loaded – call `load()` first.")
        return int(self._doc.pageCount())

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def render_page(self, page: int, width: int) -> QPixmap:  # noqa: D401
        """Render *page* at *width* pixels keeping aspect ratio.

        Parameters
        ----------
        page
            Zero‑based page index.
        width
            Requested pixel width for the thumbnail (height is calculated
            automatically to preserve aspect ratio).

        Returns
        -------
        PySide6.QtGui.QPixmap
            A pixmap that can safely be used on Qt widgets or saved to disk.

        Raises
        ------
        RuntimeError
            If the document has not been loaded.
        ValueError
            If *page* is out of range or *width* is not positive.
        """
        if not self._is_loaded:
            raise RuntimeError("PDF not loaded – call `load()` first.")

        if page < 0 or page >= self.page_count:
            raise ValueError(f"Page index {page} out of range (0‑{self.page_count - 1}).")
        if width <= 0:
            raise ValueError("Width must be positive.")

        # Page size in points (1/72 inch). Using that we figure out the height
        # so we match the original aspect ratio.
        size_pts = self._doc.pagePointSize(page)
        if size_pts.isEmpty():
            return QPixmap()  # empty pixmap – caller can decide what to do

        # Calculate the height preserving aspect ratio.
        aspect = size_pts.height() / size_pts.width()
        height = int(round(width * aspect))
        if height <= 0:
            height = 1  # fallback – Qt will return empty pixmap for zero height

        image_size = QSize(width, height)
        image = self._doc.render(page, image_size)
        pixmap = QPixmap.fromImage(image)
        return pixmap

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _reset(self) -> None:
        """Reset the internal state (used after a failed load)."""
        self._doc.close()
        self._path = None
        self._is_loaded = False

    # ------------------------------------------------------------------
    # Python protocol helpers
    # ------------------------------------------------------------------
    def __del__(self) -> None:  # noqa: D401
        """Ensure underlying `QPdfDocument` is closed before GC.

        This prevents crashes observed on some Qt versions when a QPdfDocument
        instance is destroyed while still holding an open file.
        """
        try:
            self._doc.close()
        except Exception:  # pragma: no cover – best‑effort cleanup
            pass 