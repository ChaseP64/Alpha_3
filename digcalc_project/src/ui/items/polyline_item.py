"""DigCalc UI - PolylineItem

Interactive polyline graphics item composed of one or more :class:`VertexItem` cross-hair
handles. Each vertex can be dragged, automatically updating the polyline path 
in real-time.  The item supports two *mode*s (for future use):

- ``"entered"`` (default): a straight-line polyline connecting vertices in order.
- ``"interpolated"``: will later render a spline/curve through the vertices.
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QObject, QPointF, Signal, Qt
from PySide6.QtGui import QPainterPath, QPen, QColor
from PySide6.QtWidgets import QGraphicsPathItem

from digcalc_project.src.tools.spline import catmull_rom
from digcalc_project.src.tools.spline import sample as spline_sample

from .vertex_item import VertexItem


class PolylineItem(QObject, QGraphicsPathItem):
    """Graphical polyline composed of draggable :class:`VertexItem` handles.

    Args:
        points: Initial list of vertex positions in *scene* coordinates.
        layer_pen: Pen used to draw the polyline.
        mode: Either ``"entered"`` (straight lines) or ``"interpolated"`` (future spline).
        layer_id: Optional layer ID for the polyline.

    """

    # Future: Could add a signal "geometryChanged" to inform external listeners.

    # Signal forwarded when a child vertex is double-clicked
    vertexDoubleClicked = Signal(object, object)  # (self, vertex)

    # ------------------------------------------------------------------
    # Modes constant
    # ------------------------------------------------------------------
    MODES = ("entered", "interpolated")

    def __init__(
        self,
        points: List[QPointF],
        layer_pen: QPen,
        mode: str = "entered",
        layer_id: str | None = None,
    ):
        # Ensure a valid mode is provided
        assert mode in self.MODES, f"Mode must be one of {self.MODES}, got {mode!r}"
        QObject.__init__(self)
        QGraphicsPathItem.__init__(self)

        self.mode: str = mode  # stored for later path rebuilds
        self.layer_id: str | None = layer_id
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
    # Accessors
    # ------------------------------------------------------------------
    def vertices(self) -> List[VertexItem]:
        """Return the list of :class:`VertexItem` handles.

        This accessor is primarily used by undo / redo commands that need direct
        access to the vertex objects themselves rather than just their
        coordinates.
        """
        return self._vertex_items

    # ------------------------------------------------------------------
    # Evaluation helpers
    # ------------------------------------------------------------------
    def sample(self, density_ft: float):
        """Return simplified list of (x, y, z) tuples at ≈ ``density_ft`` spacing.

        First generate *pts3d* either via spline resampling (for *interpolated*
        mode) or by taking the raw vertices (for *entered* mode).  Then apply
        *compression* based on user settings (T-6 optimisation):

        • Drop consecutive points that lie closer than
          :pyattr:`SettingsService.smooth_min_spacing_ft`.
        • Stop once :pyattr:`SettingsService.smooth_max_points` have been
          emitted, guarding against pathological polylines producing millions
          of samples.
        """
        # ------------------------------------------------------------------
        # 1) Generate the full point list (may be long for splines)
        # ------------------------------------------------------------------
        if self.mode == "interpolated":
            # Helper accepts *any* iterable exposing .x(), .y(), .z()/z attr
            pts3d = spline_sample(self.vertices(), density_ft)
        else:
            # Straight-line polyline – just spit back the original vertices
            pts3d = [v.to_tuple() for v in self.vertices()]

        # ------------------------------------------------------------------
        # 2) Compression – distance filter + global cap
        # ------------------------------------------------------------------
        from digcalc_project.src.services.settings_service import SettingsService

        ss = SettingsService()
        min_d = ss.smooth_min_spacing_ft()
        max_n = ss.smooth_max_points()

        # Fast exit when nothing to compress.
        if len(pts3d) <= 1:
            return pts3d

        compressed: list[tuple[float, float, float]] = []
        last_pt = None
        for pt in pts3d:
            if last_pt is None:
                compressed.append(pt)
                last_pt = pt
                # Do *not* continue here – allow first-point duplication guard below.
                continue

            dx = pt[0] - last_pt[0]
            dy = pt[1] - last_pt[1]
            dz = pt[2] - last_pt[2]
            if (dx * dx + dy * dy + dz * dz) ** 0.5 >= min_d * 0.9999:
                compressed.append(pt)
                last_pt = pt

            if len(compressed) >= max_n:
                break

        return compressed

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

        if self.mode == "interpolated":
            # Use Catmull-Rom spline helper for smooth interpolation
            self.setPath(catmull_rom(pts))
            return

        # Fallback: straight lines between entered vertices
        path = QPainterPath()
        if pts:
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)

        self.setPath(path)
        # Cache for custom paint() routine (avoids repeatedly walking path())
        self._cached_path = path

    # ------------------------------------------------------------------
    # Qt housekeeping
    # ------------------------------------------------------------------
    def shape(self):
        """Return the item's shape for collision/select uses.

        Using the underlying :class:`QPainterPath` is sufficient because the
        pen width is cosmetic (0-width hairline).  We avoid calling *scaled* –
        not available on QPainterPath in PySide 6.
        """
        return self.path()

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------
    def toggle_mode(self):
        """Toggle between *entered* and *interpolated* display modes."""
        self.mode = "interpolated" if self.mode == "entered" else "entered"
        self._rebuild_path()

    # ------------------------------------------------------------------
    # Colour update helper (called when layer palette changes)
    # ------------------------------------------------------------------
    def update_color(self, hex_colour: str):
        """Update the item's pen colour *in-place* and refresh vertices."""
        import sys # For print
        print(f"PolylineItem {self}: update_color CALLED with {hex_colour=}", flush=True, file=sys.stderr)
        from PySide6.QtGui import QColor
        
        col = QColor(hex_colour)
        current_pen = self.pen()

        if current_pen.color() != col:
            new_pen = QPen(current_pen) 
            new_pen.setColor(col)
            self.setPen(new_pen)
            print(f"PolylineItem {self}: Inside update_color, after setPen, self.pen().color().name() is {self.pen().color().name()}", flush=True, file=sys.stderr)

            for v in self._vertex_items:
                setattr(v, "_colour_hex", hex_colour)
            for v in self._vertex_items:
                if hasattr(v, "update_color"):
                    v.update_color(hex_colour)
            self.update() 
        else:
            print(f"PolylineItem {self}: update_color - colors are SAME ({current_pen.color().name()} vs {col.name()}), no update.", flush=True, file=sys.stderr)

    # ------------------------------------------------------------------
    # Qt paint override – add black outline for contrast
    # ------------------------------------------------------------------
    def paint(self, painter, option, widget=None):  # noqa: D401
        """Draw an outline + coloured stroke for high contrast.

        We render two passes:

        1. A slightly thicker black stroke that forms the halo/outline.
        2. The actual layer-coloured stroke on top.
        """
        from PySide6.QtGui import QColor, QPen
        from PySide6.QtCore import Qt

        path = getattr(self, "_cached_path", None) or self.path()

        # Foreground pen – derive width & colour from item pen
        fg_pen: QPen = self.pen()
        w = max(1, int(fg_pen.widthF() or 2))  # enforce ≥1

        # 1) Outline (black)
        pen_bg = QPen(Qt.black, w + 2, Qt.SolidLine, Qt.RoundCap, Qt.BevelJoin)
        painter.setPen(pen_bg)
        painter.drawPath(path)

        # 2) Main coloured stroke (reuse fg_pen but ensure cosmetic caps)
        pen_fg = QPen(QColor(fg_pen.color()), w, Qt.SolidLine, Qt.RoundCap, Qt.BevelJoin)
        painter.setPen(pen_fg)
        painter.drawPath(path)


__all__ = ["PolylineItem"]
