"""Dialog to create a new Material (Phase 1-2)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QWidget,
)


class AddMaterialDialog(QDialog):
    """Modal dialog prompting for material attributes."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add Material")
        self._color = QColor("#CCCCCC")

        form = QFormLayout(self)

        # Name field
        self.name_edit = QLineEdit(self)
        form.addRow("Name:", self.name_edit)

        # Color picker
        color_layout = QHBoxLayout()
        self.color_btn = QPushButton()
        self._update_color_btn()
        self.color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()
        form.addRow("Color:", color_layout)

        # Opacity slider (0-1 mapped to 0-100)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_label = QLabel("1.00", self)
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(f"{v/100:.2f}")
        )
        op_layout = QHBoxLayout()
        op_layout.addWidget(self.opacity_slider)
        op_layout.addWidget(self.opacity_label)
        form.addRow("Opacity:", op_layout)

        # Dialog buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    # ------------------------------------------------------------------
    def _choose_color(self):
        col = QColorDialog.getColor(self._color, self, "Select Color")
        if col.isValid():
            self._color = col
            self._update_color_btn()

    def _update_color_btn(self):
        self.color_btn.setText(self._color.name())
        self.color_btn.setStyleSheet(f"background-color:{self._color.name()};")

    # ------------------------------------------------------------------
    def _on_accept(self):
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        self.accept()

    # ------------------------------------------------------------------
    def material_kwargs(self) -> dict:
        """Return dict suitable for *Material* constructor."""
        return {
            "id": 0,  # will be assigned by StrataStack
            "name": self.name_edit.text().strip(),
            "colour": self._color.name(),
        }
