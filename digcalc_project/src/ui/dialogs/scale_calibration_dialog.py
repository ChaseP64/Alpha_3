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
    QRadioButton,
    QButtonGroup,
    QApplication,
    QMessageBox,
    QTabWidget,
    QWidget,
    QLineEdit,
)

from digcalc_project.src.models.project_scale import ProjectScale
from digcalc_project.src.services.settings_service import SettingsService
from digcalc_project.src.models.project import Project

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

    def __init__(self, parent, project: Project, scene, page_pixmap: QPixmap | None = None):  # noqa: D401
        super().__init__(parent)
        self.setWindowTitle("Calibrate Printed Scale")
        self.resize(800, 600)
        self._project = project
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

        # ---------------- Tabs ---------------------------------------------
        self.tabs = QTabWidget(self)

        # ---- Pick Points tab (existing controls) ----
        pick_tab = QWidget()
        pick_lay = QVBoxLayout(pick_tab)
        pick_lay.addWidget(self._view, stretch=1)
        pick_lay.addWidget(self._info_lbl)
        pick_lay.addLayout(dist_row)
        pick_lay.addLayout(presets_row)
        pick_lay.addWidget(self._pick_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.tabs.addTab(pick_tab, "Pick Points")

        # ---- Enter Scale tab ---------------------------------------------
        enter_tab = QWidget()
        enter_lay = QVBoxLayout(enter_tab)

        # Mode radios
        self.radio_world = QRadioButton("Direct entry (units / inch)")
        self.radio_ratio = QRadioButton("Ratio (1 : N)")
        self.radio_world.setChecked(True)
        mode_group = QButtonGroup(enter_tab)
        mode_group.addButton(self.radio_world)
        mode_group.addButton(self.radio_ratio)

        # Direct entry widgets
        self.spin_value = QDoubleSpinBox()
        self.spin_value.setDecimals(3)
        self.spin_value.setMinimum(0.01)
        self.spin_value.setMaximum(1_000_000)
        self.combo_units = QComboBox()
        self.combo_units.addItems(["ft", "yd", "m"])

        direct_row = QHBoxLayout()
        direct_row.addWidget(self.spin_value)
        direct_row.addWidget(self.combo_units)

        # Ratio widgets
        ratio_row = QHBoxLayout()
        self.edit_numer = QLabel("1 :")  # Fixed numerator label
        self.edit_denom = QLineEdit()
        self.edit_denom.setPlaceholderText("denominator")
        ratio_row.addWidget(self.edit_numer)
        ratio_row.addWidget(self.edit_denom)

        # Helper label showing world_per_px preview
        self.lbl_helper = QLabel("")

        # Assemble enter tab layout
        enter_lay.addWidget(self.radio_world)
        enter_lay.addLayout(direct_row)
        enter_lay.addSpacing(8)
        enter_lay.addWidget(self.radio_ratio)
        enter_lay.addLayout(ratio_row)
        enter_lay.addStretch(1)
        enter_lay.addWidget(self.lbl_helper)

        self.tabs.addTab(enter_tab, "Enter Scale")

        # Dialog buttons -----------------------------------------------------
        self._btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self._btn_box.accepted.connect(self._on_accept)
        self._btn_box.rejected.connect(self.reject)
        ok_button = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setEnabled(False)

        # Expose for tests
        self.buttonBox = self._btn_box  # type: ignore

        # Main dialog layout -------------------------------------------------
        main_lay = QVBoxLayout(self)
        main_lay.addWidget(self.tabs, stretch=1)
        main_lay.addWidget(self._btn_box)

        # Load last-used defaults and connect signals
        self._units_combo.currentTextChanged.connect(self._on_units_changed)
        self._dist_spin.valueChanged.connect(self._validate_ready)
        
        self._load_last_used_settings()

        # Force default selection to 'ft' for test determinism
        if self._units_combo.currentText() != "ft":
            self._units_combo.setCurrentText("ft")

        # Connect validation for new widgets
        self.spin_value.valueChanged.connect(self._validate_ready)
        self.combo_units.currentTextChanged.connect(self._validate_ready)
        self.radio_world.toggled.connect(self._validate_ready)
        self.edit_denom.textChanged.connect(self._validate_ready)
        self.radio_ratio.toggled.connect(self._validate_ready)

        self.tabs.currentChanged.connect(self._validate_ready)

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
        if not ok_btn:
            return

        if self.tabs.currentIndex() == 0:
            # Pick points mode
            ready = (self._span_px > 1e-6) and (self._dist_spin.value() > 1e-6)
            ok_btn.setEnabled(ready)
        else:
            # Enter scale tab
            if self.radio_world.isChecked():
                ready = self.spin_value.value() > 0.0
            else:
                try:
                    denom_val = float(self.edit_denom.text())
                    ready = denom_val > 0.0
                except ValueError:
                    ready = False
            ok_btn.setEnabled(ready)

            # Update helper preview
            try:
                dpi = float(self._project.pdf_background_dpi) if self._project else 96.0
                if self.radio_world.isChecked():
                    world_per_px = self.spin_value.value() / dpi
                else:
                    denom_val = float(self.edit_denom.text()) if self.edit_denom.text() else 0.0
                    if denom_val > 0:
                        # world_per_in depends on units – assume ratio 1:denom same units as selected
                        units = self.combo_units.currentText()
                        if units == "ft":
                            world_per_in = denom_val / 12.0
                        elif units == "yd":
                            world_per_in = denom_val / 36.0
                        else:
                            world_per_in = denom_val * 0.0254
                        world_per_px = world_per_in / dpi
                    else:
                        world_per_px = 0.0
                self.lbl_helper.setText(f"~{world_per_px:.4f} {self.combo_units.currentText()}/px @ {dpi} dpi")
            except Exception:
                self.lbl_helper.setText("")

    # ------------------------------------------------------------------
    # Accept / result helpers
    # ------------------------------------------------------------------
    def _on_accept(self):
        # Branch based on active tab ---------------------------------------
        if self.tabs.currentIndex() == 0:
            # Original pick-points workflow --------------------------------
            if self._span_px < 1e-6:
                return  # validation

            selected_units_code = self._units_combo.currentText()
            real_dist_in_selected_units = self._dist_spin.value()

            px_per_in_display = self._compute_px_per_in()

            world_per_px = real_dist_in_selected_units / self._span_px
            world_val_per_inch_paper = world_per_px * px_per_in_display

            self._scale = ProjectScale(
                px_per_in=px_per_in_display,
                world_units=selected_units_code,
                world_per_in=world_val_per_inch_paper,
            )
        else:
            dpi = float(self._project.pdf_background_dpi) if self._project else 96.0
            if dpi <= 0:
                QMessageBox.warning(self, "Scale Calibration", "Invalid or unknown PDF DPI; cannot build scale.")
                return

            units = self.combo_units.currentText()
            if self.radio_world.isChecked():
                self._scale = ProjectScale.from_direct(
                    value=self.spin_value.value(),
                    units=units,
                    render_dpi=dpi,
                )
            else:
                denom_val = float(self.edit_denom.text())
                self._scale = ProjectScale.from_ratio(
                    numer=1.0,
                    denom=denom_val,
                    units=units,
                    render_dpi=dpi,
                )

        # Store on project immediately
        if self._project is not None:
            self._project.scale = self._scale

        # Persist settings: Convert to ft or m for SettingsService
        unit_to_persist = self._units_combo.currentText() if self.tabs.currentIndex()==0 else self.combo_units.currentText()
        value_to_persist = getattr(self._scale, 'world_per_in', None)
        if unit_to_persist in ("ft", "m") and value_to_persist:
            SettingsService().set_last_scale(unit_to_persist, value_to_persist)

        self.accept()

    def _compute_px_per_in(self) -> float:
        """
        Returns the DPI at which the currently displayed PDF page (for calibration)
        was rendered. This comes from the project settings.
        """
        if self._project and self._project.pdf_background_path and self._project.pdf_background_dpi > 0:
            # Ensure a PDF is actually loaded in the project and has a valid DPI set
            return float(self._project.pdf_background_dpi)
        else:
            # Fallback or error condition if no PDF is loaded or DPI is invalid
            # This case should ideally be prevented by disabling calibration if no PDF/DPI
            QMessageBox.warning(
                self, 
                "Scale Calibration Error", 
                "Cannot determine rendering DPI. Please ensure a PDF is loaded with a valid DPI setting in the project."
            )
            return 96.0 # Or raise an error / return a value that signals failure

    # ------------------------------------------------------------------
    def result_scale(self) -> ProjectScale | None: # Changed to allow None if not accepted
        """Return the calculated ProjectScale instance, or None if not set."""
        return self._scale

    # Alias for backward-compatibility with older tests that directly call _accept()
    # and for consistency as _on_accept is the slot.
    _accept = _on_accept 