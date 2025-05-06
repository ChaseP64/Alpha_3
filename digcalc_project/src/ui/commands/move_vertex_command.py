from __future__ import annotations

"""DigCalc UI – MoveVertexCommand

Undo/redo command for moving a single :class:`~digcalc_project.src.ui.items.vertex_item.VertexItem`.

The command is *mergeable*: successive drags of the **same** vertex will
be collapsed into a single entry on the :class:`PySide6.QtGui.QUndoStack`,
matching typical UX expectations (one uninterrupted drag ⇒ one undo).
"""

from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPointF

from digcalc_project.src.ui.items.vertex_item import VertexItem

__all__ = ["MoveVertexCommand"]


class MoveVertexCommand(QUndoCommand):
    """One vertex drag — mergeable so an entire drag = one undo step.

    Args:
        vtx:   The :class:`VertexItem` being moved.
        old_pos: The starting position *before* the drag (scene coordinates).
        new_pos: The ending position *after* the drag (scene coordinates).
    """

    def __init__(self, vtx: VertexItem, old_pos: QPointF, new_pos: QPointF):
        super().__init__("Move vertex")
        self._vtx = vtx
        self._old: QPointF = QPointF(old_pos)
        self._new: QPointF = QPointF(new_pos)
        # Unique command ID for QUndoStack to allow merging.
        # Using a constant ensures all MoveVertexCommand instances are
        # considered for merging provided :py:meth:`mergeWith` returns *True*.
        self._cmd_id: int = 0xA10C  # Arbitrary non-zero constant

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------
    def undo(self):  # noqa: D401
        """Restore the vertex to its *pre-drag* position."""
        self._vtx.setPos(self._old)

    def redo(self):  # noqa: D401
        """Apply the drag to move the vertex to its final position."""
        self._vtx.setPos(self._new)

    # ------------------------------------------------------------------
    # Merge logic – successive drags on the **same vertex** merge.
    # ------------------------------------------------------------------
    def mergeWith(self, other: "QUndoCommand") -> bool:  # noqa: D401,N802
        """Collapse consecutive drags of the *same* vertex into one step.

        The newest command's *new* position replaces the existing one so that
        the composite command represents the full drag extents.
        """
        if isinstance(other, MoveVertexCommand) and other._vtx is self._vtx:
            # Adopt the *new* position from the most recent movement.
            self._new = QPointF(other._new)
            return True
        return False

    # ------------------------------------------------------------------
    # Qt override – command id for mergeable commands
    # ------------------------------------------------------------------
    def id(self) -> int:  # noqa: D401,N802 – Qt uses camelCase
        """Return constant ID so QUndoStack groups these commands."""

        return self._cmd_id 