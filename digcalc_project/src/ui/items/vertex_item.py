"""DigCalc UI - VertexItem

Cross-hair marker item used to represent and manipulate a single vertex of a polyline
within a QGraphicsScene. The item can be dragged, emits a *moved* signal whenever its
scene position changes, and highlights on hover.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGraphicsPathItem, QStyleOptionGraphicsItem, QGraphicsItem
from PySide6.QtGui import QPainterPath, QPen, QPainter
from PySide6.QtCore import Qt, Signal, QPointF, QObject, QEvent


class VertexItem(QObject, QGraphicsPathItem):
    """Cross-hair marker for a polyline vertex that can be dragged in-scene.

    Emits:
        moved (Signal[QPointF]): emitted whenever the item centre (its scene position)
            changes.
        doubleClicked (Signal[object]): emitted when the item is double-clicked.
    """

    moved = Signal(QPointF)  # Signal carrying new scene position
    # Signal emitted when the vertex is double-clicked
    doubleClicked = Signal(object)  # emits self

    CROSS_HALF: int = 3  # Half-length of the cross arms in px (later from settings)

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def __init__(self, pos: QPointF, parent: QGraphicsPathItem | None = None):
        QObject.__init__(self)
        QGraphicsPathItem.__init__(self, parent)

        # Item flags – make the item movable and notify on geometry changes.
        # Use the enum values from QGraphicsItem directly – accessing them via
        # ``self`` is unreliable because the attributes are defined on the
        # C++ base class, not on the Python wrapper instance.
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # Create the cross-hair path and apply it
        self._make_path()
        self.setPos(pos)

        # Pens for normal and hover states (0 px width == hairline pen in Qt)
        self._normal_pen: QPen = QPen(Qt.darkMagenta, 0)
        self._hover_pen: QPen = QPen(Qt.yellow, 0)
        self.setPen(self._normal_pen)

        # --- Z (elevation) ------------------------------------------
        self._z: float = 0.0  # elevation value in feet
        # Initialise tooltip with Z value
        self.set_z(0.0)

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
        if change == QGraphicsItem.ItemPositionChange:
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

    # --- Z value -------------------------------------------------------
    def z(self) -> float:
        """Return the stored elevation (Z) value for this vertex in feet."""
        return self._z

    def set_z(self, value: float):
        """Set the vertex elevation and update its tooltip accordingly."""
        self._z = float(value)
        # Update tooltip to show elevation formatted to 3 decimals
        self.setToolTip(f"Z = {self._z:,.3f} ft")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def to_tuple(self) -> tuple[float, float, float]:  # noqa: D401
        """Return the vertex position as an *(x, y, z)* tuple in scene units."""

        pos: QPointF = self.pos()
        return (pos.x(), pos.y(), self._z)

    # ------------------------------------------------------------------
    # Mouse interaction overrides
    # ------------------------------------------------------------------
    def mouseDoubleClickEvent(self, ev):  # noqa: D401
        """Emit :pyattr:`doubleClicked` when the item is double-clicked."""
        # Emit signal with self reference so listeners can access properties
        self.doubleClicked.emit(self)
        # Call base implementation (keeps default accepted state)
        super().mouseDoubleClickEvent(ev)


__all__ = ["VertexItem"] 