import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QFormLayout, QWidget,
    QSizePolicy
)
from PySide6.QtCore import Qt

class ReportDialog(QDialog):
    """
    A dialog window to display the results of a volume calculation.

    Args:
        existing_surface_name (str): Name of the existing surface.
        proposed_surface_name (str): Name of the proposed surface.
        grid_resolution (float): The grid resolution used for calculation.
        cut_volume (float): Calculated cut volume.
        fill_volume (float): Calculated fill volume.
        net_volume (float): Calculated net volume (fill - cut).
        parent (QWidget | None): The parent widget. Defaults to None.
    """
    def __init__(self, 
                 existing_surface_name: str, 
                 proposed_surface_name: str, 
                 grid_resolution: float, 
                 cut_volume: float, 
                 fill_volume: float, 
                 net_volume: float, 
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Volume Calculation Report")
        self.setMinimumWidth(400) # Ensure a reasonable minimum width

        self.existing_surface_name = existing_surface_name
        self.proposed_surface_name = proposed_surface_name
        self.grid_resolution = grid_resolution
        self.cut_volume = cut_volume
        self.fill_volume = fill_volume
        self.net_volume = net_volume
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Layouts
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 10, 10, 10) # Add padding
        form_layout.setSpacing(10) # Add spacing between rows

        # --- Report Details ---
        self.lbl_existing = QLabel(self.existing_surface_name)
        self.lbl_proposed = QLabel(self.proposed_surface_name)
        self.lbl_resolution = QLabel(f"{self.grid_resolution:.2f} units")
        # Format volumes to 2 decimal places
        self.lbl_cut = QLabel(f"{self.cut_volume:.2f} cubic units")
        self.lbl_fill = QLabel(f"{self.fill_volume:.2f} cubic units")
        self.lbl_net = QLabel(f"{self.net_volume:.2f} cubic units")
        self.lbl_timestamp = QLabel(self.timestamp)

        # Add rows to form layout
        form_layout.addRow("Calculation Time:", self.lbl_timestamp)
        form_layout.addRow("Existing Surface:", self.lbl_existing)
        form_layout.addRow("Proposed Surface:", self.lbl_proposed)
        form_layout.addRow("Grid Resolution:", self.lbl_resolution)
        form_layout.addRow("Cut Volume:", self.lbl_cut)
        form_layout.addRow("Fill Volume:", self.lbl_fill)
        form_layout.addRow("Net Volume:", self.lbl_net)
        
        # Set label alignment for clarity
        for i in range(form_layout.rowCount()):
            label_item = form_layout.itemAt(i, QFormLayout.LabelRole)
            if label_item and label_item.widget():
                 label_item.widget().setAlignment(Qt.AlignRight | Qt.AlignVCenter)


        main_layout.addLayout(form_layout)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.adjustSize() # Adjust size to fit contents

if __name__ == '__main__':
    # Example Usage (for testing)
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = ReportDialog(
        existing_surface_name="Ground Survey Data",
        proposed_surface_name="Final Grade Plan",
        grid_resolution=5.0,
        cut_volume=1234.567,
        fill_volume=876.543,
        net_volume=876.543 - 1234.567,
    )
    dialog.exec()
    sys.exit() 