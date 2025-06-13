"""Baseline grid-based cut/fill volume calculator (Phase 0).

For now this module simply re-exports the implementation that already lives in
``digcalc_project.src.core.calculations.volume_calculator`` so that existing
code can transition to the new import path *without* duplication.  Future
phases can freely evolve this API in place.
"""

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING
import numpy as _np

from digcalc_project.src.models.strata_models import StrataStack, StrataSurface

_module: ModuleType = import_module("digcalc_project.src.core.calculations.volume_calculator")
VolumeCalculator = _module.VolumeCalculator  # type: ignore[attr-defined]

# Re-export additional helpers so external imports keep working.
calculate_mass_haul_by_material = _module.calculate_mass_haul_by_material  # type: ignore[attr-defined]

# Export list
__all__ = ["VolumeCalculator"]

if TYPE_CHECKING:  # pragma: no cover – mypy only
    from digcalc_project.src.core.calculations.volume_calculator import VolumeCalculator as _VolCalc  # noqa: F401 

__all__.append("build_cumulative_arrays")
__all__.extend(["build_cumulative_arrays", "calculate_material_cut"])

# ---------------------------------------------------------------------------
# Cut/Fill balancing helper – determines import/export volumes based on user
# configuration *spoil_to_fill_ratio*.
# ---------------------------------------------------------------------------
from digcalc_project.src.services.settings_service import SettingsService  # late import to avoid cycles


def balance_cut_fill(cut_volume: float, fill_volume: float, *, ratio: float | None = None) -> dict[str, float]:
    """Return dict with ``import_volume`` and ``export_volume``.

    Args:
        cut_volume: Total cut (ft³) – positive.
        fill_volume: Total fill (ft³) – positive.
        ratio: Optional override; if *None* uses
            ``SettingsService().strata_spoil_to_fill_ratio``.

    The *ratio* represents the proportion of *cut* that is assumed suitable
    for re-use as fill (\[0, 1\]).  Remaining fill is treated as *import*;
    remaining cut (if any) as *export/spoil*.
    """

    if ratio is None:
        ratio = SettingsService().strata_spoil_to_fill_ratio

    ratio = max(0.0, min(1.0, ratio))  # clamp defensively

    usable_cut = cut_volume * ratio
    fill_satisfied = min(usable_cut, fill_volume)
    import_vol = max(0.0, fill_volume - fill_satisfied)
    export_vol = max(0.0, cut_volume - fill_satisfied)

    return {
        "import_volume": import_vol,
        "export_volume": export_vol,
        "reused_cut_volume": fill_satisfied,
    }

# make helper public
__all__.append("balance_cut_fill")

def build_cumulative_arrays(strata_stack: StrataStack, base_grid: float):
    """Return cumulative top and bottom Z arrays for the given *strata_stack*.

    Args:
        strata_stack: The StrataStack containing generated StrataSurface objects.
        base_grid: Cell size (ft) used for the grids – determines resolution.

    Returns:
        Tuple of ``(top_z, bottom_z)`` where each is a 2-D ``numpy.ndarray``
        with shape matching the StrataSurface grids. ``top_z`` records the
        shallowest (highest) Z at each cell while ``bottom_z`` records the
        deepest (lowest) Z encountered when iterating through the layers.
    """
    if not getattr(strata_stack, "surfaces", None):
        raise ValueError("StrataStack has no surfaces – generate them first.")

    # Assume all StrataSurface grids share identical dimensions/metadata.
    first_grid = strata_stack.surfaces[0].grid_data
    shape = first_grid.shape
    top_z = _np.full(shape, _np.nan, dtype=float)
    bottom_z = _np.full(shape, _np.nan, dtype=float)

    # Sort surfaces shallowest → deepest (id ascending)
    for surface in sorted(strata_stack.surfaces, key=lambda s: s.id):
        grid = surface.grid_data
        if grid is None:
            continue
        mask = ~_np.isnan(grid)
        # Write into top_z only where empty
        empty_mask = _np.isnan(top_z) & mask
        top_z[empty_mask] = grid[empty_mask]
        # Always write into bottom_z (overwriting deeper each time)
        bottom_z[mask] = grid[mask]

    return top_z, bottom_z 

def calculate_material_cut(existing_z: _np.ndarray, proposed_z: _np.ndarray, strata_stack: StrataStack, cell_area: float) -> dict[int, float]:
    """Return cut volumes per material id given existing/proposed Z grids.

    Args:
        existing_z: 2-D array of existing ground elevations.
        proposed_z: 2-D array of design elevations.
        strata_stack: Stack holding StrataSurface grids (top elevations) in .surfaces.
        cell_area: Area of a single grid cell (ft²).

    Returns:
        Dict mapping material_id → cut volume (ft³).
    """
    if not strata_stack.surfaces:
        raise ValueError("StrataStack surfaces required")

    # Build list shallow→deep
    layers = sorted(strata_stack.surfaces, key=lambda s: s.id)
    # Append a synthetic bottom layer using deepest grid so we can compute thickness for last layer
    bottom_grid = _np.full_like(layers[0].grid_data, _np.nan)
    for surf in reversed(layers):
        bottom_grid = _np.where(~_np.isnan(surf.grid_data), surf.grid_data, bottom_grid)
    layers.append(StrataSurface(id=9999, material_id=-1, grid_data=bottom_grid - 1e6, grid_metadata={}))  # very deep

    cut_remaining = _np.clip(existing_z - proposed_z, 0, None)
    vol_by_mat: dict[int, float] = {surf.material_id: 0.0 for surf in layers[:-1]}

    for idx, surf in enumerate(layers[:-1]):
        top = surf.grid_data
        bottom = layers[idx + 1].grid_data
        if top is None or bottom is None:
            continue
        layer_thickness = bottom - top
        layer_thickness[layer_thickness < 0] = 0  # safety
        cut_here = _np.clip(cut_remaining, 0, layer_thickness)
        vol_by_mat[surf.material_id] += float(_np.nansum(cut_here) * cell_area)
        cut_remaining = cut_remaining - cut_here
    return vol_by_mat 

__all__.append("calculate_mass_haul_by_material") 