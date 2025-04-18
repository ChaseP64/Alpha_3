# digcalc_project/src/ui/dialogs/build_surface_dialog.py

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, QDialogButtonBox,
    QWidget
)
from PySide6.QtCore import Slot, Qt

# --- Standard try/except import ---
try:
    from ...models.project import Project
    logger.debug("Successfully imported Project model.")
except ImportError:
    logger.error("Failed relative import of Project model. Defining as object.", exc_info=True)
    Project = object # Define as object if import fails
# --- End Import ---

class BuildSurfaceDialog(QDialog):
    """
    Dialog for selecting the source layer and naming the new surface
    to be built from traced polylines.
    """
    # --- Use the potentially imported Project or fallback object ---
    def __init__(self, project: Optional[Project], parent: Optional[QWidget] = None):
    # --- END ---
        super().__init__(parent)
        self.setWindowTitle("Build Surface from Layer")

        # --- Simplified Runtime Check ---
        # Check if the loaded 'Project' is the actual class or the fallback 'object'
        self._project_model_available = Project is not object
        if not self._project_model_available:
             logger.critical("Project model could not be imported. Dialog cannot function properly.")
             self.project = None
        else:
             # Perform isinstance check against the imported Project class
             if project is not None and not isinstance(project, Project):
                 logger.error(f"Incorrect type passed for project: expected {Project}, got {type(project)}")
                 self.project = None
             else:
                 self.project = project
        # --- END Simplified Check ---
        self.setMinimumWidth(350)

        # --- UI Elements ---
        self.layer_combo = QComboBox(self)
        self.layer_combo.setToolTip("Select the layer containing polylines with elevation data.")

        self.name_edit = QLineEdit(self)
        self.name_edit.setToolTip("Enter a name for the new surface.")

        # --- Layout ---
        form_layout = QFormLayout()
        form_layout.addRow("Source Layer:", self.layer_combo)
        form_layout.addRow("New Surface Name:", self.name_edit)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # --- Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.button_box)

        # --- Populate and Connect ---
        self._populate_layers() # Uses self._project_model_available now
        self.layer_combo.currentTextChanged.connect(self._update_default_name)
        self._update_default_name(self.layer_combo.currentText())
        self._validate() # Uses self._project_model_available now
        self.layer_combo.currentIndexChanged.connect(self._validate)
        self.name_edit.textChanged.connect(self._validate)

        logger.debug("BuildSurfaceDialog initialized.")

    def _populate_layers(self):
        """Populates the layer combo box with layers containing traced polylines."""
        self.layer_combo.clear()
        layers_found = []
        # --- FIX: Use self._project_model_available flag ---
        # if self.project and _ProjectModel and self.project.traced_polylines:
        if self.project and self._project_model_available and self.project.traced_polylines:
        # --- END FIX ---
            for layer_name, polylines in self.project.traced_polylines.items():
                # Add safety check for dictionary format inside loop
                has_elevation = any(p.get('elevation') is not None for p in polylines if isinstance(p, dict))
                if has_elevation:
                    layers_found.append(layer_name)
                else:
                    logger.debug(f"Layer '{layer_name}' skipped (no polylines with elevation)." )

        if layers_found:
            self.layer_combo.addItems(sorted(layers_found))
            self.layer_combo.setEnabled(True)
        else:
            if not self._project_model_available:
                 placeholder = "<Project model error>"
            elif not self.project:
                 placeholder = "<No project>"
            else: # Project exists, but no suitable layers found
                 placeholder = "<No layers with elevation data>"
            self.layer_combo.addItem(placeholder)
            self.layer_combo.setEnabled(False)

        logger.debug(f"Populated layer combo with: {self.layer_combo.count()} items.")

    @Slot(str)
    def _update_default_name(self, layer_name: str):
        """Updates the default surface name based on the selected layer."""
        # --- FIX: Check project existence and model availability ---
        # if layer_name and not layer_name.startswith("<") and self.project and _ProjectModel:
        if layer_name and not layer_name.startswith("<") and self.project and self._project_model_available:
        # --- END FIX ---
            default_name = f"{layer_name}_Surface"
            current_text = self.name_edit.text()
            is_default_pattern = current_text.endswith("_Surface") and \
                                (self.project and current_text[:-8] in self.project.traced_polylines)
            if not current_text or is_default_pattern:
                 self.name_edit.setText(default_name)
            logger.debug(f"Default surface name potentially updated to: {default_name}")
        elif not layer_name or layer_name.startswith("<"):
             self.name_edit.clear()

    @Slot()
    def _validate(self):
        """Enable OK button only if a valid layer and name are provided."""
        selected_layer = self.layer()
        surface_name = self.surface_name()
        is_layer_valid = selected_layer is not None
        is_name_valid = bool(surface_name)
        is_name_unique = True
        # --- FIX: Check project existence and model availability ---
        # if self.project and _ProjectModel and is_name_valid:
        if self.project and self._project_model_available and is_name_valid:
        # --- END FIX ---
            is_name_unique = surface_name not in self.project.surfaces

        can_accept = is_layer_valid and is_name_valid and is_name_unique
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(can_accept)

        tooltip = ""
        if not is_layer_valid:
            tooltip = "Please select a source layer with elevation data."
        elif not is_name_valid:
            tooltip = "Please enter a name for the new surface."
        elif not is_name_unique:
            # Ensure f-string is clean
            tooltip = f"A surface named '{surface_name}' already exists."
        else:
            tooltip = "Create the surface."
        self.button_box.button(QDialogButtonBox.Ok).setToolTip(tooltip)

    # --- Public Getters ---
    def layer(self) -> Optional[str]:
        """Returns the selected source layer name, or None if invalid."""
        current_text = self.layer_combo.currentText()
        if self.layer_combo.isEnabled() and current_text and not current_text.startswith("<"):
            return current_text
        return None

    def surface_name(self) -> str:
        """Returns the entered surface name, stripped of whitespace."""
        return self.name_edit.text().strip() 