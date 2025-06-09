"""Dock for managing stratigraphy data (materials & boreholes)."""

from __future__ import annotations

from PySide6.QtCore import Qt
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
)

from digcalc_project.src.models.strata_models import Material, StrataStack
from digcalc_project.src.ui.dialogs.add_material_dialog import AddMaterialDialog
from digcalc_project.src.ui.commands.add_material_command import AddMaterialCommand
from PySide6.QtGui import QUndoStack


class StrataManagerDock(QDockWidget):
    """Dock widget providing tables to edit *StrataStack* contents."""

    def __init__(self, main_window):
        super().__init__("Strata Manager", main_window)
        self.main = main_window
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.undo_stack = QUndoStack(self)

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
        self.mat_table = QTableWidget(0, 3, mat_tab)
        self.mat_table.setHorizontalHeaderLabels(["ID", "Name", "Color"])
        self.mat_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mat_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        mat_layout.addWidget(self.mat_table)

        # Boreholes tab placeholder
        bh_tab = QWidget()
        tabs.addTab(bh_tab, "Boreholes")
        bh_layout = QVBoxLayout(bh_tab)
        self.bh_table = QTableWidget(0, 4, bh_tab)
        self.bh_table.setHorizontalHeaderLabels(["ID", "X", "Y", "Layers"])
        self.bh_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        bh_layout.addWidget(self.bh_table)

        # initial refresh
        self.refresh_from_project()

    # ------------------------------------------------------------------
    def refresh_from_project(self):
        pc = getattr(self.main, "project_controller", None)
        project = pc.get_current_project() if pc else None
        self._stack = project.strata if project else None
        self.refresh_materials()
        self.refresh_boreholes()

    # ------------------------------------------------------------------
    def refresh_materials(self):
        self.mat_table.setRowCount(0)
        if not self._stack:
            return
        for mat in self._stack.materials:
            row = self.mat_table.rowCount()
            self.mat_table.insertRow(row)
            self.mat_table.setItem(row, 0, QTableWidgetItem(str(mat.id)))
            self.mat_table.setItem(row, 1, QTableWidgetItem(mat.name))
            cell = QTableWidgetItem(mat.colour)
            cell.setBackground(mat.colour)
            self.mat_table.setItem(row, 2, cell)

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