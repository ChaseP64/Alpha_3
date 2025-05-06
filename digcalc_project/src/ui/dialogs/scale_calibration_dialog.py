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
from PySide6.QtGui import QPixmap, QPen, QBrush, QColor, QPainter
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
)

from digcalc_project.src.models.project_scale import ProjectScale
from digcalc_project.src.services.settings_service import SettingsService

__all__ = ["ScaleCalibrationDialog"]

_RED_DOT_PEN = QPen(QColor("red"), 2)
_RED_DOT_BRUSH = QBrush(QColor("red"))
_YELLOW_LINE_PEN = QPen(QColor("yellow"), 1, Qt.DashLine)
_DOT_RADIUS = 4.0

# ---------------------------------------------------------------------------
class _PointPicker(QObject):
    """Event-filter that records two mouse clicks on the *view* scene."""

    points_picked = Signal(QPointF, QPointF)  # emitted when both points chosen

    def __init__(self, view: QGraphicsView):
        super().__init__(view)
        self._view = view
        self._p1: Optional[QPointF] = None
        view.viewport().installEventFilter(self)

    # ----------------------------------------------
    def eventFilter(self, obj, ev):  # noqa: D401 – Qt API
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent

        if ev.type() == QEvent.GraphicsSceneMousePress:
            if isinstance(ev, QGraphicsSceneMouseEvent):
                pt = ev.scenePos()
                if self._p1 is None:
                    self._p1 = pt
                    return True
                else:
                    self.points_picked.emit(self._p1, pt)
                    self._cleanup()
                    return True
        return False

    # ----------------------------------------------
    def _cleanup(self):
        self._view.viewport().removeEventFilter(self)
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
        self._info_lbl = QLabel("Click *Pick* and then select the first point.")
        self._pick_btn = QPushButton("Pick Points…")
        self._pick_btn.clicked.connect(self._on_pick)

        self._dist_spin = QDoubleSpinBox(decimals=3, minimum=0.01, maximum=1e6)
        self._dist_spin.setSuffix(" ft")
        # Alias for backward-compatibility with older tests
        self.dist_spin = self._dist_spin

        last_units, last_wpi = SettingsService().last_scale()
        default_dist = 20.0 if last_units == "ft" else 5.0
        self._dist_spin.setValue(default_dist)
        self._dist_spin.valueChanged.connect(self._validate_ready)

        dist_row = QHBoxLayout()
        dist_row.addWidget(QLabel("Real-world distance:"))
        dist_row.addWidget(self._dist_spin)

        # Preset buttons row
        presets_row = QHBoxLayout()
        for val in (10, 20, 50, 100):
            btn = QPushButton(f"{val} ft")
            btn.clicked.connect(lambda _=False, v=val: self._dist_spin.setValue(v))
            presets_row.addWidget(btn)
        presets_row.addStretch()

        # Dialog buttons -----------------------------------------------------
        self._btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._btn_box.accepted.connect(self._on_accept)
        self._btn_box.rejected.connect(self.reject)
        self._btn_box.button(QDialogButtonBox.Ok).setEnabled(False)

        # Layout -------------------------------------------------------------
        lay = QVBoxLayout(self)
        lay.addWidget(self._view, stretch=1)
        lay.addWidget(self._info_lbl)
        lay.addLayout(dist_row)
        lay.addLayout(presets_row)
        lay.addWidget(self._pick_btn, alignment=Qt.AlignLeft)
        lay.addWidget(self._btn_box)

    # ------------------------------------------------------------------
    # Picking logic
    # ------------------------------------------------------------------
    def _on_pick(self):
        self._clear_overlay()
        self._info_lbl.setText("Click the *first* reference point.")
        self._pick_btn.setEnabled(False)
        picker = _PointPicker(self._view)
        picker.points_picked.connect(self._on_points_selected)

    def _on_points_selected(self, p1: QPointF, p2: QPointF):  # noqa: D401 – Qt slot
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
        self._info_lbl.setText(f"Span: {self._span_px:.1f} px – enter distance and press OK.")
        self._pick_btn.setEnabled(True)
        self._validate_ready()

    def _clear_overlay(self):
        for it in self._dot_items:
            if it in self._scene.items():
                self._scene.removeItem(it)
        self._dot_items.clear()
        if self._ruler_item and self._ruler_item in self._scene.items():
            self._scene.removeItem(self._ruler_item)
        self._ruler_item = None
        self._span_px = 0.0
        self._validate_ready()

    def _validate_ready(self):
        ok_btn = self._btn_box.button(QDialogButtonBox.Ok)
        ready = self._span_px > 0 and self._dist_spin.value() > 0
        ok_btn.setEnabled(ready)

    # ------------------------------------------------------------------
    # Accept / result helpers
    # ------------------------------------------------------------------
    def _on_accept(self):
        if self._span_px == 0:
            return  # should not happen due to validation
        real_dist_ft = self._dist_spin.value()
        px_per_in = self._compute_px_per_in()
        world_per_px = real_dist_ft / self._span_px
        world_per_in = world_per_px * px_per_in

        self._scale = ProjectScale(
            px_per_in=px_per_in,
            world_units="ft",  # future: unit combo could be added
            world_per_in=world_per_in,
        )
        SettingsService().set_last_scale("ft", world_per_in)
        self.accept()

    def _compute_px_per_in(self) -> float:
        """Attempt to estimate the current monitor DPI * zoom factor*."""
        try:
            dpi = self._view.physicalDpiX() * self._view.devicePixelRatioF()
            return float(dpi)
        except Exception:  # pragma: no cover
            return 96.0

    # ------------------------------------------------------------------
    def result_scale(self) -> ProjectScale:
        if self._scale is None:
            units, wpi = SettingsService().last_scale()
            return ProjectScale(px_per_in=96.0, world_units=units, world_per_in=wpi)
        return self._scale

    # Backward-compat alias for old tests that directly call _accept()
    _accept = _on_accept 