import math
import pytest
from unittest.mock import MagicMock

from digcalc_project.src.ui.dialogs.scale_calibration_dialog import ScaleCalibrationDialog
from digcalc_project.src.models.project import Project


# Create a reusable mock project fixture
@pytest.fixture
def mock_project():
    project = MagicMock(spec=Project)
    project.pdf_background_path = "dummy.pdf"
    project.pdf_background_dpi = 96.0
    project.pdf_background_page = 1
    return project


def test_scale_calibration_dialog_simple(qtbot, mock_project):
    """Ensure the dialog converts picked span + distance into ProjectScale."""
    # Create dialog with no scene (we will inject the picked span manually)
    dlg = ScaleCalibrationDialog(parent=None, project=mock_project, scene=None, page_pixmap=None)

    # Inject picked span (10 px) and set real-world distance (20 ft)
    dlg._span_px = 10.0
    dlg.dist_spin.setValue(20.0)

    # Call accept routine directly (bypasses UI interactions)
    dlg._accept()
    scale = dlg.result_scale()

    # world_per_px should be 20/10 = 2 ft/px
    assert math.isclose(scale.world_per_px, 2.0)
    # Reciprocal pixels per foot should therefore be 0.5 px/ft
    assert math.isclose(1 / scale.world_per_px, 0.5, rel_tol=1e-6)
    assert scale.world_units == "ft" 