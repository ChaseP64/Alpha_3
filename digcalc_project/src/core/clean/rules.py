from __future__ import annotations

"""Built-in Smart-Clean rules (Phase-2 Day-2).

Imported automatically by *core.clean* to register the default rules.
"""

from typing import List, Sequence

from ..geom.polyline import Polyline  # relative to core.clean
from .rule_engine import BaseRule, RuleRegistry

__all__ = ["GapCloseRule", "LayerClassifyRule"]


class GapCloseRule(BaseRule):  # noqa: D101 – simple wrapper
    name = "GapCloseRule"

    def apply(self, items: Sequence[Polyline]) -> List[Polyline]:  # noqa: D401
        # Bridge small gaps & angle misalignments via helper
        return Polyline.auto_join_v2(items)


class LayerClassifyRule(BaseRule):  # noqa: D101 – heuristics implementation (Phase-6)
    name = "LayerClassifyRule"

    # ------------------------------------------------------------------
    # Tunable colour → layer palette (RGB 0-255).  Keys are canonical layer
    # names used throughout DigCalc.  Values are *representative* stroke
    # colours commonly found in construction plan sets.  The list may be
    # expanded in later sprints or made user-configurable via SettingsService.
    # ------------------------------------------------------------------
    _PALETTE: dict[str, list[tuple[int, int, int]]] = {
        "contour": [  # brown/sepia
            (150, 75, 0),
            (120, 60, 0),
        ],
        "road": [  # black or dark-grey
            (0, 0, 0),
            (50, 50, 50),
        ],
        "water": [  # blue
            (0, 0, 255),
            (0, 120, 200),
        ],
        "boundary": [  # magenta
            (255, 0, 255),
            (200, 0, 200),
        ],
    }

    _THRESH: float = 60.0  # max Euclidean distance in RGB space to accept match

    @staticmethod
    def _colour_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
        """Return Euclidean distance between two RGB triples (0-255)."""
        return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

    # ------------------------------------------------------------------
    def _classify_by_colour(self, rgb: tuple[int, int, int]) -> str | None:
        """Return layer name whose representative colour lies *nearest* to *rgb*.

        None when no colour lies within :pyattr:`_THRESH`.
        """
        best_layer: str | None = None
        best_dist: float = float("inf")
        for layer, samples in self._PALETTE.items():
            for s in samples:
                d = self._colour_distance(rgb, s)
                if d < best_dist:
                    best_layer, best_dist = layer, d
        return best_layer if best_dist <= self._THRESH else None

    # ------------------------------------------------------------------
    def _classify_by_ocr(self, text: str | None) -> str | None:
        """Return layer guess from *text* heuristics (case-insensitive)."""
        if not text:
            return None
        t = text.lower()
        if any(k in t for k in ("cl", "centerline", "road")):
            return "road"
        if any(k in t for k in ("contour", "elev", "el")):
            return "contour"
        if any(k in t for k in ("water", "pond", "lake")):
            return "water"
        if any(k in t for k in ("prop line", "boundary", "prop. line", "property")):
            return "boundary"
        return None

    # ------------------------------------------------------------------
    def apply(self, items: Sequence[Polyline]) -> List[Polyline]:  # noqa: D401
        for pl in items:
            layer: str | None = None

            # 1) OCR-based hint (higher priority)
            layer = self._classify_by_ocr(getattr(pl, "ocr_label", None))

            # 2) Fallback to colour distance if still unknown
            if layer is None and pl.stroke_rgb is not None:
                layer = self._classify_by_colour(pl.stroke_rgb)

            # 3) Dash pattern hint (centreline dashed) – keep simple for now
            if layer is None and pl.dash is not None:
                layer = "centreline" if len(pl.dash) == 2 else None

            # 4) Default catch-all
            if layer is None:
                layer = "misc"

            # Attach classification attribute so downstream code can access
            setattr(pl, "layer_class", layer)
        return list(items)


# Auto-register rules so users only need to `import core.clean`
RuleRegistry.register(GapCloseRule)
RuleRegistry.register(LayerClassifyRule)
