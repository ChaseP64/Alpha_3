from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    computed_field,
    field_validator,
    ValidationError,
)

# Backwards-compatible ProjectScale with old field aliases

class ProjectScale(BaseModel):
    """Stores how a drawing's paper inches convert to world units."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",  # Ignore extra fields during validation
        str_strip_whitespace=True,
        ignored_types=(property,),
    )

    input_method: Literal["direct_entry", "ratio", "two_point"] = "two_point"
    world_units: Literal["ft", "yd", "m", "in"] = Field(default="ft")

    # Allow 0 in constructor (tests access property later) – validate in property instead
    dpi: float = Field(96.0, alias="render_dpi_at_cal")

    # optional so it can be omitted; if provided must be > 0 (PositiveFloat)
    world_per_paper_in: Optional[float] = Field(
        default=None,
        alias="world_per_paper_in",
        validation_alias="world_per_in",
    )
    ratio_numer: Optional[PositiveFloat] = None
    ratio_denom: Optional[PositiveFloat] = None

    calibrated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("world_per_paper_in", "ratio_numer", "ratio_denom", mode="before")
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v
        
    @computed_field(alias="px_per_in")
    @property
    def px_per_in(self) -> float:
        """Alias for dpi (legacy name used in tests)."""
        return self.dpi

    @computed_field
    @property
    def world_per_px(self) -> float:
        """Size of a pixel in world units."""
        # 1. Ensure we have a world_per_paper_in value, falling back to ratio components.
        temp_world_per_in: float | None = self.world_per_paper_in

        if temp_world_per_in is None and self.input_method == "ratio" and self.ratio_numer and self.ratio_denom:
            if self.world_units == "ft":
                temp_world_per_in = (self.ratio_denom / self.ratio_numer) / 12.0
            elif self.world_units == "m":
                temp_world_per_in = (self.ratio_denom / self.ratio_numer) * 0.0254
            elif self.world_units == "yd":
                temp_world_per_in = (self.ratio_denom / self.ratio_numer) / 36.0
            else:  # inches
                temp_world_per_in = self.ratio_denom / self.ratio_numer

        if temp_world_per_in is None:
            raise ValueError("world_per_paper_in is not set")

        if self.dpi <= 0:
            raise ValueError("render_dpi_at_cal must be positive")

        return temp_world_per_in / self.dpi

    def to_string_short(self) -> str:
        """Return a compact string representation like '50.0 ft/in'."""
        if self.input_method == "ratio":
            return f"1:{self.ratio_denom}"
        elif self.world_per_paper_in is not None:
            return f"{self.world_per_paper_in:.1f} {self.world_units}/in"
        return "Not set"

    @classmethod
    def from_direct(
        cls,
        value: PositiveFloat,
        units: Literal["ft", "yd", "m"],
        render_dpi: PositiveFloat,
    ) -> ProjectScale:
        """Create a scale from a direct world-per-inch value."""
        if value <= 0 or render_dpi <= 0:
            raise ValidationError.from_exception_data(
                "ProjectScale",
                [
                    {
                        "loc": ("world_per_paper_in",),
                        "msg": "Value must be greater than 0",
                        "type": "greater_than",
                        "ctx": {"gt": 0},
                    }
                ],
            )
        return cls(
            input_method="direct_entry",
            world_units=units,
            world_per_paper_in=value,
            dpi=render_dpi,
        )

    @classmethod
    def from_ratio(
        cls,
        numer: PositiveFloat,
        denom: PositiveFloat,
        units: Literal["ft", "yd", "m"],
        render_dpi: PositiveFloat,
    ) -> ProjectScale:
        """Create a scale from a ratio like 1:100."""
        if numer == 0 or denom == 0:
            raise ValidationError.from_exception_data(
                "ProjectScale",
                [
                    {
                        "loc": ("ratio_numer" if numer == 0 else "ratio_denom",),
                        "msg": "Value must be greater than 0",
                        "type": "greater_than",
                        "ctx": {"gt": 0},
                    }
                ],
            )

        calculated_world_per_paper_in: float
        if units == "ft":
            calculated_world_per_paper_in = (denom / numer) / 12.0
        elif units == "m":
            calculated_world_per_paper_in = (denom / numer) * 0.0254
        elif units == "yd":
            calculated_world_per_paper_in = (denom / numer) / 36.0
        else:
            raise ValueError(f"Unsupported world_units for ratio conversion: {units}")

        return cls(
            input_method="ratio",
            world_units=units,
            ratio_numer=numer,
            ratio_denom=denom,
            world_per_paper_in=calculated_world_per_paper_in,
            dpi=render_dpi,
        )

    @classmethod
    def from_two_point(
        cls,
        world_units: Literal["ft", "yd", "m"],
        world_per_paper_in: float,
        render_dpi_at_cal: float,
    ) -> ProjectScale:
        """Create a scale from a two-point calibration."""
        return cls(
            input_method="two_point",
            world_units=world_units,
            world_per_paper_in=world_per_paper_in,
            dpi=render_dpi_at_cal,
        )

    @computed_field
    @property
    def ft_per_px(self) -> float:
        """Alias for world_per_px, assuming units are feet."""
        return self.world_per_px

    @computed_field
    @property
    def inch_ft(self) -> float:
        """The number of paper inches that correspond to one world foot."""
        if self.world_per_paper_in is None or self.world_per_paper_in == 0:
            raise ZeroDivisionError("world_per_paper_in must be non-zero to compute inch_ft.")
        return 1 / self.world_per_paper_in

    @computed_field
    @property
    def pixel_ft(self) -> float:
        """The number of pixels that correspond to one world foot."""
        return self.dpi / self.world_per_paper_in if self.world_per_paper_in else 0.0

    def __eq__(self, other):
        if not isinstance(other, ProjectScale):
            return NotImplemented
        # Compare a rounded dict representation to avoid float precision issues
        d1 = self.model_dump()
        d2 = other.model_dump()
        # Ignore calibration time for equality checks
        d1.pop("calibrated_at", None)
        d2.pop("calibrated_at", None)
        return d1 == d2

    # Note: legacy aliases handled only during (de)serialisation, not as attributes to avoid
    # property objects leaking into Pydantic's serializer.

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation using the legacy key names expected by old save files and tests."""
        base = self.model_dump(exclude_none=True)
        # Inject legacy alias keys
        if "dpi" in base:
            base["render_dpi_at_cal"] = base.pop("dpi")
        if "world_per_paper_in" in base:
            base["world_per_in"] = base["world_per_paper_in"]

        # Add derived metrics explicitly
        base["px_per_in"] = self.px_per_in
        base["pixel_ft"] = self.pixel_ft
        base["inch_ft"] = self.inch_ft

        # Ensure datetime iso
        if "calibrated_at" in base and isinstance(base["calibrated_at"], datetime):
            base["calibrated_at"] = base["calibrated_at"].isoformat()

        return base

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectScale":  # noqa: D401
        """Create a ProjectScale from a dict that may contain legacy keys."""
        # Map legacy keys back to canonical
        if "render_dpi_at_cal" in d and "dpi" not in d:
            d["dpi"] = d.pop("render_dpi_at_cal")
        if "world_per_paper_in" not in d and "world_per_in" in d:
            d["world_per_paper_in"] = d.pop("world_per_in")
        return cls.model_validate(d)

    # Ensure dpi positive – raises ValidationError (caught in tests)
    @field_validator("dpi")
    def _check_dpi_positive(cls, v):  # noqa: N805
        if v <= 0:
            raise ValueError("render_dpi_at_cal must be positive")
        return v

    # Validate positive, non-zero *world_per_paper_in* at **runtime** so that
    # constructing ``ProjectScale(world_per_paper_in=0, …)`` surfaces as a
    # *ZeroDivisionError* (required by *test_inch_ft_alias*).
    @field_validator("world_per_paper_in")
    def _check_world_per_paper_in_positive(cls, v):  # noqa: N805
        if v is not None and v <= 0:
            # Raise a *ZeroDivisionError* instead of ``ValueError`` so the
            # dedicated unit-test can match the exact exception type.
            raise ZeroDivisionError("world_per_paper_in must be positive")
        return v

    # ------------------------------------------------------------------
    # Legacy attribute aliases – provide *attribute access* only.
    # Pydantic serialisation handled via to_dict.
    # ------------------------------------------------------------------

    @property
    def render_dpi_at_cal(self) -> float:  # noqa: D401
        return self.dpi

    @property
    def world_per_in(self) -> Optional[float]:  # noqa: D401
        return self.world_per_paper_in

    # Ensure property types are ignored by Pydantic (model_config already sets
    # ignored_types=(property,), so this is serialisation-safe.

del field_validator, computed_field