from typing import List

from PySide6.QtGui import QUndoCommand

from digcalc_project.src.ui.items.polyline_item import PolylineItem


class SetPolylineUniformZCommand(QUndoCommand):
    """Undoable command to apply a single elevation to every vertex in a polyline.

    This is used by the TracingScene workflow when the *Line Elevation* mode is
    active.  On *redo* the supplied elevation is written to every
    :class:`~digcalc_project.src.ui.items.vertex_item.VertexItem`.  *undo*
    restores the original Z values captured during construction.

    Args:
        polyline: The ``PolylineItem`` whose vertices will be modified.
        z: The elevation (Z) value to apply in *feet*.
    """

    def __init__(self, polyline: PolylineItem, z: float):
        super().__init__("Set line elevation")
        self._polyline: PolylineItem = polyline
        self._new_z: float = float(z)
        # Capture original Z values in the order of vertices
        self._old_z: List[float] = [v.z() for v in polyline.vertices()]

    # ------------------------------------------------------------------
    # QtUndoCommand overrides
    # ------------------------------------------------------------------
    def redo(self):  # noqa: D401 – Qt signature
        """Apply the uniform Z elevation to all vertices."""
        for v in self._polyline.vertices():
            v.set_z(self._new_z)

    def undo(self):  # noqa: D401 – Qt signature
        """Restore the original per-vertex elevations that existed before redo."""
        for v, old_z in zip(self._polyline.vertices(), self._old_z):
            v.set_z(old_z) 