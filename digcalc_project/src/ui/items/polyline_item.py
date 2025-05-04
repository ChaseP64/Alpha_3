"""DigCalc UI - PolylineItem

Interactive polyline graphics item composed of one or more :class:`VertexItem` cross-hair
handles. Each vertex can be dragged, automatically updating the polyline path 
in real-time.  The item supports two *mode*s (for future use):

- ``"entered"`` (default): a straight-line polyline connecting vertices in order.
- ``"interpolated"``: will later render a spline/curve through the vertices.
"""

from __future__ import annotations

from typing import List

from PySide6.QtWidgets import QGraphicsPathItem
from PySide6.QtGui import QPainterPath, QPen
from PySide6.QtCore import QPointF, Qt, Signal, QObject

from .vertex_item import VertexItem


class PolylineItem(QObject, QGraphicsPathItem):
    """Graphical polyline composed of draggable :class:`VertexItem` handles.

    Args:
        points: Initial list of vertex positions in *scene* coordinates.
        layer_pen: Pen used to draw the polyline.
        mode: Either ``"entered"`` (straight lines) or ``"interpolated"`` (future spline).
    """

    # Future: Could add a signal "geometryChanged" to inform external listeners.

    # Signal forwarded when a child vertex is double-clicked
    vertexDoubleClicked = Signal(object, object)  # (self, vertex)

    def __init__(self, points: List[QPointF], layer_pen: QPen, mode: str = "entered"):
        QObject.__init__(self)
        QGraphicsPathItem.__init__(self)

        self.mode: str = mode  # straight-line vs interpolated ‑ stored for later phases
        self._vertex_items: List[VertexItem] = []
        self.setPen(layer_pen)

        # Create a VertexItem for every supplied point
        for pt in points:
            vertex = VertexItem(pt, parent=self)
            vertex.moved.connect(self._rebuild_path)
            vertex.doubleClicked.connect(lambda v=vertex: self.vertexDoubleClicked.emit(self, v))
            self._vertex_items.append(vertex)

        # Build initial path
        self._rebuild_path()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def points(self) -> List[QPointF]:
        """Return the current list of vertex positions (scene coordinates)."""
        return [v.pos() for v in self._vertex_items]

    # ------------------------------------------------------------------
    # Internal logic
    # ------------------------------------------------------------------
    def _rebuild_path(self, *_):  # slot connected to vertex ``moved`` signals – accepts extra args
        """Recalculate the QPainterPath for the polyline based on vertices.

        Accepts a positional placeholder so it can be directly connected to
        :pyattr:`VertexItem.moved` which emits the new :class:`QPointF` but we
        do not need that value here.
        """
        pts = self.points()
        path = QPainterPath()

        if pts:
            path.moveTo(pts[0])
            if self.mode == "interpolated":
                # Placeholder – straight segments for now (future: spline interpolation)
                for pt in pts[1:]:
                    path.lineTo(pt)
            else:  # "entered" or fallback
                for pt in pts[1:]:
                    path.lineTo(pt)

        self.setPath(path)

    # ------------------------------------------------------------------
    # Qt housekeeping
    # ------------------------------------------------------------------
    def shape(self):  # noqa: D401
        """Return the item's shape for collision/select uses.

        Using the underlying :class:`QPainterPath` is sufficient because the
        pen width is cosmetic (0-width hairline).  We avoid calling *scaled* –
        not available on QPainterPath in PySide 6.
        """
        return self.path()


__all__ = ["PolylineItem"] 