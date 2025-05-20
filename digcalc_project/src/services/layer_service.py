"""Helper utilities for working with *Layer* objects.

This tiny service centralises logic for generating new layers with cycling
colours so the UI can simply call ``create_layer()`` rather than constructing
:class:`digcalc_project.src.models.layer.Layer` directly.
"""

from uuid import uuid4

# NOTE: Relative import (services ─► models)
from ..models.layer import Layer

__all__ = ["create_layer"]


def create_layer(name: str, mode: str = "entered") -> Layer:  # noqa: D401
    """Return a new ``Layer`` with a unique *id* and next palette colours."""
    line_col, point_col = Layer.next_default_colors()
    return Layer(
        id=str(uuid4()),
        name=name,
        mode=mode,  # type: ignore[arg-type]  # Literal validated at Layer level
        line_color=line_col,
        point_color=point_col,
        visible=True,
    ) 