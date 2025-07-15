from __future__ import annotations

"""Built-in Smart-Clean rules (Phase-2 Day-2).

Imported automatically by *core.clean* to register the default rules.
"""

from typing import List, Sequence

from .rule_engine import BaseRule, RuleRegistry
from ..geom.polyline import Polyline  # relative to core.clean

__all__ = ["GapCloseRule", "LayerClassifyRule"]


class GapCloseRule(BaseRule):  # noqa: D101 – simple wrapper
    name = "GapCloseRule"

    def apply(self, items: Sequence[Polyline]) -> List[Polyline]:  # noqa: D401
        # Bridge small gaps & angle misalignments via helper
        return Polyline.auto_join_v2(items)


class LayerClassifyRule(BaseRule):  # noqa: D101 – heuristics stub
    name = "LayerClassifyRule"

    def apply(self, items: Sequence[Polyline]) -> List[Polyline]:  # noqa: D401
        for pl in items:
            # Naïve heuristic classification (placeholder)
            if pl.dash is not None:
                layer = "road"
            elif pl.stroke_rgb and pl.stroke_rgb[0] < pl.stroke_rgb[1]:
                layer = "contour"
            else:
                layer = "misc"
            # Attach classification attribute dynamically
            setattr(pl, "layer_class", layer)
        return list(items)


# Auto-register rules so users only need to `import core.clean`
RuleRegistry.register(GapCloseRule)
RuleRegistry.register(LayerClassifyRule) 