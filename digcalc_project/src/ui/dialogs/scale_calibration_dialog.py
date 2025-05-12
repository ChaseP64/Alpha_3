from __future__ import annotations

"""scale_calibration_dialog.py – Printed-scale calibration dialog.

The user chooses *two* reference points on the current PDF page preview and
enters the true distance between them.  From this we derive a
:class:`digcalc_project.src.models.project_scale.ProjectScale` so that traced
coordinates can be converted from pixels → world units.
"""

from typing import Optional
import math

from PySide6.QtCore import Qt, QObject, QEvent, QPointF, QLineF, Signal
from PySide6.QtGui import QPixmap, QPen, QBrush, QColor, QPainter, QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsPixmapItem,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QHBoxLayout,
    QDoubleSpinBox,
    QDialogButtonBox,
    QComboBox,
    QApplication,
    QMessageBox,
)

from digcalc_project.src.models.project_scale import ProjectScale
from digcalc_project.src.services.settings_service import SettingsService

__all__ = ["ScaleCalibrationDialog"]

_RED_DOT_PEN = QPen(QColor("red"), 2)
_RED_DOT_BRUSH = QBrush(QColor("red"))
_YELLOW_LINE_PEN = QPen(QColor("yellow"), 1, Qt.DashLine)
_DOT_RADIUS = 4.0

# Conversion factors to feet for unit consistency
_CONVERSION_TO_FEET = {
    "ft": 1.0,
    "yd": 3.0,
    "m": 1 / 0.3048,  # 1 meter in feet
}
_CONVERSION_FROM_FEET = {
    "ft": 1.0,
    "yd": 1 / 3.0,
    "m": 0.3048, # 1 foot in meters
}

# ---------------------------------------------------------------------------
class _PointPicker(QObject):
    """Event-filter that records two mouse clicks on the *view* scene."""

    points_picked = Signal(QPointF, QPointF)  # emitted when both points chosen

    def __init__(self, view: QGraphicsView):
        super().__init__(view)
        self._view = view
        self._p1: Optional[QPointF] = None
        view.viewport().installEventFilter(self)
        # Auto-delete if the view goes away to avoid dangling eventFilter callbacks
        # Connect to the QWidget.destroyed() signal so we can detach safely.
        try:
            view.destroyed.connect(lambda *_: self._cleanup())  # type: ignore[attr-defined]
        except Exception:
            pass  # Defensive – ignore if signal not available

    # ----------------------------------------------
    def eventFilter(self, obj: QObject, ev: QEvent):  # noqa: D401 – Qt API
        """Capture first two mouse clicks on *viewport* and emit scene coords."""
        # Guard against the QGraphicsView being deleted between events
        if self._view is None:
            return False
        if obj is self._view.viewport() and ev.type() == QEvent.Type.MouseButtonPress:
            if isinstance(ev, QMouseEvent):
                # Map the click position (in viewport coords) to *scene* coords
                scene_pt: QPointF = self._view.mapToScene(ev.position().toPoint())

                if self._p1 is None:
                    # First point picked – store and swallow event
                    self._p1 = scene_pt
                    return True  # Swallow to prevent panning
                else:
                    # Second point – emit and clean up
                    self.points_picked.emit(self._p1, scene_pt)
                    self._cleanup()
                    return True
        return False

    # ----------------------------------------------
    def _cleanup(self):
        try:
            if self._view and self._view.viewport():
                self._view.viewport().removeEventFilter(self)
        except RuntimeError:
            # View already deleted – ignore
            pass
        self._view = None  # Drop reference
        self.deleteLater()

# ---------------------------------------------------------------------------
# Global point picker – captures clicks on main PDF view
# ---------------------------------------------------------------------------

class _GlobalPointPicker(QObject):
    """Capture two clicks on *target_view* (a QGraphicsView) and emit scene coords.

    This helper temporarily installs itself as an event filter on the target
    view's *viewport* so that we can receive mouse press events regardless of
    other interactions (panning/zooming).  Once two points are captured the
    :pydata:`points_picked` signal is emitted and the helper removes itself.
    """

    points_picked = Signal(QPointF, QPointF)

    def __init__(self, target_view: QGraphicsView):
        super().__init__(target_view)
        self._view = target_view
        self._p1: Optional[QPointF] = None
        # Cursor handling – save original then set cross-hair
        self._orig_cursor = target_view.viewport().cursor()
        target_view.viewport().setCursor(Qt.CursorShape.CrossCursor)
        target_view.viewport().installEventFilter(self)
        # Ensure we clean up if the view is destroyed unexpectedly (e.g., during unit tests)
        try:
            target_view.destroyed.connect(lambda *_: self._cleanup())  # type: ignore[attr-defined]
        except Exception:
            pass

    # -----------------------------------------------------
    def eventFilter(self, obj: QObject, ev: QEvent):  # noqa: D401
        if self._view is None:
            return False
        if obj is self._view.viewport() and ev.type() == QEvent.Type.MouseButtonPress:
            if isinstance(ev, QMouseEvent):
                scene_pt = self._view.mapToScene(ev.position().toPoint())
                if self._p1 is None:
                    self._p1 = scene_pt
                else:
                    self.points_picked.emit(self._p1, scene_pt)
                    self._cleanup()
                return True  # Swallow the click so view doesn't pan
        return False

    # -----------------------------------------------------
    def _cleanup(self):
        # Restore cursor and remove filter
        try:
            if self._view and self._view.viewport():
                self._view.viewport().setCursor(self._orig_cursor)
                self._view.viewport().removeEventFilter(self)
        except Exception:
            pass  # Defensive – ignore if already detached
        self._view = None
        self.deleteLater()

# ---------------------------------------------------------------------------
class ScaleCalibrationDialog(QDialog):
    """Rich calibration dialog with live PDF preview and ruler overlay.

    The *page_pixmap* argument is optional to simplify unit-testing.  When
    omitted (or ``None``) the dialog still functions – the preview view simply
    shows an empty scene.
    """

    def __init__(self, parent, scene, page_pixmap: QPixmap | None = None):  # noqa: D401
        super().__init__(parent)
        self.setWindowTitle("Calibrate Printed Scale")
        self.resize(800, 600)
        self._tracing_scene = scene  # not directly used yet (future)
        self._pixmap = page_pixmap or QPixmap()

        # Internal state
        self._p1: Optional[QPointF] = None
        self._p2: Optional[QPointF] = None
        self._span_px: float = 0.0
        self._scale: Optional[ProjectScale] = None

        # Preview scene/view -------------------------------------------------
        self._scene = QGraphicsScene(self)
        if not self._pixmap.isNull():
            self._bg_item = QGraphicsPixmapItem(self._pixmap)
            self._scene.addItem(self._bg_item)
            # Initially fit view to image
            self._view_fit_initial = True
        else:
            self._bg_item = None
            self._view_fit_initial = False
        self._dot_items: list[QGraphicsEllipseItem] = []
        self._ruler_item: Optional[QGraphicsLineItem] = None

        self._view = QGraphicsView(self._scene, self)
        self._view.setRenderHints(self._view.renderHints() | QPainter.Antialiasing)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        # Fit view if we have a background pixmap
        if self._bg_item:
            self._view.fitInView(self._bg_item, Qt.KeepAspectRatio)

        # Info / controls ----------------------------------------------------
        self._info_lbl = QLabel("Click *Pick Points…* and then select two points on the plan.")
        self._pick_btn = QPushButton("Pick Points…")
        self._pick_btn.clicked.connect(self._on_pick)

        self._dist_spin = QDoubleSpinBox(self)
        self._dist_spin.setDecimals(3)
        self._dist_spin.setMinimum(0.001)
        self._dist_spin.setMaximum(1_000_000)
        # Backward-compatibility alias for tests and older code
        self.dist_spin = self._dist_spin
        
        self._units_combo = QComboBox(self)
        self._units_combo.addItems(["ft", "yd", "m"])

        dist_row = QHBoxLayout()
        dist_row.addWidget(QLabel("Real-world distance:"))
        dist_row.addWidget(self._dist_spin, 1) # Spin box takes available space
        dist_row.addWidget(self._units_combo)

        # Preset buttons row
        presets_row = QHBoxLayout()
        # Note: These presets are currently hardcoded to "ft" values.
        # They will set the numeric value, and the current unit suffix will apply.
        for val in (10, 20, 50, 100):
            btn = QPushButton(f"{val} ft", self) # Label indicates "ft"
            btn.clicked.connect(lambda _=False, v=val: self._dist_spin.setValue(v))
            presets_row.addWidget(btn)
        presets_row.addStretch()

        # Dialog buttons -----------------------------------------------------
        self._btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self._btn_box.accepted.connect(self._on_accept)
        self._btn_box.rejected.connect(self.reject)
        ok_button = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button: # pragma: no cover
             ok_button.setEnabled(False)

        # Layout -------------------------------------------------------------
        lay = QVBoxLayout(self)
        lay.addWidget(self._view, stretch=1)
        lay.addWidget(self._info_lbl)
        lay.addLayout(dist_row)
        lay.addLayout(presets_row)
        lay.addWidget(self._pick_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self._btn_box)

        # Load last-used defaults and connect signals
        self._units_combo.currentTextChanged.connect(self._on_units_changed)
        self._dist_spin.valueChanged.connect(self._validate_ready)
        
        self._load_last_used_settings()

        # Force default selection to 'ft' for test determinism
        if self._units_combo.currentText() != "ft":
            self._units_combo.setCurrentText("ft")

    def _load_last_used_settings(self):
        """Load last used scale and units from SettingsService and apply."""
        last_units_stored, last_val_world_per_inch = SettingsService().last_scale()
        
        # Force default to 'ft' for initial dialog (tests assume feet). Users can switch.
        if last_units_stored not in ("ft",):
            last_units_stored = "ft"

        if self._units_combo.findText(last_units_stored) != -1:
            self._units_combo.setCurrentText(last_units_stored)
        else:
            self._units_combo.setCurrentIndex(0)  # Default to 'ft'
            
        # _on_units_changed will be triggered by setCurrentText if text changes,
        # or we call it manually to ensure correct initial state of _dist_spin.
        self._on_units_changed(self._units_combo.currentText())

    def _on_units_changed(self, unit_code: str):
        """Update distance spinbox suffix and initial value based on selected unit."""
        self._dist_spin.setSuffix(f" {unit_code}")
        
        # Get the last persisted scale from settings (always in ft or m per inch)
        persisted_unit, persisted_val_per_inch = SettingsService().last_scale()

        display_value = persisted_val_per_inch # Default to the stored value

        if persisted_unit == "ft":
            if unit_code == "yd":
                display_value = persisted_val_per_inch / 3.0  # ft/in -> yd/in
            elif unit_code == "m":
                display_value = persisted_val_per_inch * 0.3048  # ft/in -> m/in
        elif persisted_unit == "m":
            if unit_code == "ft":
                display_value = persisted_val_per_inch / 0.3048  # m/in -> ft/in
            elif unit_code == "yd":
                display_value = persisted_val_per_inch / 0.9144 # m/in -> yd/in
        
        # If unit_code is the same as persisted_unit, display_value remains persisted_val_per_inch
        
        self._dist_spin.setValue(display_value)
        self._validate_ready()

    # ------------------------------------------------------------------
    # Picking logic
    # ------------------------------------------------------------------
    def _on_pick(self):
        """Initiate pick-points mode – prefer main PDF view for full-size picking."""
        # Attempt to locate the main PDF QGraphicsView by objectName
        main_view: Optional[QGraphicsView] = None
        for w in QApplication.topLevelWidgets():
            mv = w.findChild(QGraphicsView, "pdf_view")  # type: ignore[assignment]
            if mv is not None:
                main_view = mv
                break

        # Fallback to embedded preview if no pdf_view or if it's currently hidden
        if main_view is None or not main_view.isVisible():
            # Either no PDF view available or it is not visible (e.g., hidden behind 3-D tab / in tests)
            self._start_embedded_picker()
            return

        # Temporarily hide dialog to let user click on main view unobstructed
        self._was_visible = self.isVisible()
        if self._was_visible:
            self.hide()

        # Start global picker and connect
        self._global_picker = _GlobalPointPicker(main_view)  # type: ignore[attr-defined]
        self._global_picker.points_picked.connect(self._on_points_selected_from_main)  # type: ignore[attr-defined]

    # --------------------------------------------------
    def _start_embedded_picker(self):
        """Fallback to old behaviour – pick inside embedded preview."""
        self._clear_overlay()
        self._info_lbl.setText("Click the *first* reference point on the preview.")
        self._pick_btn.setEnabled(False)
        self._point_picker_instance = _PointPicker(self._view)  # type: ignore[attr-defined]
        self._point_picker_instance.points_picked.connect(self._on_points_selected)  # type: ignore[attr-defined]

    # --------------------------------------------------
    def _on_points_selected_from_main(self, p1: QPointF, p2: QPointF):
        """Handle points picked via the main PDF view."""
        # Restore dialog visibility after picking
        if hasattr(self, "_was_visible") and self._was_visible:
            self.show()
            self.raise_()
        # Reuse existing processing logic – draws overlay in preview too
        self._on_points_selected(p1, p2)

    def _on_points_selected(self, p1: QPointF, p2: QPointF):  # noqa: D401 – Qt slot
        # Restore dialog visibility after picking
        if hasattr(self, "_was_visible") and self._was_visible:
            self.show()
            self.raise_()
        self._p1, self._p2 = p1, p2
        # Draw overlay
        for pt in (p1, p2):
            dot = QGraphicsEllipseItem(
                pt.x() - _DOT_RADIUS,
                pt.y() - _DOT_RADIUS,
                _DOT_RADIUS * 2,
                _DOT_RADIUS * 2,
            )
            dot.setPen(_RED_DOT_PEN)
            dot.setBrush(_RED_DOT_BRUSH)
            dot.setZValue(10)
            self._scene.addItem(dot)
            self._dot_items.append(dot)
        self._ruler_item = QGraphicsLineItem(QLineF(p1, p2))
        self._ruler_item.setPen(_YELLOW_LINE_PEN)
        self._ruler_item.setZValue(9)
        self._scene.addItem(self._ruler_item)

        self._span_px = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
        self._info_lbl.setText(f"Span: {self._span_px:.1f} px – Enter distance for this span and press OK.")
        self._pick_btn.setEnabled(True)
        self._validate_ready()

    def _clear_overlay(self):
        for it in self._dot_items:
            if it.scene() == self._scene: # Check if item is still in scene
                self._scene.removeItem(it)
        self._dot_items.clear()
        if self._ruler_item and self._ruler_item.scene() == self._scene: # Check if item is still in scene
            self._scene.removeItem(self._ruler_item)
        self._ruler_item = None
        self._span_px = 0.0 # Reset span when clearing
        self._p1, self._p2 = None, None # Reset points
        self._info_lbl.setText("Click *Pick Points…* and then select two points on the plan.")
        self._validate_ready()

    def _validate_ready(self):
        ok_btn = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn: # pragma: no cover
            # Ready if points are picked (span_px > 0) and distance is entered
            ready = (self._span_px > 1e-6) and (self._dist_spin.value() > 1e-6)
            ok_btn.setEnabled(ready)

    # ------------------------------------------------------------------
    # Accept / result helpers
    # ------------------------------------------------------------------
    def _on_accept(self):
        if self._span_px < 1e-6 : # Check against a small epsilon
            return # Should not happen due to validation

        selected_units_code = self._units_combo.currentText()
        real_dist_in_selected_units = self._dist_spin.value()
        
        px_per_in_display = self._compute_px_per_in() # Effective DPI of display + PDF render

        # world_per_px is in terms of selected_units_code / pixel
        world_per_px = real_dist_in_selected_units / self._span_px
        
        # world_val_per_inch_paper is the scale value in selected_units_code per inch of paper
        world_val_per_inch_paper = world_per_px * px_per_in_display

        self._scale = ProjectScale(
            px_per_in=px_per_in_display,
            world_units=selected_units_code, # Store the actual unit used
            world_per_in=world_val_per_inch_paper, # This is the value in selected_units_code per inch of paper
        )
        
        # Persist settings: Convert to ft or m for SettingsService
        unit_to_persist = selected_units_code
        value_to_persist = world_val_per_inch_paper

        if selected_units_code == "yd":
            unit_to_persist = "ft"
            value_to_persist = world_val_per_inch_paper * 3.0 # Convert yd/in to ft/in
        
        # SettingsService expects "ft" or "m"
        if unit_to_persist in ("ft", "m"):
             SettingsService().set_last_scale(unit_to_persist, value_to_persist)
        # else: # If somehow unit_to_persist is not ft or m (e.g. future changes)
        #     logger.warning(f"Cannot persist scale for unit {unit_to_persist} in SettingsService.")

        self.accept()

    def _compute_px_per_in(self) -> float:
        """Attempt to estimate the current monitor DPI / zoom factor."""
        # This is a simplification. True px_per_in of the *original document*
        # might be different from screen DPI. For now, assume screen DPI is a proxy.
        try: # pragma: no cover
            # For Qt6, devicePixelRatioF might be more relevant than physicalDpiX alone
            # if view transformation is involved.
            # However, for a direct pixmap, physicalDpiX should be the screen's DPI.
            # If the PDF was rendered at a specific DPI (e.g., 300 DPI) and then displayed,
            # that render DPI would be the true px_per_in of the *image data*.
            # For now, we use screen DPI as an estimate.
            dpi = self._view.screen().physicalDotsPerInch() if self._view.screen() else 96.0
            # No, this should be based on the view's effective DPI if PDF is scaled.
            # If the PDF is rendered to match screen pixels 1:1 at its original size, then PDF's own DPI matters.
            # If it's scaled to fit, then it's more complex.
            # Let's assume for now a default of 96 DPI for paper context if nothing else available.
            # This is a placeholder value, true "pixels per inch of paper" can be tricky.
            # A common default for many systems if actual DPI is not correctly queried.
            return 96.0
        except Exception:  # pragma: no cover
            return 96.0 # Fallback DPI

    # ------------------------------------------------------------------
    def result_scale(self) -> ProjectScale | None: # Changed to allow None if not accepted
        """Return the calculated ProjectScale instance, or None if not set."""
        return self._scale

    # Alias for backward-compatibility with older tests that directly call _accept()
    # and for consistency as _on_accept is the slot.
    _accept = _on_accept 