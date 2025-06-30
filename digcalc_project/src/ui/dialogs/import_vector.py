from __future__ import annotations

"""digcalc_project.src.ui.dialogs.import_vector

Qt dialog that previews vectorized PDF content and lets the user map groups
(layers/colours) to DigCalc layers.  Skeleton only for now.
"""

from typing import List, Dict

from PySide6.QtWidgets import QDialog

from ...core.geom.polyline import Polyline

__all__ = ["ImportVectorDialog"]


class ImportVectorDialog(QDialog):
    """Stub dialog – full UI implementation arrives in Step 5."""

    def __init__(self, parent=None):  # noqa: D401 – simple stub
        super().__init__(parent)

        # TODO: build widgets in Step 5
        self.setWindowTitle("Import Vector Lines (stub)")

    # Signal placeholders (Qt will complain without real `Signal` objects, so
    # we define attrs and assign later when PySide is properly integrated.)
    vectorized_polylines_ready: object = None  # Will become Signal[list[Polyline], dict]

    # API expected by MainWindow integration later
    def set_page_preview(self, polylines: List[Polyline]):  # noqa: D401
        ... 