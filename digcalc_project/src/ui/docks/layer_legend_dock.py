from __future__ import annotations

"""LayerLegendDock – shows a colour legend of currently-visible layers.

Each entry: 20×12 swatch + layer name + eye-icon toggle.

Signals
-------
visibleLayersChanged(int)
    Emitted whenever the *number of visible layers* changes so the main window
    can auto-show / hide the dock depending on count.
layerVisibilityToggled(str, bool)
    layer_id, new_visible – forwarded to scene.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDockWidget,
    QListWidget,
    QListWidgetItem,
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from digcalc_project.src.models.layer import Layer

__all__ = ["LayerLegendDock"]


class _LegendRow(QWidget):
    """Composite widget for a single layer entry in the legend."""

    def __init__(self, layer: Layer, *, parent: QWidget | None = None):
        super().__init__(parent)
        self._layer = layer

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(6)

        # Swatch -------------------------------------------------------
        swatch = QLabel(self)
        swatch.setFixedSize(20, 12)
        swatch.setStyleSheet(
            f"background:{layer.line_color}; border:1px solid #555;",
        )
        layout.addWidget(swatch)
        self._swatch = swatch  # store for colour updates

        # Name ---------------------------------------------------------
        layout.addWidget(QLabel(layer.name, self), 1)

        # Eye-toggle ---------------------------------------------------
        btn = QPushButton(self)
        btn.setFlat(True)
        btn.setCheckable(True)
        btn.setChecked(layer.visible)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_eye = btn
        layout.addWidget(btn)
        self._refresh_icon()
        btn.toggled.connect(self._on_toggled)

    # ------------------------------------------------------------------
    def _refresh_icon(self):
        icon_name = "mdi.eye" if self._btn_eye.isChecked() else "mdi.eye-off"
        if QIcon.hasThemeIcon(icon_name):
            self._btn_eye.setIcon(QIcon.fromTheme(icon_name))
            self._btn_eye.setText("")
        else:
            # Fallback text icons
            self._btn_eye.setIcon(QIcon())
            self._btn_eye.setText("👁" if self._btn_eye.isChecked() else "🚫")

    # ------------------------------------------------------------------
    def _on_toggled(self, checked: bool):
        self._layer.visible = checked
        self._refresh_icon()
        # bubble up to dock
        dock: LayerLegendDock = self.parent().parent().parent()  # type: ignore[assignment]
        dock._emit_visibility_toggle(self._layer.id, checked)

    # ------------------------------------------------------------------
    def update_colors(self):
        self._swatch.setStyleSheet(
            f"background:{self._layer.line_color}; border:1px solid #555;",
        )
        self.update()


class LayerLegendDock(QDockWidget):
    """Dock widget listing layers with colour swatch and visibility eye."""

    visibleLayersChanged = Signal(int)
    layerVisibilityToggled = Signal(str, bool)  # layer_id, visible

    def __init__(self, project, parent: QWidget | None = None):
        super().__init__("Legend", parent)
        self.setObjectName("LayerLegendDock")
        self._project = project

        self._list = QListWidget(self)
        self._list.setSpacing(2)
        self.setWidget(self._list)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self):
        """Rebuild legend from current project layers."""
        self._list.clear()
        if not self._project:
            self.visibleLayersChanged.emit(0)
            return

        visible_count = 0
        for lyr in self._project.layers:
            row_widget = _LegendRow(lyr, parent=self)
            item = QListWidgetItem(self._list)
            item.setSizeHint(row_widget.sizeHint())
            self._list.setItemWidget(item, row_widget)
            if lyr.visible:
                visible_count += 1
        self.visibleLayersChanged.emit(visible_count)

    # ------------------------------------------------------------------
    def _emit_visibility_toggle(self, layer_id: str, visible: bool):
        """Forward eye-toggle to listeners and re-emit layer count."""
        self.layerVisibilityToggled.emit(layer_id, visible)
        if self._project:
            count = sum(1 for l in self._project.layers if l.visible)
            self.visibleLayersChanged.emit(count)

    # ------------------------------------------------------------------
    def update_layer_colors(self, layer_id: str):
        """Refresh swatch for a specific layer."""
        for i in range(self._list.count()):
            widget = self._list.itemWidget(self._list.item(i))
            if isinstance(widget, _LegendRow) and widget._layer.id == layer_id:
                widget.update_colors() 