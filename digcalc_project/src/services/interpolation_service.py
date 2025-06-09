"""Interpolation service – interface for generating stratigraphy surfaces.

Phase 0-4 introduces a *pluggable* interpolation interface so future phases can
experiment with alternative algorithms (IDW, Kriging, RBF, etc.) without
touching callers.

Only the *interface* and a minimal **IDWInterpolator** stub are provided here.
The concrete implementation will follow in a later phase.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import List, Protocol, runtime_checkable

from ..models.strata_models import StrataStack, StrataSurface
from ..models.surface import Surface
from .settings_service import SettingsService

__all__ = [
    "IStrataInterpolator",
    "IDWInterpolator",
]


@runtime_checkable
class IStrataInterpolator(Protocol):
    """Contract for strata-surface interpolation backends."""

    # ------------------------------------------------------------------
    @abstractmethod
    def generate_surfaces(
        self,
        strata_stack: StrataStack,
        existing_surface: Surface,
        settings: SettingsService | None = None,
    ) -> List[StrataSurface]:
        """Generate boundary surfaces for each layer in *strata_stack*.

        Parameters
        ----------
        strata_stack
            Collection of boreholes, materials and optional pre-existing
            surfaces that require infilling / regeneration.
        existing_surface
            Existing ground surface providing XY/Z extents for the
            interpolation grid.
        settings
            Optional SettingsService instance – allows algorithms to read user
            preferences such as grid spacing without additional coupling.
        """

        raise NotImplementedError  # pragma: no cover


# ---------------------------------------------------------------------------
# Stub implementation – Inverse Distance Weighting (coming soon)
# ---------------------------------------------------------------------------


class IDWInterpolator(IStrataInterpolator):
    """Inverse Distance Weighting (IDW) placeholder.

    The algorithm will be implemented in a later phase.  For now the class
    merely satisfies :class:`IStrataInterpolator` at *import* time.
    """

    def generate_surfaces(
        self,
        strata_stack: StrataStack,
        existing_surface: Surface,
        settings: SettingsService | None = None,
    ) -> List[StrataSurface]:
        raise NotImplementedError(
            "IDW interpolation not implemented yet – will be introduced in a later phase."
        ) 