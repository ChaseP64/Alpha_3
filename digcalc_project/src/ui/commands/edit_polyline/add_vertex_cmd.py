from __future__ import annotations

"""DigCalc UI – AddVertexCommand

QUndoCommand that inserts a new :class:`~digcalc_project.src.ui.items.vertex_item.VertexItem`
into an existing :class:`~digcalc_project.src.ui.items.polyline_item.PolylineItem`.

The command stores enough state to undo/redo reliably in *head-less* unit
tests (no active Qt view required).

Usage example
-------------
>>> cmd = AddVertexCommand(poly_item, QPointF(10, 15), index=3)
>>> undo_stack.push(cmd)
"""

from typing import Optional

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPen, QUndoCommand
from PySide6.QtWidgets import QGraphicsScene

from digcalc_project.src.ui.items.polyline_item import PolylineItem
from digcalc_project.src.ui.items.vertex_item import VertexItem

__all__ = ["AddVertexCommand"]


class AddVertexCommand(QUndoCommand):
    """Insert a vertex at *index* (defaults to append).

    Args:
        polyline: Target :class:`PolylineItem`.
        pos: Scene-coordinate position for the new vertex.
        index: Optional insertion index.  ``None`` (default) appends to the
            end of the vertex chain.
    """

    def __init__(self, polyline: PolylineItem, pos: QPointF, index: Optional[int] = None):
        super().__init__("Add vertex")
        self._poly = polyline
        self._pos = QPointF(pos)
        self._index = index if index is not None else len(polyline.vertices())

        # Will be created on first *redo* so we can destroy/recreate on undo.
        self._vtx: Optional[VertexItem] = None

        # Keep reference to scene for (re)adding item; may be None during tests.
        self._scene: Optional[QGraphicsScene] = polyline.scene() if polyline is not None else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _create_vertex(self) -> VertexItem:
        """Instantiate a new VertexItem and wire signals."""
        pen: QPen = self._poly.pen()  # reuse layer colour
        vtx = VertexItem(self._pos, parent=self._poly)
        vtx.moved.connect(self._poly._rebuild_path)  # type: ignore[attr-defined]
        return vtx

    # ------------------------------------------------------------------
    # QUndoCommand overrides
    # ------------------------------------------------------------------
    def redo(self) -> None:  # noqa: D401
        if self._vtx is None:
            self._vtx = self._create_vertex()
        # Insert into vertex list & arrange Z-order to follow others
        verts = self._poly.vertices()
        # Ensure index within bounds
        idx = max(0, min(self._index, len(verts)))
        verts.insert(idx, self._vtx)

        # Parent already set; simply add to scene if not present
        if self._scene and self._vtx.scene() is None:
            self._scene.addItem(self._vtx)

        # Rebuild polyline path
        self._poly._rebuild_path()  # type: ignore[attr-defined]

    def undo(self) -> None:  # noqa: D401
        if self._vtx is None:
            return
        # Remove from list & scene
        try:
            self._poly.vertices().remove(self._vtx)
        except ValueError:
            pass
        if self._scene:
            self._scene.removeItem(self._vtx)
        # Rebuild path after removal
        self._poly._rebuild_path()  # type: ignore[attr-defined]
