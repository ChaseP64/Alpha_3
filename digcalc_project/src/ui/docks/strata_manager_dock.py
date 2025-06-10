"""Dock for managing stratigraphy data (materials & boreholes)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QToolBar,
    QAction,
    QHeaderView,
    QTableWidgetItem,
    QFormLayout,
    QDoubleSpinBox,
    QPushButton,
    QProgressBar,
    QLabel,
    QColorDialog,
)
from PySide6.QtGui import QUndoStack, QColor
from digcalc_project.src.models.strata_models import Material, StrataStack
from digcalc_project.src.ui.dialogs.add_material_dialog import AddMaterialDialog
from digcalc_project.src.ui.commands.add_material_command import AddMaterialCommand
from digcalc_project.src.services.interpolation_service import IDWInterpolator, StrataJob
from digcalc_project.src.services.settings_service import SettingsService
import os


class StrataManagerDock(QDockWidget):
    """Dock widget providing tables to edit *StrataStack* contents."""

    materialColorChanged = Signal(int, str)  # material_id, new_color_hex
    materialVisibilityChanged = Signal(int, bool)  # material_id, is_visible

    def __init__(self, main_window):
        super().__init__("Strata Manager", main_window)
        self.main = main_window
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.undo_stack = QUndoStack(self)
        self.settings = SettingsService()
        self.strata_job: StrataJob | None = None

        # Obtain current project/stack helper
        self._stack: StrataStack | None = None

        # ------------------------------------------------------------------
        # Tabs & layout
        # ------------------------------------------------------------------
        tabs = QTabWidget(self)
        self.setWidget(tabs)

        # Materials tab
        mat_tab = QWidget()
        tabs.addTab(mat_tab, "Materials")
        mat_layout = QVBoxLayout(mat_tab)

        # Toolbar
        tb = QToolBar(mat_tab)
        act_add = QAction("Add…", self)
        act_add.triggered.connect(self._on_add_material)
        tb.addAction(act_add)
        # Export / Import buttons
        act_exp = QAction("Export…", self)
        act_imp = QAction("Import…", self)
        act_exp.triggered.connect(self._export_csv)
        act_imp.triggered.connect(self._import_csv)
        tb.addAction(act_exp)
        tb.addAction(act_imp)
        mat_layout.addWidget(tb)

        # Table
        self.mat_table = QTableWidget(0, 4, mat_tab)
        self.mat_table.setHorizontalHeaderLabels(["Visible", "ID", "Name", "Color"])
        self.mat_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mat_table.cellDoubleClicked.connect(self._on_mat_cell_double_clicked)
        self.mat_table.itemChanged.connect(self._on_mat_item_changed)
        mat_layout.addWidget(self.mat_table)

        # Boreholes tab placeholder
        bh_tab = QWidget()
        tabs.addTab(bh_tab, "Boreholes")
        bh_layout = QVBoxLayout(bh_tab)
        self.bh_table = QTableWidget(0, 4, bh_tab)
        self.bh_table.setHorizontalHeaderLabels(["ID", "X", "Y", "Layers"])
        self.bh_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        bh_layout.addWidget(self.bh_table)

        # Generate tab
        gen_tab = self._create_generate_tab()
        tabs.addTab(gen_tab, "Generate")

        # initial refresh
        self.refresh_from_project()

    def _create_generate_tab(self) -> QWidget:
        """Builds the 'Generate' tab UI."""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # --- Interpolation Settings ---
        self.power_spinbox = QDoubleSpinBox()
        self.power_spinbox.setRange(1.0, 10.0)
        self.power_spinbox.setSingleStep(0.5)
        self.power_spinbox.setValue(self.settings.strata_idw_power)
        self.power_spinbox.valueChanged.connect(lambda v: self.settings.set("strata_idw_power", v))
        layout.addRow("IDW Power:", self.power_spinbox)

        self.radius_spinbox = QDoubleSpinBox()
        self.radius_spinbox.setRange(1.0, 1000.0)
        self.radius_spinbox.setSingleStep(10)
        self.radius_spinbox.setValue(self.settings.strata_idw_radius)
        self.radius_spinbox.valueChanged.connect(lambda v: self.settings.set("strata_idw_radius", v))
        layout.addRow("IDW Radius (m):", self.radius_spinbox)
        
        # --- Action Button & Progress ---
        self.generate_button = QPushButton("Generate Surfaces")
        self.generate_button.clicked.connect(self._on_generate_surfaces)
        layout.addRow(self.generate_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addRow(self.progress_bar)
        
        self.rmse_label = QLabel("RMSE: -")
        self.rmse_label.setVisible(False)
        layout.addRow(self.rmse_label)

        return tab

    # ------------------------------------------------------------------
    def refresh_from_project(self):
        pc = getattr(self.main, "project_controller", None)
        project = pc.get_current_project() if pc else None
        self._stack = project.strata if project else None
        
        is_ready = self._stack is not None and len(self._stack.boreholes) >= 3
        self.generate_button.setEnabled(is_ready)
        
        self.refresh_materials()
        self.refresh_boreholes()

    # ------------------------------------------------------------------
    def refresh_materials(self):
        self.mat_table.setRowCount(0)
        if not self._stack:
            return
        
        self.mat_table.blockSignals(True)
        for mat in self._stack.materials:
            row = self.mat_table.rowCount()
            self.mat_table.insertRow(row)

            # Visibility Checkbox
            vis_item = QTableWidgetItem()
            vis_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            vis_item.setCheckState(Qt.Checked if mat.visible else Qt.Unchecked)
            self.mat_table.setItem(row, 0, vis_item)
            
            # Other data
            id_item = QTableWidgetItem(str(mat.id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable) # Make ID not editable
            self.mat_table.setItem(row, 1, id_item)

            self.mat_table.setItem(row, 2, QTableWidgetItem(mat.name))
            
            cell = QTableWidgetItem(mat.colour)
            cell.setBackground(QColor(mat.colour))
            self.mat_table.setItem(row, 3, cell)
        self.mat_table.blockSignals(False)

    # ------------------------------------------------------------------
    def _on_add_material(self):
        dlg = AddMaterialDialog(self)
        if dlg.exec() != dlg.Accepted:
            return
        if not self._stack:
            return
        kwargs = dlg.material_kwargs()
        mat = Material(**kwargs)
        cmd = AddMaterialCommand(self._stack, mat)
        self.undo_stack.push(cmd)
        self.refresh_materials()

    # ------------------------------------------------------------------
    def refresh_boreholes(self):
        self.bh_table.setRowCount(0)
        if not self._stack:
            return
        for bh in self._stack.boreholes:
            row = self.bh_table.rowCount()
            self.bh_table.insertRow(row)
            self.bh_table.setItem(row, 0, QTableWidgetItem(str(bh.id)))
            self.bh_table.setItem(row, 1, QTableWidgetItem(f"{bh.x:.2f}"))
            self.bh_table.setItem(row, 2, QTableWidgetItem(f"{bh.y:.2f}"))
            self.bh_table.setItem(row, 3, QTableWidgetItem(str(len(bh.layers))))

    # ------------------------------------------------------------------
    # CSV helpers
    # ------------------------------------------------------------------
    def _export_csv(self):
        if not self._stack:
            return
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export Boreholes", "boreholes.csv", "CSV Files (*.csv)")
        if not path:
            return
        from digcalc_project.src.services.borehole_csv_io import save_csv
        save_csv(path, self._stack)

    def _import_csv(self):
        if not self._stack:
            return
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(self, "Import Boreholes", "", "CSV Files (*.csv)")
        if not path:
            return
        from digcalc_project.src.services.borehole_csv_io import load_csv
        added, skipped = load_csv(path, self._stack)
        if added:
            # wrap in undo command group
            from PySide6.QtGui import QUndoCommand
            group = QUndoCommand(f"Import Boreholes ({added} rows)")
            # Simply mark stack dirty; full per-row undo not needed now
            self.undo_stack.push(group)
        self.refresh_materials(); self.refresh_boreholes()
        if skipped:
            QMessageBox.information(self, "Import", f"{skipped} rows skipped due to errors.")

    def _on_generate_surfaces(self):
        """Handler to kick off the strata generation job."""
        pc = getattr(self.main, "project_controller", None)
        project = pc.get_current_project() if pc else None
        if not project or not self._stack:
            return

        # TODO: Get proper existing surface from project
        existing_surface = getattr(project, "existing_surface", None)
        if not existing_surface:
            # Placeholder error message
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Existing ground surface not found.")
            return

        self.generate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.rmse_label.setVisible(False)

        interpolator = IDWInterpolator()
        cache_dir = os.path.join(project.get_cache_dir(), "strata")
        
        self.strata_job = StrataJob(interpolator, project, self._stack, existing_surface, cache_dir)
        self.strata_job.progress.connect(self._on_job_progress)
        self.strata_job.finished.connect(self._on_job_finished)
        self.strata_job.start()

    def _on_job_progress(self, value: int):
        """Updates the progress bar."""
        self.progress_bar.setValue(value)

    def _on_job_finished(self, surfaces: list, rmse: float):
        """Handles completion of the strata generation job."""
        self.progress_bar.setVisible(False)
        self.generate_button.setEnabled(True)
        
        if self._stack:
            self._stack.surfaces = surfaces
        
        if surfaces:
            # Format and display RMSE
            self.rmse_label.setText(f"RMSE: {rmse:.4f} ft")
            
            # Style the label based on the threshold from settings
            threshold = self.settings.strata_rmse_threshold
            color = "green" if rmse < threshold else "red"
            self.rmse_label.setStyleSheet(f"color: {color};")
            self.rmse_label.setVisible(True)
            
            # TODO: Add to undo stack and refresh 3D view
            # cmd = GenerateStrataCommand(...)
            # self.undo_stack.push(cmd)
            if hasattr(self.main, "refresh_3d_view"):
                self.main.refresh_3d_view()
        elif rmse < 0:
             self.rmse_label.setText("RMSE: Error")
             self.rmse_label.setStyleSheet("color: red;")
             self.rmse_label.setVisible(True)


        self.strata_job = None

    def _on_mat_item_changed(self, item: QTableWidgetItem):
        """Handle changes to the materials table."""
        if not self._stack or self.mat_table.signalsBlocked():
            return

        row = item.row()
        material_id = int(self.mat_table.item(row, 1).text())
        material = self._stack.get_material(material_id)
        if not material:
            return

        column = item.column()
        if column == 0:  # Visibility
            is_visible = item.checkState() == Qt.Checked
            if material.visible != is_visible:
                material.visible = is_visible
                self.materialVisibilityChanged.emit(material.id, is_visible)
        elif column == 2:  # Name
            new_name = item.text()
            if material.name != new_name:
                material.name = new_name
                # Optional: emit a name changed signal if needed elsewhere
        # Color is handled by double-click, not itemChanged directly

    def _on_mat_cell_double_clicked(self, row: int, column: int):
        """Handle double-clicks for editing material properties."""
        if column == 3: # Color column
            self._edit_material_color(row)

    def _edit_material_color(self, row: int):
        if not self._stack:
            return
            
        material_id = int(self.mat_table.item(row, 1).text())
        material = self._stack.get_material(material_id)
        if not material:
            return

        dialog = QColorDialog(QColor(material.colour), self)
        if dialog.exec():
            new_color = dialog.currentColor()
            if new_color.isValid():
                new_hex = new_color.name()
                material.colour = new_hex
                self.mat_table.item(row, 3).setBackground(new_color)
                self.mat_table.item(row, 3).setText(new_hex)
                self.materialColorChanged.emit(material.id, new_hex) 