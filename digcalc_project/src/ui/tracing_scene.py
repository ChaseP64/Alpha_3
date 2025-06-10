from __future__ import annotations

# src/ui/tracing_scene.py
import logging
import math
from collections.abc import Sequence
import os  # <-- added for _show_scale_warning
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, TypeAlias

from PySide6.QtCore import QLineF, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QImage,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
    QUndoCommand,
    QUndoStack,  # Moved from QtWidgets
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QInputDialog,
    QMenu,
    QMessageBox,
    QRubberBand,
    QToolTip,
)

from digcalc_project.src.exceptions import NoScaleError
from digcalc_project.src.services.settings_service import SettingsService
from digcalc_project.src.ui.commands.edit_vertex_z_command import EditVertexZCommand
from digcalc_project.src.ui.commands.interpolate_segment_z_command import (
    InterpolateSegmentZCommand,
)

# --- Elevation workflow commands ---
from digcalc_project.src.ui.commands.set_polyline_uniform_z_command import (
    SetPolylineUniformZCommand,
)
from digcalc_project.src.ui.commands.toggle_smooth_command import ToggleSmoothCommand
from digcalc_project.src.ui.dialogs.elevation_dialog import ElevationDialog
from digcalc_project.src.ui.items.polyline_item import PolylineItem
from digcalc_project.src.ui.items.vertex_item import VertexItem

# --- MODIFIED: Use TYPE_CHECKING for PolylineData ---
if TYPE_CHECKING:
    from ..models.project import Project, PolylineData
    from .visualization_panel import VisualizationPanel
else:
    # Provide a runtime fallback (e.g., dict or Any)
    PolylineData = Any # Or Dict[str, Any] if it's always a dict structure
    VisualizationPanel = Any # <<< Add fallback for runtime
# --- END MODIFIED ---

# --- NEW: Define Type Alias ---
LayerPolylineDict: TypeAlias = Dict[str, List[List[Tuple[float, float]]]]
# --- END NEW ---

class TracingScene(QGraphicsScene):
    """A custom QGraphicsScene for interactive polyline tracing over a background image,
    with support for basic layer management.
    """

    # ------------------------------------------------------------
    #  Constants – translucent in-scene banner when no PDF scale
    # ------------------------------------------------------------
    _NOSCALE_TEXT: str = "⚠  No scale calibrated"
    _NOSCALE_Z: int = 99  # Draw above everything
    _NOSCALE_COLOR: QColor = QColor(255, 0, 0, 160)  # Semi-transparent red

    # --- MODIFIED: Update signal definition ---
    # Signal emitted when a polyline is finalized (e.g., by double-click or Enter)
    # Sends the list of QPointF vertices AND the created QGraphicsPathItem.
    polyline_finalized = Signal(list, QGraphicsPathItem)
    # --- END MODIFIED ---

    # --- NEW: Signal for item selection ---
    # Emits the selected QGraphicsItem when selection changes.
    # In this context, it will be the QGraphicsPathItem representing a polyline.
    selectionChanged = Signal(QGraphicsItem)
    # --- END NEW ---

    # --- NEW: Signal for page bounding rect ---
    pageRectChanged = Signal()
    # --- END NEW ---

    # --- NEW: Signal when a closed pad polyline is drawn ---
    padDrawn = Signal(list)  # Emits list[tuple[float, float]] representing 2-D vertices
    # --- END NEW ---

    # --- MODIFIED: Accept and store panel reference ---
    def __init__(self, view: QGraphicsView, panel: VisualizationPanel, parent=None):
        """Initialize the TracingScene.

        Args:
            view (QGraphicsView): The view that displays this scene.
            panel (VisualizationPanel): The parent visualization panel.
            parent (QObject, optional): Parent object. Defaults to None.

        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.parent_view = view # Store reference to the parent view
        self.panel = panel # Store reference to the panel
        self.project: Optional['Project'] = None # Explicitly initialize project attribute
        # Settings access – used for tracing enable flag and elevation mode
        self._settings = SettingsService()

        # Cache global tracing-enabled flag & elevation prompt mode
        self._tracing_enabled: bool = self._settings.tracing_enabled()
        self._elev_mode: str = self._settings.tracing_elev_mode()
        # Alias for clarity with new API
        self._prompt_mode: str = self._elev_mode

        # Allow multiple stacked background layers (one per PDF page)
        self._background_items: List[QGraphicsPixmapItem] = []
        self._is_drawing: bool = False
        self._current_polyline_points: List[QPointF] = []
        self._current_vertices_items: List[QGraphicsEllipseItem] = []
        self._temporary_line_item: Optional[QGraphicsLineItem] = None
        self._selected_polyline: PolylineItem | None = None

        # Placeholder for Backspace-local undo shortcut (created when tracing starts)
        self._undo_shortcut = None

        # --- Styling ---
        # TODO: Consider layer-specific styling later
        self._background_opacity = 0.7
        self._vertex_pen = QPen(QColor("cyan"), 1)
        self._vertex_brush = QBrush(QColor("cyan"))
        self._vertex_radius = 3.0
        self._rubber_band_pen = QPen(QColor("yellow"), 1, Qt.DashLine)
        self._finalized_polyline_pen = QPen(QColor("lime"), 4)
        self._selected_polyline_pen = QPen(QColor("yellow"), 5, Qt.DotLine)

        # --- Local "Backspace" shortcut to undo last vertex ---
        if self.parent_view and self._undo_shortcut is None:
            target_widget = self.parent_view.viewport()

            sc = QShortcut(QKeySequence(Qt.Key_Backspace), target_widget)
            sc.setContext(Qt.WidgetWithChildrenShortcut)

            def _local_backspace():
                self.logger.debug("Local Backspace activated (vertex undo)")
                if self._is_drawing:
                    self._undo_last_vertex()
            sc.activated.connect(_local_backspace)

            self._undo_shortcut = sc

        # VertexItem double-clicks will be routed via PolylineItem.signal; no event filter needed.

        # --- Spline smoothing state ---
        # Stores *True* when the in-progress polyline should display as a smooth
        # spline, *False* for straight segments.  Default obtained from user
        # settings.
        self._current_mode: bool = SettingsService().smooth_default()

        # Live preview polyline (spline or straight) while tracing – optional
        self._preview_poly: PolylineItem | None = None

        # Elevations collected during *point* mode drawing (aligned to _current_polyline_points)
        self._current_z_values: List[float] = []

        self._rubber_band: QRubberBand | None = None
        self._marquee_origin: QPointF | None = None
        self._marquee_selection: list[VertexItem] = []

        # ------------------------------------------------------------------
        # scale-calibration hint helpers
        # ------------------------------------------------------------------
        self._scale_warn_shown: bool = False  # one-shot QMessageBox flag
        # Legacy name kept for backward-compat but no longer used directly.
        self._scale_overlay: QGraphicsSimpleTextItem | None = None  # DEPRECATED

        # New overlay item reference
        self._noscale_item: QGraphicsSimpleTextItem | None = None

        # ------------------------------------------------------------------
        # Local undo/redo stack – lightweight per-scene stack so tests can push
        # commands without spinning up the whole MainWindow.  MainWindow still
        # owns its *own* stack for full application use, but exposing one here
        # simplifies isolated unit-tests that manipulate the scene directly.
        # ------------------------------------------------------------------
        self._undo_stack = QUndoStack(self)

        # Expose accessor compatible with MainWindow.undoStack()
        self.undoStack = lambda: self._undo_stack

        # ------------------------------------------------------------------
        # Strata-Contour mode (Phase 5-1A)
        # ------------------------------------------------------------------
        self._strata_contour_mode: bool = False  # Flag toggled via UI
        self._current_material_id: Optional[int] = None  # Active material when flag on

        # ------------------------------------------------------------------
        # Ensure the scene has a non-zero rect so early unit-tests that click
        # at small positive coordinates (10,10) will register even before any
        # items or background images are added.  With an empty scene Qt leaves
        # the rect at (0,0,0,0) which causes all clicks to be ignored.
        # ------------------------------------------------------------------
        if self.sceneRect().width() == 0 or self.sceneRect().height() == 0:
            default_size = 1000.0
            self.setSceneRect(0.0, 0.0, default_size, default_size)

    # --- Background Image ---

    # ------------------------------------------------------------------
    # Background layer helpers (multi‑page stacking)
    # ------------------------------------------------------------------

    def addBackgroundLayer(self, pixmap: QPixmap, z: float | None = None) -> None: # noqa: N802
        """Add a new PDF page pixmap as a background layer."""
        item = QGraphicsPixmapItem(pixmap)
        if z is None:
            z = -(len(self._background_items) + 1) # stack downwards
        item.setZValue(z)
        item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        item.setFlag(QGraphicsItem.ItemIsMovable, False)
        item.setOpacity(self._background_opacity)
        self.addItem(item)
        self._background_items.append(item)
        # Expand scene rect to fit all layers (use combined bounds)
        self.setSceneRect(self.itemsBoundingRect())
        self.pageRectChanged.emit()

    def removeBackgroundLayer(self, index: int) -> None: # noqa: N802
        """Remove a background layer by its index in the stack."""
        if 0 <= index < len(self._background_items):
            item = self._background_items.pop(index)
            if item in self.items():
                self.removeItem(item)
            # Update Z‑values to keep ordering compact
            for i, it in enumerate(self._background_items, start=1):
                it.setZValue(-i)
            self.setSceneRect(self.itemsBoundingRect())
            self.pageRectChanged.emit()
        else:
            self.logger.warning("removeBackgroundLayer: index out of range (%s)", index)

    # Legacy single‑image API retained for compatibility -----------------------------------\
    def set_background_image(self, image: Optional[QImage]):
        """Maintain old API: clear layers then add one."""
        # clear existing
        for item in list(self._background_items):
            if item in self.items():
                self.removeItem(item)
        self._background_items.clear()
        if image and not image.isNull():
            self.addBackgroundLayer(QPixmap.fromImage(image))
        else:
            # If image is None, clear scene rect or set to default
            self.setSceneRect(self.itemsBoundingRect()) # Update rect even if empty
            self.pageRectChanged.emit() # Emit signal

    # ------------------------------------------------------------------
    # Backward‑compat helper – some code paths call *setBackgroundImage*.
    # ------------------------------------------------------------------
    def setBackgroundImage(self, pixmap: QPixmap): # camelCase alias
        """Qt slot‑style camel‑case alias for :py:meth:`set_background_image`."""
        img = pixmap.toImage() if isinstance(pixmap, QPixmap) else None
        self.set_background_image(img)

    # --- NEW: Fit View ---
    def fit_current_page(self):
        """Emits the pageRectChanged signal, indicating the view should refit the scene contents.
        The actual fitting is handled by the connected slot in the MainWindow/VisualizationPanel.
        """
        self.logger.debug("fit_current_page called, emitting pageRectChanged.")
        self.pageRectChanged.emit()
    # --- END NEW ---

    # --- Drawing Control ---

    def start_drawing(self):
        """Explicitly enables drawing mode."""
        # ------------------------------------------------------------------
        # Always handle missing-scale warning/overlay *before* tracing-enabled check
        # so the user is reminded even if tracing is disabled. This matches the
        # behaviour expected by unit-tests (scale_warning_shown_once).
        # ------------------------------------------------------------------
        project = getattr(self, "project", None)
        if project is None and hasattr(self.panel, "current_project"):
            project = self.panel.current_project

        if project is not None and project.scale is None:
            if not self._scale_warn_shown:
                # Flag set here *immediately* so unit-tests can assert after
                # start_drawing() even if the warning dialog itself is
                # suppressed in headless mode.
                self._scale_warn_shown = True
                self._show_scale_warning()

            # Always refresh/hide the passive overlay based on current scale
            self._update_noscale_overlay()

        # ------------------------------------------------------------------
        # Respect tracing-enabled flags – abort drawing operations if disabled.
        # (Warning/overlay code above has already run.)
        # ------------------------------------------------------------------
        if not (self._tracing_enabled and self._settings.tracing_enabled()):
            self.logger.debug(
                "start_drawing aborted – tracing disabled (runtime flag %s, user setting %s).",
                self._tracing_enabled,
                self._settings.tracing_enabled(),
            )
            return

        # Do not mutate _tracing_enabled here; it reflects global toggle state
        # Snapshot current elevation prompt mode for this drawing session
        self._elev_mode = self._prompt_mode = self._settings.tracing_elev_mode()
        self.logger.debug("Drawing mode explicitly enabled.")
        # Change cursor when tracing starts
        if self.parent_view:
            self.parent_view.setCursor(Qt.CrossCursor)

        # Ensure viewport has focus so key events (Space/Enter) reach scene
        if self.parent_view:
            self.parent_view.viewport().setFocus()
        # Reset smoothing mode for new polyline according to user default
        self._current_mode = SettingsService().smooth_default()

        # Reset per-vertex Z cache
        self._current_z_values = []

        # Drop any stale preview item from previous operation
        if self._preview_poly and self._preview_poly in self.items():
            self.removeItem(self._preview_poly)
        self._preview_poly = None

        # Ensure overlay visibility is updated once drawing actually starts
        self._update_noscale_overlay()

    def stop_drawing(self):
        """Explicitly disables drawing mode and cancels any current polyline."""
        # Keep global flag intact; simply stop current drawing session
        if self._is_drawing:
            self._cancel_current_polyline()
            self.logger.debug("Drawing mode explicitly disabled, current polyline cancelled.")
        # Reset cursor when tracing stops
        if self.parent_view:
             # Restore appropriate cursor based on view's drag mode
            cursor = Qt.ArrowCursor
            if self.parent_view.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                cursor = Qt.OpenHandCursor
            self.parent_view.setCursor(cursor)

    # --- Event Handling for Drawing ---

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles mouse press events to add vertices to the polyline."""
        # Check if the parent view is currently performing manual panning
        if self.parent_view and hasattr(self.parent_view, "_panning") and self.parent_view._panning:
            self.logger.debug("Scene mousePress ignored: View is manually panning.")
            return

        panel = self.panel  # VisualizationPanel

        # Borehole tool click handling
        if panel.drawing_mode.name == "BOREHOLE" and event.button() == Qt.LeftButton:
            self.logger.info("Borehole mode click at (%.2f, %.2f)", event.scenePos().x(), event.scenePos().y())
            scene_pos = event.scenePos()
            panel.boreholePointPicked.emit(scene_pos.x(), scene_pos.y())
            # exit borehole mode (handled by panel or caller)
            event.accept()
            return

        if not self._tracing_enabled:
            # If tracing is disabled, allow the base class/view to handle selection/panning etc.
            super().mousePressEvent(event)
            return

        # ---------------- Pre-flight scale validation ----------------
        if event.button() == Qt.LeftButton:
            # Use self.project directly, which is set by VisualizationPanel.set_project
            proj_to_check = self.project # No need for getattr if always initialized

            if self._scale_invalid(proj_to_check):
                QMessageBox.warning(
                    self.views()[0],
                    "Scale Required",
                    "Tracing is disabled until a valid scale is set.\n"
                    "Choose Tracing ▸ Calibrate Scale… or click the green scale pill.",
                )
                return  # Abort – do *not* start tracing
        # -------------------------------------------------------------

        # --- Tracing is Enabled ---
        if event.button() == Qt.LeftButton:
            # No additional scale checks needed (already validated)
            pos = self._constrained_pos(event.scenePos(), event.modifiers())  # Apply constraints on press

            # Check if click is within any background item bounds (if backgrounds exist)
            can_draw = True
            if self._background_items:
                can_draw = any(bg.sceneBoundingRect().contains(pos) for bg in self._background_items)

            if can_draw:
                if not self._is_drawing:
                    self._is_drawing = True
                    self._current_polyline_points = [pos]
                    # ----------------------------------------------
                    # Point-prompt elevation input (first vertex)
                    # ----------------------------------------------
                    if self._elev_mode == "point":
                        z_val, ok = self._ask_vertex_z()
                        if not ok:
                            # Abort creation entirely if user cancels on first point
                            self._is_drawing = False
                            self._current_polyline_points.clear()
                            return
                        self._current_z_values = [z_val]
                    else:
                        self._current_z_values = [0.0]
                    self._add_vertex_marker(pos)
                    self.logger.debug(f"Started new polyline at: {pos.x():.2f}, {pos.y():.2f}")
                else:
                    # Add the constrained position
                    self._current_polyline_points.append(pos)
                    # Prompt elevation for this vertex if in point mode
                    if self._elev_mode == "point":
                        z_val, ok = self._ask_vertex_z()
                        if not ok:
                            # Cancel adding this vertex; revert lists
                            self._current_polyline_points.pop()
                            return
                        self._current_z_values.append(z_val)
                    else:
                        self._current_z_values.append(0.0)
                    self._add_vertex_marker(pos)
                    self._update_temporary_line(pos)  # Update rubber band to this new point
                    self.logger.debug(f"Added vertex at: {pos.x():.2f}, {pos.y():.2f}")
                event.accept()  # We handled the click for drawing
            else:
                # If click is outside drawable area when tracing, let view handle pan/etc.
                super().mousePressEvent(event)
        else:
            # --- New: Right-click finalises polyline when drawing ---
            if event.button() == Qt.RightButton and self._is_drawing and self._tracing_enabled:
                if len(self._current_polyline_points) >= 2:
                    active_layer = self._get_active_layer_name()
                    self._finalize_current_polyline(active_layer)
                else:
                    self._cancel_current_polyline()
                event.accept()
                return

            # Pass other non-left clicks to base class
            super().mousePressEvent(event)

        if event.button() == Qt.LeftButton and not self.itemAt(event.scenePos(), self.views()[0].transform()):
            # Start marquee selection
            self._marquee_origin = event.scenePos()
            if self._rubber_band is None:
                self._rubber_band = QRubberBand(QRubberBand.Rectangle, self.views()[0])
            self._rubber_band.setGeometry(QRectF(self._marquee_origin, QSize()).toRect())
            self._rubber_band.show()
            return

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles mouse move events to update the temporary rubber-band line with constraints."""
        if not self._tracing_enabled or not self._is_drawing or not self._current_polyline_points:
            super().mouseMoveEvent(event)
            return

        constrained_pos = self._constrained_pos(event.scenePos(), event.modifiers())
        self._update_temporary_line(constrained_pos)
        event.accept() # We are handling the move for the rubber band

        if self._rubber_band and self._marquee_origin is not None:
            rect = QRectF(self._marquee_origin, event.scenePos()).normalized()
            self._rubber_band.setGeometry(rect.toRect())
            return

    def _constrained_pos(self, current_pos: QPointF, modifiers: Qt.KeyboardModifiers) -> QPointF:
        """Calculates the constrained position based on the last point and modifier keys.

        Args:
            current_pos (QPointF): The current mouse position in scene coordinates.
            modifiers (Qt.KeyboardModifiers): Keyboard modifiers (Shift, Ctrl).

        Returns:
            QPointF: The potentially constrained position.

        """
        if not self._current_polyline_points:
            return current_pos # No previous point to constrain relative to

        last_point = self._current_polyline_points[-1]
        dx = current_pos.x() - last_point.x()
        dy = current_pos.y() - last_point.y()

        if modifiers == Qt.ShiftModifier:
            # Constrain to horizontal or vertical
            if abs(dx) > abs(dy):
                return QPointF(current_pos.x(), last_point.y()) # Horizontal
            return QPointF(last_point.x(), current_pos.y()) # Vertical
        if modifiers == Qt.ControlModifier:
            # Constrain to 45-degree increments
            angle = math.atan2(dy, dx)
            snapped_angle = round(angle / (math.pi / 4)) * (math.pi / 4)
            dist = math.hypot(dx, dy)
            snapped_x = last_point.x() + dist * math.cos(snapped_angle)
            snapped_y = last_point.y() + dist * math.sin(snapped_angle)
            return QPointF(snapped_x, snapped_y)
        # No constraint
        return current_pos

    # --- NEW: Scene → World conversion helper -----------------------------------------
    def _scene_to_world(self, scene_pos: QPointF) -> Tuple[float, float]:
        """Convert a Qt scene-pixel position to model (world) coordinates based on the
        currently calibrated PDF scale stored on the :pyattr:`project` instance.

        Args:
            scene_pos (QPointF): Position in scene (pixel) coordinates.

        Returns:
            tuple[float, float]: (x_world, y_world) in project units (ft or m).

        """
        # Attempt to fetch the Project reference.  If this scene owns a direct
        # handle, prefer it; otherwise fall back to the panel's current project.
        project = getattr(self, "project", None)
        if project is None and hasattr(self.panel, "current_project"):
            project = self.panel.current_project

        scale = getattr(project, "scale", None) if project else None
        if not scale:
            # Escalate – tracing logic should never call this without a scale.
            raise NoScaleError(
                "Tracing requires a calibrated scale. "
                "Use Tracing ▸ Calibrate Scale… before digitising.",
            )

        factor = scale.world_per_px  # direct helper
        return scene_pos.x() * factor, scene_pos.y() * factor

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        """Handles double-click events to finalize the current polyline."""
        if not self._tracing_enabled or not self._is_drawing:
            super().mouseDoubleClickEvent(event)
            return

        if event.button() == Qt.LeftButton:
            if len(self._current_polyline_points) >= 2:
                if self._elev_mode != "point":
                    # For interpolate/line modes we still add the last vertex
                    final_pos = self._constrained_pos(event.scenePos(), event.modifiers())
                    self._current_polyline_points.append(final_pos)
                    self._add_vertex_marker(final_pos)

                # Finalise without adding an extra prompt for point-mode
                active_layer = self._get_active_layer_name()
                self._finalize_current_polyline(active_layer)
            else:
                # Not enough points, cancel
                self._cancel_current_polyline()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key press events (Enter to finalize, Backspace to undo, Esc to cancel)."""
        if not self._tracing_enabled or not self._is_drawing:
            super().keyPressEvent(event)
            return

        # --- Hot-key: toggle spline smoothing while drawing (Key 'S') ---
        if self._is_drawing and event.key() == Qt.Key_S:
            self._current_mode = not self._current_mode
            if self._preview_poly:
                self._preview_poly.mode = "interpolated" if self._current_mode else "entered"
                self._preview_poly._rebuild_path()
            event.accept()
            return

        # --- Spacebar or Enter/Return finalises polyline now ---
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if len(self._current_polyline_points) >= 2:
                active_layer = self._get_active_layer_name()
                self._finalize_current_polyline(active_layer)
            else:
                self._cancel_current_polyline()
            event.accept()
        elif event.key() == Qt.Key_Z and (event.modifiers() & Qt.ControlModifier):
            # Ctrl+Z during drawing should undo the last vertex (similar to backspace)
            self._undo_last_vertex()
            event.accept()
        elif event.key() == Qt.Key_Backspace:
            self._undo_last_vertex()
            event.accept()
        elif event.key() == Qt.Key_Escape:
             self._cancel_current_polyline()
             event.accept()
        else:
            # Allow other keys (like modifiers) to pass through
            super().keyPressEvent(event)

    # --- Helper to get active layer ---
    def _get_active_layer_name(self) -> str:
        """Safely gets the active layer name from the parent panel."""
        active_layer = "Default" # Fallback
        # --- MODIFIED: Use stored panel reference ---
        if self.panel and hasattr(self.panel, "active_layer_name"):
            active_layer = self.panel.active_layer_name
        else:
            self.logger.warning("Could not get active_layer_name: Panel reference or attribute missing.")
        # --- END MODIFIED ---
        return active_layer

    # --- NEW: Override mouseReleaseEvent to detect selection ---
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | QMouseEvent): # Allow QMouseEvent from view
        """Overrides mouseReleaseEvent to emit selectionChanged signal
        when a selectable item (polyline) is clicked.
        """
        # Check if the parent view handled panning
        if self.parent_view and hasattr(self.parent_view, "_panning") and self.parent_view._panning:
             # If view was panning, don't process release for selection in scene
             # The view's release handler should reset state
             return

        # Important: Call super implementation to handle standard selection behavior first!
        super().mouseReleaseEvent(event)

        # After base class handled it, check selection and emit signal
        selected_items = self.selectedItems()
        if selected_items:
            # Emit the first selected item (assuming single selection for now)
            # Filter for QGraphicsPathItem specifically if needed
            selected_item = selected_items[0]
            if isinstance(selected_item, PolylineItem):  # Ensure it's a traced polyline
                 # Store reference for convenience
                 self._selected_polyline = selected_item
                 self.logger.debug(f"Selection changed, emitting signal for item: {selected_item}")
                 self.selectionChanged.emit(selected_item)
            else:
                 self.logger.debug(f"Selection changed, but item is not a QGraphicsPathItem: {type(selected_item)}")
                 self.selectionChanged.emit(None)

        elif not selected_items:
            # Emit None if selection is cleared
            self.logger.debug("Selection cleared, emitting None.")
            self.selectionChanged.emit(None)

        if self._rubber_band and self._rubber_band.isVisible():
            self._rubber_band.hide()
            band_rect = self._rubber_band.geometry()
            # Map band rect from view coords to scene
            scene_rect = self.views()[0].mapToScene(band_rect).boundingRect()
            self._marquee_selection = [item for item in self.items(scene_rect) if isinstance(item, VertexItem)]
            for v in self._marquee_selection:
                v.setPen(v.pen().color().lighter())
            return

    # --- Polyline Drawing Helpers ---

    def _add_vertex_marker(self, pos: QPointF):
        """Adds a visual marker for a vertex."""
        radius = self._vertex_radius
        # Adjust position to center the ellipse on the point
        ellipse = QGraphicsEllipseItem(pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)
        ellipse.setPen(self._vertex_pen)
        ellipse.setBrush(self._vertex_brush)
        # Ensure the marker **does not** intercept mouse events – otherwise the
        # 2nd click of a double-click lands on the marker and the scene never
        # receives the `mouseDoubleClickEvent`, leaving drawing stuck in
        # "add-vertex" mode.  Disabling mouse buttons on the marker lets the
        # event propagate to the scene where the polyline is finalized.
        ellipse.setAcceptedMouseButtons(Qt.NoButton)
        ellipse.setFlag(QGraphicsItem.ItemIsSelectable, False)
        ellipse.setFlag(QGraphicsItem.ItemIsMovable, False)
        ellipse.setZValue(10) # Ensure vertices are drawn above lines/background
        self.addItem(ellipse)
        self._current_vertices_items.append(ellipse)

    def _update_temporary_line(self, current_pos: QPointF):
        """Updates the rubber-band line from the last vertex to the current mouse position."""
        if not self._current_polyline_points:
            return

        last_point = self._current_polyline_points[-1]
        # Suppress Ruff F841 by using underscore for unused assignment (no side effects)
        _ = self._constrained_pos(current_pos, Qt.NoModifier)  # noqa: F841

        # Use the already constrained position from mouseMoveEvent
        pos_to_draw_to = current_pos # Use the position passed in (already constrained)

        if self._temporary_line_item:
            # Update existing line
            self._temporary_line_item.setLine(QLineF(last_point, pos_to_draw_to))
        else:
            # Create new line
            self._temporary_line_item = QGraphicsLineItem(QLineF(last_point, pos_to_draw_to))
            self._temporary_line_item.setPen(self._rubber_band_pen)
            self._temporary_line_item.setZValue(5) # Draw rubber band above background but below vertices
            self.addItem(self._temporary_line_item)

    def _finalize_current_polyline(self, layer_name: str):
        """Finalizes the current polyline, creates a QGraphicsPathItem, and resets state."""
        if len(self._current_polyline_points) < 2:
            self._cancel_current_polyline()
            return

        # ------------------------------------------------------------------
        # Prepare two parallel point lists:
        #   • scene_points – original *scene-pixel* coordinates for on-screen
        #     drawing (QGraphicsScene expects these units).
        #   • world_points – converted coordinates in *project* world units
        #     stored as metadata for downstream calculations.
        # ------------------------------------------------------------------

        scene_points: list[QPointF] = list(self._current_polyline_points)  # draw with these
        world_points: list[QPointF] = [QPointF(*self._scene_to_world(p)) for p in scene_points]  # meta only

        # --- Determine initial pen and layer_id for the PolylineItem ---
        layer_color_hex = self._get_layer_color_from_project(layer_name)
        initial_pen: QPen
        default_pen_width = self._finalized_polyline_pen.widthF() if self._finalized_polyline_pen else 2.0

        if layer_color_hex:
            color = QColor(layer_color_hex)
            if color.isValid():
                initial_pen = QPen(color, default_pen_width)
            else:
                self.logger.warning(f"Invalid color '{layer_color_hex}' for layer '{layer_name}'. Using default pen.")
                initial_pen = QPen(self._finalized_polyline_pen.color(), default_pen_width) # Use default color, custom width
        else:
            self.logger.debug(f"No color defined for layer '{layer_name}'. Using default pen.")
            initial_pen = QPen(self._finalized_polyline_pen.color(), default_pen_width) # Use default color, custom width
        # --- End Determine initial pen ---

        poly_item = PolylineItem(
            points=scene_points,
            layer_pen=initial_pen,  # Pass the determined pen
            mode="interpolated" if getattr(self, "_current_mode", False) else "entered",
            layer_id=layer_name  # Pass the layer_name as layer_id
        )

        # NEW: Store strata-contour metadata ---------------------------------------
        poly_item.setData(Qt.UserRole + 4, self._strata_contour_mode)
        poly_item.setData(Qt.UserRole + 5, self._current_material_id)
        # -------------------------------------------------------------------------

        # Make selectable & movable similar to previous behaviour
        poly_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        poly_item.setFlag(QGraphicsItem.ItemIsMovable, True)
        poly_item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        poly_item.setZValue(1)

        # --- Store metadata on the item ---
        poly_item.setData(Qt.UserRole + 1, layer_name)
        # Store *world* coordinates for downstream processing
        points_data = [(p.x(), p.y()) for p in world_points]
        poly_item.setData(Qt.UserRole + 2, points_data)
        # --- END Store ---

        # Connect vertex double-clicks to elevation editor
        poly_item.vertexDoubleClicked.connect(lambda _poly, vtx: self._edit_vertex_elevation(vtx))

        # Directly add the item – do NOT push onto the global undo stack so that
        # Ctrl+Z does not remove an entire newly-drawn polyline.  Full-line
        # deletion remains available via the Delete key / context menu.
        if poly_item not in self.items():
            self.addItem(poly_item)

        # Track as the currently selected polyline
        self._selected_polyline = poly_item

        # --- Apply Z-values to poly_item BEFORE emitting the signal ---
        # Point-prompt mode: apply Z-values collected during point clicks
        if self._elev_mode == "point" and self._current_z_values:
            verts = poly_item.vertices()
            if len(verts) != len(self._current_z_values):
                self.logger.warning(
                    "Vertex/Z-list length mismatch in point-prompt mode (%d vs %d). "
                    "Falling back to previous prompt behaviour.",
                    len(verts),
                    len(self._current_z_values),
                )
                # Fallback: trigger the standard elevation workflow if point mode pre-collection failed
                try:
                    self._apply_elevation_workflow(poly_item)
                except Exception as exc:
                    self.logger.error(f"Fallback elevation workflow failed: {exc}", exc_info=True)
            else:
                main_win = self.parent_view.window() if self.parent_view else None
                undo_stack = getattr(main_win, "undoStack", None) if main_win else None
                for v, z_val in zip(verts, self._current_z_values):
                    if z_val is None: # User might have cancelled for a specific point
                        continue
                    if undo_stack:
                        undo_stack.push(EditVertexZCommand(v, z_val))
                    else:
                        v.set_z(z_val)
        # Elevation workflow for modes other than *point* (e.g., interpolate, line)
        # or if point mode Z value pre-collection was not applicable/failed
        elif self._elev_mode != "point": # Catches other modes, or if point mode didn't run above
            try:
                self._apply_elevation_workflow(poly_item)
            except Exception as exc:
                self.logger.error(f"Elevation workflow failed: {exc}", exc_info=True)
        # --- END Apply Z-values ---

        self.logger.info(
            f"Finalized polyline with {len(self._current_polyline_points)} points on layer '{layer_name}'."
        )

        # --- Prepare 3D world points for the signal ---
        scene_3d_points = poly_item.get_vertices_scene_3d() # List[Tuple[float, float, float]]
        world_3d_points = []
        for sx, sy, sz in scene_3d_points:
            # Convert scene X,Y to world X,Y; keep Z as is (already world Z from elevation workflow)
            world_x, world_y = self._scene_to_world(QPointF(sx, sy))
            world_3d_points.append((world_x, world_y, sz))
        # --- END Prepare 3D world points ---

        # Emit finalized signal with 3D *world* coordinates and the item
        self.polyline_finalized.emit(world_3d_points, poly_item)

        # --- Emit padDrawn if polyline belongs to "pads" layer and is closed ---
        # This uses the original 2D world_points for its contract.
        try:
            pad_points_2d = [(p.x(), p.y()) for p in world_points] # world_points is original 2D list
            if layer_name.lower() == "pads" and self._path_is_closed(pad_points_2d):
                self.logger.debug("padDrawn emitted for closed pad on 'pads' layer with %d vertices", len(pad_points_2d))
                self.padDrawn.emit(pad_points_2d)
        except Exception as e:
            self.logger.error(f"Failed to evaluate/emit padDrawn: {e}", exc_info=True)
        # --- END Emit padDrawn ---

        self._reset_drawing_state()

    def _cancel_current_polyline(self):
        """Cancels the current polyline drawing."""
        self.logger.debug("Cancelling current polyline.")
        self._reset_drawing_state()

    def _undo_last_vertex(self):
        """Removes the last added vertex and its marker."""
        if len(self._current_polyline_points) > 1 and self._current_vertices_items:
            removed_point = self._current_polyline_points.pop()
            removed_marker = self._current_vertices_items.pop()
            if removed_marker in self.items():
                self.removeItem(removed_marker)
            self.logger.debug(f"Undid last vertex at: {removed_point.x():.2f}, {removed_point.y():.2f}")
            # Update the temporary line to the new last point
            if self._current_polyline_points:
                 # Need current mouse pos - tricky. Get from view? Or just remove temp line?
                 # For now, just remove it until next mouse move.
                 if self._temporary_line_item:
                     if self._temporary_line_item in self.items():
                         self.removeItem(self._temporary_line_item)
                     self._temporary_line_item = None
            else:
                 # If only one point was left after undo, cancel drawing
                 self._cancel_current_polyline()

        elif len(self._current_polyline_points) == 1:
             # If only the starting point remains, cancel the whole line
             self._cancel_current_polyline()

    def _reset_drawing_state(self):
        """Resets all temporary items and flags related to the current drawing operation."""
        # Remove temporary line
        if self._temporary_line_item and self._temporary_line_item in self.items():
            self.removeItem(self._temporary_line_item)
        self._temporary_line_item = None

        # Remove vertex markers
        for item in self._current_vertices_items:
            if item in self.items():
                self.removeItem(item)
        self._current_vertices_items.clear()

        # Reset state variables
        self._is_drawing = False
        self._current_polyline_points = []
        # Don't disable tracing mode here, only reset the current polyline state

        # Also clear cached elevations list
        self._current_z_values = []

        # ------------------------------------------------------------------
        # End of _reset_drawing_state
        # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Scale-calibration overlay helpers (inside TracingScene)
    # ------------------------------------------------------------------
    def _update_noscale_overlay(self) -> None:
        """Create, remove, or reposition the translucent banner as needed."""
        project_scale = getattr(self.panel, "current_project", None)
        project_scale = getattr(project_scale, "scale", None) if project_scale else None

        have_scale = project_scale is not None

        # In headless CI test runs, still create the overlay (tests assert its
        # presence) but ensure it does not intercept mouse events.

        # Show banner when *no* scale is set
        if not have_scale:
            if self._noscale_item is None:
                txt = QGraphicsSimpleTextItem(self._NOSCALE_TEXT)
                txt.setBrush(self._NOSCALE_COLOR)
                txt.setZValue(self._NOSCALE_Z)
                txt.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
                # Ensure the overlay banner does **not** intercept mouse clicks which
                # would otherwise block the sceneʼs own mousePressEvent and prevent
                # warning dialogs from being triggered in headless tests.
                txt.setAcceptedMouseButtons(Qt.NoButton)
                txt.setFlag(QGraphicsItem.ItemIsSelectable, False)
                self.addItem(txt)
                self._noscale_item = txt

            # Anchor top-left with margin inside current scene rect
            self._noscale_item.setPos(self.sceneRect().topLeft() + QPointF(6, 6))
        else:
            # Remove if exists
            if self._noscale_item and self._noscale_item.scene() is self:
                try:
                    self.removeItem(self._noscale_item)
                except RuntimeError:
                    pass
            self._noscale_item = None

        # Maintain legacy attribute for tests referencing _scale_overlay
        self._scale_overlay = self._noscale_item  # type: ignore[assignment]

    # ------------------------------------------------------------------
    def on_scale_calibrated(self) -> None:
        """Called by MainWindow when the user finishes scale calibration."""
        self._update_noscale_overlay()

    # ------------------------------------------------------------------
    # Public helpers (cache invalidation & scale warning)
    # ------------------------------------------------------------------
    def invalidate_cache(self) -> None:
        """Invalidate any cached data, like spline samples, upon geometry change."""
        for item in self.items():
            if isinstance(item, PolylineItem):
                item.invalidate_sample_cache()
        self.logger.debug("Polyline sample caches invalidated.")

    def _show_scale_warning(self) -> None:
        """Show a non-modal warning that tracing requires a valid scale.
        This method is designed to be monkeypatched in tests to prevent UI popups.
        """
        # Record flag *before* possibly short-circuiting for headless tests.
        self._scale_warn_shown = True

        if os.getenv("PYTEST_CURRENT_TEST"):
            return

        try:
            parent = self.parent_view # self.views()[0] if self.views() else None
            # Use a more informative message
            QMessageBox.information(
                parent, # Parent widget
                "Scale Required for Tracing",
                "The project scale has not been set or is invalid. "
                "Please calibrate the scale using 'Tracing > Calibrate Scale...' "
                "or by clicking the scale indicator in the status bar before you can trace.",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            # Log minimally if dialog fails, but don't spam during normal operation
            logging.getLogger(__name__).error(f"Failed to show scale warning dialog: {e}", exc_info=False)

    def _apply_elevation_workflow(self, poly_item: PolylineItem) -> None:
        """Run the elevation-prompt workflow for *poly_item* based on *self._elev_mode*."""
        vertices = poly_item.vertices()
        if not vertices:
            return

        mode = self._elev_mode
        main_win = self.parent_view.window() if self.parent_view else None
        undo_stack = getattr(main_win, "undoStack", None) if main_win else None

        # ---------------- Point mode ----------------
        if mode == "point":
            if not undo_stack:
                self.logger.warning(
                    "Undo stack unavailable – point-mode elevations will be applied directly.",
                )
            last_z_val: float | None = None
            for v in vertices:
                # Default to the previous entered elevation when available.
                initial = last_z_val if last_z_val is not None else v.z()
                z, ok = self._ask_vertex_z(initial_z=initial)
                if not ok:
                    # Keep previous value (unchanged)
                    continue
                last_z_val = z  # Remember for next vertex
                if undo_stack:
                    undo_stack.push(EditVertexZCommand(v, z))
                else:
                    v.set_z(z)

        # -------------- Interpolate mode -------------
        elif mode == "interpolate":
            # Prompt first vertex
            z0, ok0 = self._ask_vertex_z(vertices[0].z())
            if not ok0:
                return
            # Prompt last vertex
            z1, ok1 = self._ask_vertex_z(vertices[-1].z())
            if not ok1:
                return

            if undo_stack:
                undo_stack.push(EditVertexZCommand(vertices[0], z0))
                undo_stack.push(EditVertexZCommand(vertices[-1], z1))
                undo_stack.push(InterpolateSegmentZCommand(vertices))
            else:
                vertices[0].set_z(z0)
                vertices[-1].set_z(z1)
                InterpolateSegmentZCommand(vertices).redo()

        # ---------------- Line mode ------------------
        elif mode == "line":
            z, ok = self._ask_uniform_z()
            if not ok:
                return
            if undo_stack:
                undo_stack.push(SetPolylineUniformZCommand(poly_item, z))
            else:
                SetPolylineUniformZCommand(poly_item, z).redo()

    def _ask_vertex_z(self, initial_z: float = 0.0) -> tuple[float, bool]:
        """Prompt the user for a single-vertex elevation and return (value, accepted)."""
        parent_widget = self.views()[0] if self.views() else None
        dlg = ElevationDialog(parent_widget, initial_value=initial_z)
        if dlg.exec():
            return dlg.value(), True
        return initial_z, False

    def _ask_uniform_z(self) -> tuple[float, bool]:
        """Prompt for uniform Z for all vertices in current polyline."""
        # This could also be a custom dialog; using QInputDialog for simplicity.
        z_val, ok = QInputDialog.getDouble(
            self.parent_view, # Parent to the view
            "Set Uniform Elevation",
            "Enter elevation (Z value):",
            0.0,  # Default value
            -1_000_000,  # Min value
            1_000_000,  # Max value
            3,    # Decimals
        )
        return z_val, ok

    def set_elevation_mode(self, mode: str) -> None:
        """Set the elevation entry mode."""
        self._elev_mode = mode
        self._prompt_mode = mode # Keep alias updated
        self._settings.set_tracing_elev_mode(mode)

    # ------------------------------------------------------------------
    # Scale validation helper (inside class)
    # ------------------------------------------------------------------
    def _scale_invalid(self, proj_arg) -> bool:
        """Check if the project's scale is currently invalid for tracing.
        Returns True if invalid, False if valid.
        Also updates the visual no-scale overlay and shows a warning if invalid.
        """
        scale_is_actually_invalid = True
        if proj_arg and proj_arg.scale:
            if (proj_arg.scale.world_per_paper_in is not None and
                proj_arg.scale.world_per_paper_in > 0 and
                proj_arg.scale.render_dpi_at_cal > 0):
                scale_is_actually_invalid = False
        
        if scale_is_actually_invalid:
            # Only show the pop-up warning if it hasn't been shown before for this session or if scale became invalid again.
            self._show_scale_warning()
        
        # Always update the visual overlay to reflect the current scale status.
        self._update_noscale_overlay()
        
        return scale_is_actually_invalid

    # ------------------------------------------------------------------
    # Compatibility aliases for new API expected by MainWindow
    # ------------------------------------------------------------------
    def set_tracing_enabled(self, flag: bool):
        """Enable/disable tracing globally at runtime (no persistence).

        When *flag* is True, verify that the project has a valid scale; if not,
        immediately show the same modal warning used during mouse clicks and
        keep tracing disabled.  This helps tests (and real users) discover the
        invalid-scale state even when no vertex is yet added.
        """
        enable = bool(flag)

        # Early scale validation when turning *on* tracing
        if enable:
            proj_to_check = self.project
            if self._scale_invalid(proj_to_check):
                pass # self._show_scale_warning() # No longer needed here

        self._tracing_enabled = enable

    def set_prompt_mode(self, mode: str):
        """Alias to :py:meth:`set_elevation_mode` for API compatibility."""
        self.set_elevation_mode(mode)

    # --- Loading / Saving / Layer Management ---

    def clear_finalized_polylines(self):
        """Removes all finalized QGraphicsPathItems from the scene."""
        items_to_remove = [item for item in self.items() if isinstance(item, QGraphicsPathItem)]
        for item in items_to_remove:
            self.removeItem(item)
        self.logger.info("Cleared all finalized polylines.")

    def load_polylines_with_layers(self, polylines_by_layer: Dict[str, Sequence[PolylineData]]):
        """Loads polylines from a dictionary structure, creating QGraphicsPathItems
        and assigning layer information.

        Args:
            polylines_by_layer (Dict[str, Sequence[PolylineData]]):
                A dictionary where keys are layer names and values are sequences of
                polyline data (e.g., lists of point tuples or dicts).

        Example:
                {
                    "Existing": [ [(10, 10), (50, 10)], [(20, 30), (60, 30)] ],
                    "Proposed": [ [(15, 45), (55, 45), (55, 65)] ]
                }
                PolylineData format assumes a list/tuple of (x, y) tuples/lists.

        """
        self.clear_finalized_polylines() # Clear existing before loading

        for layer_name, polylines in polylines_by_layer.items():
            self.logger.debug(f"Loading {len(polylines)} polylines for layer '{layer_name}'")
            for poly_data in polylines:
                if not poly_data or len(poly_data) < 2:
                    self.logger.warning(f"Skipping invalid polyline data for layer '{layer_name}': {poly_data}")
                    continue

                try:
                    path = QPainterPath()
                    start_point = QPointF(poly_data[0][0], poly_data[0][1])
                    path.moveTo(start_point)
                    for point_data in poly_data[1:]:
                        path.lineTo(QPointF(point_data[0], point_data[1]))

                    polyline_item = QGraphicsPathItem(path)
                    polyline_item.setPen(self._finalized_polyline_pen)
                    polyline_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                    polyline_item.setFlag(QGraphicsItem.ItemIsMovable, True)
                    polyline_item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
                    polyline_item.setZValue(1)

                    # Store layer name and original points
                    polyline_item.setData(Qt.UserRole + 1, layer_name)
                    # Re-store points data as list of tuples
                    points_data = [(p[0], p[1]) for p in poly_data]
                    polyline_item.setData(Qt.UserRole + 2, points_data)

                    self.addItem(polyline_item)
                except (TypeError, IndexError, ValueError) as e:
                    self.logger.error(f"Error processing polyline data for layer '{layer_name}': {poly_data}. Error: {e}")

        self.logger.info(f"Finished loading polylines for {len(polylines_by_layer)} layers.")
        # Update scene rect after loading all items
        self.setSceneRect(self.itemsBoundingRect())
        self.pageRectChanged.emit() # Emit signal after loading

    def dump_scene_state(self) -> LayerPolylineDict:
        """Serializes all finalized PolylineItems into a dictionary by layer.
        This is for saving the project state.
        Returns:
            LayerPolylineDict: A dictionary where keys are layer names (str) and
                               values are lists of polylines. Each polyline is a
                               list of (x, y, z) tuples.
        """
        state: LayerPolylineDict = {}
        for item in self.items():
            if isinstance(item, PolylineItem) and item.is_finalized():
                layer_name = item.layer_name
                # Ensure points are in world coordinates with Z values
                # PolylineItem.points_3d() should provide this directly.
                points_3d = item.points_3d() # This should be List[Tuple[float,float,float]]
                # Convert to simple list of tuples for serialization if not already
                # Assuming points_3d() already returns the correct serializable format
                if layer_name not in state:
                    state[layer_name] = []
                state[layer_name].append(points_3d) # Add the list of 3D points
        self.logger.debug(f"Dumped scene state with {sum(len(v) for v in state.values())} polylines across {len(state)} layers.")
        return state

    def setLayerVisible(self, layer_name: str, visible: bool) -> None: # noqa: N802
        """Sets the visibility of all polyline items associated with a layer."""
        count = 0
        for item in self.items():
            if isinstance(item, QGraphicsPathItem):
                item_layer = item.data(Qt.UserRole + 1)
                if item_layer == layer_name:
                    item.setVisible(visible)
                    count += 1
        self.logger.debug(f"Set visibility for {count} items on layer '{layer_name}' to {visible}.")

    # --- Debugging ---
    def dump_scene_state(self):
        """Logs the current state of items in the scene for debugging."""
        self.logger.debug(f"Tracing Enabled: {self._tracing_enabled}")
        self.logger.debug(f"Is Drawing: {self._is_drawing}")
        self.logger.debug(f"Current Points: {len(self._current_polyline_points)}")
        if self._background_items:
            self.logger.debug(f"Background Item: {self._background_items[0].boundingRect()}")
        else:
            self.logger.debug("Background Item: None")
        self.logger.debug(f"Item Count: {len(self.items())}")

    # --- Helper to get current selected polyline ---
    def current_polyline(self):
        """Return the currently selected QGraphicsPathItem (polyline), if any."""
        sel = [itm for itm in self.selectedItems() if isinstance(itm, QGraphicsPathItem)]
        return sel[0] if sel else None

    def current_polyline_points(self) -> list[tuple[float, float]]:
        """Return the 2-D points of the currently selected polyline."""
        item = self.current_polyline()
        if not item:
            return []
        path: QPainterPath = item.path()
        return [(path.elementAt(i).x, path.elementAt(i).y) for i in range(path.elementCount())]

    def add_offset_breakline(self, pts3d: list[tuple[float, float, float]], *, push_to_undo: bool = True):
        """Add a 3-D aware offset breakline to the scene.

        If *push_to_undo* is True (default), an AddPolylineCommand is pushed onto the
        application's undo stack.  When False, the caller is responsible for
        managing undo/redo behaviour.  The created QGraphicsPathItem is returned
        in all cases.
        """
        if not pts3d or len(pts3d) < 2:
            self.logger.warning("add_offset_breakline called with insufficient points.")
            return None

        # Create a 2-D path (ignore z for screen representation)
        path = QPainterPath()
        path.moveTo(QPointF(pts3d[0][0], pts3d[0][1]))
        for x, y, _ in pts3d[1:]:
            path.lineTo(QPointF(x, y))

        item = QGraphicsPathItem(path)
        # Use dashed magenta pen to visually distinguish offset lines
        pen = self._finalized_polyline_pen
        pen.setStyle(Qt.DashLine)
        pen.setColor(Qt.magenta)
        item.setPen(pen)
        item.setZValue(1)
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        # Store layer and both 2D & 3D pts
        item.setData(Qt.UserRole + 1, "Offsets")
        item.setData(Qt.UserRole + 2, [(x, y) for x, y, *_ in pts3d])
        item.setData(Qt.UserRole + 3, pts3d)  # Full 3-D points

        main_win = self.parent_view.window() if self.parent_view else None
        if push_to_undo and main_win and hasattr(main_win, "undoStack"):
            cmd = AddPolylineCommand(self, item)
            main_win.undoStack.push(cmd)
        elif item not in self.items():
            self.addItem(item)

        return item

    # ------------------------------------------------------------------
    def _edit_vertex_elevation(self, vertex):
        """Prompt the user to edit *vertex* elevation and push undo command."""
        parent_widget = self.views()[0] if self.views() else None
        dlg = ElevationDialog(parent_widget, initial_value=vertex.z())
        if dlg.exec():
            new_z = dlg.value()
            if abs(new_z - vertex.z()) < 1e-6:
                return  # No effective change
            main_win = parent_widget.window() if parent_widget else None
            if main_win and hasattr(main_win, "undoStack"):
                main_win.undoStack.push(EditVertexZCommand(vertex, new_z))
            else:
                vertex.set_z(new_z)
            # Future: trigger surface rebuild if necessary
        # Dialog cancelled – nothing to do

    # ------------------------------------------------------------------
    # Qt context-menu override – add Toggle Smooth action
    # ------------------------------------------------------------------
    def contextMenuEvent(self, ev):
        """Custom context menu for polylines and vertices."""
        if self._marquee_selection:
            menu = QMenu()
            bulk = QAction("Bulk Z offset…", menu)

            def _bulk():
                dz, ok = QInputDialog.getDouble(self.views()[0], "Bulk Z offset", "Δ feet:", 0.0, decimals=3)
                if ok and abs(dz) > 1e-9:
                    from digcalc_project.src.ui.commands.bulk_offset_z_command import (
                        BulkOffsetZCommand,
                    )
                    main_win = self.views()[0].window()
                    if hasattr(main_win, "undoStack"):
                        main_win.undoStack.push(BulkOffsetZCommand(self._marquee_selection, dz))
                    self._marquee_selection = []

            bulk.triggered.connect(_bulk)
            menu.addAction(bulk)
            menu.exec(ev.screenPos())
            return None

        item = self.itemAt(ev.scenePos(), self.views()[0].transform()) if self.views() else None
        if not item:
            return super().contextMenuEvent(ev)

        menu = QMenu()
        selected_action = None
        if isinstance(item, PolylineItem):
            selected_action = menu.addAction("Toggle Smooth")

        chosen = menu.exec(ev.screenPos())
        if chosen and chosen == selected_action and isinstance(item, PolylineItem):
            main_win = self.parent_view.window() if self.parent_view else None
            if main_win and hasattr(main_win, "undoStack"):
                main_win.undoStack.push(ToggleSmoothCommand(item))
            else:
                # Fallback – direct toggle without undo stack (shouldn't occur in production)
                item.toggle_mode()
            ev.accept()
            return None

        # Default handling for other cases
        super().contextMenuEvent(ev)

    # --- NEW: Public helper to trigger scene refresh ----------------
    def invalidate_cache(self):
        """Trigger a redraw / overlay refresh after scale updates."""
        try:
            self._update_noscale_overlay()
        except Exception:
            pass
        self.update()

    # ------------------------------------------------------------------
    def _show_scale_warning(self):
        """Show non-blocking scale warning, safe for headless tests."""
        if os.getenv("PYTEST_CURRENT_TEST"):
            return
        try:
            msg = QMessageBox(
                QMessageBox.Icon.Warning,
                "Scale Required",
                "Tracing is disabled until a valid scale is set.\n"
                "Choose Tracing ▸ Calibrate Scale… or click the green scale pill.",
                QMessageBox.StandardButton.Ok,
                self.views()[0] if self.views() else None,
            )
            msg.setModal(False)
            msg.show()
        except Exception as e:
            # Log minimally, e.g., if no views are available
            logging.getLogger(__name__).warning(f"Failed to show scale warning dialog: {e}", exc_info=False)

    # ------------------------------------------------------------------
    # Layer-colour propagation
    # ------------------------------------------------------------------
    def refresh_layer_item(self, layer_id: str, target_item: Optional[PolylineItem] = None):
        """Repaint all scene items belonging to *layer_id* (polyline & vertices).

        If target_item is provided, only that item is refreshed if its layer_id matches.
        Otherwise, all items on the layer are refreshed.
        """
        items_refreshed_count = 0

        if target_item is not None:
            item_layer_id = getattr(target_item, "layer_id", None)
            if item_layer_id == layer_id:
                colour_hex = self._get_layer_color_from_project(layer_id)
                if colour_hex:
                    target_item.update_color(colour_hex)
                    items_refreshed_count += 1
                else:
                    pass
            else:
                pass
        else:
            # Original behavior: iterate all items if no specific target_item
            for item in self.items():
                if isinstance(item, PolylineItem):
                    item_layer_id = getattr(item, "layer_id", None)
                    if item_layer_id == layer_id:
                        colour_hex = self._get_layer_color_from_project(layer_id)
                        if colour_hex:
                            item.update_color(colour_hex)
                            items_refreshed_count += 1
                        else:
                            pass

        if items_refreshed_count == 0:
            if target_item is None:
                self.logger.warning(f"TracingScene.refresh_layer_item: No items found for layer_id {layer_id}")
        else:
            pass
        
        self.update()

    def _get_layer_color_from_project(self, layer_id: str) -> Optional[str]:
        """Helper to retrieve the color for a given layer_id from the current project."""
        # This internal helper consolidates the color retrieval logic
        colour_hex = None
        proj = None # Initialize to None
        try:
            # Try to get project from self.project first, then from panel
            proj = getattr(self, "project", None) 
            if proj is None:
                proj = getattr(self.panel, "current_project", None)
            
            if proj:
                # proj.layers is a list of Layer objects
                if hasattr(proj, 'layers') and isinstance(proj.layers, list):
                    pass # No specific logging needed here for normal operation
                
                lyr = proj.get_layer(layer_id) # This uses project.get_layer(layer_id)
                if lyr and hasattr(lyr, 'line_color'):
                    colour_hex = lyr.line_color
                elif lyr:
                    self.logger.warning(f"      [TracingScene._get_layer_color] Layer '{layer_id}' found (id: {id(lyr)}), but has no 'line_color' attribute or it's None. Layer object: {lyr}")
                else:
                    # Log available layer IDs if layer is not found
                    available_layer_ids = [layer.id for layer in proj.layers if hasattr(layer, 'id')] if hasattr(proj, 'layers') and isinstance(proj.layers, list) else []
                    self.logger.warning(f"      [TracingScene._get_layer_color] Layer with id '{layer_id}' NOT FOUND in project (Project ID: {id(proj)}). Available layer IDs: {available_layer_ids}")
            else:
                self.logger.error("      [TracingScene._get_layer_color] Project object (proj) is None or not found.")
        except AttributeError as ae:
            self.logger.error(f"AttributeError in _get_layer_color_from_project for layer {layer_id}: {ae}", exc_info=False) # Keep log lean
        except Exception as e:
            self.logger.error(f"Error retrieving color for layer {layer_id} in _get_layer_color_from_project: {e}", exc_info=False) # Keep log lean
        return colour_hex

    # ------------------------------------------------------------------
    # Hover tooltips for boreholes
    # ------------------------------------------------------------------
    def hoverMoveEvent(self, event):  # type: ignore[override]
        super().hoverMoveEvent(event)
        item = self.itemAt(event.scenePos(), self.views()[0].transform()) if self.views() else None
        if item and item.data(0):
            bh = item.data(0)
            try:
                from digcalc_project.src.models.strata_models import BoreholeLog
                if isinstance(bh, BoreholeLog):
                    lines = [f"BH-{bh.id:02d}"]
                    for ld in bh.layers:
                        mat_name = self.panel.current_project.strata.materials[ld.material_id-1].name if getattr(self.panel.current_project,'strata',None) else "Mat"
                        lines.append(f"{mat_name} {ld.top_z:.0f}–{ld.bottom_z:.0f} ft")
                    QToolTip.showText(event.screenPos(), "\n".join(lines))
                    return
            except Exception:
                pass
        QToolTip.hideText()

    # ------------------------------------------------------------------
    # Strata-Contour helpers
    # ------------------------------------------------------------------
    def set_strata_contour_mode(self, enabled: bool) -> None:
        """Enable or disable *strata-contour* drawing mode."""
        self._strata_contour_mode = bool(enabled)
        self.logger.debug("Strata-Contour mode set to %s", enabled)

    def strata_contour_mode(self) -> bool:
        """Return the current strata-contour mode flag."""
        return self._strata_contour_mode

    def set_current_material_id(self, mat_id: Optional[int]) -> None:
        """Set the *current* material ID used when strata-contour mode is active."""
        self._current_material_id = mat_id
        self.logger.debug("Current material id set to %s", mat_id)

    def current_material_id(self) -> Optional[int]:
        """Return the currently selected material ID (may be *None*)."""
        return self._current_material_id

# ------------------------------------------------------------------
# Undo/Redo Command
# ------------------------------------------------------------------

class AddPolylineCommand(QUndoCommand):
    """QUndoCommand to add/remove a polyline item from the scene."""

    def __init__(self, scene: TracingScene, item_or_pts, layer: str | None = None):
        super().__init__("Add Polyline")
        self._scene = scene
        if isinstance(item_or_pts, QGraphicsPathItem):
            self._item = item_or_pts
        else:
            # Assume iterable of (x,y,?) tuples – create path (ignore z)
            from PySide6.QtCore import QPointF
            path = QPainterPath()
            pts = list(item_or_pts)
            if not pts:
                raise ValueError("No points supplied for AddPolylineCommand")
            path.moveTo(QPointF(pts[0][0], pts[0][1]))
            for x, y, *_ in pts[1:]:
                path.lineTo(QPointF(x, y))
            self._item = QGraphicsPathItem(path)
            pen = QPen(Qt.magenta, 1, Qt.DashLine)
            self._item.setPen(pen)
            self._item.setZValue(1)
            # Store metadata
            self._item.setData(Qt.UserRole + 1, layer or "Offsets")
            self._item.setData(Qt.UserRole + 2, [(x, y) for x, y, *_ in pts])
            self._item.setData(Qt.UserRole + 3, pts)

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------

    def redo(self):
        if self._item not in self._scene.items():
            self._scene.addItem(self._item)

    def undo(self):
        if self._item in self._scene.items():
            self._scene.removeItem(self._item)

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _path_is_closed(pts: list[tuple[float, float]], tol: float = 1e-6) -> bool:
        """Return True if path is closed (first & last vertices coincide within *tol*)."""
        return len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < tol and abs(pts[0][1] - pts[-1][1]) < tol

class SetPadElevationCommand(QUndoCommand):
    """QUndoCommand to add/remove a *pad* polyline (closed polygon) with constant elevation."""

    def __init__(self, scene: TracingScene, pts3d: list[tuple[float, float, float]]):
        super().__init__("Add Pad")
        if not pts3d or len(pts3d) < 3:
            raise ValueError("Pad requires at least 3 vertices.")
        self._scene = scene
        self._pts3d = pts3d
        self._item: Optional[QGraphicsPathItem] = None

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------
    def redo(self):
        # Build the graphics item on first redo
        if self._item is None:
            path = QPainterPath()
            path.moveTo(QPointF(self._pts3d[0][0], self._pts3d[0][1]))
            for x, y, *_ in self._pts3d[1:]:
                path.lineTo(QPointF(x, y))
            # Close the path visually
            path.closeSubpath()

            self._item = QGraphicsPathItem(path)
            pen = QPen(QColor("orange"), 3)
            self._item.setPen(pen)
            self._item.setZValue(1)
            self._item.setFlag(QGraphicsItem.ItemIsSelectable, True)

            # Store metadata
            self._item.setData(Qt.UserRole + 1, "Pads")
            self._item.setData(Qt.UserRole + 2, [(x, y) for x, y, *_ in self._pts3d])
            self._item.setData(Qt.UserRole + 3, self._pts3d)  # 3-D vertices

        if self._item not in self._scene.items():
            self._scene.addItem(self._item)

    def undo(self):
        if self._item and self._item in self._scene.items():
            self._scene.removeItem(self._item)

    # --------------------------------------------------------------
    # Generic event filter to intercept vertex-item double-clicks
    # --------------------------------------------------------------
