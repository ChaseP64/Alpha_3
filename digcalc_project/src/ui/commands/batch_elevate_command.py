from __future__ import annotations

"""BatchElevateCommand – apply elevation changes to multiple polylines in one undo step.

Phase-5 D2 requirement: user can multi-select several ``PolylineItem`` objects and
apply either a *uniform* elevation or a *slope percentage* (linear grade) across
each polyline.  All modifications are grouped so that a single *undo* reverses
all changes.
"""

from typing import List, Optional

from PySide6.QtGui import QUndoCommand

from digcalc_project.src.ui.items.polyline_item import PolylineItem
from digcalc_project.src.ui.commands.set_polyline_uniform_z_command import (
    SetPolylineUniformZCommand,
)
from digcalc_project.src.ui.commands.auto_increment_z_command import (
    AutoIncrementZCommand,
)

__all__ = ["BatchElevateCommand"]


class BatchElevateCommand(QUndoCommand):
    """Group elevation edits across multiple polylines in a single command."""

    def __init__(
        self,
        polylines: List[PolylineItem],
        *,
        uniform_z: Optional[float] = None,
        first_z: Optional[float] = None,
        slope_percent: Optional[float] = None,
    ):
        """Construct the command.

        Exactly **one** of the following mode combinations must be supplied:

        • *uniform_z* – constant elevation applied to *all* vertices in every
          supplied polyline.
        • *first_z* + *slope_percent* – linear grade applied individually to
          each polyline starting at *first_z*.
        """

        super().__init__("Batch Elevate Polylines")

        if not polylines:
            raise ValueError("At least one polyline required for batch elevate.")

        # Validate mode selection
        uniform_mode = uniform_z is not None
        slope_mode = slope_percent is not None and first_z is not None
        if uniform_mode == slope_mode:  # both True or both False
            raise ValueError(
                "Provide exactly *uniform_z* OR (*first_z* + *slope_percent*)."
            )

        self._sub_cmds: List[QUndoCommand] = []

        if uniform_mode:
            z_val = float(uniform_z)  # type: ignore[arg-type]
            self._sub_cmds = [SetPolylineUniformZCommand(pl, z_val) for pl in polylines]
        else:
            assert first_z is not None and slope_percent is not None
            for pl in polylines:
                verts = pl.vertices()
                cmd = AutoIncrementZCommand(
                    verts,
                    first_z=first_z,
                    slope_percent=slope_percent,
                )
                self._sub_cmds.append(cmd)

    # --------------------------------------------- QUndoCommand overrides
    def redo(self):
        for cmd in self._sub_cmds:
            cmd.redo()

    def undo(self):
        # reverse order for deterministic undo
        for cmd in reversed(self._sub_cmds):
            cmd.undo() 