from __future__ import annotations

"""DigCalc UI – DeleteVertexCommand

Remove a selected :class:`~digcalc_project.src.ui.items.vertex_item.VertexItem`
from a :class:`~digcalc_project.src.ui.items.polyline_item.PolylineItem`.
"""

from typing import Optional

from PySide6.QtCore import QPointF
from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import QGraphicsScene

from digcalc_project.src.ui.items.vertex_item import VertexItem
from digcalc_project.src.ui.items.polyline_item import PolylineItem

__all__ = ["DeleteVertexCommand"]


class DeleteVertexCommand(QUndoCommand):
    """Delete *vertex* from *polyline* keeping ability to undo."""

    def __init__(self, polyline: PolylineItem, vertex: VertexItem):
        super().__init__("Delete vertex")
        self._poly = polyline
        self._vtx = vertex
        # Capture position and insertion index for undo
        self._pos: QPointF = QPointF(vertex.pos())
        # Determine current index in list
        try:
            self._index: int = polyline.vertices().index(vertex)
        except ValueError:
            self._index = -1
        self._scene: Optional[QGraphicsScene] = polyline.scene() if polyline is not None else None

    # ------------------------------------------------------------------
    def redo(self) -> None:  # noqa: D401
        if self._index < 0:
            return  # vertex not part of polyline
        try:
            self._poly.vertices().remove(self._vtx)
        except ValueError:
            pass
        if self._scene:
            self._scene.removeItem(self._vtx)
        self._poly._rebuild_path()  # type: ignore[attr-defined]

    def undo(self) -> None:  # noqa: D401
        if self._index < 0:
            return
        verts = self._poly.vertices()
        idx = max(0, min(self._index, len(verts)))
        verts.insert(idx, self._vtx)
        # Restore position
        self._vtx.setPos(self._pos)
        if self._scene and self._vtx.scene() is None:
            self._scene.addItem(self._vtx)
        self._poly._rebuild_path()  # type: ignore[attr-defined] 