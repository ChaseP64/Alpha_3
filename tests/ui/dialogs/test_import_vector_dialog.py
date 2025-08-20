import os

import numpy as np
import pytest
from PySide6 import QtCore
from pytestqt.qtbot import QtBot

from digcalc_project.src.core.geom.polyline import Polyline
from digcalc_project.src.ui.dialogs.import_vector import ImportVectorDialog

# Skip if vectorizer disabled
if os.getenv("DIGCALC_PDF_VEC") != "1":
    pytest.skip("PDF vectorizer feature disabled (DIGCALC_PDF_VEC != 1)", allow_module_level=True)


def _dummy_polylines():
    # Two groups: solid black and dashed red
    solid = Polyline(vertices=np.asarray([[0, 0], [10, 0]]), stroke_rgb=(0, 0, 0), dash=None)
    dashed = Polyline(
        vertices=np.asarray([[0, 0], [0, 10]]), stroke_rgb=(255, 0, 0), dash=(3.0, 3.0)
    )
    return [solid, dashed]


@pytest.mark.parametrize("accept", [True])
def test_dialog_lists_groups_and_emits(qtbot: QtBot, accept: bool):
    dlg = ImportVectorDialog()
    qtbot.addWidget(dlg)

    polylines = _dummy_polylines()
    dlg.set_page_preview(polylines)

    # Should have 2 group rows
    root = dlg._group_tree.invisibleRootItem()
    assert root.childCount() == 2

    # Change mapping of first combo
    combo = dlg._group_tree.itemWidget(root.child(0), 1)
    combo.setCurrentIndex(2)  # select "Offsets"

    with qtbot.waitSignal(dlg.vectorized_polylines_ready) as catcher:
        qtbot.mouseClick(
            dlg.findChild(type(combo)).parentWidget(), QtCore.Qt.LeftButton
        )  # ensure widget focus
        dlg._on_accept()

    emitted_polys, mapping = catcher.args
    assert emitted_polys == polylines
    assert len(mapping) == 2
