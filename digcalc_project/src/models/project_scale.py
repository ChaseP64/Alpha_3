from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


UnitSystem = Literal["ft", "m"]


@dataclass(slots=True)
class ProjectScale:
    """Printed-scale calibration details.

    Attributes:
        px_per_in (float): Screen pixels per inch. Example: 96 for ~72 dpi * zoom.
        world_units (UnitSystem): Unit system of the drawing ("ft" or "m").
        world_per_in (float): World units represented by one printed inch.

    The helper property :pyattr:`~ProjectScale.world_per_px` converts
    between pixel and world space, which is useful when mapping traced
    PDF coordinates to engineering units.
    """

    px_per_in: float  # e.g. 96 ≈ 72 dpi * zoom factor
    world_units: UnitSystem  # "ft" or "m"
    world_per_in: float  # e.g. 20.0 (ft) or 5.0 (m)

    # ------------------------------------------------------------------ #
    @property
    def world_per_px(self) -> float:
        """Return the conversion factor (ft/px or m/px)."""
        if self.px_per_in == 0:
            raise ZeroDivisionError("px_per_in must be non-zero to compute world_per_px.")
        return self.world_per_in / self.px_per_in

    # ------------------------------------------------------------------ #
    # Backwards-compat / semantic alias
    # ------------------------------------------------------------------ #
    @property
    def ft_per_px(self) -> float:  # noqa: D401  (imperial naming kept for brevity)
        """Alias of :pyattr:`world_per_px`.

        Historically our UI copy referred to the conversion factor as
        *ft per px* (even when the drawing used metres).  To avoid a noisy
        rename across the code-base we expose this convenience alias that
        simply delegates to :pyattr:`world_per_px`.

        Returns:
            float: Identical value to :pyattr:`world_per_px` (units per pixel).
        """

        return self.world_per_px

    # ------------------------------------------------------------------ #
    # Convenience aliases for other representations
    # ------------------------------------------------------------------ #
    @property
    def inch_ft(self) -> float:
        """Return inches on paper per *world* foot.

        Reciprocal of :pyattr:`world_per_in` when units = ft.  Useful when the
        printed scale is expressed as *inches per foot* (common in civil
        drawings, e.g. 1" = 20').
        """

        if self.world_per_in == 0:
            raise ZeroDivisionError("world_per_in must be non-zero to compute inch_ft.")
        return 1 / self.world_per_in

    @property
    def pixel_ft(self) -> float:
        """Return *pixels per foot* for the current monitor + zoom setup."""

        return self.px_per_in / self.world_per_in if self.world_per_in else 0

    # ---------------- (de)serialisation helpers ----------------------- #
    def to_dict(self) -> dict[str, float | str]:
        """Serialise the object to a JSON-compatible dict."""
        return {
            "px_per_in": self.px_per_in,
            "world_units": self.world_units,
            "world_per_in": self.world_per_in,
            # Convenience extras for newer schema (redundant but harmless)
            "pixel_ft": self.pixel_ft,
            "inch_ft": self.inch_ft,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectScale":
        """Create :class:`ProjectScale` from a dictionary.

        Args:
            d (dict): A mapping with the keys ``px_per_in``, ``world_units``,
                and ``world_per_in``. Additional keys are ignored.
        """
        return cls(
            px_per_in=float(d["px_per_in"]),
            world_units=str(d["world_units"]),
            world_per_in=float(d["world_per_in"]),
        ) 