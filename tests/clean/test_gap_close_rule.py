import numpy as np

from digcalc_project.src.core.clean.rule_engine import RuleRegistry
from digcalc_project.src.core.clean.rules import GapCloseRule
from digcalc_project.src.core.geom.polyline import Polyline


def test_gap_close_rule_merges_segments():
    pl1 = Polyline(vertices=np.array([[0.0, 0.0], [1.0, 0.0]]))
    pl2 = Polyline(vertices=np.array([[1.005, 0.0], [2.0, 0.0]]))

    RuleRegistry.clear()
    RuleRegistry.register(GapCloseRule)

    result = RuleRegistry.evaluate([pl1, pl2])
    assert len(result) == 1 