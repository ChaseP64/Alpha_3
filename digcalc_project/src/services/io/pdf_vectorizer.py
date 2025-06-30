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
    def vectorize(self, pdf_path: str | Path, page_no: int = 0, *, scale: float = 1.0, offset: tuple[float, float] = (0.0, 0.0)) -> List[Polyline]:
        """Extract *stroke* paths on the given page and return polylines.

        Args:
            pdf_path: Path to the PDF file.
            page_no:  Zero-based page index (default 0).
            scale:    World-units per *PDF unit* (point).  If you already know the
                       project scale in *world/px*, pass it here – otherwise
                       leave ``1.0`` and convert later.
            offset:   (x0, y0) translation applied *after* scaling.  Useful when
                       the user picks an origin in the preview dialog.

        Returns:
            List[Polyline] – always planar (XY only).
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(pdf_path)

        with fitz.open(pdf_path) as doc:
            try:
                page = doc.load_page(page_no)
            except ValueError as exc:
                raise IndexError(f"Page index out of range: {page_no}") from exc

            drawings = self._extract_graphics(page)

        polylines: list[Polyline] = []
        for poly, stroke_rgb, dash in drawings:
            
            # normalise coordinates to world units
            norm_vertices = self._normalize(poly.vertices, scale, offset)
            poly.vertices = norm_vertices  # type: ignore[misc]
            poly.stroke_rgb = stroke_rgb
            poly.dash = dash
            poly.src_page = page_no + 1  # user-facing page numbers are 1-based
            polylines.append(poly)

        return polylines

    # ------------------------------------------------------------------
    # Internal helpers – concrete implementations (Step-2)
    # ------------------------------------------------------------------
    def _extract_graphics(self, page: "fitz.Page") -> list[tuple[Polyline, tuple[int, int, int] | None, tuple[float, ...] | None]]:
        """Return stroke-only polylines already flattened plus colour & dash info."""

        results: list[tuple[Polyline, tuple[int, int, int] | None, tuple[float, ...] | None]] = []
        for drawing in page.get_drawings():
            if drawing.get("fill") is not None:
                continue
            stroke_rgb: tuple[int, int, int] | None = drawing.get("color")
            dash: tuple[float, ...] | None = tuple(drawing.get("dashes") or ()) or None

            for item in drawing["items"]:
                tag = item[0]
                if tag == "path":
                    path: fitz.Path = item[1]
                    poly = self._path_to_polyline(path)
                    if poly:
                        results.append((poly, stroke_rgb, dash))
                elif tag == "l":
                    # Line item: either a flat 4-tuple or two Point objects
                    if len(item) == 2 and len(item[1]) == 4:
                        x0, y0, x1, y1 = item[1]
                    elif len(item) == 3:
                        # item[1] and item[2] are fitz.Point
                        p0, p1 = item[1], item[2]
                        x0, y0, x1, y1 = p0.x, p0.y, p1.x, p1.y
                    else:
                        continue  # unsupported variant
                    verts = np.asarray([[x0, y0], [x1, y1]], dtype=np.float64)
                    results.append((Polyline(vertices=verts), stroke_rgb, dash))
                # Ignore other item types for now (rectangles, curves, etc.)
        return results

    def _path_to_polyline(self, path: "fitz.Path") -> Polyline | None:
        """Flatten a fitz.Path into a Polyline of straight segments.

        Bézier curves are converted to many small line segments by
        ``fitz.Path.get_lines()`` which already performs the flattening.
        """

        lines = path.get_lines()
        if not lines:
            return None

        # Each *line* is (x0, y0, x1, y1).  Build vertex list while de-duplicating.
        vertices: list[tuple[float, float]] = [(lines[0][0], lines[0][1])]
        for x0, y0, x1, y1 in lines:
            vertices.append((x1, y1))

        verts_arr = np.asarray(vertices, dtype=np.float64)
        return Polyline(vertices=verts_arr)

    def _normalize(self, vertices: np.ndarray, scale: float, offset: tuple[float, float]):
        """Apply scaling and translation to raw vertices."""
        return vertices * scale + np.asarray(offset, dtype=np.float64) 