"""Unit tests for *LayerClassifyRule* heuristic classifier (Phase-6 D1).

These tests exercise the colour-distance heuristic, the OCR keyword path and
fallback behaviour.
"""

from __future__ import annotations

import numpy as np

from digcalc_project.src.core.clean.rule_engine import RuleRegistry
from digcalc_project.src.core.clean.rules import LayerClassifyRule
from digcalc_project.src.core.geom.polyline import Polyline


def _make_poly(vertices=((0.0, 0.0), (1.0, 0.0)), *, rgb=None, dash=None, label=None):
    pl = Polyline(vertices=np.asarray(vertices))
    pl.stroke_rgb = rgb
    pl.dash = dash
    if label is not None:
        setattr(pl, "ocr_label", label)
    return pl


def test_colour_based_classification():
    """Dark-brown stroke should map to *contour* layer within threshold."""
    contour_rgb = (140, 70, 10)
    pl = _make_poly(rgb=contour_rgb)

    RuleRegistry.clear()
    RuleRegistry.register(LayerClassifyRule)
    [classified] = RuleRegistry.evaluate([pl])

    assert getattr(classified, "layer_class") == "contour"


def test_ocr_priority_over_colour():
    """OCR keyword wins over colour hint if both are present."""
    road_rgb = (0, 0, 0)  # black
    pl = _make_poly(rgb=road_rgb, label="Existing Contour")

    RuleRegistry.clear()
    RuleRegistry.register(LayerClassifyRule)
    [classified] = RuleRegistry.evaluate([pl])

    assert getattr(classified, "layer_class") == "contour", "OCR hint should take precedence"


def test_unknown_defaults_to_misc():
    """No colour inside palette and no OCR → *misc*."""
    weird_rgb = (123, 231, 45)
    pl = _make_poly(rgb=weird_rgb)

    RuleRegistry.clear()
    RuleRegistry.register(LayerClassifyRule)
    [classified] = RuleRegistry.evaluate([pl])

    assert getattr(classified, "layer_class") == "misc"
