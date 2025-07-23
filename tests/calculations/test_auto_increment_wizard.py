import numpy as np
import pytest

from PySide6.QtGui import QUndoStack

from digcalc_project.src.ui.commands.auto_increment_z_command import AutoIncrementZCommand


class _DummyVertex:
    """Light-weight stub replicating minimal VertexItem API for tests."""

    def __init__(self, x: float, y: float):
        from PySide6.QtCore import QPointF

        self._pos = QPointF(x, y)
        self._z = 0.0

    # --- Methods expected by AutoIncrementZCommand -------------------
    def pos(self):  # noqa: D401 – mimic Qt API name
        return self._pos

    def z(self):
        return self._z

    def set_z(self, value: float):
        self._z = float(value)

    # Convenience for tests
    def xyz(self):
        return (self._pos.x(), self._pos.y(), self._z)


# ---------------------------------------------------------------------
# Interpolation accuracy
# ---------------------------------------------------------------------

def test_linear_grade_interpolation_explicit_end():
    # Five vertices 25-ft apart along X-axis
    xs = np.linspace(0, 100, 5)
    verts = [_DummyVertex(float(x), 0.0) for x in xs]

    # Command with explicit end elevation
    cmd = AutoIncrementZCommand(verts, first_z=10.0, last_z=20.0)
    cmd.redo()  # apply

    expected = [10.0, 12.5, 15.0, 17.5, 20.0]
    assert [v.z() for v in verts] == pytest.approx(expected, abs=1e-6)


def test_linear_grade_interpolation_slope_percent():
    xs = np.linspace(0, 100, 5)
    verts = [_DummyVertex(float(x), 0.0) for x in xs]

    # 10 % slope – should result in +10 ft over 100 ft run
    cmd = AutoIncrementZCommand(verts, first_z=10.0, slope_percent=10.0)
    cmd.redo()

    expected = [10.0, 12.5, 15.0, 17.5, 20.0]
    assert [v.z() for v in verts] == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------
# Undo integration – ensure grouped command restores original Z values
# ---------------------------------------------------------------------

def test_auto_increment_undo_redo_cycle():
    xs = np.linspace(0, 100, 3)
    verts = [_DummyVertex(float(x), 0.0) for x in xs]

    stack = QUndoStack()
    stack.beginMacro("auto-inc-test")
    stack.push(AutoIncrementZCommand(verts, first_z=0.0, last_z=5.0))
    stack.endMacro()

    # After push, redo has executed -> vertices should be graded
    assert [v.z() for v in verts] == pytest.approx([0.0, 2.5, 5.0])

    # Undo
    stack.undo()
    assert [v.z() for v in verts] == pytest.approx([0.0, 0.0, 0.0])

    # Redo again
    stack.redo()
    assert [v.z() for v in verts] == pytest.approx([0.0, 2.5, 5.0]) 