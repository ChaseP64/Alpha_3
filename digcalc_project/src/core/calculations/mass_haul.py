from __future__ import annotations

"""digcalc_project.src.core.calculations.mass_haul

Mass-haul (earth-moving) calculation utilities.

This module provides functionality to project cut/fill volumes along a
user-defined haul alignment and build the classical *mass-haul curve*.

The implementation deliberately avoids any direct UI or file I/O so it can
be unit-tested in isolation.
"""

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, TYPE_CHECKING

import numpy as np
from shapely.geometry import LineString, Point

# Local imports – doing it this way avoids a circular-import risk while keeping
# the dependency explicit. We purposefully avoid a *"from models import Surface"*
# import because that would create a hard runtime dependency. Instead we rely on
# Python duck-typing: any object exposing a *points* attribute that behaves like
# a mapping of *(x, y) -> point* will work here.

if TYPE_CHECKING:  # pragma: no cover
    from ...models.surface import Surface, Point3D  # type: ignore

@dataclass(slots=True)
class HaulStation:
    """Represents the mass-haul metrics for a single station.

    Args:
        station (float): Station along the alignment (same unit as *alignment*
            coordinates, typically feet).
        cut (float): Total cut (positive) volume assigned to this station.
        fill (float): Total fill (positive) volume assigned to this station.
        cumulative (float): Running cumulative (cut – fill) up to this station.
    """

    station: float
    cut: float
    fill: float
    cumulative: float


class HaulStationList(list[HaulStation]):
    """Custom list that can carry extra metadata like *overhaul*.

    Python's builtin *list* type cannot have attributes assigned directly
    because it does not expose *__dict__*.  By subclassing we get that
    flexibility without changing the call-site semantics (the returned object
    is still iterable and indexable exactly like a normal list).
    """

    # Attribute is added dynamically inside *build_mass_haul*.
    overhaul_yd_station: float | None = None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def build_mass_haul(
    surface_ref: "Surface",
    surface_diff: "Surface",
    alignment: LineString,
    station_interval: float,
    free_haul_ft: float,
) -> HaulStationList:
    """Build a mass-haul curve along an alignment.

    A *reference* (design) surface and a *difference* (existing) surface of the
    same resolution are compared. Positive *dz* (existing higher than design)
    is treated as *fill*; negative *dz* as *cut*.

    The algorithm projects every point's *(x, y)* onto the supplied
    *alignment* polyline and bins volumes into regular station intervals. It
    then integrates the per-station volumes to build the cumulative mass curve
    and finally computes the *over-haul* (i.e. the haul distance beyond the
    free-haul allowance).

    Args:
        surface_ref (Surface): The reference/design surface.
        surface_diff (Surface): The comparison surface (existing or adjusted).
        alignment (LineString): The haul alignment poly-line (Shapely geometry).
        station_interval (float): Spacing (feet) of mass-haul stations.
        free_haul_ft (float): Free-haul distance. Movement within this distance
            is considered cost-free; movement beyond contributes to *overhaul*.

    Returns:
        HaulStationList: A list-like container of :class:`HaulStation` objects
        with an additional attribute ``overhaul_yd_station`` holding the
        computed overhaul (volume-distance product).

    Notes:
        • The function purposefully ignores any cell/triangle area – it assumes
          that *dz* values provided are already volumetric. If your data is in
          elevation differences, pre-multiply by the appropriate area before
          calling this helper.
        • The algorithm is *O(n²)* for the overhaul calculation due to the
          nested loops. For small to medium station counts (< 1 000) this is
          acceptable; if performance becomes an issue we can switch to a more
          efficient prefix-sum approach.
    """

    if station_interval <= 0:
        raise ValueError("station_interval must be positive")
    if free_haul_ft < 0:
        raise ValueError("free_haul_ft cannot be negative")

    length = alignment.length
    n_stations = int(math.ceil(length / station_interval)) + 1

    # Initialise per-station cut/fill arrays.
    cuts: np.ndarray = np.zeros(n_stations, dtype=float)
    fills: np.ndarray = np.zeros(n_stations, dtype=float)

    # ---------------------------------------------------------------------
    # Bin each surface point into the nearest station based on projection onto
    # the alignment.
    # ---------------------------------------------------------------------

    # Build a quick lookup dict for the *diff* surface keyed by XY coordinates.
    diff_lookup: dict[tuple[float, float], "Point3D"] = {
        (p.x, p.y): p for p in surface_diff.points.values()
    }

    # Iterate over design/reference points (assumed canonical grid) and find
    # the matching point in *diff* by XY.
    for p_ref in surface_ref.points.values():
        key = (p_ref.x, p_ref.y)
        p_diff = diff_lookup.get(key)
        if p_diff is None:
            # Skip if diff surface lacks this node.
            continue

        x, y = p_ref.x, p_ref.y

        # Distance along alignment for this point.
        station_dist = alignment.project(Point(x, y))
        idx = int(station_dist // station_interval)
        if idx >= n_stations:
            # The projection might technically fall exactly on the end due to
            # floating-point fuzz; clamp it in that rare case.
            idx = n_stations - 1

        dz = p_diff.z - p_ref.z  # Positive = fill, negative = cut
        if dz > 0:
            fills[idx] += dz
        elif dz < 0:
            cuts[idx] += -dz  # store positive magnitude

    # ---------------------------------------------------------------------
    # Build the cumulative curve and convert to user-friendly objects.
    # ---------------------------------------------------------------------
    results = HaulStationList()
    cumulative = 0.0
    for i in range(n_stations):
        cumulative += fills[i] - cuts[i]
        results.append(
            HaulStation(
                station=i * station_interval,
                cut=cuts[i],
                fill=fills[i],
                cumulative=cumulative,
            )
        )

    # ---------------------------------------------------------------------
    # Compute overhaul (distance × volume beyond the free-haul distance).
    # The classic method integrates |Δmass| over station separations > free-haul.
    # ---------------------------------------------------------------------
    overhaul = 0.0
    free_stations = int(free_haul_ft // station_interval)

    # Simple nested loop – fine for typical station counts (<~ 1k)
    for i, s_i in enumerate(results[:-1]):
        # Pre-exit optimisation – if *i* is too close to the end to exceed
        # *free_stations*, we can stop early.
        if (len(results) - i - 1) <= free_stations:
            break
        for j in range(i + free_stations + 1, len(results)):
            s_j = results[j]
            vol = abs(s_j.cumulative - s_i.cumulative)
            dist = (j - i) * station_interval
            overhaul += (dist - free_haul_ft) * vol

    # Store as attribute for convenience.
    results.overhaul_yd_station = overhaul
    return results
