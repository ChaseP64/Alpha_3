from __future__ import annotations
from dataclasses import dataclass, field
from uuid import uuid4
from typing import List, Tuple, Optional

Point2D = Tuple[float, float]

@dataclass(slots=True)
class Region:
    """Named polygon with optional stripping depth (ft)."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Unnamed Region"
    polygon: List[Point2D] = field(default_factory=list)
    strip_depth_ft: Optional[float] = None   # None → fallback to global default

    # --- (de)serialization ---
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "polygon": self.polygon,
            "strip_depth_ft": self.strip_depth_ft,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Region":
        return cls(
            id=d["id"],
            name=d["name"],
            polygon=[tuple(pt) for pt in d["polygon"]],
            strip_depth_ft=d.get("strip_depth_ft"),
        )

