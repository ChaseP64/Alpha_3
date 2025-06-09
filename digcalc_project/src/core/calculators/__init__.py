"""Calculator facade subpackage.

Currently this package re-exports the existing *calculations* implementation so
imports like::

    from digcalc_project.src.core.calculators.volume_calculator import VolumeCalculator

continue to work even though the engine lives in
``digcalc_project.src.core.calculations``.

This indirection lets upcoming phases replace the implementation incrementally
without breaking the public API.
"""

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING


# Lazily proxy to the real calculations module ------------------------------
_module: ModuleType = import_module("digcalc_project.src.core.calculations.volume_calculator")
VolumeCalculator = _module.VolumeCalculator  # type: ignore[attr-defined]

if TYPE_CHECKING:  # pragma: no cover – mypy only
    from digcalc_project.src.core.calculations.volume_calculator import VolumeCalculator as _VolCalc  # noqa: F401 