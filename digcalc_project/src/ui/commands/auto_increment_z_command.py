from __future__ import annotations

"""AutoIncrementZCommand – assign linear grade elevations to a chain of vertices.

The command sets new Z values for a list of :class:`VertexItem` objects so that
all vertices follow a straight-line grade between the first and last vertex.
The end elevation can be specified directly (``last_z``) or derived from a
slope percentage (rise-over-run) relative to the horizontal chain length.
"""

from typing import List, Optional

from PySide6.QtGui import QUndoCommand

from digcalc_project.src.ui.items.vertex_item import VertexItem
from digcalc_project.src.core.calculations.linear_grade import interpolate_z_linear

__all__ = ["AutoIncrementZCommand"]


class AutoIncrementZCommand(QUndoCommand):
    """Undoable command that interpolates vertex elevations along a polyline."""

    def __init__(
        self,
        vertices: List[VertexItem],
        *,
        first_z: float,
        last_z: Optional[float] = None,
        slope_percent: Optional[float] = None,
    ):
        """Construct the command.

        Args
        -----
        vertices:
            Ordered list of :class:`VertexItem` objects to be updated.  Must
            contain **at least two** vertices.
        first_z:
            Elevation (ft) to apply to the first vertex.
        last_z:
            Elevation (ft) for the last vertex – mutually exclusive with
            *slope_percent*.
        slope_percent:
            Grade as percent (ΔZ / ΔXY × 100), mutually exclusive with
            *last_z*.
        """

        super().__init__("Auto-Increment Elevations")
        if len(vertices) < 2:
            raise ValueError("Need at least two vertices for auto-increment wizard.")

        self._verts: List[VertexItem] = list(vertices)
        # Snapshot original elevations for undo
        self._old_z: List[float] = [v.z() for v in self._verts]

        # Calculate new elevations once and cache them for redo
        xy = [(v.pos().x(), v.pos().y()) for v in self._verts]
        self._new_z: List[float] = interpolate_z_linear(
            xy,
            first_z=first_z,
            last_z=last_z,
            slope_percent=slope_percent,
        )

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------
    def undo(self):
        for v, z in zip(self._verts, self._old_z):
            v.set_z(z)

    def redo(self):
        for v, z in zip(self._verts, self._new_z):
            v.set_z(z) 