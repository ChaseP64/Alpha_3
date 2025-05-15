#!/usr/bin/env python3
"""Pad Elevation dialog.

Provides a simple interface for the user to enter a pad elevation and optionally
apply that elevation to all pads created during the current session.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_LAST_PAD_ELEV: float = 0.0  # Remember the last entered elevation this session


class PadElevationDialog(QDialog):
    """Modal dialog to request a pad elevation from the user."""

    def __init__(self, last_value: Optional[float] | None = None, parent=None):
        super().__init__(parent)
        global _LAST_PAD_ELEV

        # Determine the value to show in the spin-box
        start_value = last_value if last_value is not None else _LAST_PAD_ELEV

        self.setWindowTitle("Pad Elevation")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(True)

        # --- Elevation spin-box ------------------------------------------------
        self._elev = QDoubleSpinBox(decimals=2)
        self._elev.setRange(-9999.0, 9999.0)
        self._elev.setSingleStep(0.1)
        self._elev.setSuffix(" ft")
        self._elev.setValue(start_value)
        self._elev.selectAll()

        # --- Apply-all checkbox ----------------------------------------------
        self._apply_all = QCheckBox("Apply to all pads in this session")

        # ---------------------------------------------------------------------
        # Layout
        # ---------------------------------------------------------------------
        form = QFormLayout()
        form.addRow("Elevation:", self._elev)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.accepted.connect(self._update_last_value)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self._apply_all)
        lay.addWidget(buttons)
        self.setLayout(lay)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def value(self) -> float:
        """Return the elevation entered by the user (in feet)."""
        return self._elev.value()

    def apply_to_all(self) -> bool:
        """Return *True* if the user checked "apply to all"."""
        return self._apply_all.isChecked()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_last_value(self) -> None:
        """Cache the accepted value for the next dialog instance."""
        global _LAST_PAD_ELEV
        _LAST_PAD_ELEV = self.value()
        logger.debug("Stored last pad elevation value: %.2f", _LAST_PAD_ELEV)
