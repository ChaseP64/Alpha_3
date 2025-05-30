import pyvista as pv
from qtpy.QtGui import QColor

from digcalc_project.src.models.mesh_actor import MeshActor


def test_mesh_actor_defaults():
    """Ensure MeshActor initialises with expected default values."""
    cube = pv.Cube()
    ma = MeshActor(surface_name="Cube", mesh=cube, color=QColor("#ff0000"))

    # Default scalar properties
    assert ma.opacity == 1.0
    assert ma.representation == "surface"
    assert ma.visible is True

    # Runtime-only field should be uninitialised
    assert ma.actor is None 