from typing import List

from PySide6.QtGui import QUndoCommand

from digcalc_project.src.ui.items.vertex_item import VertexItem


class InterpolateSegmentZCommand(QUndoCommand):
    """Undo command that linearly interpolates Z between first and last vertices."""

    def __init__(self, vertices: List[VertexItem]):
        super().__init__("Interpolate Vertices Elevation")
        if len(vertices) < 3:
            raise ValueError("Interpolation requires at least 3 vertices")
        self._verts = vertices
        # Capture old Z for undo
        self._old_z = [v.z() for v in vertices]
        # Compute new Z values
        z0 = vertices[0].z()
        z1 = vertices[-1].z()
        n = len(vertices) - 1
        self._new_z = [z0 + (z1 - z0) * i / n for i in range(n + 1)]

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------
    def redo(self):  # noqa: D401
        for v, z in zip(self._verts, self._new_z):
            v.set_z(z)

    def undo(self):  # noqa: D401
        for v, z in zip(self._verts, self._old_z):
            v.set_z(z) 