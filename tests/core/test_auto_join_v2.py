import numpy as np

from digcalc_project.src.core.geom.polyline import Polyline


def test_auto_join_v2_basic_merge():
    """Two colinear segments separated by small gap should merge."""

    pl1 = Polyline(vertices=np.array([[0.0, 0.0], [1.0, 0.0]]))
    pl2 = Polyline(vertices=np.array([[1.005, 0.0], [2.0, 0.0]]))

    merged = Polyline.auto_join_v2([pl1, pl2], gap_tol=0.01)
    assert len(merged) == 1, "Segments within gap_tol should merge into single polyline"
    assert np.allclose(merged[0].vertices[0], [0.0, 0.0])
    assert np.allclose(merged[0].vertices[-1], [2.0, 0.0])
