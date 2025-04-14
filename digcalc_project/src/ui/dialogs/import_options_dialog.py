import logging
from typing import Optional, Dict, List

# PySide6 imports
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QSpinBox, QLineEdit, 
    QFormLayout, QDialogButtonBox, QWidget, QSizePolicy
)

# Local imports - Use relative paths
# Assuming parser types might be needed for isinstance checks or methods
from ...core.importers.csv_parser import CSVParser
from ...core.importers.file_parser import FileParser # Import base or specific parsers as needed

class ImportOptionsDialog(QDialog):
    """Dialog for configuring import options for various file types."""
    def __init__(self, parent: Optional[QWidget], parser: FileParser, default_name: str, filename: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Import Options")
        self.parser = parser
        self.filename = filename # Store filename for potential use (e.g., CSV header peek)
        self.setMinimumWidth(400) # Increase minimum width for better layout
        self.logger = logging.getLogger(__name__) # Added logger

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(10)

        # --- Surface Name ---
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setToolTip("Enter a name for the surface to be created from this file.")
        form_layout.addRow("Surface Name:", self.name_edit)

        # --- Parser-Specific Options ---
        self._add_parser_options(form_layout)
        
        # Align labels to the right
        for i in range(form_layout.rowCount()):
            label_item = form_layout.itemAt(i, QFormLayout.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addLayout(form_layout)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.adjustSize() # Adjust size to fit contents

    def get_surface_name(self) -> str:
        """Get the desired surface name entered by the user."""
        name = self.name_edit.text().strip()
        if not name:
             self.logger.warning("Surface name was empty, using default.")
             name = "Imported Surface" # Provide a fallback
        return name

    def _add_parser_options(self, layout: QFormLayout):
        """Dynamically add options based on the parser type."""
        if isinstance(self.parser, CSVParser):
            # --- CSV Specific Options ---
            self.combo_x = QComboBox()
            self.combo_y = QComboBox()
            self.combo_z = QComboBox()
            self.spin_skip_rows = QSpinBox()
            self.spin_skip_rows.setRange(0, 100)
            self.spin_skip_rows.setValue(0)
            self.spin_skip_rows.setToolTip("Number of header rows to skip before data starts.")
            self.combo_delimiter = QComboBox()
            self.combo_delimiter.addItems([",", "\t", " ", ";"])
            self.combo_delimiter.setEditable(True)
            self.combo_delimiter.setToolTip("Select or enter the character separating columns.")

            layout.addRow("Delimiter:", self.combo_delimiter)
            layout.addRow("Skip Header Rows:", self.spin_skip_rows)
            layout.addRow("X Column:", self.combo_x)
            layout.addRow("Y Column:", self.combo_y)
            layout.addRow("Z/Elevation Column:", self.combo_z)
            
            self.combo_x.setToolTip("Select the column containing X coordinates.")
            self.combo_y.setToolTip("Select the column containing Y coordinates.")
            self.combo_z.setToolTip("Select the column containing Z (elevation) values.")

            # Populate column dropdowns if filename is available
            if self.filename:
                self._update_csv_column_options()
                # Connect signals to update dropdowns if parameters change
                self.spin_skip_rows.valueChanged.connect(self._update_csv_column_options)
                # Use textChanged for editable combo box to catch user input
                self.combo_delimiter.currentTextChanged.connect(self._update_csv_column_options) 
                
        # Add elif blocks here for other parsers (DXFParser, PDFParser, etc.)
        # elif isinstance(self.parser, DXFParser):
        #     # Add DXF specific options (e.g., layer selection)
        #     pass 
        else:
            # Default/Fallback message if no specific options needed
            no_options_label = QLabel("No specific import options available for this file type.")
            no_options_label.setStyleSheet("font-style: italic; color: gray;")
            layout.addRow(no_options_label)

    def _update_csv_column_options(self):
        """Read CSV headers and update column selection comboboxes."""
        if not self.filename or not isinstance(self.parser, CSVParser):
            self.logger.debug("_update_csv_column_options skipped: No filename or not CSVParser.")
            return

        skip_rows = self.spin_skip_rows.value()
        delimiter_text = self.combo_delimiter.currentText()
        
        # Handle potential special characters from editable combo box
        if delimiter_text == "\t":
            delimiter = '\t'
        elif delimiter_text == " ":
            delimiter = ' '
        else:
            delimiter = delimiter_text # Use the text directly
            
        if not delimiter: # Handle empty case gracefully
             self.logger.debug("Delimiter text is empty, defaulting to comma for header peek.")
             delimiter = ',' 

        self.logger.debug(f"Updating CSV columns: Skip={skip_rows}, Delimiter='{repr(delimiter)}'")

        try:
            # Ensure peek_headers can handle the potential delimiter
            headers = self.parser.peek_headers(self.filename, num_lines=skip_rows + 1, delimiter=delimiter)
            
            # Clear existing items before adding new ones
            self.combo_x.clear()
            self.combo_y.clear()
            self.combo_z.clear()

            if headers:
                self.logger.debug(f"Headers found: {headers}")
                self.combo_x.addItems(headers)
                self.combo_y.addItems(headers)
                self.combo_z.addItems(headers)
                self._try_preselect_columns(headers) # Attempt to guess columns
            else:
                 self.logger.warning(f"No headers could be read from '{self.filename}' with skip={skip_rows}, delim='{repr(delimiter)}'")
                 err_msg = "- Cannot read headers -"
                 self.combo_x.addItem(err_msg)
                 self.combo_y.addItem(err_msg)
                 self.combo_z.addItem(err_msg)

        except Exception as e:
            self.logger.exception(f"Error peeking headers for '{self.filename}': {e}")
            # Clear and show error in combo boxes
            self.combo_x.clear()
            self.combo_y.clear()
            self.combo_z.clear()
            err_msg = "- Error reading headers -"
            self.combo_x.addItem(err_msg)
            self.combo_y.addItem(err_msg)
            self.combo_z.addItem(err_msg)

    def _try_preselect_columns(self, headers: List[str]):
        """Attempt to automatically select common column names (case-insensitive)."""
        # More robust matching, ignoring case and common variations
        common_x = ['x', 'easting', 'lon', 'longitude', 'east']
        common_y = ['y', 'northing', 'lat', 'latitude', 'north']
        common_z = ['z', 'elevation', 'elev', 'height', 'altitude', 'alt']

        selected_x, selected_y, selected_z = False, False, False

        for i, header in enumerate(headers):
            h_lower = header.strip().lower()
            if not selected_x and any(term == h_lower for term in common_x):
                self.combo_x.setCurrentIndex(i)
                selected_x = True
            if not selected_y and any(term == h_lower for term in common_y):
                self.combo_y.setCurrentIndex(i)
                selected_y = True
            if not selected_z and any(term == h_lower for term in common_z):
                self.combo_z.setCurrentIndex(i)
                selected_z = True
        
        self.logger.debug(f"Preselection results: X={selected_x}, Y={selected_y}, Z={selected_z}")

        # If some were not preselected, default to first columns if possible
        if not selected_x and len(headers) > 0:
             self.combo_x.setCurrentIndex(0)
        if not selected_y and len(headers) > 1:
             self.combo_y.setCurrentIndex(1)
        if not selected_z and len(headers) > 2:
             self.combo_z.setCurrentIndex(2)

    def get_options(self) -> Dict:
        """Get the parser-specific options selected by the user."""
        options = {}
        if isinstance(self.parser, CSVParser):
            # Handle delimiter text carefully
            delimiter_text = self.combo_delimiter.currentText()
            if delimiter_text == "\t":
                 delimiter = '\t'
            elif delimiter_text == " ":
                 delimiter = ' '
            else:
                 delimiter = delimiter_text
                 
            options['delimiter'] = delimiter if delimiter else ',' # Default to comma if empty
            options['skip_rows'] = self.spin_skip_rows.value()
            
            x_col = self.combo_x.currentText()
            y_col = self.combo_y.currentText()
            z_col = self.combo_z.currentText()
            
            # Basic validation: ensure columns are selected and different if possible
            if x_col and y_col and z_col and not x_col.startswith("-") and not y_col.startswith("-") and not z_col.startswith("-"):
                 cols = {x_col, y_col, z_col}
                 if len(cols) < 3:
                      self.logger.warning("Duplicate columns selected for X, Y, Z. Parser might behave unexpectedly.")
                      # Maybe show a warning dialog here?
                 options['x_col'] = x_col
                 options['y_col'] = y_col
                 options['z_col'] = z_col
            else:
                 self.logger.error("Invalid column selection (missing or error state). Options not fully set.")
                 # Potentially raise an error or return indication of failure?

        # Add elif blocks for other parsers
        # elif isinstance(self.parser, DXFParser):
        #     options['layer'] = self.layer_combo.currentText() if self.layer_combo.currentText() != "All Layers" else None
        
        self.logger.debug(f"Returning import options: {options}")
        return options 