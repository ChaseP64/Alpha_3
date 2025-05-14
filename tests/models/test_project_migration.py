import json
from pathlib import Path

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.project_scale import ProjectScale


def test_migrate_world_per_in(tmp_path):
    """Legacy files with world_per_in should migrate to ProjectScale or set flag."""
    legacy_data = {
        "name": "legacy job",
        "world_per_in": 40.0,
        "world_units": "ft",
    }

    pth: Path = tmp_path / "legacy.json"
    pth.write_text(json.dumps(legacy_data))

    # Case 1 – no PDF service, expect flag + scale is None
    proj = Project.load(str(pth), pdf_service=None)
    assert proj is not None, "Project.load returned None for legacy file"
    assert proj.scale is None
    assert "scale-invalid" in proj.flags

    # Case 2 – provide dummy PDF service with DPI
    class DummyPdfService:  # noqa: D401 – simple stub
        @staticmethod
        def current_render_dpi() -> float:
            return 150.0

    proj2 = Project.load(str(pth), pdf_service=DummyPdfService())
    assert isinstance(proj2.scale, ProjectScale)
    # world_per_px should equal 40ft / 150dpi
    expected = 40.0 / 150.0
    assert abs(proj2.scale.world_per_px - expected) < 1e-6 