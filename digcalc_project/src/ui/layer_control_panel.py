# digcalc_project/src/ui/layer_control_panel.py

import logging
from typing import List, Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, QRadioButton, QButtonGroup,
    QSizePolicy, QLabel, QScrollArea
)

# Use TYPE_CHECKING to avoid circular import at runtime
if TYPE_CHECKING:
    from src.ui.tracing_scene import TracingScene

class LayerControlPanel(QWidget):
    """
    A widget panel for controlling layer visibility and the active drawing layer
    in a TracingScene.
    """
    # Signal potentially useful for MainWindow if other actions depend on active layer
    # active_layer_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._tracing_scene: Optional['TracingScene'] = None
        self._layer_checkboxes: List[QCheckBox] = []
        self._active_layer_group: QButtonGroup = QButtonGroup(self)

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI elements for layer control."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5) # Reduced margins

        # --- Visibility Group ---
        visibility_groupbox = QGroupBox("Layer Visibility")
        self.visibility_layout = QVBoxLayout() # Content layout for checkboxes
        self.visibility_layout.setSpacing(2) # Compact spacing

        # Use QScrollArea to handle potentially many layers
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content_widget = QWidget()
        scroll_content_widget.setLayout(self.visibility_layout)
        scroll_area.setWidget(scroll_content_widget)
        scroll_area.setMinimumHeight(100) # Prevent collapsing too small

        visibility_groupbox_layout = QVBoxLayout()
        visibility_groupbox_layout.addWidget(scroll_area)
        visibility_groupbox.setLayout(visibility_groupbox_layout)

        # --- Active Layer Group ---
        active_layer_groupbox = QGroupBox("Active Drawing Layer")
        self.active_layer_layout = QVBoxLayout()
        self.active_layer_layout.setSpacing(2) # Compact spacing
        active_layer_groupbox.setLayout(self.active_layer_layout)

        main_layout.addWidget(visibility_groupbox)
        main_layout.addWidget(active_layer_groupbox)
        main_layout.addStretch() # Push groups to the top

        self.setLayout(main_layout)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)


    def set_tracing_scene(self, scene: Optional['TracingScene']):
        """
        Connects this panel to a TracingScene instance to control its layers.
        Populates the UI based on the layers defined in the scene.
        """
        self._tracing_scene = scene
        self._populate_layer_controls()

    def _clear_layout(self, layout):
        """Helper to remove all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_layer_controls(self):
        """Populate checkboxes and radio buttons based on scene layers."""
        # Clear existing controls
        self._clear_layout(self.visibility_layout)
        self._clear_layout(self.active_layer_layout)
        self._layer_checkboxes.clear()
        # Need to recreate buttongroup or remove buttons
        for button in self._active_layer_group.buttons():
            self._active_layer_group.removeButton(button)

        if not self._tracing_scene:
            self.visibility_layout.addWidget(QLabel("No scene connected."))
            self.active_layer_layout.addWidget(QLabel("No scene connected."))
            return

        layer_names = self._tracing_scene.get_layers()
        active_layer = self._tracing_scene.get_active_layer()

        if not layer_names:
            self.visibility_layout.addWidget(QLabel("No layers defined in scene."))
            self.active_layer_layout.addWidget(QLabel("No layers defined in scene."))
            return

        for i, name in enumerate(layer_names):
            # Visibility Checkbox
            checkbox = QCheckBox(name)
            checkbox.setChecked(True) # Default to visible
            checkbox.stateChanged.connect(lambda state, n=name: self._on_visibility_changed(n, state))
            self.visibility_layout.addWidget(checkbox)
            self._layer_checkboxes.append(checkbox)

            # Active Layer Radio Button
            radio_button = QRadioButton(name)
            radio_button.setProperty("layer_name", name) # Store name for signal handler
            self.active_layer_layout.addWidget(radio_button)
            self._active_layer_group.addButton(radio_button, i) # Add with an ID

            if name == active_layer:
                radio_button.setChecked(True)

        # Add stretch at the end of layouts to push items up
        self.visibility_layout.addStretch()
        self.active_layer_layout.addStretch()

        # Connect button group signal AFTER populating
        self._active_layer_group.buttonClicked.connect(self._on_active_layer_changed)


    @Slot(int) # state can be 0 (Unchecked), 1 (PartiallyChecked), 2 (Checked)
    def _on_visibility_changed(self, layer_name: str, state: int):
        """Slot called when a layer visibility checkbox state changes."""
        if self._tracing_scene:
            is_visible = (state == Qt.Checked)
            self._tracing_scene.set_layer_visibility(layer_name, is_visible)

    @Slot(QRadioButton)
    def _on_active_layer_changed(self, radio_button: QRadioButton):
        """Slot called when the active layer radio button selection changes."""
        if self._tracing_scene and radio_button.isChecked():
             layer_name = radio_button.property("layer_name")
             if layer_name:
                 self._tracing_scene.set_active_layer(layer_name)
                 # self.active_layer_changed.emit(layer_name) # Emit if needed


    def update_ui_from_scene(self):
        """Updates the UI controls to match the current state of the TracingScene."""
        if not self._tracing_scene:
            return

        active_layer = self._tracing_scene.get_active_layer()
        # Update active layer radio buttons
        for button in self._active_layer_group.buttons():
            if button.property("layer_name") == active_layer:
                # block signals? Not strictly necessary if handler checks isChecked()
                button.setChecked(True)
                break

        # Update visibility checkboxes (less critical unless state can change outside UI)
        # for checkbox in self._layer_checkboxes:
        #      layer_name = checkbox.text()
        #      if layer_name in self._tracing_scene._layer_groups:
        #         is_visible = self._tracing_scene._layer_groups[layer_name].isVisible()
        #         checkbox.setChecked(is_visible)

        # ... rest of the method remains unchanged ... 