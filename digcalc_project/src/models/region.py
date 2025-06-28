from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from uuid import uuid4

Point2D = Tuple[float, float]

@dataclass(slots=True)
class Region:
    """Named polygon with optional stripping depth (ft)."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Unnamed Region"
    polygon: List[Point2D] = field(default_factory=list)
    strip_depth_ft: Optional[float] = None   # None → fallback to global default
    # Accept meters input for convenience (tests use strip_depth_m)
    strip_depth_m: Optional[float] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        # Convert meters to feet if provided and ft not already set
        if self.strip_depth_m is not None and self.strip_depth_ft is None:
            self.strip_depth_ft = self.strip_depth_m / 0.3048

    # --- (de)serialization ---
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "polygon": self.polygon,
            "strip_depth_ft": self.strip_depth_ft,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Region:
        return cls(
            id=d["id"],
            name=d["name"],
            polygon=[tuple(pt) for pt in d["polygon"]],
            strip_depth_ft=d.get("strip_depth_ft"),
        )

