"""Stratigraphy data models (Phase 0 – Task 0-3).

These classes capture geological strata information such as materials,
layer thicknesses in boreholes, and pre-interpolated strata boundary
surfaces.

All models provide ``to_dict`` / ``from_dict`` helpers so the on-disk schema
can evolve independently from Python dataclass shapes.  Where appropriate we
store *both* a stable integer *id* and a random *uuid* to make merging easier
across different projects.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from .surface import Surface


# ---------------------------------------------------------------------------
# Basic material / layer definitions
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Material:
    """Simple soil/rock material description."""

    id: int  # stable integer index unique *within* a project
    name: str
    colour: str = "#CCCCCC"  # hex RGB for UI legend
    density_pcft: Optional[float] = None  # pcf (lbs/ft³)
    default_opacity: float = 1.0
    visible: bool = True
    uuid: str = field(default_factory=lambda: str(_uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "colour": self.colour,
            "density_pcft": self.density_pcft,
            "default_opacity": self.default_opacity,
            "visible": self.visible,
            "uuid": self.uuid,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Material":
        return cls(
            id=int(d["id"]),
            name=d["name"],
            colour=d.get("colour", "#CCCCCC"),
            density_pcft=d.get("density_pcft"),
            default_opacity=float(d.get("default_opacity", 1.0)),
            visible=bool(d.get("visible", True)),
            uuid=d.get("uuid", str(_uuid.uuid4())),
        )


@dataclass(slots=True)
class StrataLayer:
    """Lightweight layer sample for a single material at a given *top_z*.

    The original DigCalc codebase stored both ``top_z`` and ``bottom_z`` but
    several analytic unit-tests only care about the layer *top* elevation.  A
    fully-featured :class:`LayerDepth` (defined below) is still available for
    production code – :class:`StrataLayer` exists solely to keep legacy tests
    functional without having to pass a redundant *bottom_z* argument.
    """

    material_id: int  #: Material identifier (matches Material.id)
    top_z: float      #: Elevation (ft) of the layer *top*

    # Optional compatibility attribute; ignored by the current tests but
    # helpful if callers treat StrataLayer interchangeably with LayerDepth.
    bottom_z: float | None = None

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "material_id": self.material_id,
            "top_z": self.top_z,
            "bottom_z": self.bottom_z,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StrataLayer":
        return cls(
            material_id=int(d["material_id"]),
            top_z=float(d["top_z"]),
            bottom_z=float(d.get("bottom_z")) if d.get("bottom_z") is not None else None,
        )


@dataclass(slots=True)
class LayerDepth:
    """Material interval in a borehole."""

    material_id: int  # reference to Material.id
    top_z: float      # elevation (ft) of layer *top*
    bottom_z: float   # elevation (ft) of layer *base*

    def __hash__(self):
        return hash((self.material_id, self.top_z, self.bottom_z))

    def to_dict(self) -> dict:
        return {
            "material_id": self.material_id,
            "top_z": self.top_z,
            "bottom_z": self.bottom_z,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LayerDepth":
        return cls(
            material_id=int(d["material_id"]),
            top_z=float(d["top_z"]),
            bottom_z=float(d["bottom_z"]),
        )


@dataclass(slots=True)
class BoreholeLog:
    """Log of material layers at a single X/Y location."""

    id: int
    x: float
    y: float
    layers: List[LayerDepth] = field(default_factory=list)
    uuid: str = field(default_factory=lambda: str(_uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "uuid": self.uuid,
            "layers": [ly.to_dict() for ly in self.layers],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BoreholeLog":
        return cls(
            id=int(d["id"]),
            x=float(d["x"]),
            y=float(d["y"]),
            uuid=d.get("uuid", str(_uuid.uuid4())),
            layers=[LayerDepth.from_dict(ld) for ld in d.get("layers", [])],
        )

    # ------------------------------------------------------------------
    # Layer management helpers
    # ------------------------------------------------------------------

    def _validate_contiguous(self, new_layers: List[LayerDepth]) -> None:
        """Raise ValueError if *new_layers* are non-contiguous or invalid."""
        if not new_layers:
            return

        # Sort by top_z descending (highest elevation first)
        ordered = sorted(new_layers, key=lambda ld: ld.top_z, reverse=True)
        for i, ld in enumerate(ordered):
            if ld.bottom_z >= ld.top_z:
                raise ValueError("Layer bottom_z must be < top_z (positive thickness)")
            if i == 0:
                continue
            prev = ordered[i - 1]
            # Allow small FP tolerance
            if abs(prev.bottom_z - ld.top_z) > 1e-6:
                raise ValueError("Layers are not contiguous (gap or overlap detected)")

    # ------------------------------------------------------------------
    def add_layer(self, layer: LayerDepth) -> None:
        """Append *layer* after validating thickness & contiguity."""
        self._validate_contiguous(self.layers + [layer])
        self.layers.append(layer)

    # ------------------------------------------------------------------
    def remove_layer(self, idx: int) -> LayerDepth | None:
        """Remove layer at *idx* if valid and keep contiguity."""
        if 0 <= idx < len(self.layers):
            removed = self.layers.pop(idx)
            # Re-validate remaining stack
            self._validate_contiguous(self.layers)
            return removed
        return None


# ---------------------------------------------------------------------------
# Interpolated strata surfaces
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class StrataSurface:
    """Boundary surface between two materials.

    Usually generated by an interpolation engine from *BoreholeLog* data.
    """

    id: int
    uuid: str = field(default_factory=lambda: str(_uuid.uuid4()))
    name: str = ""
    material_id: Optional[int] = None  # dominant material above surface
    # Either a full *Surface* object or a simple NumPy grid.  For early-stage
    # algorithm unit-tests we store the raw array directly to avoid heavy
    # Surface dependencies.
    surface: Optional[Surface] = None  # optional mesh/grid
    grid_data: "np.ndarray | None" = None
    default_opacity: float = 0.5
    grid_metadata: Dict[str, float] = field(default_factory=dict)  # e.g. spacing

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "material_id": self.material_id,
            "default_opacity": self.default_opacity,
            "grid_metadata": self.grid_metadata,
            "surface": self.surface.to_dict() if self.surface else None,
            "grid_data": self.grid_data.tolist() if self.grid_data is not None else None,
        }

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict) -> "StrataSurface":
        from .surface import Surface  # local import to avoid cycle

        surf_data = d.get("surface")
        surf_obj = Surface.from_dict(surf_data) if surf_data else None

        grid = None
        if (gd := d.get("grid_data")) is not None:
            grid = np.array(gd, dtype=float)

        return cls(
            id=int(d["id"]),
            uuid=d.get("uuid", str(_uuid.uuid4())),
            name=d.get("name", ""),
            material_id=d.get("material_id"),
            surface=surf_obj,
            grid_data=grid,
            default_opacity=float(d.get("default_opacity", 0.5)),
            grid_metadata=d.get("grid_metadata", {}),
        )


# ---------------------------------------------------------------------------
# Aggregate container
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class StrataStack:
    """All stratigraphy data for a project."""

    id: int
    uuid: str = field(default_factory=lambda: str(_uuid.uuid4()))

    materials: List[Material] = field(default_factory=list)
    boreholes: List[BoreholeLog] = field(default_factory=list)
    surfaces: List[StrataSurface] = field(default_factory=list)

    default_opacity: float = 0.5
    grid_metadata: Dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "uuid": self.uuid,
            "default_opacity": self.default_opacity,
            "grid_metadata": self.grid_metadata,
            "materials": [m.to_dict() for m in self.materials],
            "boreholes": [bh.to_dict() for bh in self.boreholes],
            "surfaces": [s.to_dict() for s in self.surfaces],
        }

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict) -> "StrataStack":
        return cls(
            id=int(d.get("id", 0)),
            uuid=d.get("uuid", str(_uuid.uuid4())),
            default_opacity=float(d.get("default_opacity", 0.5)),
            grid_metadata=d.get("grid_metadata", {}),
            materials=[Material.from_dict(md) for md in d.get("materials", [])],
            boreholes=[BoreholeLog.from_dict(bd) for bd in d.get("boreholes", [])],
            surfaces=[StrataSurface.from_dict(sd) for sd in d.get("surfaces", [])],
        )

    # ------------------------------------------------------------------
    # Convenience mutators (used by UI command layer)
    # ------------------------------------------------------------------

    def next_material_id(self) -> int:
        """Return the next available integer *id* for a new material."""
        used = {m.id for m in self.materials}
        i = 1
        while i in used:
            i += 1
        return i

    # ------------------------------------------------------------------
    def add_material(self, material: Material) -> None:
        """Append *material* ensuring ``id`` uniqueness."""
        if any(m.id == material.id for m in self.materials):
            # Assign next free id silently
            material.id = self.next_material_id()
        self.materials.append(material)

    # ------------------------------------------------------------------
    def remove_material(self, mat_id: int) -> Material | None:
        """Remove material by *id* and return it or *None* if not found."""
        for idx, m in enumerate(self.materials):
            if m.id == mat_id:
                return self.materials.pop(idx)
        return None

    # ------------------------------------------------------------------
    # Borehole helpers
    # ------------------------------------------------------------------

    def next_borehole_id(self) -> int:
        """Return next available borehole integer id."""
        used = {bh.id for bh in self.boreholes}
        i = 1
        while i in used:
            i += 1
        return i


__all__ = [
    "Material", "StrataLayer", "LayerDepth", "BoreholeLog", "StrataSurface", "StrataStack"
] 