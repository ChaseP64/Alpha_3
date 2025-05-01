"""DigCalc UI - VertexItem

Cross-hair marker item used to represent and manipulate a single vertex of a polyline
within a QGraphicsScene. The item can be dragged, emits a *moved* signal whenever its
scene position changes, and highlights on hover.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGraphicsPathItem, QStyleOptionGraphicsItem
from PySide6.QtGui import QPainterPath, QPen, QPainter
from PySide6.QtCore import Qt, Signal, QPointF, QObject


class VertexItem(QObject, QGraphicsPathItem):
    """Cross-hair marker for a polyline vertex that can be dragged in-scene.

    Emits:
        moved (Signal[QPointF]): emitted whenever the item centre (its scene position)
            changes.
    """

    moved = Signal(QPointF)  # Signal carrying new scene position

    CROSS_HALF: int = 3  # Half-length of the cross arms in px (later from settings)

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def __init__(self, pos: QPointF, parent: QGraphicsPathItem | None = None):
        QObject.__init__(self)
        QGraphicsPathItem.__init__(self, parent)

        # Item flags – make the item movable and notify on geometry changes
        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # Create the cross-hair path and apply it
        self._make_path()
        self.setPos(pos)

        # Pens for normal and hover states (0 px width == hairline pen in Qt)
        self._normal_pen: QPen = QPen(Qt.darkMagenta, 0)
        self._hover_pen: QPen = QPen(Qt.yellow, 0)
        self.setPen(self._normal_pen)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _make_path(self) -> None:
        """Generate the cross-hair path for the item and assign it."""
        h = self.CROSS_HALF
        path = QPainterPath()
        # horizontal arm
        path.moveTo(-h, 0)
        path.lineTo(+h, 0)
        # vertical arm
        path.moveTo(0, -h)
        path.lineTo(0, +h)
        self.setPath(path)

    # ------------------------------------------------------------------
    # QGraphicsItem overrides
    # ------------------------------------------------------------------
    def hoverEnterEvent(self, _event):  # noqa: D401 – Qt override signature
        """Highlight the item when hovered."""
        self.setPen(self._hover_pen)

    def hoverLeaveEvent(self, _event):  # noqa: D401 – Qt override signature
        """Restore normal appearance when the cursor leaves."""
        self.setPen(self._normal_pen)

    def itemChange(self, change: QGraphicsPathItem.GraphicsItemChange, value):  # type: ignore[name-defined]
        """Emit *moved* whenever the position has changed."""
        if change == self.ItemPositionChange:
            # *value* holds the new position in item coordinates – convert to scene coords
            if isinstance(value, QPointF):
                self.moved.emit(value)
        # Call the implementation from QGraphicsPathItem directly to bypass QObject in MRO
        return QGraphicsPathItem.itemChange(self, change, value)

    # ------------------------------------------------------------------
    # Painting – ensure crisp rendering (optional override)
    # ------------------------------------------------------------------
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):  # noqa: D401,E501
        """Ensure the pen is used from current item state then delegate to base."""
        painter.setPen(self.pen())
        QGraphicsPathItem.paint(self, painter, option, widget)


__all__ = ["VertexItem"] 