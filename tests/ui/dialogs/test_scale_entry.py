import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox

from digcalc_project.src.ui.dialogs.scale_calibration_dialog import ScaleCalibrationDialog
from digcalc_project.src.models.project import Project
from digcalc_project.src.models.project_scale import ProjectScale


def test_ratio_entry_sets_scale(qtbot):
    proj = Project(name="ScaleEntryTest")
    proj.pdf_background_dpi = 150  # simulate loaded PDF dpi

    dlg = ScaleCalibrationDialog(None, proj, scene=None)
    qtbot.addWidget(dlg)

    # switch to Enter Scale tab (index 1)
    dlg.tabs.setCurrentIndex(1)

    # select ratio mode
    dlg.radio_ratio.setChecked(True)
    dlg.edit_denom.setText("600")  # 1:600 scale

    ok_btn = dlg.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_btn.isEnabled()

    qtbot.mouseClick(ok_btn, Qt.LeftButton)

    assert proj.scale is not None
    # For ratio 1:600 ft, world_per_in = 600/12 = 50 ft/in -> world_per_px = 50/150 = 0.333...
    expected = 50.0 / 150.0
    assert abs(proj.scale.world_per_px - expected) < 1e-3 