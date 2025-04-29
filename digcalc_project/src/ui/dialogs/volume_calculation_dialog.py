import logging
from typing import Optional, Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QComboBox, QLabel, QDoubleSpinBox, QFormLayout, 
    QDialogButtonBox, QWidget, QSizePolicy, QCheckBox
)
import numpy as np

class VolumeCalculationDialog(QDialog):
    """Dialog for selecting surfaces and parameters for volume calculation."""
    # volumeComputed = Signal(float, float, float, np.ndarray, np.ndarray, np.ndarray, bool) # Removed unused signal

    def __init__(self, surface_names: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Calculate Volumes")
        self.surface_names = surface_names
        self.setMinimumWidth(350) # Set a minimum width
        self.logger = logging.getLogger(__name__) # Added logger

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(10)

        # --- Surface Selection ---
        self.combo_existing = QComboBox(self)
        self.combo_existing.addItems(self.surface_names)
        self.combo_existing.setToolTip("Select the surface representing the original ground or starting condition.")
        form_layout.addRow("Existing Surface:", self.combo_existing)

        self.combo_proposed = QComboBox(self)
        self.combo_proposed.addItems(self.surface_names)
        self.combo_proposed.setToolTip("Select the surface representing the final grade or proposed design.")
        form_layout.addRow("Proposed Surface:", self.combo_proposed)

        # ------------------------------------------------------------
        # Include synthesized *Lowest* surface if available
        # ------------------------------------------------------------
        controller = None
        if parent is not None and hasattr(parent, "project_controller"):
            controller = getattr(parent, "project_controller")

        if controller is not None and getattr(controller, "lowest_surface", None):
            if controller.lowest_surface():
                # Append to both combo-boxes so users can pick it as either
                self.combo_existing.addItem("Lowest")
                self.combo_proposed.addItem("Lowest")

        # --- Grid Resolution ---
        self.spin_resolution = QDoubleSpinBox(self)
        self.spin_resolution.setRange(0.1, 1000.0) # Sensible range
        self.spin_resolution.setValue(5.0) # Default value
        self.spin_resolution.setDecimals(2)
        self.spin_resolution.setSingleStep(0.5)
        self.spin_resolution.setToolTip("Specify the size of the grid cells for volume calculation (e.g., 5.0 means 5x5 units). Smaller values increase accuracy but take longer.")
        form_layout.addRow("Grid Resolution (units):", self.spin_resolution)

        # --- Cut/Fill Map Option ---
        self.check_generate_map = QCheckBox("Generate cut/fill map", self)
        self.check_generate_map.setChecked(True) # Default to checked
        self.check_generate_map.setToolTip("Generate a visual representation of cut (red) and fill (blue) areas.")
        form_layout.addRow(self.check_generate_map) # Add checkbox to layout

        # Align labels to the right
        for i in range(form_layout.rowCount()):
            label_item = form_layout.itemAt(i, QFormLayout.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Handle checkbox alignment if it spans both columns
            widget_item = form_layout.itemAt(i, QFormLayout.FieldRole)
            if isinstance(widget_item.widget(), QCheckBox):
                 # Reset alignment or specific handling if needed, currently adds to FieldRole
                 pass

        layout.addLayout(form_layout)

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Connect signals for validation
        self.combo_existing.currentIndexChanged.connect(self._validate_selection)
        self.combo_proposed.currentIndexChanged.connect(self._validate_selection)
        self._validate_selection() # Initial validation
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.adjustSize() # Adjust size to fit contents

    def _validate_selection(self):
        """Enable OK button only if different surfaces are selected."""
        valid = (self.combo_existing.currentText() != self.combo_proposed.currentText())
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(valid)
        if not valid and len(self.surface_names) > 1:
            # Optional: Log warning or provide non-modal feedback
            # self.logger.debug("Validation failed: Same surface selected.")
            pass 

    def get_selected_surfaces(self) -> Optional[Dict[str, str]]:
        """Get the names of the selected existing and proposed surfaces."""
        # Re-check validation state on retrieval
        valid = (self.combo_existing.currentText() != self.combo_proposed.currentText())
        if valid and self.combo_existing.currentText() and self.combo_proposed.currentText():
             return {
                 'existing': self.combo_existing.currentText(),
                 'proposed': self.combo_proposed.currentText()
             }
        elif not valid:
             self.logger.warning("Attempted to get selection when validation failed (surfaces are the same).")
        return None

    def get_grid_resolution(self) -> float:
        """Get the selected grid resolution."""
        return self.spin_resolution.value()

    def should_generate_map(self) -> bool:
        """Check if the cut/fill map generation is requested."""
        return self.check_generate_map.isChecked()

    # ------------------------------------------------------------------
    # Accept override – ensure *Lowest* resolves to actual Surface object
    # ------------------------------------------------------------------
    def accept(self):  # noqa: D401
        """Re-implement accept to resolve the *Lowest* placeholder.

        The MainWindow currently queries :py:meth:`get_selected_surfaces` after
        ``exec()``.  We'll therefore stash a mapping of selected combo-box
        names to actual :class:`~digcalc_project.models.surface.Surface`
        instances so external code can fetch them.
        """
        super().accept()

    # Convenience for callers -------------------------------------------------
    def resolve_surface(self, name: str):
        """Return the actual Surface corresponding to *name*.

        This method relies on having access to the parent MainWindowʼs
        ``project_controller``.
        """
        parent = self.parent()  # MainWindow
        if parent is not None and hasattr(parent, "project_controller"):
            controller = parent.project_controller
            project = controller.get_current_project()
            if name == "Lowest":
                return controller.lowest_surface()
            if project:
                return project.get_surface(name)
        return None

    # Note: The actual calculation and signal emission would typically happen
    # in the MainWindow after the dialog is accepted and surfaces are retrieved.
    # This dialog class itself usually doesn't perform the calculation.
    # If the calculation logic *is* meant to be here (less common),
    # it would need access to the actual Surface objects.
    # Assuming calculation happens externally, this dialog only provides parameters.

    # Example of how signal *would* be emitted if calculation was internal:
    # def _perform_calculation_and_emit(self, existing_surf, proposed_surf):
    #     resolution = self.get_grid_resolution()
    #     generate_map = self.should_generate_map()
    #     # ... call calculation function (e.g., grid_method) ...
    #     # cut, fill, net, dz_grid, grid_x, grid_y = calculate_stuff(...)
    #     if generate_map and dz_grid is not None:
    #          self.volumeComputed.emit(cut, fill, net, dz_grid, grid_x, grid_y, True)
    #     else:
    #          # Emit without dz data if map not generated or calculation failed
    #          self.volumeComputed.emit(cut, fill, net, np.array([]), np.array([]), np.array([]), False) 