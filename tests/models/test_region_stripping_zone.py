import json
import tempfile
from pathlib import Path

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.region import Region


def test_region_serialise_roundtrip():
    reg = Region(
        name="Zone A", polygon=[(0, 0), (10, 0), (10, 10)], strip_depth_ft=1.5, material_id=2
    )
    data = reg.to_dict()
    reg2 = Region.from_dict(data)
    assert reg2.name == reg.name
    assert reg2.strip_depth_ft == reg.strip_depth_ft
    assert reg2.material_id == 2
    assert reg2.polygon == reg.polygon


def test_project_save_load_with_region(tmp_path):
    proj = Project("StripDemo")
    reg = Region(name="Zone B", polygon=[(0, 0), (5, 0), (5, 5)], strip_depth_ft=2.0, material_id=3)
    proj.regions.append(reg)

    file_path = Path(tmp_path) / "project_strip.json"
    assert proj.save(str(file_path))

    loaded = Project.load(str(file_path))
    assert loaded is not None
    assert len(loaded.regions) == 1
    lr = loaded.regions[0]
    assert lr.name == "Zone B"
    assert lr.material_id == 3
    assert lr.strip_depth_ft == 2.0
