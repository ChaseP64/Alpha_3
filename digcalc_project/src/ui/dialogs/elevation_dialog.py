#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialog to prompt user for a constant elevation value."""

import logging
from PySide6 import QtWidgets, QtCore
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level variable to remember the last entered elevation
_LAST_ELEV: float = 0.0


class ElevationDialog(QtWidgets.QDialog):
    """A simple dialog to get a constant elevation from the user."""

    def __init__(self, parent=None, initial_value: Optional[float] = None):
        """Initializes the dialog.

        Args:
            parent (QWidget, optional): Parent widget. Defaults to None.
            initial_value (float, optional): Initial value for the spinbox. 
                                           If None, uses the last remembered value.
        """
        super().__init__(parent)
        global _LAST_ELEV

        # Determine the starting value
        start_value = initial_value if initial_value is not None else _LAST_ELEV

        self.setWindowTitle("Enter Constant Elevation")
        self.setModal(True)

        # Widgets
        self._label = QtWidgets.QLabel("Constant elevation (ft):")
        self._spinbox = QtWidgets.QDoubleSpinBox()
        self._spinbox.setRange(-10000.00, 10000.00)
        self._spinbox.setDecimals(2)
        self._spinbox.setValue(start_value) # Use determined start value
        self._spinbox.selectAll() # Select text for easy replacement

        self._buttonbox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        h_layout = QtWidgets.QHBoxLayout()
        h_layout.addWidget(self._label)
        h_layout.addWidget(self._spinbox)
        layout.addLayout(h_layout)
        layout.addWidget(self._buttonbox)
        self.setLayout(layout)

        # Connections
        self._buttonbox.accepted.connect(self.accept)
        self._buttonbox.rejected.connect(self.reject)
        self.accepted.connect(self._update_last_elevation) # Update memory on accept

        logger.debug("ElevationDialog initialized with value: %.2f", start_value)

    def value(self) -> float:
        """Returns the current value in the spin box."""
        return self._spinbox.value()

    def _update_last_elevation(self):
        """Stores the accepted value for the next time the dialog is opened."""
        global _LAST_ELEV
        _LAST_ELEV = self.value()
        logger.debug("Stored last elevation value: %.2f", _LAST_ELEV)

# Example Usage (for testing the dialog directly)
if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)
    app = QtWidgets.QApplication(sys.argv)
    dialog = ElevationDialog()
    result = dialog.exec()
    if result == QtWidgets.QDialog.Accepted:
        print(f"Dialog accepted, value: {dialog.value():.2f}")
        print(f"Next dialog default will be: {_LAST_ELEV:.2f}")
        # Open again to test default
        dialog2 = ElevationDialog()
        dialog2.exec()
    else:
        print("Dialog cancelled.")
    sys.exit() 