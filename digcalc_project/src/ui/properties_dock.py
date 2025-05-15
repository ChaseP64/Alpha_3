# digcalc_project/src/ui/properties_dock.py

import logging
from typing import Any, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsPathItem,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# New import for ToggleSmoothCommand
from digcalc_project.src.ui.commands.toggle_smooth_command import ToggleSmoothCommand

# New import for vertex items
from digcalc_project.src.ui.items.vertex_item import VertexItem

# Relative imports
from ..models.region import Region
from ..services.settings_service import SettingsService

# Define module-level logger
logger = logging.getLogger(__name__)

class PropertiesDock(QDockWidget):
    """A dock widget to display and edit properties of selected items.
    Uses tabs for different item types (Polyline, Region).
    """

    # Signals emitted when the 'Apply' button is clicked for each type.
    polylineEdited = Signal(str, int, float) # layer_name, polyline_index, new_elevation
    regionUpdated = Signal(Region)           # Updated Region object
    # Signal emitted when a setting affecting rebuilds is changed
    settingsChanged = Signal()

    def __init__(self, parent=None):
        """Initialize the PropertiesDock."""
        super().__init__("Properties", parent)
        self.setObjectName("PropertiesDock") # Important for saving/restoring state
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)

        # --- Main Tab Widget ---
        self.tabs = QTabWidget()
        self.setWidget(self.tabs)

        # --- State ---
        self._current_polyline_info: Optional[Tuple[str, int]] = None # tuple(layer_name, index)
        self._current_region: Optional[Region] = None # Currently selected Region object

        # --- Initialize Tabs ---
        self._create_polyline_tab()
        self._create_region_tab()
        self._create_vertex_tab()
        self._create_tracing_tab()

        # --- Hide initially ---
        self.tabs.setCurrentIndex(0) # Show Polyline tab by default if needed
        self.hide()

        # Use module-level logger
        logger.debug("PropertiesDock initialized with tabs.")

    def _create_polyline_tab(self):
        """Creates the QWidget and layout for the Polyline properties tab."""
        self.polyline_tab = QWidget()
        layout = QVBoxLayout(self.polyline_tab)
        form_layout = QFormLayout()

        # --- UI Elements ---
        self._polyline_layer_label = QLabel("<i>None selected</i>")
        self._polyline_elev_spin = QDoubleSpinBox()
        self._polyline_elev_spin.setRange(-10000, 10000)
        self._polyline_elev_spin.setDecimals(2)
        self._polyline_elev_spin.setSuffix(" ft")
        self._polyline_elev_spin.setToolTip("Enter the constant elevation for this polyline.")
        self._polyline_elev_spin.setEnabled(False)

        # --- Smooth checkbox ---
        self.smooth_chk = QCheckBox("Smooth (Spline)")
        form_layout.addRow(self.smooth_chk)
        self.smooth_chk.stateChanged.connect(self._apply_polyline_smooth)

        form_layout.addRow("Layer:", self._polyline_layer_label)
        form_layout.addRow("Elevation:", self._polyline_elev_spin)

        # --- Buttons ---
        # Using Apply/Cancel for consistency, though maybe just Apply is needed?
        polyline_button_box = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        apply_button = polyline_button_box.button(QDialogButtonBox.Apply)
        cancel_button = polyline_button_box.button(QDialogButtonBox.Cancel)

        if apply_button:
            apply_button.setEnabled(False)
            apply_button.clicked.connect(self._apply_polyline)
        if cancel_button:
            cancel_button.clicked.connect(self._cancel) # Generic cancel hides dock

        # --- Layout ---
        layout.addLayout(form_layout)
        layout.addWidget(polyline_button_box)
        layout.addStretch()

        self.tabs.addTab(self.polyline_tab, "Polyline")

    def _create_region_tab(self):
        """Creates the QWidget and layout for the Region properties tab."""
        self.region_tab = QWidget()
        layout = QVBoxLayout(self.region_tab)
        form_layout = QFormLayout()

        # --- UI Elements ---
        self.region_name_edit = QLineEdit()
        self.region_name_edit.setToolTip("Enter a name for this region.")

        self.region_strip_depth_spin = QDoubleSpinBox()
        self.region_strip_depth_spin.setRange(0.0, 20.0) # Range 0-20 ft
        self.region_strip_depth_spin.setDecimals(1)      # 0.1 steps
        self.region_strip_depth_spin.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        self.region_strip_depth_spin.setSuffix(" ft")
        # Use special value text to indicate default
        self.region_strip_depth_spin.setSpecialValueText("(Default)")
        # Set minimum to a value slightly below 0 to allow setting 0 explicitly
        # Or rely on the special value text. Let's try the latter first.
        # self.region_strip_depth_spin.setMinimum(-0.01) # Alternative approach
        self.region_strip_depth_spin.setToolTip("Stripping depth (leave as '(Default)' to use global setting).")
        self.region_strip_depth_spin.setEnabled(False)
        self.region_name_edit.setEnabled(False)

        form_layout.addRow("Name:", self.region_name_edit)
        form_layout.addRow("Stripping depth:", self.region_strip_depth_spin)

        # --- Buttons ---
        region_apply_button = QPushButton("Apply Region Changes")
        region_apply_button.setEnabled(False)
        region_apply_button.clicked.connect(self._apply_region_changes)
        # Maybe add cancel button too? For now, just Apply.

        # --- Layout ---
        layout.addLayout(form_layout)
        layout.addWidget(region_apply_button)
        layout.addStretch()

        self.tabs.addTab(self.region_tab, "Region")
        # Store refs needed later
        self._region_apply_button = region_apply_button

    def _create_vertex_tab(self):
        """Creates the tab for editing VertexItem elevation."""
        from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QPushButton

        self.vertex_tab = QWidget()
        vlay = QFormLayout(self.vertex_tab)

        self.vertex_z_spin = QDoubleSpinBox()
        self.vertex_z_spin.setDecimals(3)
        self.vertex_z_spin.setRange(-9999, 9999)
        self.vertex_z_spin.setSingleStep(0.1)
        self.vertex_z_spin.setSuffix(" ft")

        self.vertex_apply_btn = QPushButton("Apply")
        self.vertex_apply_btn.clicked.connect(self._apply_vertex_z)

        vlay.addRow("Elevation (ft):", self.vertex_z_spin)
        vlay.addRow(self.vertex_apply_btn)

        self.tabs.addTab(self.vertex_tab, "Vertex")

        # Internal state holder
        self._current_vertex: VertexItem | None = None

        # Start disabled – becomes active only when a single vertex is selected
        self.vertex_tab.setEnabled(False)

    def _create_tracing_tab(self):
        """Creates the QWidget and layout for the Tracing settings tab."""
        self.tracing_tab = QWidget()
        layout = QVBoxLayout(self.tracing_tab)
        form_layout = QFormLayout()

        settings = SettingsService()

        # --- UI Elements ---
        # Spline sample spacing
        self._spline_sampling_spin = QDoubleSpinBox()
        self._spline_sampling_spin.setRange(0.1, 10.0)
        self._spline_sampling_spin.setDecimals(1) # Match range step
        self._spline_sampling_spin.setSingleStep(0.1)
        self._spline_sampling_spin.setSuffix(" ft")
        self._spline_sampling_spin.setToolTip("Distance between samples along smoothed polylines (splines).")
        self._spline_sampling_spin.setValue(settings.smooth_sampling_ft())
        self._spline_sampling_spin.valueChanged.connect(self._update_smooth_sampling)

        # Elevation prompt mode
        self._elev_mode_combo = QComboBox()
        self._elev_mode_combo.setToolTip("How elevation is prompted for during polyline tracing.")
        # Add items with user data
        self._elev_mode_combo.addItem("Point-by-point", userData="point")
        self._elev_mode_combo.addItem("First/last (interpolate)", userData="interpolate")
        self._elev_mode_combo.addItem("Whole line", userData="line")

        # Set initial value
        current_mode = settings.tracing_elev_mode()
        index = self._elev_mode_combo.findData(current_mode)
        if index != -1:
            self._elev_mode_combo.setCurrentIndex(index)
        else: # Default to point-by-point if setting is somehow invalid
             logger.warning(f"Invalid tracing_elev_mode '{current_mode}' in settings, defaulting.")
             self._elev_mode_combo.setCurrentIndex(self._elev_mode_combo.findData("point"))

        self._elev_mode_combo.currentIndexChanged.connect(self._update_tracing_mode)

        # --- Vertex cross size (px) ---
        self._vertex_size_spin = QSpinBox()
        self._vertex_size_spin.setRange(2, 20)
        self._vertex_size_spin.setSuffix(" px")
        self._vertex_size_spin.setValue(settings.vertex_cross_px())
        self._vertex_size_spin.valueChanged.connect(self._update_vertex_size)
        form_layout.addRow("Vertex cross half-px:", self._vertex_size_spin)

        # --- Vertex line thickness ---
        self._vertex_line_spin = QSpinBox()
        self._vertex_line_spin.setRange(0, 5)
        self._vertex_line_spin.setValue(settings.vertex_line_thickness())
        self._vertex_line_spin.valueChanged.connect(self._update_vertex_line)
        form_layout.addRow("Vertex line width:", self._vertex_line_spin)

        # --- Hover colour (hex) ---
        self._hover_colour_edit = QLineEdit(settings.vertex_hover_colour())
        self._hover_colour_edit.setMaxLength(7)
        self._hover_colour_edit.setToolTip("Hover colour as #RRGGBB")
        self._hover_colour_edit.editingFinished.connect(self._update_hover_colour)
        form_layout.addRow("Hover colour:", self._hover_colour_edit)

        # --- Layout ---
        layout.addLayout(form_layout)
        layout.addStretch()

        self.tabs.addTab(self.tracing_tab, "Tracing")
        logger.debug("Tracing settings tab created.")

    def update_for_selection(self, item: Optional[Any]):
        """Updates the displayed properties based on the selected item type."""
        # Clear previous state
        self.clear_selection()

        # --- Handle VertexItem selection ---
        if isinstance(item, list) and len(item) == 1:
            itm0 = item[0]
            if isinstance(itm0, VertexItem):
                self.load_vertex(itm0)
                return

        if isinstance(item, VertexItem):
            self.load_vertex(item)
            return

        # Existing polyline / region logic
        if isinstance(item, tuple) and len(item) == 3:
            layer_name, index, elevation = item
            self.load_polyline(layer_name, index, elevation)
            self.tabs.setCurrentWidget(self.polyline_tab)
            if not self.isVisible():
                self.show()
            return

        if isinstance(item, Region):
            self.load_region(item)
            self.tabs.setCurrentWidget(self.region_tab)
            if not self.isVisible():
                self.show()
            return

        # If no specific item is selected, maybe show the tracing tab?
        # Or just hide as before.
        # Let's stick to hiding for now unless explicitly told otherwise.
        if not self.isVisible(): # Keep hidden if already hidden
             pass # self.hide()
        elif self.tabs.currentWidget() not in [self.polyline_tab, self.region_tab, self.vertex_tab]:
             # If some other tab was visible (e.g. Tracing), maybe keep it?
             # Let's reconsider this - standard behaviour is probably to hide if nothing relevant selected.
             self.hide()
        # Previous logic: self.hide() if no item matched. Let's restore that simplicity.
        self.hide()

    def load_polyline(self, layer_name: str, index: int, elevation: Optional[float]):
        """Loads polyline properties into the Polyline tab."""
        self._polyline_layer_label.setText(f"<b>{layer_name}</b> (Index: {index})")
        current_elevation = float(elevation) if elevation is not None else 0.0
        self._polyline_elev_spin.setValue(current_elevation)
        self._polyline_elev_spin.setEnabled(True)
        self.polyline_tab.findChild(QDialogButtonBox).button(QDialogButtonBox.Apply).setEnabled(True)
        self._current_polyline_info = (layer_name, index)
        # sync checkbox state
        # Attempt to find the polyline item in the scene via main window reference
        main_win = self.parent()
        while main_win and not hasattr(main_win, "undoStack"):
            main_win = main_win.parent()
        polyline_item = None
        if main_win and hasattr(main_win, "_selected_scene_item"):
            polyline_item = main_win._selected_scene_item
        self.smooth_chk.setChecked(bool(polyline_item and getattr(polyline_item, "mode", "entered") == "interpolated"))
        logger.debug(f"Loaded polyline: Layer='{layer_name}', Index={index}, Elevation={elevation}")

    def load_region(self, region: Region):
        """Loads region properties into the Region tab."""
        self._current_region = region
        self.region_name_edit.setText(region.name)
        if region.strip_depth_ft is None:
             # Display special text when depth is None (use default)
             self.region_strip_depth_spin.setValue(self.region_strip_depth_spin.minimum() - 1) # Hacky way to show special text
        else:
             self.region_strip_depth_spin.setValue(float(region.strip_depth_ft))

        # Enable editing
        self.region_name_edit.setEnabled(True)
        self.region_strip_depth_spin.setEnabled(True)
        self._region_apply_button.setEnabled(True)
        logger.debug(f"Loaded region: ID='{region.id}', Name='{region.name}', StripDepth={region.strip_depth_ft}")

    def clear_selection(self):
        """Clears all tabs and disables editing."""
        # Clear Polyline Tab
        self._polyline_layer_label.setText("<i>None selected</i>")
        self._polyline_elev_spin.setValue(0.0)
        self._polyline_elev_spin.setEnabled(False)
        apply_btn_poly = self.polyline_tab.findChild(QDialogButtonBox).button(QDialogButtonBox.Apply)
        if apply_btn_poly: apply_btn_poly.setEnabled(False)
        self._current_polyline_info = None

        # Clear Region Tab
        self.region_name_edit.clear()
        # Reset spinbox to show special value text
        self.region_strip_depth_spin.setValue(self.region_strip_depth_spin.minimum() -1)
        self.region_name_edit.setEnabled(False)
        self.region_strip_depth_spin.setEnabled(False)
        self._region_apply_button.setEnabled(False)
        self._current_region = None

        # Do NOT clear tracing tab widgets, they reflect global settings

        logger.debug("Properties dock cleared.")

    def _apply_polyline(self):
        """Emits the 'polylineEdited' signal with the current values."""
        if self._current_polyline_info:
            layer, idx = self._current_polyline_info
            new_elevation = self._polyline_elev_spin.value()
            logger.info(f"Apply Polyline: Layer='{layer}', Index={idx}, New Elev={new_elevation:.2f}")
            self.polylineEdited.emit(layer, idx, new_elevation)
            # self.hide() # Keep dock open after apply? User preference.
        else:
            logger.warning("Apply polyline clicked but no item information is loaded.")

    def _apply_region_changes(self):
        """Updates the current Region object and emits 'regionUpdated'."""
        if self._current_region:
            updated_region = self._current_region # Work on the stored region object
            old_name = updated_region.name
            old_depth = updated_region.strip_depth_ft

            # Get new name
            new_name = self.region_name_edit.text().strip()
            updated_region.name = new_name if new_name else "Unnamed Region" # Ensure name isn't empty

            # Get new strip depth
            # Check if the spinbox is showing the special value text
            if self.region_strip_depth_spin.text() == self.region_strip_depth_spin.specialValueText():
                new_depth = None # Use default
            else:
                new_depth = self.region_strip_depth_spin.value()

            updated_region.strip_depth_ft = new_depth

            logger.info(f"Apply Region: ID='{updated_region.id}', Name='{old_name}'->{updated_region.name}', Depth={old_depth}->{updated_region.strip_depth_ft}")
            self.regionUpdated.emit(updated_region)
            # self.hide() # Keep dock open?
        else:
            logger.warning("Apply region clicked but no region is loaded.")

    def _cancel(self):
        """Clears selection and hides the dock without applying changes."""
        logger.debug("Cancel clicked, clearing and hiding dock.")
        self.clear_selection()
        self.hide()

    def load_vertex(self, v: VertexItem):
        """Load a single :class:`VertexItem` into the Vertex tab for editing."""
        self._current_vertex = v
        self.vertex_z_spin.setValue(v.z())
        self.tabs.setCurrentWidget(self.vertex_tab)
        if not self.isVisible():
            self.show()

    def _apply_vertex_z(self):
        """Apply the elevation change for the currently loaded vertex."""
        if getattr(self, "_current_vertex", None):
            z = self.vertex_z_spin.value()
            from digcalc_project.src.ui.commands.edit_vertex_z_command import (
                EditVertexZCommand,
            )
            # Access undoStack via main window
            main_win = self.parent()
            if main_win and hasattr(main_win, "undoStack"):
                main_win.undoStack.push(EditVertexZCommand(self._current_vertex, z))
            else:
                self._current_vertex.set_z(z)
            logger.info("Vertex elevation applied: %.3f", z)

    # ------------------------------------------------------------------
    # Smooth checkbox handlers
    # ------------------------------------------------------------------
    def _apply_polyline_smooth(self):
        """Push ToggleSmoothCommand when user toggles checkbox."""
        if not getattr(self, "_current_polyline_info", None):
            return
        main_win = self.parent()
        while main_win and not hasattr(main_win, "undoStack"):
            main_win = main_win.parent()

        polyline_item = None
        if main_win and hasattr(main_win, "_selected_scene_item"):
            polyline_item = main_win._selected_scene_item

        if not polyline_item or not isinstance(polyline_item, QGraphicsPathItem):
            return

        # Only push when states differ
        should_be_interp = self.smooth_chk.isChecked()
        if (polyline_item.mode == "interpolated") != should_be_interp:
            if main_win and hasattr(main_win, "undoStack"):
                main_win.undoStack.push(ToggleSmoothCommand(polyline_item))
            else:
                polyline_item.toggle_mode()

    # --- Handlers for Tracing Tab ---

    def _update_smooth_sampling(self, value: float):
        """Update smooth sampling setting and emit signal."""
        logger.debug(f"Updating smooth_sampling_ft to: {value}")
        SettingsService().set_smooth_sampling_ft(value)
        self.settingsChanged.emit()

    def _update_tracing_mode(self, index: int):
        """Update tracing elevation mode setting and emit signal."""
        mode = self._elev_mode_combo.itemData(index)
        if mode:
            logger.debug(f"Updating tracing_elev_mode to: {mode}")
            SettingsService().set_tracing_elev_mode(mode)
            self.settingsChanged.emit()
        else:
             logger.error(f"Could not get user data for combo box index {index}")

    def _update_vertex_size(self, value: int):
        """Update vertex cross size setting and emit signal."""
        logger.debug(f"Updating vertex_cross_px to: {value}")
        SettingsService().set_vertex_cross_px(value)
        self.settingsChanged.emit()

    def _update_vertex_line(self, value: int):
        """Update vertex line thickness setting and emit signal."""
        logger.debug(f"Updating vertex_line_thickness to: {value}")
        SettingsService().set_vertex_line_thickness(value)
        self.settingsChanged.emit()

    def _update_hover_colour(self):
        """Update vertex hover colour setting and emit signal."""
        colour = self._hover_colour_edit.text()
        if colour:
            logger.debug(f"Updating vertex_hover_colour to: {colour}")
            SettingsService().set_vertex_hover_colour(colour)
            self.settingsChanged.emit()
        else:
            logger.warning("Hover colour is empty, not updating.")
