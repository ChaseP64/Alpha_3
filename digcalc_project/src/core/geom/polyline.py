from __future__ import annotations

"""digcalc_project.src.core.geom.polyline

Light-weight data container representing a 2-D polyline (sequence of XY
vertices) plus optional stylistic metadata extracted from vector PDF input.

The previous full implementation was removed during the refactor that
introduced the PDF vectorizer.  Several modules still rely on the public API
(shape only for now) therefore we re-introduce a *stub* that is sufficient
for current usages and unit tests.  A richer geometry model will replace this
stub in a future sprint.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

__all__ = ["Polyline"]


@dataclass
class Polyline:
    """Minimal XY polyline used by the PDF vectorizer pipeline.

    Attributes
    ----------
    vertices: np.ndarray
        Array of shape (N, 2) holding XY coordinates in *world units*.
    stroke_rgb: tuple[int, int, int] | None, optional
        Source stroke colour as extracted from the PDF (RGB 0-255).  ``None``
        if unavailable.
    dash: tuple[float, ...] | None, optional
        Dash pattern in *world units* (already scaled) or ``None`` when the
        stroke is solid.
    src_page: int | None, optional
        1-based PDF page index the polyline originated from.  ``None`` until
        assigned by :pyclass:`~digcalc_project.src.services.io.pdf_vectorizer.PDFVectorizer`.
    """

    vertices: np.ndarray = field(repr=False)
    stroke_rgb: Optional[Tuple[int, int, int]] = None
    dash: Optional[Tuple[float, ...]] = None
    src_page: Optional[int] = None

    # ------------------------------------------------------------------
    # Dataclass hooks
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:  # noqa: D401 – not a public API method
        """Validate *vertices* and coerce to the expected NumPy format."""
        self.vertices = np.asarray(self.vertices, dtype=np.float64)

        if self.vertices.ndim != 2 or self.vertices.shape[1] != 2:
            raise ValueError(
                "Polyline.vertices must be a 2-D array with shape (N, 2) representing XY coordinates"
            )

    # ------------------------------------------------------------------
    # Convenience helpers (future-proofing)
    # ------------------------------------------------------------------
    def bbox(self) -> Tuple[float, float, float, float]:
        """Return the axis-aligned bounding box *(min_x, min_y, max_x, max_y)*."""
        min_xy = self.vertices.min(axis=0)
        max_xy = self.vertices.max(axis=0)
        return (*min_xy, *max_xy)

    def copy(self) -> "Polyline":
        """Return a *shallow* copy (vertices array is duplicated)."""
        return Polyline(
            vertices=self.vertices.copy(),
            stroke_rgb=self.stroke_rgb,
            dash=self.dash,
            src_page=self.src_page,
        )

    # ------------------------------------------------------------------
    # Geometry helpers --------------------------------------------------
    # ------------------------------------------------------------------
    @staticmethod
    def join_colinear(poly: "Polyline", *, angle_tol_deg: float = 1.0, dist_tol: float = 1e-8) -> "Polyline":
        """Return a simplified copy with intermediate *nearly-colinear* vertices removed.

        The algorithm walks the vertex chain and discards any interior vertex
        whose turning angle is within *angle_tol_deg* of 180° **and** whose
        perpendicular distance to the line through its neighbours is below
        *dist_tol*.  This retains end-points of genuine bends while merging
        perfectly straight dash segments output by the PDF vectoriser.

        Args
        -----
        poly: Polyline to simplify.
        angle_tol_deg:  Maximum deviation from 180° to treat three consecutive
            points as colinear.  Default 1°.
        dist_tol:  Additional safety guard – points further away than this
            distance from the line AB will be kept even if the angle criterion
            passes.  Expressed in the same world units as *vertices*.
        """

        verts = poly.vertices
        if len(verts) <= 2:
            return poly.copy()

        keep_idx: list[int] = [0]

        # Pre-compute cosine threshold for efficiency
        import math

        cos_thresh = math.cos(math.radians(180.0 - angle_tol_deg))

        for i in range(1, len(verts) - 1):
            a = verts[i - 1]
            b = verts[i]
            c = verts[i + 1]

            # Vectors BA and BC
            v1 = a - b
            v2 = c - b

            # Normalise
            norm1 = math.hypot(*v1)
            norm2 = math.hypot(*v2)
            if norm1 < 1e-12 or norm2 < 1e-12:
                keep_idx.append(i)
                continue
            v1 /= norm1
            v2 /= norm2

            # Cosine of angle between vectors; cos(180°)=-1
            cos_ang = v1.dot(v2)

            # Perpendicular distance of point *b* to line AC
            # Using area formula for triangle.
            area = abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1]))
            base = math.hypot(*(c - a))
            dist = area / base if base else 0.0

            if cos_ang <= cos_thresh and dist <= dist_tol:
                # b is nearly colinear – skip it
                continue
            keep_idx.append(i)

        keep_idx.append(len(verts) - 1)

        # ------------------------------------------------------------------
        # SECOND-PASS: Remove "zig-zag" artefacts
        # ------------------------------------------------------------------
        # Scenario: small horizontal/vertical dash segment followed by an
        # equally small turn in the opposite direction.  After the first
        # pass the vertex chain might look like:
        #    A ── B ╱ C ── D
        # where the turns at *B* and *C* are both shallow (~45°) but in
        # opposite orientations (left-then-right or vice-versa).  Keeping
        # both makes the polyline unnecessarily detailed.  We drop the
        # *earlier* vertex so that only the dominant corner survives.

        simplified: list[int] = [keep_idx[0]]

        def _unit_vec(v: np.ndarray) -> np.ndarray:
            n = math.hypot(*v)
            return v / n if n else v

        i = 1
        while i < len(keep_idx) - 1:
            a = verts[keep_idx[i - 1]]
            b = verts[keep_idx[i]]
            c = verts[keep_idx[i + 1]]

            # Direction vectors (forward orientation)
            v_ab = _unit_vec(b - a)
            v_bc = _unit_vec(c - b)

            # Turning metrics
            cos_turn = v_ab.dot(v_bc)
            # cross_z sign encodes left/right orientation
            cross_z = v_ab[0] * v_bc[1] - v_ab[1] * v_bc[0]

            remove_b = False

            # Mild turn (|angle| < 60°) & followed by opposite mild turn
            if cos_turn > math.cos(math.radians(60.0)) and i + 2 < len(keep_idx):
                # Look-ahead one extra vertex to inspect next turn
                d = verts[keep_idx[i + 2]] if i + 2 < len(keep_idx) else None
                if d is not None:
                    v_cd = _unit_vec(d - c)
                    cos_next = v_bc.dot(v_cd)
                    cross_next = v_bc[0] * v_cd[1] - v_bc[1] * v_cd[0]

                    # Also a mild turn and opposite orientation → zig-zag
                    if cos_next > math.cos(math.radians(60.0)) and cross_z * cross_next < 0:
                        remove_b = True

            if remove_b:
                # Skip *b* – do **not** append keep_idx[i]
                i += 1  # advance to the next vertex (c becomes new *b*)
                continue

            simplified.append(keep_idx[i])
            i += 1

        simplified.append(keep_idx[-1])

        new_verts = verts[simplified]

        return Polyline(
            vertices=new_verts,
            stroke_rgb=poly.stroke_rgb,
            dash=poly.dash,
            src_page=poly.src_page,
        ) 