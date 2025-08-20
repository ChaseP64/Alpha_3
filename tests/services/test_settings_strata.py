from digcalc_project.src.services.interpolation_service import IDWInterpolator
from digcalc_project.src.services.settings_service import SettingsService


def test_idw_power_persistence(tmp_path, monkeypatch):
    # Override settings path to temp file so we don't affect user settings
    monkeypatch.setattr(SettingsService, "_path", tmp_path / "settings.json", raising=False)
    s = SettingsService()
    s.set("strata", "idw_power", 4)
    # instantiate new interpolator, which internally fetches settings
    interp = IDWInterpolator()
    assert interp._settings.strata_idw_power == 4
