from __future__ import annotations

"""digcalc_project.src.services.cleaners.smart_clean

Placeholder for automatic polyline clean-up routines (gap closing, duplicate
removal, etc.).  Implemented properly in Phase-2; for now just exposes a
stable function signature used by the PDF vectorizer integration.
"""

from typing import List, Sequence

from ...core.geom.polyline import Polyline

__all__ = ["auto_run"]


def auto_run(polylines: Sequence[Polyline]) -> List[Polyline]:
    """Return a cleaned copy of *polylines* (currently no-op)."""

    # TODO: real clean-up logic Phase-2
    return list(polylines) 