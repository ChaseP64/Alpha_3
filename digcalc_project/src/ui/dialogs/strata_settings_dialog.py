from __future__ import annotations

"""StrataSettingsDialog – allows editing of IDW interpolation parameters.

Fields:
    • IDW power (int 1-5)
    • Search radius (float, project units)
    • Max grid cell size (float)

Values persist via SettingsService automatically on dialog accept.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
)

from ...services.settings_service import SettingsService


class StrataSettingsDialog(QDialog):
    """Modal preferences page for Strata interpolation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Strata Settings")
        self._settings = SettingsService()
        self._init_ui()
        self._load_values()

    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        form = QFormLayout(self)

        # IDW power
        self._spin_power = QSpinBox(self)
        self._spin_power.setRange(1, 5)
        form.addRow("IDW Power", self._spin_power)

        # Radius
        self._spin_radius = QDoubleSpinBox(self)
        self._spin_radius.setRange(1.0, 1e6)
        self._spin_radius.setDecimals(1)
        self._spin_radius.setSuffix(" ft")
        form.addRow("Search radius", self._spin_radius)

        # Max cell size
        self._spin_cell = QDoubleSpinBox(self)
        self._spin_cell.setRange(0.1, 1000.0)
        self._spin_cell.setDecimals(1)
        self._spin_cell.setSuffix(" ft")
        form.addRow("Max grid cell", self._spin_cell)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    # ------------------------------------------------------------------
    def _load_values(self) -> None:
        self._spin_power.setValue(self._settings.strata_idw_power)
        self._spin_radius.setValue(self._settings.strata_idw_radius)
        self._spin_cell.setValue(self._settings.strata_default_cell_size)

    # ------------------------------------------------------------------
    def accept(self) -> None:  # noqa: D401
        """Persist settings then close."""
        self._settings.set("strata", "idw_power", int(self._spin_power.value()))
        self._settings.set("strata", "idw_radius_ft", float(self._spin_radius.value()))
        self._settings.set("strata", "default_cell_size_ft", float(self._spin_cell.value()))
        super().accept()
