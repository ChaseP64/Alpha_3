from __future__ import annotations

"""Stub dialog for Smart Clean configuration (Phase-2 Day-1).
Currently exposes a single enable/disable checkbox – functional logic will
arrive in later milestones.
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget,
)


class SmartCleanDialog(QDialog):
    """Simple modal dialog with an *Enable Smart Clean* toggle."""

    def __init__(self, parent: QWidget | None = None) -> None:  # noqa: D401
        super().__init__(parent)
        self.setWindowTitle("Smart Clean")

        # Layout ----------------------------------------------------------
        layout = QVBoxLayout(self)

        self.enable_chk = QCheckBox("Enable Smart Clean", self)
        self.enable_chk.setChecked(True)
        layout.addWidget(self.enable_chk)

        # Compression tolerance sliders ----------------------------------
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider

        self.dist_slider = QSlider(Qt.Orientation.Horizontal)
        self.dist_slider.setRange(1, 100)  # map 0.01-1.00 ft
        self.dist_slider.setValue(10)
        self.dist_label = QLabel("0.10 ft")
        self.dist_slider.valueChanged.connect(lambda v: self.dist_label.setText(f"{v/100:.2f} ft"))

        dist_layout = QHBoxLayout()
        dist_layout.addWidget(QLabel("Distance Tol:"))
        dist_layout.addWidget(self.dist_slider)
        dist_layout.addWidget(self.dist_label)
        layout.addLayout(dist_layout)

        self.angle_slider = QSlider(Qt.Orientation.Horizontal)
        self.angle_slider.setRange(1, 180)
        self.angle_slider.setValue(1)
        self.angle_label = QLabel("1°")
        self.angle_slider.valueChanged.connect(lambda v: self.angle_label.setText(f"{v}°"))

        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("Angle Tol:"))
        angle_layout.addWidget(self.angle_slider)
        angle_layout.addWidget(self.angle_label)
        layout.addLayout(angle_layout)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ------------------------------------------------------------------
    def is_enabled(self) -> bool:  # noqa: D401
        """Return checkbox state (True when Smart Clean is enabled)."""
        return self.enable_chk.isChecked()

    # ------------------------------------------------------------------
    def tolerances(self) -> tuple[float, float]:  # noqa: D401
        """Return (dist_tol_ft, angle_tol_deg) from sliders."""
        return self.dist_slider.value() / 100.0, float(self.angle_slider.value())
