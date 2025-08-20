from __future__ import annotations

"""digcalc_project.src.core.calculations.linear_grade

Utility helpers for linear grade interpolation used by Elevation-related dialogs.

The main helper :pyfunc:`interpolate_z_linear` converts a chain of XY vertices
into per-vertex Z values that follow a straight-line grade between the first
and last vertex (specified either explicitly or via slope percentage).
"""

from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "interpolate_z_linear",
]


# -----------------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------------


def interpolate_z_linear(
    xy: Sequence[Tuple[float, float]] | np.ndarray,
    *,
    first_z: float,
    last_z: Optional[float] = None,
    slope_percent: Optional[float] = None,
) -> List[float]:
    """Return per-vertex elevations following a straight grade.

    Exactly one of ``last_z`` *or* ``slope_percent`` must be supplied.

    Args
    -----
    xy:
        Iterable of *(x, y)* coordinates representing consecutive vertices.
    first_z:
        Elevation (ft) to assign to the **first** vertex.
    last_z:
        Elevation (ft) of the **last** vertex.  Mutually exclusive with
        *slope_percent*.
    slope_percent:
        Grade as **percent** (ΔZ/ΔXY × 100).  Positive values slope *upwards*
        when moving from the first towards the last vertex, negative values
        slope *down*.  Mutually exclusive with *last_z*.

    Returns
    -------
    list[float]
        New Z values – same length as *xy*.

    Raises
    ------
    ValueError
        If both or neither of *last_z* and *slope_percent* are provided.
    """

    if (last_z is None and slope_percent is None) or (
        last_z is not None and slope_percent is not None
    ):
        raise ValueError("Provide exactly one of 'last_z' or 'slope_percent'.")

    # Convert coordinates to NumPy array for fast math
    xy_arr = np.asarray(xy, dtype=float)
    if xy_arr.ndim != 2 or xy_arr.shape[1] != 2:
        raise ValueError("'xy' must have shape (N, 2)")

    # Compute cumulative chord lengths starting at 0 for the first vertex
    deltas = np.diff(xy_arr, axis=0)
    seg_lengths = np.hypot(deltas[:, 0], deltas[:, 1])
    cum_dist = np.concatenate(([0.0], np.cumsum(seg_lengths)))
    total_len = float(cum_dist[-1])

    # Guard zero-length polyline – return constant grade
    if total_len < 1e-12:
        return [first_z for _ in xy_arr]

    if slope_percent is not None:
        # ΔZ = slope% / 100 × total horizontal distance
        dz_total = float(slope_percent) / 100.0 * total_len
        last_z = first_z + dz_total
    else:
        assert last_z is not None  # mypy guard
        dz_total = float(last_z) - float(first_z)

    # Interpolate Z for each vertex proportional to distance along chain
    z_values = first_z + (cum_dist / total_len) * dz_total
    return z_values.tolist()
