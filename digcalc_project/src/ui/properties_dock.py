# digcalc_project/src/ui/properties_dock.py

import logging
from typing import Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QLabel, QDoubleSpinBox, QFormLayout, QDialogButtonBox,
    QWidget, QVBoxLayout
)

# Define module-level logger
logger = logging.getLogger(__name__)

class PropertiesDock(QDockWidget):
    """
    A dock widget to display and edit properties of selected items,
    specifically the elevation of traced polylines.
    """
    # Signal emitted when the 'Apply' button is clicked.
    # Arguments: layer_name (str), polyline_index (int), new_elevation (float)
    edited = Signal(str, int, float)

    def __init__(self, parent=None):
        """Initialize the PropertiesDock."""
        super().__init__("Properties", parent)
        self.setObjectName("PropertiesDock") # Important for saving/restoring state
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)

        # --- UI Elements ---
        self._layer_label = QLabel()
        self._layer_label.setText("<i>None selected</i>") # Initial placeholder

        self._elev_spin = QDoubleSpinBox()
        self._elev_spin.setRange(-10000, 10000)
        self._elev_spin.setDecimals(2)
        self._elev_spin.setSuffix(" ft") # Added unit suffix
        self._elev_spin.setToolTip("Enter the constant elevation for this polyline.")
        self._elev_spin.setEnabled(False) # Disabled until an item is loaded

        # --- Layout ---
        form_layout = QFormLayout()
        form_layout.addRow("Layer:", self._layer_label)
        form_layout.addRow("Elevation:", self._elev_spin)

        form_widget = QWidget()
        form_widget.setLayout(form_layout)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)

        # --- FIX: Connect specific button signals --- 
        apply_button = button_box.button(QDialogButtonBox.Apply)
        cancel_button = button_box.button(QDialogButtonBox.Cancel)

        if apply_button:
            apply_button.setEnabled(False) # Disabled initially
            apply_button.clicked.connect(self._apply) # Connect clicked signal
        else:
            logger.error("Could not find Apply button in PropertiesDock button box.")

        if cancel_button:
            cancel_button.clicked.connect(self._cancel) # Connect clicked signal
        else:
            logger.error("Could not find Cancel button in PropertiesDock button box.")
        # Remove old connections if they existed
        # try: button_box.accepted.disconnect(self._apply) 
        # except RuntimeError: pass 
        # try: button_box.rejected.disconnect(self._cancel) 
        # except RuntimeError: pass 
        # --- END FIX --- 

        # --- Main Container ---
        vbox = QVBoxLayout()
        vbox.addWidget(form_widget)
        vbox.addWidget(button_box)
        vbox.addStretch() # Push content to the top

        container_widget = QWidget()
        container_widget.setLayout(vbox)
        self.setWidget(container_widget)

        # --- State ---
        self._current_item_info: Optional[Tuple[str, int]] = None # tuple(layer_name, index)

        # Use module-level logger
        logger.debug("PropertiesDock initialized.")

    def load_polyline(self, layer_name: str, index: int, elevation: Optional[float]):
        """
        Loads the properties of a selected polyline into the dock.

        Args:
            layer_name (str): The name of the layer the polyline belongs to.
            index (int): The index of the polyline within its layer list.
            elevation (Optional[float]): The current elevation of the polyline.
        """
        self._layer_label.setText(f"<b>{layer_name}</b> (Index: {index})") # Display layer and index
        # Ensure elevation is treated as float, handle None
        current_elevation = float(elevation) if elevation is not None else 0.0
        self._elev_spin.setValue(current_elevation)
        self._elev_spin.setEnabled(True) # Enable editing
        self.widget().findChild(QDialogButtonBox).button(QDialogButtonBox.Apply).setEnabled(True) # Enable Apply

        self._current_item_info = (layer_name, index)
        # Use module-level logger
        logger.debug(f"Loaded polyline: Layer='{layer_name}', Index={index}, Elevation={elevation}")
        if not self.isVisible():
             self.show() # Ensure dock is visible only if hidden

    def clear_selection(self):
        """Clears the displayed properties and disables editing."""
        self._layer_label.setText("<i>None selected</i>")
        self._elev_spin.setValue(0.0)
        self._elev_spin.setEnabled(False)
        self.widget().findChild(QDialogButtonBox).button(QDialogButtonBox.Apply).setEnabled(False)
        self._current_item_info = None
        # Use module-level logger
        logger.debug("Properties dock cleared.")
        # self.hide() # Optionally hide when selection is cleared

    def _apply(self):
        """Emits the 'edited' signal with the current values and hides the dock."""
        if self._current_item_info:
            layer, idx = self._current_item_info
            new_elevation = self._elev_spin.value()
            logger.info(f"Apply clicked: Layer='{layer}', Index={idx}, New Elevation={new_elevation:.2f}")
            self.edited.emit(layer, idx, new_elevation)
            self.hide()
        else:
            logger.warning("Apply clicked but no item information is loaded.")

    def _cancel(self):
        """Hides the dock without applying changes."""
        # Use module-level logger
        logger.debug("Cancel clicked, hiding dock.")
        self.clear_selection() # Clear the display
        self.hide() # Hide the dock 