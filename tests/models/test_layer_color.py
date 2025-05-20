"""Unit tests for the *Layer* colour round-trip serialisation."""

from digcalc_project.src.models.layer import Layer
from digcalc_project.src.models.serializers import layer_to_dict, layer_from_dict


def test_layer_color_roundtrip() -> None:
    """Layer ➜ dict ➜ Layer should preserve colour fields."""
    layer = Layer(id="l1", name="Pad A")
    data = layer_to_dict(layer)
    clone = layer_from_dict(data)

    assert clone.line_color.startswith("#"), "Expected hex colour string."
    assert clone.point_color == clone.line_color 