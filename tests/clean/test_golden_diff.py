import numpy as np

from digcalc_project.src.core.geom.polyline import Polyline
from tests.golden import diff_percentage, to_jsonable, from_jsonable


def test_diff_percentage_zero():
    polys = [Polyline(vertices=np.array([[0, 0], [1, 0]]))]
    diff = diff_percentage(polys, polys)
    assert diff == 0.0 