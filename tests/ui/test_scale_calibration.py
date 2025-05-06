import math
import pytest

from digcalc_project.src.ui.dialogs.scale_calibration_dialog import ScaleCalibrationDialog


def test_scale_calibration_dialog_simple(qtbot):
    """Ensure the dialog converts picked span + distance into ProjectScale."""
    # Create dialog with no scene (we will inject the picked span manually)
    dlg = ScaleCalibrationDialog(parent=None, scene=None, page_pixmap=None)

    # Inject picked span (10 px) and set real-world distance (20 ft)
    dlg._picked_span_px = 10.0
    dlg.dist_spin.setValue(20.0)

    # Call accept routine directly (bypasses UI interactions)
    dlg._accept()
    scale = dlg.result_scale()

    # world_per_px should be 20/10 = 2 ft/px
    assert math.isclose(scale.world_per_px, 2.0)
    # Reciprocal pixels per foot should therefore be 0.5 px/ft
    assert math.isclose(1 / scale.world_per_px, 0.5, rel_tol=1e-6)
    assert scale.world_units == "ft" 