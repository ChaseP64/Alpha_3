from __future__ import annotations

"""Batch Elevate Dialog – apply uniform Z or slope grade to multiple polylines.

Phase-5 D2 deliverable.  The dialog is *headless-friendly* (usable in tests
without a full MainWindow) – callers supply the list of selected
:class:`PolylineItem` objects and the target :class:`QUndoStack`.
"""

from typing import List

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)
from PySide6.QtGui import QUndoStack

from digcalc_project.src.ui.items.polyline_item import PolylineItem
from digcalc_project.src.ui.commands.batch_elevate_command import BatchElevateCommand

__all__ = ["BatchElevateDialog"]


class BatchElevateDialog(QDialog):
    """Dialog letting the user elevate multiple polylines in one action."""

    def __init__(
        self,
        polylines: List[PolylineItem],
        undo_stack: QUndoStack,
        parent=None,
    ):
        super().__init__(parent)
        if len(polylines) == 0:
            raise ValueError("No polylines supplied to BatchElevateDialog.")

        self._pls = polylines
        self._undo_stack = undo_stack
        self.setWindowTitle("Batch Elevate Polylines")
        self.setModal(True)

        # ----------------------------------------------------------------------------------
        # Widgets
        # ----------------------------------------------------------------------------------
        self._rad_uniform = QRadioButton("Uniform Elevation (ft)")
        self._rad_slope = QRadioButton("Linear Grade (% rise)")
        self._rad_uniform.setChecked(True)

        self._uniform_spin = QDoubleSpinBox()
        self._uniform_spin.setDecimals(3)
        self._uniform_spin.setRange(-9999, 9999)

        self._start_spin = QDoubleSpinBox()
        self._start_spin.setDecimals(3)
        self._start_spin.setRange(-9999, 9999)
        self._start_spin.setEnabled(False)

        self._slope_spin = QDoubleSpinBox()
        self._slope_spin.setDecimals(3)
        self._slope_spin.setRange(-1000, 1000)
        self._slope_spin.setSuffix(" %")
        self._slope_spin.setEnabled(False)

        # radio toggles enable state
        self._rad_uniform.toggled.connect(self._on_mode_change)

        form = QFormLayout()
        # Uniform row
        uniform_row = QHBoxLayout()
        uniform_row.addWidget(self._rad_uniform)
        uniform_row.addWidget(self._uniform_spin)
        form.addRow(uniform_row)

        # Slope rows
        slope_row1 = QHBoxLayout()
        slope_row1.addWidget(QLabel("Start Elev (ft):"))
        slope_row1.addWidget(self._start_spin)
        form.addRow(slope_row1)

        slope_row2 = QHBoxLayout()
        slope_row2.addWidget(self._rad_slope)
        slope_row2.addWidget(self._slope_spin)
        form.addRow(slope_row2)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)

        v = QVBoxLayout()
        v.addLayout(form)
        v.addWidget(buttons)
        self.setLayout(v)

    # ------------------------------------------------------------------
    def _on_mode_change(self, uniform_checked: bool):
        self._uniform_spin.setEnabled(uniform_checked)
        self._start_spin.setEnabled(not uniform_checked)
        self._slope_spin.setEnabled(not uniform_checked)

    # ------------------------------------------------------------------
    def _apply(self):
        try:
            if self._rad_uniform.isChecked():
                cmd = BatchElevateCommand(self._pls, uniform_z=self._uniform_spin.value())
            else:
                cmd = BatchElevateCommand(
                    self._pls,
                    first_z=self._start_spin.value(),
                    slope_percent=self._slope_spin.value(),
                )
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid parameters", str(exc))
            return

        self._undo_stack.push(cmd)
        self.accept() 