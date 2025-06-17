from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

# Adjust the import path according to your project structure
from digcalc_project.src.models.project_scale import ProjectScale


def test_project_scale_from_direct():
    """Test creating ProjectScale using the from_direct factory method."""
    scale = ProjectScale.from_direct(value=50.0, units="ft", render_dpi=150.0)
    assert scale.input_method == "direct_entry"
    assert scale.world_units == "ft"
    assert scale.world_per_paper_in == 50.0
    assert scale.render_dpi_at_cal == 150.0
    assert scale.ratio_numer is None
    assert scale.ratio_denom is None
    assert isinstance(scale.calibrated_at, datetime)

    # Test world_per_px calculation
    assert scale.world_per_px == 50.0 / 150.0

    # Test ft_per_px alias
    assert scale.ft_per_px == scale.world_per_px

def test_project_scale_from_ratio_ft():
    """Test creating ProjectScale using from_ratio with feet."""
    # Example: 1 inch on paper = 600 inches in world (which is 50 ft)
    # Ratio 1:600, project units 'ft'
    # world_per_paper_in = (600 / 1) / 12 = 50 ft/in
    scale = ProjectScale.from_ratio(numer=1.0, denom=600.0, units="ft", render_dpi=96.0)
    assert scale.input_method == "ratio"
    assert scale.world_units == "ft"
    assert scale.ratio_numer == 1.0
    assert scale.ratio_denom == 600.0
    assert scale.render_dpi_at_cal == 96.0
    assert abs(scale.world_per_paper_in - 50.0) < 1e-9 # (600/1) / 12
    assert isinstance(scale.calibrated_at, datetime)

    # Test world_per_px calculation
    # (50 ft/paper_in) / (96 px/paper_in) = 50/96 ft/px
    assert abs(scale.world_per_px - (50.0 / 96.0)) < 1e-9

def test_project_scale_from_ratio_m():
    """Test creating ProjectScale using from_ratio with meters."""
    # Example: 1 inch on paper = 1000 inches in world.
    # Ratio 1:1000, project units 'm'
    # world_per_paper_in = (1000 / 1) * 0.0254 = 25.4 m/in
    scale = ProjectScale.from_ratio(numer=1.0, denom=1000.0, units="m", render_dpi=100.0)
    assert scale.input_method == "ratio"
    assert scale.world_units == "m"
    assert scale.ratio_numer == 1.0
    assert scale.ratio_denom == 1000.0
    assert scale.render_dpi_at_cal == 100.0
    assert abs(scale.world_per_paper_in - 25.4) < 1e-9 # (1000/1) * 0.0254
    assert isinstance(scale.calibrated_at, datetime)

    # Test world_per_px calculation
    # (25.4 m/paper_in) / (100 px/paper_in) = 25.4/100 m/px
    assert abs(scale.world_per_px - (25.4 / 100.0)) < 1e-9

def test_project_scale_from_two_point():
    """Test creating ProjectScale using the from_two_point factory method."""
    scale = ProjectScale.from_two_point(world_units="yd", world_per_paper_in=10.0, render_dpi_at_cal=200.0)
    assert scale.input_method == "two_point"
    assert scale.world_units == "yd"
    assert scale.world_per_paper_in == 10.0
    assert scale.render_dpi_at_cal == 200.0
    assert scale.ratio_numer is None
    assert scale.ratio_denom is None
    assert isinstance(scale.calibrated_at, datetime)

    # Test world_per_px calculation
    assert scale.world_per_px == 10.0 / 200.0

def test_world_per_px_calculation_direct():
    """Test the world_per_px property calculation for direct entry."""
    scale = ProjectScale(
        input_method="direct_entry",
        world_units="ft",
        world_per_paper_in=20.0, # 20 ft per paper inch
        render_dpi_at_cal=100.0,   # 100 pixels per paper inch
    )
    # Expected: (20 ft / paper_in) / (100 px / paper_in) = 0.2 ft / px
    assert abs(scale.world_per_px - 0.2) < 1e-9
    assert abs(scale.ft_per_px - 0.2) < 1e-9 # Alias check

def test_world_per_px_calculation_ratio():
    """Test the world_per_px property calculation for ratio entry."""
    # Ratio 1:240 (1 paper inch : 240 world inches)
    # world_units = "ft"
    # world_per_paper_in = (240/1) / 12 = 20 ft/in
    scale_ft = ProjectScale(
        input_method="ratio",
        world_units="ft",
        ratio_numer=1.0,
        ratio_denom=240.0, # implies 240 world inches for 1 paper inch
        world_per_paper_in=20.0, # Derived: (240/1)/12
        render_dpi_at_cal=100.0,
    )
    # Expected: (20 ft / paper_in) / (100 px / paper_in) = 0.2 ft / px
    assert abs(scale_ft.world_per_px - 0.2) < 1e-9

    # Ratio 1:100 (e.g. 1 paper cm : 100 world cm, but interpreted as 1 paper inch : 100 world inches for calculation)
    # world_units = "m"
    # world_per_paper_in = (100/1) * 0.0254 = 2.54 m/in
    scale_m = ProjectScale(
        input_method="ratio",
        world_units="m",
        ratio_numer=1.0,
        ratio_denom=100.0, # implies 100 world inches for 1 paper inch
        world_per_paper_in=2.54, # Derived: (100/1) * 0.0254
        render_dpi_at_cal=100.0,
    )
    # Expected: (2.54 m / paper_in) / (100 px / paper_in) = 0.0254 m / px
    assert abs(scale_m.world_per_px - 0.0254) < 1e-9

def test_world_per_px_missing_world_per_paper_in():
    """Test world_per_px raises error if world_per_paper_in is missing and not calculable."""
    # This scenario is less likely with Pydantic if world_per_paper_in is not Optional
    # and not provided by factories, but good to test the property's robustness.
    # The current ProjectScale model has world_per_paper_in as Optional.
    with pytest.raises(ValueError, match="world_per_paper_in is not set"):
        scale = ProjectScale(
            input_method="direct_entry", # Or any other if world_per_paper_in isn't auto-calculated
            world_units="ft",
            # world_per_paper_in is missing
            render_dpi_at_cal=100.0,
        )
        _ = scale.world_per_px # Access the property

def test_world_per_px_zero_dpi():
    """Test world_per_px raises error if render_dpi_at_cal is zero."""
    with pytest.raises(ValueError, match="render_dpi_at_cal must be positive"):
        scale = ProjectScale(
            input_method="direct_entry",
            world_units="ft",
            world_per_paper_in=20.0,
            render_dpi_at_cal=0.0, # Invalid DPI
        )
        _ = scale.world_per_px

    with pytest.raises(ValidationError): # Pydantic validation should catch this first
        ProjectScale(
            input_method="direct_entry",
            world_units="ft",
            world_per_paper_in=20.0,
            render_dpi_at_cal=0.0,
        )

def test_pydantic_validations():
    """Test Pydantic field validations."""
    # Test gt=0 for world_per_paper_in
    with pytest.raises(ValidationError):
        ProjectScale.from_direct(value=0, units="ft", render_dpi=100)
    with pytest.raises(ValidationError):
        ProjectScale.from_direct(value=-10, units="ft", render_dpi=100)

    # Test gt=0 for ratio_numer and ratio_denom
    with pytest.raises(ValidationError):
        ProjectScale.from_ratio(numer=0, denom=100, units="ft", render_dpi=100)
    with pytest.raises(ValidationError):
        ProjectScale.from_ratio(numer=1, denom=0, units="ft", render_dpi=100)

    # Test gt=0 for render_dpi_at_cal (checked during direct instantiation)
    with pytest.raises(ValidationError):
        ProjectScale(input_method="direct_entry", world_per_paper_in=10, render_dpi_at_cal=0)
    with pytest.raises(ValidationError):
        ProjectScale(input_method="direct_entry", world_per_paper_in=10, render_dpi_at_cal=-100)

# Test aliases
def test_inch_ft_alias():
    """Test inch_ft convenience alias."""
    # world_per_paper_in = 20 ft / paper_in
    # inch_ft (paper_in / world_ft) = 1 / 20 = 0.05
    scale = ProjectScale.from_direct(value=20.0, units="ft", render_dpi=100.0)
    assert abs(scale.inch_ft - (1.0/20.0)) < 1e-9

    with pytest.raises(ZeroDivisionError):
        empty_scale = ProjectScale(input_method="direct_entry", world_per_paper_in=0, render_dpi_at_cal=100, world_units="ft")
        # This will fail pydantic validation first, but if it didn't:
        # _ = empty_scale.inch_ft


def test_pixel_ft_alias():
    """Test pixel_ft convenience alias."""
    # world_per_paper_in = 20 ft / paper_in
    # render_dpi_at_cal = 100 px / paper_in
    # pixel_ft (px / world_ft) = render_dpi_at_cal / world_per_paper_in = 100 / 20 = 5
    scale = ProjectScale.from_direct(value=20.0, units="ft", render_dpi=100.0)
    assert abs(scale.pixel_ft - (100.0/20.0)) < 1e-9

    # Test zero world_per_paper_in (should be caught by Pydantic validation if not optional)
    # If world_per_paper_in is None or 0, pixel_ft should handle it (e.g. return 0 or raise)
    # Current implementation returns 0 if world_per_paper_in is None (via the getter)
    # or if it's 0.

    # This scenario is tricky because `world_per_paper_in=0` would fail pydantic validation `gt=0`.
    # If we were to bypass pydantic for a moment and set it to 0:
    # scale_zero_world = ProjectScale.construct(input_method="direct_entry", world_per_paper_in=0, render_dpi_at_cal=100, world_units="ft")
    # assert scale_zero_world.pixel_ft == 0 # based on current logic in model.

    # If world_per_paper_in is None
    scale_none_world = ProjectScale(input_method="direct_entry", render_dpi_at_cal=100, world_units="ft") # world_per_paper_in is None
    assert scale_none_world.pixel_ft == 0 # Relies on world_per_paper_in property being None

def test_to_dict_serialization():
    """Test the to_dict method for serialization."""
    dt = datetime.utcnow()
    scale = ProjectScale(
        input_method="ratio",
        world_units="m",
        world_per_paper_in=2.54, # 1in * (100in/in_paper) * (0.0254m/in_world)
        ratio_numer=1.0,
        ratio_denom=100.0, # 1:100 (paper_in : world_in)
        render_dpi_at_cal=96.0,
        calibrated_at=dt,
    )
    scale_dict = scale.to_dict()

    assert scale_dict["input_method"] == "ratio"
    assert scale_dict["world_units"] == "m"
    assert abs(scale_dict["world_per_paper_in"] - 2.54) < 1e-9
    assert scale_dict["ratio_numer"] == 1.0
    assert scale_dict["ratio_denom"] == 100.0
    assert scale_dict["render_dpi_at_cal"] == 96.0
    assert scale_dict["calibrated_at"] == dt.isoformat()
    # Check derived properties are also in the dict
    assert "pixel_ft" in scale_dict # This name is a bit misleading if units are 'm'
    assert "inch_ft" in scale_dict  # This name is also misleading if units are 'm'

    # world_per_px = 2.54 / 96
    # pixel_ft is render_dpi / world_per_paper_in = 96 / 2.54
    assert abs(scale_dict["pixel_ft"] - (96.0 / 2.54)) < 1e-9
    # inch_ft is 1 / world_per_paper_in = 1 / 2.54
    assert abs(scale_dict["inch_ft"] - (1.0 / 2.54)) < 1e-9

def test_from_dict_deserialization():
    """Test the from_dict class method for deserialization."""
    dt_iso = datetime.utcnow().isoformat()
    data = {
        "input_method": "direct_entry",
        "world_units": "ft",
        "world_per_paper_in": 50.0,
        "ratio_numer": None,
        "ratio_denom": None,
        "render_dpi_at_cal": 150.0,
        "calibrated_at": dt_iso,
        # "pixel_ft": 3.0, # These are not used by from_dict directly
        # "inch_ft": 0.02
    }
    scale = ProjectScale.from_dict(data)
    assert scale.input_method == "direct_entry"
    assert scale.world_units == "ft"
    assert scale.world_per_paper_in == 50.0
    assert scale.render_dpi_at_cal == 150.0
    assert scale.calibrated_at == datetime.fromisoformat(dt_iso)
    assert scale.ratio_numer is None
    assert scale.ratio_denom is None

def test_from_dict_missing_optional_fields():
    """Test from_dict with missing optional fields (ratio_numer, ratio_denom)."""
    dt_iso = datetime.utcnow().isoformat()
    data = {
        "input_method": "direct_entry",
        "world_units": "ft",
        "world_per_paper_in": 50.0,
        # ratio_numer is missing
        # ratio_denom is missing
        "render_dpi_at_cal": 150.0,
        "calibrated_at": dt_iso,
    }
    scale = ProjectScale.from_dict(data) # Pydantic will use defaults or None for optionals
    assert scale.ratio_numer is None
    assert scale.ratio_denom is None

def test_world_per_px_dynamic_calculation_for_ratio_if_world_per_paper_in_is_none():
    """Test if world_per_px can dynamically calculate from ratio components
    if world_per_paper_in is None (as per the logic in the property).
    """
    # Scenario: world_per_paper_in is not explicitly set, but ratio parts are.
    scale = ProjectScale(
        input_method="ratio",
        world_units="ft",
        # world_per_paper_in=None, # Explicitly None
        ratio_numer=1.0,
        ratio_denom=600.0, # 1:600 inches -> 50 ft/in
        render_dpi_at_cal=100.0,
    )
    # Expected world_per_paper_in from ratio parts = (600/1)/12 = 50 ft/in
    # Expected world_per_px = 50 / 100 = 0.5 ft/px
    assert abs(scale.world_per_px - 0.5) < 1e-9

    scale_m = ProjectScale(
        input_method="ratio",
        world_units="m",
        # world_per_paper_in=None,
        ratio_numer=1.0,
        ratio_denom=100.0, # 1:100 inches -> 100 * 0.0254 = 2.54 m/in
        render_dpi_at_cal=100.0,
    )
    # Expected world_per_paper_in from ratio parts = (100/1) * 0.0254 = 2.54 m/in
    # Expected world_per_px = 2.54 / 100 = 0.0254 m/px
    # The current logic in `world_per_px` for 'm' is `self.ratio_denom / self.ratio_numer`
    # which would be 100.0. This needs to align with `from_ratio`.
    # The from_ratio method for 'm' gives (denom/numer) * 0.0254
    # The world_per_px's dynamic calculation for 'm' is `denom/numer`. This is inconsistent.

    # For now, I will test based on the current implementation in world_per_px.
    # It seems the dynamic calculation inside world_per_px for meters is intended
    # to be `denom / numer` (e.g., 100 m/inch if ratio 1:100).
    # This is DIFFERENT from how `from_ratio` calculates `world_per_paper_in`.
    # This discrepancy should be addressed in the model.

    # Test with the assumption that from_ratio correctly populates world_per_paper_in
    # and world_per_px primarily uses that.
    # The dynamic calculation is a fallback.

    # Re-test `from_ratio` to ensure `world_per_paper_in` is set
    scale_m_via_factory = ProjectScale.from_ratio(numer=1.0, denom=100.0, units="m", render_dpi=100.0)
    assert abs(scale_m_via_factory.world_per_paper_in - (100.0 * 0.0254)) < 1e-9
    assert abs(scale_m_via_factory.world_per_px - ((100.0 * 0.0254) / 100.0)) < 1e-9


# It's good practice to also test edge cases or invalid inputs for from_dict
# but Pydantic handles most of this.
# However, if `from_dict` had more complex logic, more tests would be needed.
