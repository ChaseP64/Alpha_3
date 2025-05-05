from PySide6.QtGui import QUndoCommand

class ToggleSmoothCommand(QUndoCommand):
    """Undo/redo command that toggles a polyline's smooth (interpolated) mode."""

    def __init__(self, polyline):
        super().__init__("Toggle smooth")
        self._pl = polyline

    # ------------------------------------------------------------------
    # QUndoCommand interface
    # ------------------------------------------------------------------
    def undo(self):  # noqa: D401
        """Revert the polyline to its previous smoothing state."""
        self._pl.toggle_mode()

    def redo(self):  # noqa: D401
        """Apply the smoothing toggle on the polyline."""
        self._pl.toggle_mode() 