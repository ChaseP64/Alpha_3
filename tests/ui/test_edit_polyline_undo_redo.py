import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPen, QUndoStack
from PySide6.QtWidgets import QApplication, QGraphicsScene

from digcalc_project.src.ui.commands.edit_polyline.add_vertex_cmd import AddVertexCommand
from digcalc_project.src.ui.commands.edit_polyline.delete_vertex_cmd import DeleteVertexCommand
from digcalc_project.src.ui.items.polyline_item import PolylineItem

# Skip when PySide6 not present (CI guard)
pytest.importorskip("PySide6")


@pytest.fixture
def scene(qtbot):
    """Provide a QGraphicsScene for item tests."""
    app = QApplication.instance() or QApplication([])
    scn = QGraphicsScene()
    # No need to attach a view for command-only tests
    return scn


def _build_polyline():
    """Helper to create a simple 2-vertex polyline item."""
    pts = [QPointF(0, 0), QPointF(10, 0)]
    pen = QPen(Qt.black)
    return PolylineItem(points=pts, layer_pen=pen)


def test_add_vertex_command_undo_redo(scene):
    poly = _build_polyline()
    scene.addItem(poly)

    stack = QUndoStack()
    cmd = AddVertexCommand(poly, QPointF(5, 5), index=1)

    # push – redo executed automatically
    stack.push(cmd)
    assert len(poly.vertices()) == 3, "Vertex not added on redo"

    # undo
    stack.undo()
    assert len(poly.vertices()) == 2, "Undo did not remove vertex"

    # redo
    stack.redo()
    assert len(poly.vertices()) == 3, "Redo did not re-add vertex"


def test_delete_vertex_command_undo_redo(scene):
    poly = _build_polyline()
    scene.addItem(poly)

    # add a third vertex so delete becomes meaningful
    third = QPointF(5, 5)
    from digcalc_project.src.ui.items.vertex_item import VertexItem

    poly.vertices().append(VertexItem(third, parent=poly))  # direct add
    poly._rebuild_path()  # type: ignore[attr-defined]

    stack = QUndoStack()
    # pick middle vertex (index 1)
    vtx_to_delete = poly.vertices()[1]
    cmd = DeleteVertexCommand(poly, vtx_to_delete)

    stack.push(cmd)
    assert len(poly.vertices()) == 2, "Vertex not deleted on redo"

    stack.undo()
    assert len(poly.vertices()) == 3, "Undo did not restore vertex"
