from __future__ import annotations

"""Auto-Increment Elevation Wizard (Phase-5 D1).

This dialog prompts the user for either:
  • *Start/End Elevation* (explicit numeric values), **or**
  • *Slope Percentage* (rise over run × 100)

and applies a linear grade to the currently selected polyline vertices via an
:class:`~digcalc_project.src.ui.commands.auto_increment_z_command.AutoIncrementZCommand`.

The dialog is intentionally **headless-friendly**: when instantiated with
``parent=None`` it will not access the application‐global MainWindow.  Instead,
callers supply:
    • *vertices* – ordered list of :class:`VertexItem`s to operate on.
    • *undo_stack* – :class:`QUndoStack` used to push the command.
"""

from typing import List

from PySide6.QtGui import QUndoStack
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

from digcalc_project.src.ui.commands.auto_increment_z_command import AutoIncrementZCommand
from digcalc_project.src.ui.items.vertex_item import VertexItem

__all__ = ["AutoIncrementDialog"]


class AutoIncrementDialog(QDialog):
    """Wizard dialog to apply linear grade elevations along a polyline."""

    def __init__(
        self,
        vertices: List[VertexItem],
        undo_stack: QUndoStack,
        parent=None,
    ):
        super().__init__(parent)
        if len(vertices) < 2:
            raise ValueError("Need ≥2 vertices for auto-increment wizard.")

        self._verts = vertices
        self._undo_stack = undo_stack
        self.setWindowTitle("Auto-Increment Elevations")
        self.setModal(True)

        # ------------------------------------------------------------------
        # Widgets – choose explicit end elevation *or* slope %
        # ------------------------------------------------------------------
        self._rad_end_elev = QRadioButton("End Elevation (ft)")
        self._rad_slope = QRadioButton("Slope (% rise)")
        self._rad_end_elev.setChecked(True)

        self._start_spin = QDoubleSpinBox()
        self._start_spin.setDecimals(3)
        self._start_spin.setRange(-9999, 9999)

        self._end_spin = QDoubleSpinBox()
        self._end_spin.setDecimals(3)
        self._end_spin.setRange(-9999, 9999)

        self._slope_spin = QDoubleSpinBox()
        self._slope_spin.setDecimals(3)
        self._slope_spin.setRange(-1000, 1000)
        self._slope_spin.setSuffix(" %")
        self._slope_spin.setEnabled(False)

        # Radio toggles enable/disable relevant spin boxes
        self._rad_end_elev.toggled.connect(self._on_mode_changed)

        # Layouts -----------------------------------------------------------
        form = QFormLayout()
        form.addRow(QLabel("Start Elevation (ft):"), self._start_spin)

        # End elevation row with inline radio
        end_row = QHBoxLayout()
        end_row.addWidget(self._rad_end_elev)
        end_row.addWidget(self._end_spin)
        form.addRow(end_row)

        # Slope row
        slope_row = QHBoxLayout()
        slope_row.addWidget(self._rad_slope)
        slope_row.addWidget(self._slope_spin)
        form.addRow(slope_row)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)

        main_layout = QVBoxLayout()
        main_layout.addLayout(form)
        main_layout.addWidget(buttons)
        self.setLayout(main_layout)

    # ------------------------------------------------------------------
    def _on_mode_changed(self, checked: bool):
        self._end_spin.setEnabled(checked)
        self._slope_spin.setEnabled(not checked)

    # ------------------------------------------------------------------
    def _apply(self):
        first_z = self._start_spin.value()
        if self._rad_end_elev.isChecked():
            last_z = self._end_spin.value()
            slope = None
        else:
            last_z = None
            slope = self._slope_spin.value()

        try:
            cmd = AutoIncrementZCommand(
                self._verts,
                first_z=first_z,
                last_z=last_z,
                slope_percent=slope,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid parameters", str(exc))
            return

        self._undo_stack.push(cmd)
        self.accept()
