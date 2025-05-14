import json
from pathlib import Path

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.project_scale import ProjectScale


def test_migrate_world_per_in(tmp_path):
    """Legacy files with world_per_in should migrate to ProjectScale or set flag."""
    legacy = {
        "name": "legacy job",
        "world_per_in": 40.0,
        "world_units": "ft",
    }

    pth: Path = tmp_path / "legacy.json"
    pth.write_text(json.dumps(legacy))

    # Load without PDF service → expect invalid flag
    proj = Project.load(str(pth), pdf_service=None)
    assert proj is not None
    assert proj.scale is None
    assert "scale-invalid" in proj.flags

    # Provide dummy PDF service with DPI
    class Dummy:
        @staticmethod
        def current_render_dpi() -> float:
            return 150.0

    proj2 = Project.load(str(pth), pdf_service=Dummy())
    assert isinstance(proj2.scale, ProjectScale)
    expected = 40.0 / 150.0
    assert abs(proj2.scale.world_per_px - expected) < 1e-6 