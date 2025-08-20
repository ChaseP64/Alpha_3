from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
from uuid import uuid4


@dataclass(slots=True)
class Template:
    """Reusable excavation template definition.

    Supports simple types like "pad" and "trench" with parameter payload.

    Attributes:
        id: Stable identifier for the template
        name: Human-readable name
        type: Template kind (e.g., "pad", "trench")
        params: Free-form parameters dict (e.g., width, length, depth)
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "New Template"
    type: str = "pad"
    params: Dict[str, float] = field(default_factory=dict)
    description: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "params": self.params,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Template:
        """Create a Template from a dictionary."""
        return cls(
            id=data.get("id") or str(uuid4()),
            name=data.get("name", "New Template"),
            type=str(data.get("type", "pad")),
            params=dict(data.get("params", {})),
            description=data.get("description"),
        )

