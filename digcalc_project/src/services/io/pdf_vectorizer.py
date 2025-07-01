from __future__ import annotations

"""digcalc_project.src.services.io.pdf_vectorizer

Phase-1 scaffold for automated vector extraction from PDF sheets.
Implementation will be completed in Steps 2–4.
"""

from pathlib import Path
from typing import List, Callable

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
    def vectorize(
        self,
        pdf_path: str | Path,
        page_no: int = 0,
        *,
        scale: float = 1.0,
        offset: tuple[float, float] = (0.0, 0.0),
        progress_cb: "Callable[[int, int], None] | None" = None,
    ) -> List[Polyline]:
        """Extract *stroke* paths on the given page and return polylines.

        Args:
            pdf_path: Path to the PDF file.
            page_no:  Zero-based page index (default 0).
            scale:    World-units per *PDF unit* (point).  If you already know the
                       project scale in *world/px*, pass it here – otherwise
                       leave ``1.0`` and convert later.
            offset:   (x0, y0) translation applied *after* scaling.  Useful when
                       the user picks an origin in the preview dialog.
            progress_cb: Callback function to report progress.

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

        # Compute total *segments* for progress estimation (N-1 per poly)
        total_segs = sum(len(pl.vertices) - 1 for pl, *_ in drawings)
        seg_counter = 0
        next_emit = 5000  # emit every 5k segments

        for poly, stroke_rgb, dash in drawings:
            
            # normalise coordinates to world units
            norm_vertices = self._normalize(poly.vertices, scale, offset)
            poly.vertices = norm_vertices  # type: ignore[misc]
            poly.stroke_rgb = stroke_rgb
            poly.dash = dash
            poly.src_page = page_no + 1  # user-facing page numbers are 1-based
            polylines.append(poly)

            seg_counter += max(0, len(poly.vertices) - 1)
            if progress_cb and seg_counter >= next_emit:
                progress_cb(min(seg_counter, total_segs), total_segs)
                next_emit += 5000

        # ------------------------------------------------------------------
        # Post-processing: merge dash segments, simplify, smart-clean
        # ------------------------------------------------------------------
        polylines = self._post_process(polylines)

        if progress_cb:
            progress_cb(total_segs, total_segs)  # ensure 100 %

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

    # ------------------------------------------------------------------
    def _post_process(self, polylines: list[Polyline]) -> list[Polyline]:
        """Run dash merge, colinear simplification, and smart clean."""

        from digcalc_project.src.services.cleaners.smart_clean import auto_run  # local import to avoid heavy deps at startup

        grouped = group_by_style(polylines)
        merged: list[Polyline] = []
        for (rgb, dash), group in grouped.items():
            if _is_dashed(dash):
                group = _merge_dashes(group)
            merged.extend(group)

        # Colinear simplification per poly
        simplified = [Polyline.join_colinear(pl) for pl in merged]

        # Smart clean de-duplication (future phase will do more)
        cleaned = auto_run(simplified)

        return cleaned

    # ------------------------------------------------------------------
    # Serialisation ------------------------------------------------------
    # ------------------------------------------------------------------
    @staticmethod
    def serialize(polylines: list[Polyline]):
        """Return JSON-serialisable list of dicts for golden diffing."""
        serialised: list[dict] = []
        for pl in polylines:
            serialised.append(
                {
                    "vertices": pl.vertices.tolist(),
                    "stroke_rgb": pl.stroke_rgb,
                    "dash": list(pl.dash) if pl.dash else None,
                    "src_page": pl.src_page,
                }
            )
        return serialised

# ------------------------------------------------------------------
# Helper functions for dashed-stroke detection & polyline grouping
# ------------------------------------------------------------------


def _is_dashed(dash: tuple[float, ...] | None) -> bool:
    """Heuristic – consider stroke *dashed* when a non-empty dash pattern exists
    and at least one dash length is > 0.
    """
    return bool(dash and any(seg > 0 for seg in dash))


def _merge_dashes(polylines: list["Polyline"], *, dist_tol: float = 1e-3, angle_tol_deg: float = 1.0) -> list["Polyline"]:
    """Merge small dashed *segments* that form a long straight line.

    This simplistic implementation joins consecutive polylines whose end &
    start points are within *dist_tol* and whose overall direction differs by
    less than *angle_tol_deg*.
    """
    if not polylines:
        return []

    merged: list[Polyline] = []
    current = polylines[0].copy()

    import math
    for nxt in polylines[1:]:
        # Distance between endpoints
        if math.hypot(*(current.vertices[-1] - nxt.vertices[0])) > dist_tol:
            merged.append(current)
            current = nxt.copy()
            continue

        # Direction vectors
        v1 = current.vertices[-1] - current.vertices[-2]
        v2 = nxt.vertices[1] - nxt.vertices[0] if len(nxt.vertices) > 1 else v1
        # Normalise
        def _unit(v):
            n = math.hypot(*v)
            return v / n if n else v
        if v1.shape != v2.shape:
            merged.append(current)
            current = nxt.copy()
            continue
        cos_ang = _unit(v1).dot(_unit(v2))
        if cos_ang < math.cos(math.radians(180.0 - angle_tol_deg)):
            merged.append(current)
            current = nxt.copy()
            continue

        # Extend current polyline by concatenating vertices of nxt (skip duplicate)
        current.vertices = np.concatenate([current.vertices, nxt.vertices[1:]], axis=0)  # type: ignore[misc]

    merged.append(current)
    return merged


def group_by_style(polylines: list["Polyline"]):
    """Group polylines by (stroke_colour, dash_pattern) key."""
    from collections import defaultdict

    groups: dict[tuple, list[Polyline]] = defaultdict(list)
    for pl in polylines:
        key = (pl.stroke_rgb, tuple(pl.dash or ()))
        groups[key].append(pl)
    return groups 