"""Catmull-Rom spline helper for DigCalc.

Provides a utility to convert a list of QPointF control points into a smoothed
QPainterPath using the Catmull-Rom interpolation scheme. When fewer than three
control points are supplied, the helper gracefully falls back to drawing a
straight poly-line so that callers do not need to special-case their input size.
"""
from __future__ import annotations

# ----------------------------------------------------------------------
# Extras needed for sampling helper
# ----------------------------------------------------------------------
import hashlib
import math
from typing import List, Tuple

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath

# Internal cache keyed by density + vertex hash so repeated requests are cheap
_sample_cache: dict[str, List[Tuple[float, float, float]]] = {}


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------


def _points_to_xyz(pts: List[QPointF]) -> List[Tuple[float, float, float]]:
    """Convert ``QPointF`` list → sequence of (x, y, z) tuples.

    A ``QPointF`` does not expose *z* out-of-the-box.  If callers provide a
    subclass or monkey-patched attribute/property ``z``/``z()`` we happily
    consume it, otherwise we default to zero for compatibility.
    """
    out: List[Tuple[float, float, float]] = []
    for pt in pts:
        # Be tolerant – support .z attribute *or* .z() method if supplied.
        z_val = 0.0
        if hasattr(pt, "z"):
            z_attr = pt.z  # could be value or callable
            z_val = z_attr() if callable(z_attr) else float(z_attr)
        out.append((float(pt.x()), float(pt.y()), float(z_val)))
    return out


def _vertex_hash(pts: List[QPointF]) -> str:
    """Return SHA-1 hash for the *x,y* coordinates – cache key helper."""
    h = hashlib.sha1()
    for pt in pts:
        h.update(float(pt.x()).hex().encode())
        h.update(float(pt.y()).hex().encode())
    return h.hexdigest()


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def sample(pts: List[QPointF], density_ft: float = 1.0) -> List[Tuple[float, float, float]]:  # noqa: E501
    r"""Return evenly spaced (≈ *density_ft*) points along a smoothed spline.

    Behaviour
    ---------
    1. **SciPy available** – Use *cubic B-spline* (clamped ends, \(k=3\), \(s=0\))
       constructed in chord-length parameter space for robustness.
    2. **SciPy missing/fails** – Gracefully fall back to *linear* densify so
       callers *always* get a usable result.

    The routine internally caches results by ``(density, SHA-1(vertices))`` so
    repeated calls are *O(1)* after the first computation.
    """
    # Degenerate cases – nothing or singleton list – just echo back.
    if len(pts) < 2:
        return _points_to_xyz(pts)

    # Compose cache key
    key = f"{density_ft:.3f}-{_vertex_hash(pts)}"
    if key in _sample_cache:
        return _sample_cache[key]

    xyz = _points_to_xyz(pts)

    # ------------------------------------------------------------------
    # Attempt SciPy-powered resample first
    # ------------------------------------------------------------------
    try:
        import numpy as np
        from scipy import interpolate

        arr = np.asarray(xyz, dtype=float)

        # Chord-length parameterisation – robust with non-uniform spacing.
        dists = np.linalg.norm(np.diff(arr[:, :2], axis=0), axis=1)
        if np.allclose(dists, 0):
            # All points coincident – nothing to interpolate.
            _sample_cache[key] = xyz
            return xyz

        t = np.insert(np.cumsum(dists), 0, 0.0)
        t /= t[-1]  # normalise to [0,1]

        # Build *clamped* cubic splines for each component.
        spl_x = interpolate.CubicSpline(t, arr[:, 0], bc_type="clamped")
        spl_y = interpolate.CubicSpline(t, arr[:, 1], bc_type="clamped")
        spl_z = interpolate.CubicSpline(t, arr[:, 2], bc_type="clamped")

        length_ft = float(np.sum(dists))
        n_samples: int = max(2, int(math.ceil(length_ft / density_ft)))
        ts = np.linspace(0.0, 1.0, n_samples)

        out: List[Tuple[float, float, float]] = list(zip(spl_x(ts), spl_y(ts), spl_z(ts)))

    except Exception:  # pragma: no cover – SciPy absent or failed numerical issue
        # Fallback – linear densify so API still returns useful data.
        out = _linear_resample(xyz, density_ft)

    _sample_cache[key] = out
    return out


# ----------------------------------------------------------------------
# Helper – linear densify (fallback)
# ----------------------------------------------------------------------


def _linear_resample(xyz: List[Tuple[float, float, float]], density: float) -> List[Tuple[float, float, float]]:
    """Return linearly densified points along *xyz* polyline."""
    import numpy as np

    arr = np.asarray(xyz, dtype=float)
    seglens = np.linalg.norm(np.diff(arr[:, :2], axis=0), axis=1)

    pts: List[Tuple[float, float, float]] = [tuple(arr[0])]
    for p0, p1, seg_len in zip(arr[:-1], arr[1:], seglens):
        if seg_len == 0:
            continue  # coincident
        n = max(1, int(math.ceil(seg_len / density)))
        for k in range(1, n + 1):
            t = k / n
            pts.append(tuple(p0 + (p1 - p0) * t))
    return pts


# ----------------------------------------------------------------------
# Update public symbols
# ----------------------------------------------------------------------

__all__ = ["catmull_rom", "sample"]


def catmull_rom(pts: List[QPointF], samples_per_seg: int = 8) -> QPainterPath:
    """Return a Catmull-Rom interpolated ``QPainterPath``.

    The helper walks the provided *pts* list and creates a smoothed
    :class:`~PySide6.QtGui.QPainterPath` that passes through each control
    point. Internally, intermediate sample points are inserted for every
    segment using the Catmull-Rom basis matrix.  If the caller passes fewer
    than three points, the routine simply returns a straight poly-line so that
    all inputs remain valid.

    Args:
        pts (List[QPointF]): Control points to interpolate. The list is **not**
            modified.
        samples_per_seg (int, optional): The number of sub-samples that will be
            generated *per segment* between control points.  Higher values
            yield smoother curves at the expense of more geometry.  Defaults to
            ``8``.

    Returns:
        QPainterPath: A path that starts at ``pts[0]`` and ends at the last
            control point while smoothly passing through the intermediate
            points.

    """
    # Defensive programming – allow any iterable, but materialise once.
    pts = list(pts)

    if len(pts) < 3:
        # Degenerate cases fall back to straight lines – at most one line
        # between points – so callers do not need to special-case small lists.
        path = QPainterPath()
        if pts:
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
        return path

    path = QPainterPath()
    path.moveTo(pts[0])

    # Iterate over successive sets of 4 points (p0..p3) to build the spline.
    # We start at i=1 so that p1 is the *current* control point; p0 is the
    # previous one.  The loop therefore runs until len(pts)-2 so that p3 exists.
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1 : i + 3]  # slice is inclusive-exclusive

        for j in range(1, samples_per_seg + 1):
            t = j / samples_per_seg
            t2 = t * t
            t3 = t2 * t

            # Catmull-Rom basis matrix applied component-wise.
            x = 0.5 * (
                (2 * p1.x())
                + (-p0.x() + p2.x()) * t
                + (2 * p0.x() - 5 * p1.x() + 4 * p2.x() - p3.x()) * t2
                + (-p0.x() + 3 * p1.x() - 3 * p2.x() + p3.x()) * t3
            )
            y = 0.5 * (
                (2 * p1.y())
                + (-p0.y() + p2.y()) * t
                + (2 * p0.y() - 5 * p1.y() + 4 * p2.y() - p3.y()) * t2
                + (-p0.y() + 3 * p1.y() - 3 * p2.y() + p3.y()) * t3
            )

            path.lineTo(x, y)

    # Ensure we end exactly at the last control point.
    path.lineTo(pts[-1])
    return path
