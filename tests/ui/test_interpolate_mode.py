import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QApplication

from digcalc_project.src.ui.commands.interpolate_segment_z_command import (
    InterpolateSegmentZCommand,
)
from digcalc_project.src.ui.items.polyline_item import PolylineItem


@pytest.fixture
def app(qtbot):
    """Ensure a QApplication exists for the test session."""
    return QApplication.instance() or QApplication([])


def test_interpolate_command(app):
    """Vertices between first & last should receive linearly interpolated Z."""
    # Build a simple horizontal 3-vertex polyline (0-10-20 ft along X)
    pts = [QPointF(0, 0), QPointF(10, 0), QPointF(20, 0)]
    poly = PolylineItem(pts, QPen(Qt.black))

    # Assign Z to first & last only – leave middle at zero initially
    for v, z in zip(poly.vertices(), (0.0, 0.0, 10.0)):
        v.set_z(z)

    # Apply interpolation command
    cmd = InterpolateSegmentZCommand(poly.vertices())
    cmd.redo()

    zs = [v.z() for v in poly.vertices()]
    assert math.isclose(zs[1], 5.0, rel_tol=1e-6)

    # Undo should restore original elevations (middle vertex back to 0)
    cmd.undo()
    zs_after_undo = [v.z() for v in poly.vertices()]
    assert math.isclose(zs_after_undo[1], 0.0, rel_tol=1e-6)
