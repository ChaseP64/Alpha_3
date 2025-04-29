#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Undo command to add/remove a pad polyline with constant elevation.

A *pad* is treated here as a closed polyline (polygon) whose vertices share the
same elevation.  This command adds the pad to a `TracingScene` without nesting
another undo command inside it (avoiding double-pushes).
"""

from __future__ import annotations

from typing import List, Tuple, Optional

from PySide6.QtGui import QUndoCommand

# Locals
from digcalc_project.src.ui.tracing_scene import TracingScene

Point3D = Tuple[float, float, float]


class SetPadElevationCommand(QUndoCommand):
    """Adds or removes a pad polyline from a :class:`TracingScene`."""

    def __init__(self, scene: TracingScene, pts3d: List[Point3D], layer: str = "Pads"):  # noqa: D401
        super().__init__("Set pad elevation")
        if len(pts3d) < 3:
            raise ValueError("Pad must contain at least three vertices (closed polygon).")
        self._scene = scene
        self._pts: List[Point3D] = pts3d
        self._layer = layer
        self._item = None  # QGraphicsPathItem created on first redo()

    # ------------------------------------------------------------------
    # QUndoCommand API
    # ------------------------------------------------------------------
    def redo(self):  # noqa: D401
        """Add (or show) the pad polyline in the scene."""
        if self._item is None:
            # `add_offset_breakline` returns the item when *push_to_undo* is False
            self._item = self._scene.add_offset_breakline(self._pts, push_to_undo=False)
            # Tag with layer name for visibility filtering
            if self._item:
                self._item.setData(0, self._layer)
        else:
            self._item.setVisible(True)

    def undo(self):  # noqa: D401
        """Hide (effectively remove) the pad polyline from the scene."""
        if self._item:
            self._item.setVisible(False) 