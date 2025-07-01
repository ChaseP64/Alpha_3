from __future__ import annotations

"""digcalc_project.src.services.cleaners.smart_clean

Placeholder for automatic polyline clean-up routines (gap closing, duplicate
removal, etc.).  Implemented properly in Phase-2; for now just exposes a
stable function signature used by the PDF vectorizer integration.
"""

from typing import List, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ...core.geom.polyline import Polyline

__all__ = ["auto_run"]


def auto_run(polylines: "Sequence[Polyline]") -> List["Polyline"]:  # type: ignore[name-defined]
    """Return a cleaned copy of *polylines* (currently no-op)."""

    # NOTE: Phase-1 only performs a *de-duplication* pass.  Real topology & gap
    # fixing arrives in Phase-2.

    # Cheap de-duplication based on vertex hashes
    seen: set[int] = set()
    unique: list[Polyline] = []

    import numpy as np

    for pl in polylines:  # type: ignore[misc]
        h = hash(np.round(pl.vertices, 6).tobytes())
        if h not in seen:
            seen.add(h)
            unique.append(pl)

    return unique 