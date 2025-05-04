from PySide6.QtGui import QUndoCommand

class EditVertexZCommand(QUndoCommand):
    """Undo/redo command that edits a :class:`VertexItem` elevation (Z value)."""

    def __init__(self, vertex, new_z: float, description: str = "Edit Vertex Elevation"):
        """Initialise the command.

        Args:
            vertex: The vertex item whose elevation will be modified. Must expose
                :py:meth:`z` and :py:meth:`set_z` helpers.
            new_z (float): The new elevation value.
            description (str, optional): Description shown in the undo stack/GUI.
        """
        super().__init__(description)
        self._v = vertex
        # Cache the old and new values for undo/redo
        self._old: float = float(vertex.z())
        self._new: float = float(new_z)

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------
    def undo(self):  # noqa: D401
        """Restore the previous elevation value."""
        self._v.set_z(self._old)

    def redo(self):  # noqa: D401
        """Apply the new elevation value."""
        self._v.set_z(self._new) 