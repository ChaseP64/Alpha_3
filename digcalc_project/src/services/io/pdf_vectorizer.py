from __future__ import annotations

"""digcalc_project.src.services.io.pdf_vectorizer

Phase-1 scaffold for automated vector extraction from PDF sheets.
Implementation will be completed in Steps 2–4.
"""

from pathlib import Path
from typing import List

import numpy as np
import fitz  # PyMuPDF

from ...core.geom.polyline import Polyline

__all__ = ["PDFVectorizer"]


class PDFVectorizer:
    """Service class that converts PDF vector graphics into Polyline objects.

    This initial version only lays out the public API and method stubs so that
    other modules (UI dialog, command flow) can already depend on the class
    signature.  All heavy-lifting is deferred to later steps of the sprint.
    """

    def __init__(self, dpi: int = 300) -> None:
        self.dpi = dpi

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------
    def vectorize(self, pdf_path: str | Path, page_no: int = 0) -> List[Polyline]:
        """Extract *stroke* paths on the given page and return polylines.

        Args:
            pdf_path: Path to the PDF file.
            page_no:  Zero-based page index (default 0).

        Returns:
            List of Polyline instances (world units TBD – currently pixel).
        """
        # TODO: implement extraction pipeline (Steps 2-4)
        raise NotImplementedError("PDFVectorizer.vectorize() not yet implemented – see Phase 1 plan")

    # ------------------------------------------------------------------
    # Internal helpers – skeletons
    # ------------------------------------------------------------------
    def _extract_graphics(self, page: fitz.Page):
        raise NotImplementedError

    def _path_to_polyline(self, path: fitz.Path):
        raise NotImplementedError

    def _normalize(self, vertices: np.ndarray, scale: float, offset: tuple[float, float]):
        raise NotImplementedError 