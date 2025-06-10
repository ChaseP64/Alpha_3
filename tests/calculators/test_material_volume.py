import numpy as np
from digcalc_project.src.models.strata_models import StrataStack, StrataSurface, Material
from digcalc_project.src.core.calculators.volume_calculator import calculate_material_cut

def _flat_surface(mat_id, z):
    grid=np.full((3,3), z, dtype=float)
    return StrataSurface(id=mat_id, material_id=mat_id, grid_data=grid, grid_metadata={})

def test_material_cut_simple_trench():
    # setup surfaces 0-10,10-20,20-30
    mats=[Material(id=1,name='Dirt',colour='#111'),Material(id=2,name='Rock',colour='#222'),Material(id=3,name='Deep',colour='#333')]
    surfaces=[_flat_surface(1,0.0),_flat_surface(2,10.0),_flat_surface(3,20.0)]
    stack=StrataStack(materials=mats,boreholes=[])
    stack.surfaces=surfaces
    existing=np.full((3,3),30.0)
    proposed=np.full((3,3),15.0)
    cell_area=1.0
    vols=calculate_material_cut(existing,proposed,stack,cell_area)
    assert abs(vols[1]-10*9)<1e-6
    assert abs(vols[2]-5*9)<1e-6 