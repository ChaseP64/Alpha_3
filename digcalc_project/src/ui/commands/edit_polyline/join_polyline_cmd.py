from __future__ import annotations

"""DigCalc UI – JoinPolylineCommand

Merge two :class:`~digcalc_project.src.ui.items.polyline_item.PolylineItem` items
into **one** by concatenating their vertex sequences.

The command destroys *other* (second) polyline and appends its (optionally
reversed) vertices to *base*.  The original scene order is not preserved; the
resulting polyline remains parented to *base*'s scene.

Join direction is inferred by inspecting the distance between candidate end
points.  If either tail–head pairing is within *tol* the orientation that
creates the *shortest* link is selected.
"""

from typing import List

from PySide6.QtCore import QPointF
from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import QGraphicsScene

from digcalc_project.src.ui.items.vertex_item import VertexItem
from digcalc_project.src.ui.items.polyline_item import PolylineItem

__all__ = ["JoinPolylineCommand"]


class JoinPolylineCommand(QUndoCommand):
    """Join *other* into *base* (they must share a scene)."""

    def __init__(self, base: PolylineItem, other: PolylineItem, tol: float = 1.0):
        super().__init__("Join polylines")
        self._base = base
        self._other = other
        self._tol = tol
        self._scene: QGraphicsScene | None = base.scene()

        # Snapshot of pre-join vertices for undo
        self._base_orig: List[VertexItem] = list(base.vertices())
        self._other_orig: List[VertexItem] = list(other.vertices())

        # Cache orientation choice: True if other is reversed
        self._reversed: bool | None = None

    # ------------------------------------------------------------------
    def _choose_orientation(self) -> None:
        """Decide whether to reverse *other* before append."""
        if self._reversed is not None:
            return
        b_first = self._base_orig[0].pos()
        b_last = self._base_orig[-1].pos()
        o_first = self._other_orig[0].pos()
        o_last = self._other_orig[-1].pos()

        # Compute distances for the 4 possible head/tail matches
        def _dist(p: QPointF, q: QPointF) -> float:
            return ((p.x() - q.x()) ** 2 + (p.y() - q.y()) ** 2) ** 0.5

        d1 = _dist(b_last, o_first)  # base tail to other head
        d2 = _dist(b_last, o_last)   # base tail to other tail (rev)
        d3 = _dist(b_first, o_last)  # base head to other tail
        d4 = _dist(b_first, o_first) # base head to other head (rev)

        choices = [d1, d2, d3, d4]
        min_idx = choices.index(min(choices))
        # Only accept orientations where distance within tolerance
        if choices[min_idx] > self._tol:
            raise ValueError("Polylines endpoints too far apart to join (tol=%.2f)" % self._tol)

        if min_idx in (0, 3):
            # keep "other" orientation as-is
            self._reversed = False
        else:
            self._reversed = True

    # ------------------------------------------------------------------
    def redo(self) -> None:  # noqa: D401
        self._choose_orientation()
        verts_base = self._base.vertices()
        verts_other = list(self._other.vertices())
        if self._reversed:
            verts_other.reverse()
        # Drop duplicate meeting vertex if distance almost zero
        if verts_base[-1].pos().isNull():
            pass  # Not robust, re-eval below
        # More robust check:
        if (verts_base[-1].pos() - verts_other[0].pos()).manhattanLength() < 1e-4:
            verts_other = verts_other[1:]
        # Append to base
        verts_base.extend(verts_other)
        # Remove *other* from scene
        if self._scene:
            self._scene.removeItem(self._other)
        self._base._rebuild_path()  # type: ignore[attr-defined]

    def undo(self) -> None:  # noqa: D401
        # Restore base vertices
        verts = self._base.vertices()
        verts.clear()
        verts.extend(self._base_orig)
        self._base._rebuild_path()  # type: ignore[attr-defined]
        # Re-add other to scene
        if self._scene and self._other.scene() is None:
            self._scene.addItem(self._other)
        # Restore other vertices sequence
        other_verts = self._other.vertices()
        other_verts.clear()
        other_verts.extend(self._other_orig)
        self._other._rebuild_path()  # type: ignore[attr-defined] 