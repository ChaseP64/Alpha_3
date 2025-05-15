from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Backwards-compatible ProjectScale with old field aliases

class ProjectScale(BaseModel):
    """Stores how a drawing's paper inches convert to world units."""

    # Provide default to maintain backward compatibility where input_method was optional
    input_method: Literal["direct_entry", "ratio", "two_point"] = "two_point"

    # common
    world_units: Literal["ft", "yd", "m"] = "ft"

    # direct entry  (e.g. 50 ft / in)
    # Alias old name "world_per_in" so legacy code/tests continue to work.
    world_per_paper_in: Optional[float] = Field(
        None, gt=0, alias="world_per_in", serialization_alias="world_per_in",
    )

    # ratio entry   (e.g. 1 : 600)
    ratio_numer: Optional[float] = Field(None, gt=0)
    ratio_denom: Optional[float] = Field(None, gt=0)

    # render context
    # Alias old name "px_per_in" so legacy code/tests continue to work.
    render_dpi_at_cal: float = Field(
        96.0, gt=0, alias="px_per_in", serialization_alias="px_per_in",
    )
    calibrated_at: datetime = Field(default_factory=datetime.utcnow)

    # -------- convenience  --------
    @property
    def world_per_px(self) -> float:
        if not self.world_per_paper_in:
            # This can happen if input_method is 'ratio' and world_per_paper_in was not correctly calculated
            # or if input_method is 'two_point' and it's not yet fully populated by that method.
            # Or if direct_entry was chosen but world_per_paper_in was not provided (should be caught by validation if not Optional)
            # For now, raise an error or return a sensible default / handle as per application logic.
            # Raising an error is safer to highlight misconfiguration.
            if self.input_method == "ratio" and self.ratio_numer and self.ratio_denom:
                # Attempt to calculate on the fly if ratio parts are present
                # This logic needs to be robust and match from_ratio or a dedicated calculation method
                temp_world_per_in_for_ratio: float
                if self.world_units == "ft":
                    temp_world_per_in_for_ratio = self.ratio_denom / (self.ratio_numer * 12.0) # Assuming ratio is paper_unit:world_unit_of_same_kind e.g. 1in:600in
                elif self.world_units == "m":
                    # Assuming 1 paper_unit : N world_units_of_same_kind (e.g. 1cm : 100cm)
                    # To get world_meters per paper_inch:
                    # (ratio_denom / ratio_numer) gives world_units_of_same_kind per paper_unit_of_same_kind
                    # If paper unit is cm and world unit is cm, then convert paper cm to paper inch
                    # This part of the logic depends heavily on the interpretation of "ratio"
                    # Sticking to user's from_ratio: (denom / numer) * (inches_per_world_unit_if_ratio_is_unitless)
                    # The user's from_ratio is: world_per_in = denom / 12 if units == "ft" else denom
                    # This implies if units == "m", world_per_paper_in = denom (meaning "denom meters per paper inch")
                    # So for ratio 1:100, units 'm' => 100m/inch. Calculated here: self.ratio_denom / self.ratio_numer
                    temp_world_per_in_for_ratio = self.ratio_denom / self.ratio_numer
                else: # yd
                    temp_world_per_in_for_ratio = self.ratio_denom / (self.ratio_numer * 36.0) # inches to yards

                if self.render_dpi_at_cal > 0:
                    return temp_world_per_in_for_ratio / self.render_dpi_at_cal
                raise ValueError("render_dpi_at_cal must be positive to calculate world_per_px")

            raise ValueError("world_per_paper_in is not set, cannot calculate world_per_px.")
        if self.render_dpi_at_cal <= 0:
            raise ValueError("render_dpi_at_cal must be positive to calculate world_per_px")
        return self.world_per_paper_in / self.render_dpi_at_cal

    # factory helpers
    @classmethod
    def from_direct(cls, value: float, units: Literal["ft", "yd", "m"], render_dpi: float) -> ProjectScale:
        return cls(
            input_method="direct_entry",
            world_units=units,
            world_per_paper_in=value,
            render_dpi_at_cal=render_dpi,
        )

    @classmethod
    def from_ratio(cls, numer: float, denom: float, units: Literal["ft", "yd", "m"], render_dpi: float) -> ProjectScale:
        # Assuming ratio is numer paper_units : denom world_units_of_same_kind
        # e.g., 1 inch on paper represents 600 inches in the world for a 1:600 scale.
        # world_per_paper_in should be in 'units' per 'paper inch'.

        # Calculate how many specified 'units' are in one 'denom' unit (which is same as paper unit implied by ratio numerator)
        # Example: Ratio 1:600 (e.g. 1 paper inch to 600 world inches).
        # If project units are 'ft', then world_per_paper_in is 600in / 12(in/ft) = 50 ft/paper_in.
        # If project units are 'm', then world_per_paper_in is 600in * 0.0254(m/in) = 15.24 m/paper_in.

        calculated_world_per_paper_in: float
        if units == "ft":
            # numer paper inches : denom world inches. So (denom/numer) world inches per paper inch.
            # Convert to feet per paper inch.
            calculated_world_per_paper_in = (denom / numer) / 12.0
        elif units == "m":
            # numer paper inches : denom world inches. So (denom/numer) world inches per paper inch.
            # Convert to meters per paper inch.
            calculated_world_per_paper_in = (denom / numer) * 0.0254
        elif units == "yd":
            # numer paper inches : denom world inches. So (denom/numer) world inches per paper inch.
            # Convert to yards per paper inch.
            calculated_world_per_paper_in = (denom / numer) / 36.0
        else:
            # Should not happen with Literal types, but as a safeguard:
            raise ValueError(f"Unsupported world_units for ratio conversion: {units}")

        return cls(
            input_method="ratio",
            world_units=units,
            ratio_numer=numer,
            ratio_denom=denom,
            world_per_paper_in=calculated_world_per_paper_in,
            render_dpi_at_cal=render_dpi,
        )

    # Placeholder for two_point calibration method, if needed here
    # Or it can be constructed directly in ScaleCalibrationDialog
    @classmethod
    def from_two_point(cls, world_units: Literal["ft", "yd", "m"],
                         world_per_paper_in: float,
                         render_dpi_at_cal: float) -> ProjectScale:
        return cls(
            input_method="two_point",
            world_units=world_units,
            world_per_paper_in=world_per_paper_in,
            render_dpi_at_cal=render_dpi_at_cal,
        )

    # ------------------------------------------------------------------ #
    # Backwards-compat / semantic alias
    # ------------------------------------------------------------------ #
    @property
    def ft_per_px(self) -> float:
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
        if self.world_per_paper_in == 0:
            raise ZeroDivisionError("world_per_paper_in must be non-zero to compute inch_ft.")
        return 1 / self.world_per_paper_in

    @property
    def pixel_ft(self) -> float:
        """Return *pixels per foot* for the current monitor + zoom setup."""
        return self.render_dpi_at_cal / self.world_per_paper_in if self.world_per_paper_in else 0

    # ------------------------------------------------------------------ #
    # Legacy attribute accessors
    # ------------------------------------------------------------------ #
    @property
    def px_per_in(self) -> float:
        """Alias for :pyattr:`render_dpi_at_cal` (legacy name used in tests)."""
        return self.render_dpi_at_cal

    @property
    def world_per_in(self) -> Optional[float]:
        """Alias for :pyattr:`world_per_paper_in` (legacy name)."""
        return self.world_per_paper_in

    # Make model allow population by both field names and aliases
    model_config = ConfigDict(populate_by_name=True)

    # ---------------- (de)serialisation helpers ----------------------- #
    def to_dict(self) -> dict[str, float | str]:
        """Serialise the object to a JSON-compatible dict."""
        return {
            "input_method": self.input_method,
            "world_units": self.world_units,
            "world_per_paper_in": self.world_per_paper_in,
            "ratio_numer": self.ratio_numer,
            "ratio_denom": self.ratio_denom,
            "render_dpi_at_cal": self.render_dpi_at_cal,
            "calibrated_at": self.calibrated_at.isoformat(),
            "pixel_ft": self.pixel_ft,
            "inch_ft": self.inch_ft,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProjectScale:
        """Create :class:`ProjectScale` from a dictionary.

        Args:
            d (dict): A mapping with the keys ``input_method``, ``world_units``,
                ``world_per_paper_in``, ``ratio_numer``, ``ratio_denom``,
                ``render_dpi_at_cal``, and ``calibrated_at``. Additional keys are ignored.

        """
        return cls(
            input_method=str(d["input_method"]),
            world_units=str(d["world_units"]),
            world_per_paper_in=float(d["world_per_paper_in"]),
            ratio_numer=float(d["ratio_numer"]) if d["ratio_numer"] else None,
            ratio_denom=float(d["ratio_denom"]) if d["ratio_denom"] else None,
            render_dpi_at_cal=float(d["render_dpi_at_cal"]),
            calibrated_at=datetime.fromisoformat(d["calibrated_at"]) if d["calibrated_at"] else None,
        )
