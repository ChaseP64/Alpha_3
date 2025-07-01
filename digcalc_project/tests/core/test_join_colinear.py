import numpy as np
from digcalc_project.src.core.geom.polyline import Polyline

def test_join_colinear_removes_intermediate():
    # Create 4 colinear points along X axis
    verts = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    pl = Polyline(vertices=verts)
    simplified = Polyline.join_colinear(pl)
    assert simplified.vertices.shape[0] == 2
    np.testing.assert_allclose(simplified.vertices[[0, -1]], [[0.0, 0.0], [3.0, 0.0]])

def test_join_colinear_keeps_corner():
    verts = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 1.0], [3.0, 1.0]])
    pl = Polyline(vertices=verts)
    simplified = Polyline.join_colinear(pl)
    # Should keep corner at (2,1)
    assert simplified.vertices.shape[0] == 3 