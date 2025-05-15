"""DigCalc UI - VertexItem

Cross-hair marker item used to represent and manipulate a single vertex of a polyline
within a QGraphicsScene. The item can be dragged, emits a *moved* signal whenever its
scene position changes, and highlights on hover.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QStyleOptionGraphicsItem

from digcalc_project.src.services.settings_service import SettingsService


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

    CROSS_HALF: float = float(SettingsService().vertex_cross_px())

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
        c_base = self._layer_pen_colour()
        width_px = SettingsService().vertex_line_thickness()
        self._normal_pen = QPen(c_base.darker(130), width_px)
        hover_col = QColor(SettingsService().vertex_hover_colour())
        self._hover_pen = QPen(hover_col, width_px)
        self.setPen(self._normal_pen)

        # --- Z (elevation) ------------------------------------------
        self._z: float = 0.0  # elevation value in feet
        # Initialise tooltip
        self.set_z(0.0)
        self.setToolTip("(unset)")
        self._update_tooltip()

        self._drag_start_pos: QPointF | None = None  # Track position at drag start
        # Flags for modifier-drag behaviour
        self._dup_requested: bool = False  # Ctrl-drag duplicates on release
        self._constrain: bool = False  # Alt constrains to axis
        self._start_pos: QPointF = QPointF()

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
    def hoverEnterEvent(self, _event):
        """Highlight the item when hovered."""
        self.setPen(self._hover_pen)
        self._update_tooltip()

    def hoverLeaveEvent(self, _event):
        """Restore normal appearance when the cursor leaves."""
        self.setPen(self._normal_pen)

    def itemChange(self, change: QGraphicsPathItem.GraphicsItemChange, value):  # type: ignore[name-defined]
        """Emit *moved* whenever the position has changed."""
        if change == QGraphicsItem.ItemPositionChange:
            # *value* holds the new position in item coordinates – convert to scene coords
            if isinstance(value, QPointF):
                self.moved.emit(value)
                # Update tooltip with new coordinates
                self._update_tooltip()
        # Call the implementation from QGraphicsPathItem directly to bypass QObject in MRO
        return QGraphicsPathItem.itemChange(self, change, value)

    # ------------------------------------------------------------------
    # Painting – ensure crisp rendering (optional override)
    # ------------------------------------------------------------------
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        """Ensure the pen is used from current item state then delegate to base."""
        painter.setPen(self.pen())
        QGraphicsPathItem.paint(self, painter, option, widget)

        view_scale = painter.worldTransform().m11()
        px_half = SettingsService().vertex_cross_px() / max(view_scale, 1e-3)
        if abs(px_half - self.CROSS_HALF) > 1e-2:
            self.CROSS_HALF = px_half
            self._make_path()

    # --- Z value -------------------------------------------------------
    def z(self) -> float:
        """Return the stored elevation (Z) value for this vertex in feet."""
        return self._z

    def set_z(self, value: float):
        """Set the vertex elevation and update its tooltip accordingly."""
        self._z = float(value)
        self._update_tooltip()

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def to_tuple(self) -> tuple[float, float, float]:
        """Return the vertex position as an *(x, y, z)* tuple in scene units."""
        pos: QPointF = self.pos()
        return (pos.x(), pos.y(), self._z)

    # ------------------------------------------------------------------
    # Mouse interaction overrides
    # ------------------------------------------------------------------
    def mousePressEvent(self, ev):
        """Record starting position before a potential drag."""
        # Capture starting position *before* the built-in movable logic updates it.
        self._drag_start_pos = QPointF(self.pos())

        # Modifier checks for duplicate / constrain
        self._dup_requested = bool(ev.modifiers() & Qt.ControlModifier)
        self._constrain = bool(ev.modifiers() & Qt.AltModifier)
        self._start_pos = QPointF(self.scenePos())
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._constrain:
            delta = ev.scenePos() - self._start_pos
            if abs(delta.x()) >= abs(delta.y()):
                # Constrain horizontally: keep Y fixed
                new_scene = QPointF(ev.scenePos().x(), self._start_pos.y())
            else:
                # Constrain vertically: keep X fixed
                new_scene = QPointF(self._start_pos.x(), ev.scenePos().y())

            # Update the item's position directly, bypass default move
            self.setPos(self.mapFromScene(new_scene))
            # Mark event as handled; do not propagate to default
            ev.accept()
            return

        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        """Push a :class:`MoveVertexCommand` if the vertex has moved."""
        super().mouseReleaseEvent(ev)
        # Handle Ctrl-drag duplication
        if self._dup_requested:
            try:
                parent = self.parentItem()
                if parent and hasattr(parent, "_vertex_items"):
                    from digcalc_project.src.ui.items.vertex_item import (
                        VertexItem,  # self-import safe
                    )

                    new_v = VertexItem(self.pos(), parent=parent)
                    vertices = parent._vertex_items  # type: ignore[attr-defined]
                    idx = vertices.index(self) + 1
                    vertices.insert(idx, new_v)
                    new_v.moved.connect(parent._rebuild_path)  # type: ignore[attr-defined]
                    parent._rebuild_path()  # type: ignore[attr-defined]
            except Exception:
                pass

        # Ensure we had a recorded start pos and that the position really changed.
        if self._drag_start_pos is None:
            return
        new_pos: QPointF = QPointF(self.pos())
        if new_pos == self._drag_start_pos:
            return  # No movement – nothing to undo.

        try:
            # Only push when tracing globally enabled.
            if not SettingsService().tracing_enabled():
                return

            # Retrieve main window via the scene -> view -> window chain.
            scene = self.scene()
            main_win = None
            if scene is not None:
                view = getattr(scene, "parent_view", None)
                if view is not None:
                    main_win = view.window()
            # Fallback: try window() directly in case vertex is under a view.
            if main_win is None and self.scene() and self.scene().views():
                main_win = self.scene().views()[0].window()

            if main_win is None or not hasattr(main_win, "undoStack"):
                return

            from digcalc_project.src.ui.commands.move_vertex_command import (
                MoveVertexCommand,
            )

            main_win.undoStack.push(MoveVertexCommand(self, self._drag_start_pos, new_pos))
        finally:
            # Reset the start position marker
            self._drag_start_pos = None

    def mouseDoubleClickEvent(self, ev):
        """Emit :pyattr:`doubleClicked` when the item is double-clicked."""
        # Emit signal with self reference so listeners can access properties
        self.doubleClicked.emit(self)
        # Call base implementation (keeps default accepted state)
        super().mouseDoubleClickEvent(ev)

    # ------------------------------------------------------------------
    # Colour helper – inherit layer pen colour if possible
    # ------------------------------------------------------------------
    def _layer_pen_colour(self):
        """Return colour based on parent polyline pen or fallback."""
        p = self.parentItem()
        if p and hasattr(p, "pen"):
            try:
                return p.pen().color()
            except Exception:
                pass
        return QColor(Qt.darkMagenta)

    # --------------------------------------------------------------
    # Tooltip helper
    # --------------------------------------------------------------
    def _update_tooltip(self):
        """Update tooltip with XYZ coordinates, Δ to previous vertex, and station."""
        try:
            parent = self.parentItem()
            if parent is None or not hasattr(parent, "_vertex_items"):
                return

            vertices = parent._vertex_items  # type: ignore[attr-defined]
            if not vertices:
                return

            idx = vertices.index(self)
            this = self.pos()

            # Δ to previous vertex (Euclidean via manhattanLength for speed)
            prev_dist = 0.0
            if idx > 0:
                prev_dist = (this - vertices[idx - 1].pos()).manhattanLength()

            # Running station from start to this vertex
            station = 0.0
            for i in range(1, idx + 1):
                station += (vertices[i].pos() - vertices[i - 1].pos()).manhattanLength()

            # Tooltip string
            self.setToolTip(
                f"X:{this.x():.2f}  Y:{this.y():.2f}  Z:{self._z:.2f}\n"
                f"ΔPrev:{prev_dist:.2f}  Station:{station:.2f}",
            )
        except Exception:
            # Fail quietly – tooltip is non-critical.
            pass


__all__ = ["VertexItem"]
