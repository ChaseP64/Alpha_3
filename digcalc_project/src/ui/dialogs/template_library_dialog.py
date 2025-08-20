from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...models.template import Template


class TemplateLibraryDialog(QDialog):
    """Simple CRUD dialog for managing excavation templates (Phase-8 D2).

    Emits signals when the library changes to allow preview/update hooks.
    """

    templatesChanged = Signal(list)
    previewRequested = Signal(Template)

    def __init__(
        self, templates: Optional[List[Template]] = None, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Template Library")
        self.resize(520, 360)

        self._templates: List[Template] = list(templates or [])

        # UI widgets
        self.list_widget = QListWidget(self)
        self.name_edit = QLineEdit(self)
        self.type_edit = QLineEdit(self)
        self.depth_spin = QDoubleSpinBox(self)
        self.depth_spin.setRange(0.0, 1000.0)
        self.depth_spin.setSuffix(" ft")
        self.width_spin = QDoubleSpinBox(self)
        self.width_spin.setRange(0.0, 100000.0)
        self.width_spin.setSuffix(" ft")
        self.length_spin = QDoubleSpinBox(self)
        self.length_spin.setRange(0.0, 100000.0)
        self.length_spin.setSuffix(" ft")

        btn_add = QPushButton("Add")
        btn_delete = QPushButton("Delete")
        btn_preview = QPushButton("Preview")

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        # Layout
        root = QVBoxLayout(self)
        root.addWidget(self.list_widget, 1)

        form = QHBoxLayout()
        form.addWidget(QLabel("Name:"))
        form.addWidget(self.name_edit)
        form.addWidget(QLabel("Type:"))
        form.addWidget(self.type_edit)
        root.addLayout(form)

        dims = QHBoxLayout()
        dims.addWidget(QLabel("Depth:"))
        dims.addWidget(self.depth_spin)
        dims.addWidget(QLabel("Width:"))
        dims.addWidget(self.width_spin)
        dims.addWidget(QLabel("Length:"))
        dims.addWidget(self.length_spin)
        root.addLayout(dims)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_preview)
        root.addLayout(btn_row)

        root.addWidget(buttons)

        # Wire events
        btn_add.clicked.connect(self._on_add)
        btn_delete.clicked.connect(self._on_delete)
        btn_preview.clicked.connect(self._on_preview)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        self.name_edit.textEdited.connect(self._on_field_changed)
        self.type_edit.textEdited.connect(self._on_field_changed)
        self.depth_spin.valueChanged.connect(self._on_field_changed)
        self.width_spin.valueChanged.connect(self._on_field_changed)
        self.length_spin.valueChanged.connect(self._on_field_changed)

        self._refresh_list()

    # --- Public API ---
    def templates(self) -> List[Template]:
        return list(self._templates)

    # --- Internals ---
    def _refresh_list(self) -> None:
        self.list_widget.clear()
        for t in self._templates:
            item = QListWidgetItem(t.name)
            item.setData(Qt.UserRole, t)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0 and not self.list_widget.currentItem():
            self.list_widget.setCurrentRow(0)

    def _on_add(self) -> None:
        t = Template(
            name="Template", type="pad", params={"depth": 0.0, "width": 0.0, "length": 0.0}
        )
        self._templates.append(t)
        self._refresh_list()
        self.templatesChanged.emit(self.templates())

    def _on_delete(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        tpl: Template = item.data(Qt.UserRole)
        self._templates = [t for t in self._templates if t.id != tpl.id]
        self._refresh_list()
        self.templatesChanged.emit(self.templates())

    def _on_current_changed(self, curr: QListWidgetItem, prev: QListWidgetItem) -> None:
        tpl: Optional[Template] = curr.data(Qt.UserRole) if curr else None
        if not tpl:
            self.name_edit.clear()
            self.type_edit.clear()
            self.depth_spin.setValue(0.0)
            self.width_spin.setValue(0.0)
            self.length_spin.setValue(0.0)
            return
        self.name_edit.setText(tpl.name)
        self.type_edit.setText(tpl.type)
        self.depth_spin.setValue(float(tpl.params.get("depth", 0.0)))
        self.width_spin.setValue(float(tpl.params.get("width", 0.0)))
        self.length_spin.setValue(float(tpl.params.get("length", 0.0)))

    def _on_field_changed(self, *_args) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        tpl: Template = item.data(Qt.UserRole)
        tpl.name = self.name_edit.text().strip() or tpl.name
        tpl.type = self.type_edit.text().strip() or tpl.type
        tpl.params["depth"] = float(self.depth_spin.value())
        tpl.params["width"] = float(self.width_spin.value())
        tpl.params["length"] = float(self.length_spin.value())
        item.setText(tpl.name)
        self.templatesChanged.emit(self.templates())

    def _on_preview(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        tpl: Template = item.data(Qt.UserRole)
        self.previewRequested.emit(tpl)

    def _on_accept(self) -> None:
        self.accept()

