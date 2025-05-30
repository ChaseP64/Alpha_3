from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pyvista as pv
from qtpy.QtGui import QColor


@dataclass
class MeshActor:
    """View-state wrapper that links a Project.Surface (or future strata slice)
    to its PyVista actor and style options.

    This dataclass stores all visual parameters that influence how a particular
    surface is rendered inside the 3-D viewer as well as a reference to the
    underlying *PyVista* actor once it has been added to the scene.  The actor
    reference is **not** considered part of the persistent project state – it
    is only valid for the lifetime of the Qt application and therefore must
    not be serialised.
    """

    # Link back to the logical model
    surface_name: str

    # Geometry
    mesh: pv.PolyData

    # Styling / rendering options
    color: QColor
    opacity: float = 1.0
    representation: str = "surface"  # surface | wireframe | points
    edge_color: QColor = field(default_factory=lambda: QColor("black"))
    line_width: int = 1
    point_size: int = 5
    visible: bool = True

    # Runtime-only field (excluded from serialisation)
    actor: Optional[pv.Actor] = None 