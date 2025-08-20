"""GUI test for BulkAssignSurfaceDialog (Phase-6 D2)."""

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from digcalc_project.src.core.geom.polyline import Polyline
from digcalc_project.src.ui.dialogs.bulk_assign_surface_dialog import BulkAssignSurfaceDialog


@pytest.fixture
def sample_polys():
    # Three unclassified polylines
    p1 = Polyline(vertices=np.asarray([[0, 0], [1, 0]]))
    p2 = Polyline(vertices=np.asarray([[0, 0], [0, 1]]))
    p3 = Polyline(vertices=np.asarray([[1, 1], [2, 2]]))
    return [p1, p2, p3]


def test_bulk_assign_dialog(qtbot: QtBot, sample_polys):
    dlg = BulkAssignSurfaceDialog()
    qtbot.addWidget(dlg)

    dlg.set_polylines(sample_polys)

    # Simulate user choosing layers (Existing, Proposed, Subgrade)
    root = dlg._list  # QListWidget
    # First row combo
    combo0 = root.itemWidget(root.item(0))
    combo0.setCurrentText("Existing Surface")
    combo1 = root.itemWidget(root.item(1))
    combo1.setCurrentText("Proposed Surface")
    combo2 = root.itemWidget(root.item(2))
    combo2.setCurrentText("Subgrade")

    with qtbot.waitSignal(dlg.assignments_ready) as catcher:
        dlg._on_apply()

    [assigned] = catcher.args  # list returned

    assert [pl.layer_class for pl in assigned] == [
        "existing",
        "proposed",
        "subgrade",
    ]
