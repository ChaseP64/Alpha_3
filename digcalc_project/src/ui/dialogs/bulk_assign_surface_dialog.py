from __future__ import annotations

"""Bulk Assign Surface dialog (Phase-6 D2).

Lists *unclassified* polylines (``layer_class`` missing/"misc") and lets the
user override their layer in one go.  Emits the updated list on **Apply**.

Focus is on testability rather than full UI polish.
"""

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ...core.geom.polyline import Polyline

__all__ = ["BulkAssignSurfaceDialog"]


class BulkAssignSurfaceDialog(QDialog):
    """Dialog that shows unclassified polylines and lets user pick a layer."""

    assignments_ready = Signal(list)  # Emits list[Polyline] after user applies

    _LAYER_OPTIONS = [
        "Existing Surface",
        "Proposed Surface",
        "Subgrade",
        "Contours",
        "Misc",
    ]

    # ------------------------------------------------------------------
    def __init__(self, parent=None):  # noqa: D401 – Qt ctor
        super().__init__(parent)
        self.setWindowTitle("Bulk Assign Surface")
        self.resize(600, 400)

        self._polylines: list[Polyline] = []
        self._list = QListWidget(self)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Apply).setText("Apply")
        buttons.accepted.connect(self._on_apply)
        buttons.rejected.connect(self.reject)

        # Layout
        lay = QVBoxLayout(self)
        lay.addWidget(self._list, 1)
        lay.addWidget(buttons)

    # ------------------------------------------------------------------
    def set_polylines(self, polylines: List[Polyline]):  # noqa: D401 – Qt API
        """Populate list with *polylines* needing assignment."""
        self._polylines = polylines
        self._list.clear()

        for idx, pl in enumerate(polylines, start=1):
            item = QListWidgetItem(f"Polyline {idx} – {len(pl.vertices)} verts")
            self._list.addItem(item)

            combo = QComboBox()
            combo.addItems(self._LAYER_OPTIONS)

            # Pre-select current layer if valid
            current = getattr(pl, "layer_class", "Misc").title()  # e.g. "contour" → "Contour"
            for i in range(combo.count()):
                if combo.itemText(i).lower().startswith(current.lower()[:3]):
                    combo.setCurrentIndex(i)
                    break

            self._list.setItemWidget(item, combo)

    # ------------------------------------------------------------------
    def _on_apply(self):
        """Write selections back to polyline objects and emit signal."""
        for row in range(self._list.count()):
            item = self._list.item(row)
            combo = self._list.itemWidget(item)
            if isinstance(combo, QComboBox):
                layer = combo.currentText().lower().split()[0]  # take first word
            else:
                layer = "misc"
            pl = self._polylines[row]
            setattr(pl, "layer_class", layer)

        self.assignments_ready.emit(self._polylines)
        self.accept()
