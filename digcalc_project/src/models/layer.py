from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal


@dataclass
class Layer:
    """Represents a traced layer within a DigCalc project.

    A *layer* groups geometry (polylines, points) that share meaning – for
    example *Existing Ground* or *Design Surface* – and carries styling
    information so the UI can render it consistently.
    """

    id: str
    name: str
    mode: Literal["entered", "interpolated"] = "entered"

    # --- NEW Style ---------------------------------------------------
    line_color: str = "#4DBBD5"  # default sky-blue
    point_color: str = "#4DBBD5"

    # Visibility flag (affects layer legend & scene rendering)
    visible: bool = True

    # --- Class-level rotating palette -------------------------------
    _PALETTE: ClassVar[list[str]] = [
        "#4DBBD5", "#CB4ED6", "#FF8F00", "#43A047",
        "#C2185B", "#3D5AFE", "#FF5252", "#00897B",
        "#F9A825", "#5E35B1", "#039BE5", "#D500F9",
    ]
    _next_idx: ClassVar[int] = 0

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    @classmethod
    def next_default_colors(cls) -> tuple[str, str]:
        """Return the next colour pair from the rotating palette."""
        colour = cls._PALETTE[cls._next_idx % len(cls._PALETTE)]
        cls._next_idx += 1
        return colour, colour 