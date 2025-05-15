"""GUI tests verifying 'Enter Scale' tab behaviours of the two-tab
ScaleCalibrationDialog (Task 12).

We check three user flows:

1. Direct world-units-per-inch entry enables OK and saves a valid scale.
2. Ratio entry does the same.
3. Supplying invalid input keeps the OK button disabled.

Widget attribute names follow the dialog implementation; an alias
``radio_direct`` is provided in the dialog for forward-compatibility.
"""

import pytest

# PySide6 widgets/consts
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.project_scale import ProjectScale
from digcalc_project.src.ui.dialogs.scale_calibration_dialog import (
    ScaleCalibrationDialog,
)

# ---------------------------------------------------------------------------
# Test helpers / fixtures
# ---------------------------------------------------------------------------

DPI = 150.0  # Fixed DPI for deterministic math in assertions


@pytest.fixture
def project(tmp_path):
    """Return a fresh Project instance with a known PDF DPI."""
    return Project(name="GUI-Scale-Test", pdf_background_dpi=DPI)


def _open_dialog(qtbot, project: Project):
    """Create and show a ScaleCalibrationDialog bound to *project*."""
    dlg = ScaleCalibrationDialog(None, project, scene=None)
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg


# ---------------------------------------------------------------------------
# 1. Direct world-units-per-inch entry
# ---------------------------------------------------------------------------


def test_world_units_entry(qtbot, project):
    dlg = _open_dialog(qtbot, project)

    # Switch to "Enter Scale" tab – index 1.
    dlg.tabs.setCurrentIndex(1)

    # Select direct-entry mode and choose 50 ft / in.
    dlg.radio_direct.setChecked(True)
    dlg.spin_value.setValue(50.0)
    dlg.combo_units.setCurrentText("ft")

    ok_btn = dlg.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_btn.isEnabled(), "OK button should be enabled for valid direct entry."

    qtbot.mouseClick(ok_btn, Qt.LeftButton)

    # Dialog should have stored a ProjectScale on the project.
    assert isinstance(project.scale, ProjectScale), "Project.scale not set after accept."

    expected_world_per_px = 50.0 / DPI  # 50 world-units per inch at 150 dpi
    assert abs(project.scale.world_per_px - expected_world_per_px) < 1e-6


# ---------------------------------------------------------------------------
# 2. Ratio entry (1 : 600)
# ---------------------------------------------------------------------------


def test_ratio_entry(qtbot, project):
    dlg = _open_dialog(qtbot, project)
    dlg.tabs.setCurrentIndex(1)

    dlg.radio_ratio.setChecked(True)
    dlg.edit_denom.setText("600")  # ratio 1:600

    ok_btn = dlg.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_btn.isEnabled(), "OK button should be enabled for valid ratio entry."

    qtbot.mouseClick(ok_btn, Qt.LeftButton)

    assert isinstance(project.scale, ProjectScale)
    assert project.scale.ratio_denom == 600


# ---------------------------------------------------------------------------
# 3. Invalid input keeps OK disabled
# ---------------------------------------------------------------------------


def test_invalid_input_disables_ok(qtbot, project):
    dlg = _open_dialog(qtbot, project)
    dlg.tabs.setCurrentIndex(1)

    dlg.radio_ratio.setChecked(True)
    dlg.edit_denom.setText("")  # Empty denominator → invalid

    ok_btn = dlg.buttonBox.button(QDialogButtonBox.StandardButton.Ok)

    # With invalid input the OK button should remain disabled.
    assert not ok_btn.isEnabled(), "OK button enabled despite invalid ratio input."
