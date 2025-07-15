from __future__ import annotations

"""DigCalc UI – SplitPolylineCommand

Split a :class:`~digcalc_project.src.ui.items.polyline_item.PolylineItem` into
**two** separate items at a specified vertex *index*.

The command creates a *new* PolylineItem for the second segment and inserts it
into the same QGraphicsScene as the original.  On *undo* the new item is
removed and the original polyline is restored to its full geometry.

Limitations
-----------
• Currently supports straight-line *entered* mode only.
• Elevation (Z) values are preserved on duplicated vertices.
"""

from typing import List

from PySide6.QtCore import QPointF
from PySide6.QtGui import QUndoCommand, QPen
from PySide6.QtWidgets import QGraphicsScene

from digcalc_project.src.ui.items.vertex_item import VertexItem
from digcalc_project.src.ui.items.polyline_item import PolylineItem

__all__ = ["SplitPolylineCommand"]


class SplitPolylineCommand(QUndoCommand):
    """Split *polyline* at *index* (exclusive)."""

    def __init__(self, polyline: PolylineItem, index: int):
        super().__init__("Split polyline")
        if index <= 0 or index >= len(polyline.vertices()) - 1:
            raise ValueError("Split index must be within interior vertices")

        self._poly = polyline
        self._idx = index
        self._scene: QGraphicsScene | None = polyline.scene()

        # --- Snapshot of full geometry for undo ---
        self._orig_vertices: List[VertexItem] = list(polyline.vertices())

        # Placeholder for new right-hand PolylineItem
        self._new_poly: PolylineItem | None = None

    # ------------------------------------------------------------------
    def _build_new_polyline(self) -> PolylineItem:
        """Create the second polyline with vertices [idx .. end]."""
        rhs_vertices = self._orig_vertices[self._idx :]
        # Extract positions for constructor
        pts = [v.pos() for v in rhs_vertices]
        new_poly = PolylineItem(
            points=pts,
            layer_pen=self._poly.pen(),
            mode=self._poly.mode,
            layer_id=self._poly.layer_id,
        )
        return new_poly

    # ------------------------------------------------------------------
    def redo(self) -> None:  # noqa: D401
        if self._new_poly is None:
            self._new_poly = self._build_new_polyline()

        # 1. Trim original vertices list to left segment
        del self._poly.vertices()[self._idx :]
        # Rebuild paths
        self._poly._rebuild_path()  # type: ignore[attr-defined]

        # 2. Insert new poly into scene (if not already)
        if self._scene and self._new_poly.scene() is None:
            self._scene.addItem(self._new_poly)

    def undo(self) -> None:  # noqa: D401
        if self._new_poly is None:
            return
        # Remove new poly from scene
        if self._scene:
            self._scene.removeItem(self._new_poly)
        # Restore original vertices list
        verts = self._poly.vertices()
        verts.clear()
        verts.extend(self._orig_vertices)
        self._poly._rebuild_path()  # type: ignore[attr-defined] 