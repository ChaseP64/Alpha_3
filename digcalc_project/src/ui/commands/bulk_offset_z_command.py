from __future__ import annotations

"""BulkOffsetZCommand – apply uniform Z delta to multiple VertexItems."""

from collections.abc import Iterable
from typing import List

from PySide6.QtGui import QUndoCommand

from digcalc_project.src.ui.items.vertex_item import VertexItem

__all__ = ["BulkOffsetZCommand"]


class BulkOffsetZCommand(QUndoCommand):
    """Undoable command that offsets a group of vertices by *delta_z* feet."""

    def __init__(self, vertices: Iterable[VertexItem], delta_z: float):
        super().__init__("Bulk Z offset")
        self._verts: List[VertexItem] = list(vertices)
        self._dz: float = float(delta_z)

    def undo(self):
        for v in self._verts:
            v.set_z(v.z() - self._dz)

    def redo(self):
        for v in self._verts:
            v.set_z(v.z() + self._dz)
