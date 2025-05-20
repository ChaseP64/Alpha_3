from __future__ import annotations

"""Undo-redo command to toggle a *Layer*'s visibility flag.

This updates the legend dock and the 2-D tracing scene so polylines appear or
hide instantly and the action is fully undoable.
"""

from PySide6.QtGui import QUndoCommand

from digcalc_project.src.models.layer import Layer

__all__ = ["SetLayerVisibilityCommand"]


class SetLayerVisibilityCommand(QUndoCommand):
    def __init__(self, layer: Layer, new_val: bool, dock):
        super().__init__(f"Toggle {layer.name} visibility")
        self._layer = layer
        self._new = bool(new_val)
        self._old = layer.visible
        self._dock = dock  # LayerLegendDock

    # ------------------------------------------------------------------
    def redo(self):  # noqa: N802
        self._layer.visible = self._new
        self._after()

    def undo(self):  # noqa: N802
        self._layer.visible = self._old
        self._after()

    # ------------------------------------------------------------------
    def _after(self):
        """Refresh dock + scene after state change."""
        if self._dock and hasattr(self._dock, "refresh"):
            self._dock.refresh()
        # Inform scene (via dock's signal) to update visibility
        if self._dock and hasattr(self._dock, "layerVisibilityToggled"):
            self._dock.layerVisibilityToggled.emit(self._layer.id, self._layer.visible) 