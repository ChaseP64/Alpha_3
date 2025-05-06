from __future__ import annotations

"""Smoke test ensuring MoveVertexCommand merges successive drags."""

import os

# Use offscreen platform to avoid requiring a display in CI/headless.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QUndoStack, QPen  # noqa: E402  (import after env set)
from PySide6.QtCore import QPointF  # noqa: E402

from digcalc_project.src.ui.items.vertex_item import VertexItem  # noqa: E402
from digcalc_project.src.ui.items.polyline_item import PolylineItem  # noqa: E402
from digcalc_project.src.ui.commands.move_vertex_command import MoveVertexCommand  # noqa: E402

# pytest-qt provides the *qtbot* fixture which ensures a QApplication exists.

def test_mergeable_drag(qtbot):
    """Two drags on the same vertex should collapse into a single undo step."""

    v = VertexItem(QPointF(0, 0))
    cmd1 = MoveVertexCommand(v, QPointF(0, 0), QPointF(1, 0))
    cmd2 = MoveVertexCommand(v, QPointF(1, 0), QPointF(2, 0))

    stack = QUndoStack()
    stack.push(cmd1)
    stack.push(cmd2)  # should merge with cmd1

    assert stack.count() == 1

    # Redo/undo cycle should apply the final movement only.
    stack.undo()
    assert v.pos() == QPointF(0, 0)
    stack.redo()
    assert v.pos() == QPointF(2, 0) 