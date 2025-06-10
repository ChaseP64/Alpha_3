import csv, tempfile, os
import numpy as np
from digcalc_project.src.models.strata_models import StrataStack, StrataSurface, Material
from digcalc_project.src.core.calculators.volume_calculator import calculate_material_cut
from digcalc_project.src.core.reporting.csv_writer import save_material_cut_csv

def _flat(mat_id,z):
    return StrataSurface(id=mat_id,material_id=mat_id,grid_data=np.full((2,2),z),grid_metadata={})

def test_csv_export_matches_volumes():
    mats=[Material(id=1,name='Dirt',colour='#111'),Material(id=2,name='Rock',colour='#222')]
    stack=StrataStack(materials=mats,boreholes=[])
    stack.surfaces=[_flat(1,0),_flat(2,10)]
    existing=np.full((2,2),15.0)
    proposed=np.full((2,2),5.0)
    vols=calculate_material_cut(existing,proposed,stack,cell_area=1.0)

    with tempfile.TemporaryDirectory() as tmp:
        csv_path=os.path.join(tmp,'vols.csv')
        save_material_cut_csv(csv_path,vols,stack)
        with open(csv_path,newline='') as fp:
            rows=list(csv.reader(fp))
        data=dict((r[0],float(r[1])) for r in rows[1:])
        assert abs(data['Dirt']-5*4)<1e-6
        assert abs(data['Rock']-5*4)<1e-6 