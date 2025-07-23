import numpy as np
import pytest

from PySide6.QtGui import QUndoStack

from digcalc_project.src.ui.commands.batch_elevate_command import BatchElevateCommand


class _DummyVertex:
    def __init__(self, x: float, y: float):
        from PySide6.QtCore import QPointF

        self._pos = QPointF(x, y)
        self._z = 0.0

    def pos(self):
        return self._pos

    def z(self):
        return self._z

    def set_z(self, val: float):
        self._z = float(val)


class _DummyPolyline:
    def __init__(self, points):
        self._verts = [_DummyVertex(x, y) for x, y in points]

    def vertices(self):
        return self._verts


# ---------------------------------------------------------------------
# Uniform elevation mode ------------------------------------------------
# ---------------------------------------------------------------------

def test_batch_uniform_elevation():
    polys = [_DummyPolyline([(0, 0), (10, 0)]), _DummyPolyline([(0, 0), (0, 10)]), _DummyPolyline([(1, 1), (2, 2)])]

    stack = QUndoStack()
    stack.push(BatchElevateCommand(polys, uniform_z=42.0))

    for pl in polys:
        assert [v.z() for v in pl.vertices()] == [42.0, 42.0]

    stack.undo()
    for pl in polys:
        assert [v.z() for v in pl.vertices()] == [0.0, 0.0]

    stack.redo()
    for pl in polys:
        assert [v.z() for v in pl.vertices()] == [42.0, 42.0]


# ---------------------------------------------------------------------
# Slope mode ------------------------------------------------------------
# ---------------------------------------------------------------------

def test_batch_slope_elevation():
    # Two-point poly allows linear slope easily
    polys = [_DummyPolyline([(0, 0), (100, 0)]), _DummyPolyline([(0, 0), (50, 0)])]
    stack = QUndoStack()
    # 10 % slope starting at 5 ft → +10 ft over 100 ft run
    stack.push(BatchElevateCommand(polys, first_z=5.0, slope_percent=10.0))

    # Expected Z for first poly: 5 and 15; second poly: 5 and 10
    z_lists = [[5.0, 15.0], [5.0, 10.0]]
    for pl, exp in zip(polys, z_lists):
        assert [round(v.z(), 3) for v in pl.vertices()] == pytest.approx(exp, abs=1e-3)

    stack.undo()
    for pl in polys:
        assert [v.z() for v in pl.vertices()] == [0.0, 0.0] 