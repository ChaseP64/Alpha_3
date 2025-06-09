"""Undo-able command for adding a BoreholeLog to a StrataStack.

A *symbol* (small circle) is optionally drawn in the 2-D graphics scene.  The
command works without a scene so it can be exercised in head-less unit tests.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QUndoCommand, QPen, QBrush
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsScene
from PySide6.QtCore import Qt

from digcalc_project.src.models.strata_models import BoreholeLog, StrataStack

# ---------------------------------------------------------------------------
# Constants for the on-plan symbol
# ---------------------------------------------------------------------------
_SYMBOL_RADIUS = 5.0  # scene units (ft) – depends on world/px scale in view


class AddBoreholeCommand(QUndoCommand):
    """Add a borehole to the stack and draw a symbol (optional)."""

    def __init__(
        self,
        stack: StrataStack,
        borehole: BoreholeLog,
        scene: Optional[QGraphicsScene] = None,
    ) -> None:
        super().__init__(f"Add borehole #{borehole.id}")
        self._stack = stack
        # copy log so external mutation doesn't affect command state
        self._bh = BoreholeLog(
            id=borehole.id,
            x=borehole.x,
            y=borehole.y,
            layers=list(borehole.layers),
            uuid=borehole.uuid,
        )
        self._scene = scene
        self._item: Optional[QGraphicsEllipseItem] = None
        self._executed = False

    # ------------------------------------------------------------------
    def _add_symbol(self) -> None:
        if self._scene is None or self._item is not None:
            return
        pen = QPen(Qt.black)  # type: ignore[name-defined]
        brush = QBrush(Qt.white)  # hollow circle
        r = _SYMBOL_RADIUS
        self._item = QGraphicsEllipseItem(
            self._bh.x - r,
            self._bh.y - r,
            2 * r,
            2 * r,
        )
        self._item.setPen(pen)
        self._item.setBrush(brush)
        # Attach BoreholeLog so scene can show tooltips
        self._item.setData(0, self._bh)  # role 0
        self._scene.addItem(self._item)

    # ------------------------------------------------------------------
    def _remove_symbol(self) -> None:
        if self._scene is None or self._item is None:
            return
        self._scene.removeItem(self._item)
        self._item = None

    # ------------------------------------------------------------------
    def redo(self) -> None:  # noqa: D401
        if not self._executed:
            if any(bh.id == self._bh.id for bh in self._stack.boreholes):
                self._bh.id = self._stack.next_borehole_id()
            self._executed = True
        self._stack.boreholes.append(self._bh)
        self._add_symbol()

    # ------------------------------------------------------------------
    def undo(self) -> None:  # noqa: D401
        self._stack.boreholes = [bh for bh in self._stack.boreholes if bh.id != self._bh.id]
        self._remove_symbol() 