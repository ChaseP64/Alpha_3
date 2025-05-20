"""Serializer round-trip test for Layer.visible field."""

from digcalc_project.src.models.layer import Layer
from digcalc_project.src.models.serializers import layer_to_dict, layer_from_dict


def test_layer_visibility_roundtrip():
    """visible flag should persist through dict serialization."""
    layer = Layer(id="L1", name="Hidden", visible=False)
    blob = layer_to_dict(layer)
    clone = layer_from_dict(blob)
    assert clone.visible is False 