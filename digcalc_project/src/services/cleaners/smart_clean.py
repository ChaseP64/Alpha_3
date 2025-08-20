from __future__ import annotations

"""digcalc_project.src.services.cleaners.smart_clean

Placeholder for automatic polyline clean-up routines (gap closing, duplicate
removal, etc.).  Implemented properly in Phase-2; for now just exposes a
stable function signature used by the PDF vectorizer integration.
"""

import time
from typing import TYPE_CHECKING, List, Sequence

from ...core.clean.rule_engine import RuleRegistry
from ...core.geom.polyline import Polyline
from ..settings_service import SettingsService

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

    # Phase-2: optional Automatic Join V2 pre-processing -------------------
    settings = SettingsService()
    if settings.enable_auto_join_v2():
        t0 = time.perf_counter()
        unique = Polyline.auto_join_v2(unique)
        t1 = time.perf_counter()
        # Lightweight profiling log; keep silent in tests
        try:
            import logging

            logging.getLogger(__name__).debug("SmartClean join_v2: %.2f ms", (t1 - t0) * 1000.0)
        except Exception:
            pass

    # Compression phase -------------------------------------------------
    dist_tol = settings.compress_dist_tol_ft()
    angle_tol = settings.compress_angle_tol_deg()
    t0 = time.perf_counter()
    unique = [Polyline.compress(pl, dist_tol=dist_tol, angle_tol_deg=angle_tol) for pl in unique]
    t1 = time.perf_counter()
    try:
        import logging

        logging.getLogger(__name__).debug("SmartClean compress: %.2f ms", (t1 - t0) * 1000.0)
    except Exception:
        pass

    # Run registered Smart-Clean rules
    return RuleRegistry.evaluate(unique)
