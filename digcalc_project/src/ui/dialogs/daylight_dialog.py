from __future__ import annotations

"""Daylight offset parameter dialog.

Provides a simple UI for specifying the horizontal offset distance and
slope ratio (H:V) for daylight/break-line generation.
"""

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QDoubleSpinBox,
    QDialogButtonBox,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

class DaylightDialog(QDialog):
    """Modal dialog to request daylight offset parameters from the user."""

    def __init__(self, parent=None):  # noqa: D401 (simple init)
        super().__init__(parent)

        self.setWindowTitle("Daylight Offset")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(True)

        # --- Distance spinbox (positive = outward, negative = inward) ---
        self._dist = QDoubleSpinBox(self)
        self._dist.setMinimum(-200.0)
        self._dist.setMaximum(200.0)
        self._dist.setSingleStep(1.0)
        self._dist.setSuffix(" ft")
        self._dist.setDecimals(2)
        self._dist.setValue(5.0)  # Sensible default

        # --- Slope spinbox (H:V ratio) ---
        self._slope = QDoubleSpinBox(self)
        self._slope.setMinimum(0.01)  # Prevent division-by-zero
        self._slope.setMaximum(10.0)
        self._slope.setSingleStep(0.25)
        self._slope.setSuffix(" H:V")
        self._slope.setDecimals(2)
        self._slope.setValue(3.0)  # Common 3:1 slope

        # Layout ----------------------------------------------------------------
        form = QFormLayout()
        form.addRow("Horizontal offset (+out / –in):", self._dist)
        form.addRow("Slope (H):1V", self._slope)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

        self.setLayout(lay)

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def values(self) -> tuple[float, float]:
        """Return the (distance, slope_ratio) entered by the user."""
        return self._dist.value(), self._slope.value()


