from __future__ import annotations

"""Undoable command to change a Layer's colour (line or point).

This command is lightweight and does **not** trigger a full project-save.  The
caller (typically the *LayerDock* or tests) is responsible for pushing the
command on the relevant :class:`QUndoStack`.
"""

import logging # Added import
from PySide6.QtGui import QUndoCommand
# import sys # For printing to stderr - No longer needed

from digcalc_project.src.models.layer import Layer

__all__ = ["SetLayerColorCommand"]


class SetLayerColorCommand(QUndoCommand):
    """Undo-redo wrapper for *Layer* colour tweaks."""

    def __init__(self, layer: Layer, attr: str, new_val: str, dock):
        super().__init__(f"Change {layer.name} {attr.replace('_', ' ')}")
        self.logger = logging.getLogger(__name__) # Added logger initialization

        if attr not in ("line_color", "point_color"):
            raise ValueError("attr must be 'line_color' or 'point_color'")

        self._layer = layer
        self._attr = attr
        self._new = new_val
        self._old = getattr(layer, attr)
        self._dock = dock  # LayerDock or any object exposing refresh_layer_item()

    # ------------------------------------------------------------------
    # Qt undo/redo overrides
    # ------------------------------------------------------------------
    def redo(self):  # noqa: N802 – Qt naming
        setattr(self._layer, self._attr, self._new)
        self._refresh()

    def undo(self):  # noqa: N802 – Qt naming
        setattr(self._layer, self._attr, self._old)
        self._refresh()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _refresh(self):
        if not self._dock:
            return

        # 1) Preferred: scene-level helper (TracingScene)
        refresh_fn = getattr(self._dock, "refresh_layer_item", None)
        if callable(refresh_fn):
            try:
                refresh_fn(self._layer.id)
            except Exception as exc:
                self.logger.warning("refresh_layer_item failed: %s", exc, exc_info=True)
        else:
            # Fallback: update any PolylineItem in the scene manually
            from digcalc_project.src.ui.items.polyline_item import PolylineItem
            from PySide6.QtGui import QColor, QPen

            try:
                for item in getattr(self._dock, "items", lambda: [])():
                    if isinstance(item, PolylineItem) and getattr(item, "layer_id", None) == self._layer.id:
                        item.update_color(self._layer.line_color)
            except Exception as exc:
                self.logger.warning("Manual layer recolour fallback failed: %s", exc, exc_info=True)

        # 2) Optional legend-dock refresh
        legend_fn = getattr(self._dock, "update_layer_colors", None)
        if callable(legend_fn):
            try:
                legend_fn(self._layer.id)
            except Exception:
                pass 