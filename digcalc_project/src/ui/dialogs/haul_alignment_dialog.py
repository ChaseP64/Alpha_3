"""haul_alignment_dialog.py – Dialog for configuring mass-haul alignment parameters.

This lightweight dialog lets the user specify the *station interval* and the
*free-haul distance* prior to running a mass-haul analysis. An alignment
polyline will be supplied elsewhere in the UI (Phase 9).
"""

from __future__ import annotations

from typing import Tuple, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
)

__all__ = ["HaulAlignmentDialog"]


class HaulAlignmentDialog(QDialog):
    """Dialog for entering mass-haul alignment parameters.

    Args:
        default_interval: Initial station interval (ft).
        default_free:     Initial free-haul distance (ft).
        parent:           Parent widget.
    """

    def __init__(
        self,
        default_interval: float = 100.0,
        default_free: float = 500.0,
        parent: Optional[QDialog] = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Mass-Haul Alignment")
        self.setMinimumWidth(300)

        # ------------------------------------------------------------
        # Widgets – station interval and free-haul distance
        # ------------------------------------------------------------
        self.interval = QDoubleSpinBox(self)
        self.interval.setDecimals(1)
        self.interval.setRange(10.0, 500.0)
        self.interval.setSingleStep(10.0)
        self.interval.setSuffix(" ft")
        self.interval.setValue(default_interval)

        self.free = QDoubleSpinBox(self)
        self.free.setDecimals(1)
        self.free.setRange(0.0, 5000.0)
        self.free.setSingleStep(50.0)
        self.free.setSuffix(" ft")
        self.free.setValue(default_free)

        # ------------------------------------------------------------
        # Layout
        # ------------------------------------------------------------
        form = QFormLayout()
        form.addRow("Station interval:", self.interval)
        form.addRow("Free-haul distance:", self.free)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def values(self) -> Tuple[float, float]:
        """Return *(station_interval, free_haul_distance)* in feet."""

        return self.interval.value(), self.free.value()
