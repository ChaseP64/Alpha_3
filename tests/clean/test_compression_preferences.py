import numpy as np
from pathlib import Path

import pytest

from digcalc_project.src.core.geom.polyline import Polyline
from digcalc_project.src.services.cleaners.smart_clean import auto_run
from digcalc_project.src.services.settings_service import SettingsService
from digcalc_project.src.utils.singleton import Singleton


@pytest.fixture(autouse=True)
def _reset_settings(tmp_path):
    # Reset singleton between tests
    SettingsService.clear_instances()
    cfg_path = tmp_path / "settings.json"
    SettingsService(config_path=cfg_path)
    yield
    SettingsService.clear_instances()


def test_smart_clean_compression_respects_dist_tol():
    pl = Polyline(vertices=np.array([[0.0, 0.0], [0.05, 0.0], [0.1, 0.0]]))

    settings = SettingsService()

    # Default dist_tol=0.10 → vertices compressed
    out_default = auto_run([pl])[0]
    assert len(out_default.vertices) < len(pl.vertices)

    # Tighten tolerance to 0.001 ft – should **not** compress
    settings.set("clean", "compress_dist_tol_ft", 0.001)
    out_strict = auto_run([pl])[0]
    assert len(out_strict.vertices) == len(pl.vertices) 