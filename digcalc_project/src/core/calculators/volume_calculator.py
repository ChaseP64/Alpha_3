"""Baseline grid-based cut/fill volume calculator (Phase 0).

For now this module simply re-exports the implementation that already lives in
``digcalc_project.src.core.calculations.volume_calculator`` so that existing
code can transition to the new import path *without* duplication.  Future
phases can freely evolve this API in place.
"""

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

_module: ModuleType = import_module("digcalc_project.src.core.calculations.volume_calculator")
VolumeCalculator = _module.VolumeCalculator  # type: ignore[attr-defined]

if TYPE_CHECKING:  # pragma: no cover – mypy only
    from digcalc_project.src.core.calculations.volume_calculator import VolumeCalculator as _VolCalc  # noqa: F401 