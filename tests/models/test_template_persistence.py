from __future__ import annotations

from pathlib import Path

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.template import Template


def test_project_save_load_templates(tmp_path: Path):
    proj = Project("TplDemo")
    t1 = Template(name="Pad A", type="pad", params={"width": 10.0, "length": 20.0, "depth": 1.5})
    t2 = Template(
        name="Trench B", type="trench", params={"width": 3.0, "length": 50.0, "depth": 2.0}
    )
    proj.templates = [t1, t2]

    file_path = Path(tmp_path) / "project_tpl.json"
    assert proj.save(str(file_path))

    loaded = Project.load(str(file_path))
    assert loaded is not None
    assert len(loaded.templates) == 2
    names = {tpl.name for tpl in loaded.templates}
    assert {"Pad A", "Trench B"} <= names
    # params preserved
    match = next(t for t in loaded.templates if t.name == "Pad A")
    assert match.params["width"] == 10.0

