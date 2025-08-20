"""Dialog to compose a BoreholeLog with one or more layers."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from digcalc_project.src.models.strata_models import (
    BoreholeLog,
    LayerDepth,
    StrataStack,
)


class BoreholeEditorDialog(QDialog):
    """Create / edit a borehole log consisting of material layers."""

    def __init__(self, stack: StrataStack, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Borehole Editor")
        self._stack = stack

        layout = QVBoxLayout(self)

        # Layer table
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Material", "Top Z", "Thickness"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._validate)
        layout.addWidget(self.table)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Layer", self)
        self.btn_del = QPushButton("Delete Layer", self)
        self.btn_add.clicked.connect(self._add_layer_row)
        self.btn_del.clicked.connect(self._delete_selected_row)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Validation banner
        self.status_lbl = QLabel("", self)
        self.status_lbl.setStyleSheet("color:red;")
        layout.addWidget(self.status_lbl)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Start with one layer
        self._add_layer_row()
        self._validate()

    # ------------------------------------------------------------------
    def _material_combo(self) -> QComboBox:
        combo = QComboBox(self.table)
        for mat in self._stack.materials:
            combo.addItem(mat.name, mat.id)
        return combo

    def _add_layer_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        # Material combo in column 0
        combo = self._material_combo()
        self.table.setCellWidget(row, 0, combo)
        # Top Z default
        self.table.setItem(row, 1, QTableWidgetItem("0.0"))
        # Thickness default
        self.table.setItem(row, 2, QTableWidgetItem("1.0"))
        self._validate()

    def _delete_selected_row(self):
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        for r in sorted(rows, reverse=True):
            self.table.removeRow(r)
        self._validate()

    # ------------------------------------------------------------------
    def _read_layers(self) -> List[LayerDepth]:
        layers: List[LayerDepth] = []
        for r in range(self.table.rowCount()):
            combo = self.table.cellWidget(r, 0)
            if not isinstance(combo, QComboBox):
                continue
            mat_id = int(combo.currentData())
            try:
                top_z = float(self.table.item(r, 1).text())
                thickness = float(self.table.item(r, 2).text())
            except (AttributeError, ValueError):
                raise ValueError("Numeric fields must contain valid numbers")
            if thickness <= 0:
                raise ValueError("Thickness must be > 0")
            layer = LayerDepth(material_id=mat_id, top_z=top_z, bottom_z=top_z - thickness)
            layers.append(layer)
        return layers

    # ------------------------------------------------------------------
    def _validate(self):
        try:
            layers = self._read_layers()
            # Use BoreholeLog validation logic for contiguity
            temp = BoreholeLog(id=0, x=0, y=0, layers=layers)
            temp._validate_contiguous(layers)  # pylint: disable=protected-access
            self.status_lbl.setText("")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        except ValueError as e:
            self.status_lbl.setText(str(e))
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    # ------------------------------------------------------------------
    def _on_accept(self):
        self._validate()
        if self.button_box.button(QDialogButtonBox.StandardButton.Ok).isEnabled():
            self.accept()

    # ------------------------------------------------------------------
    def to_borehole(self, x: float, y: float, bh_id: int) -> BoreholeLog:
        """Return BoreholeLog built from table (caller provides XY/id)."""
        layers = self._read_layers()
        return BoreholeLog(id=bh_id, x=x, y=y, layers=layers)
