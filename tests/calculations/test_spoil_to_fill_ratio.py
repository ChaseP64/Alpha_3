import numpy as np

import pytest

from digcalc_project.src.core.calculators.volume_calculator import balance_cut_fill
from digcalc_project.src.services.settings_service import SettingsService


def test_spoil_ratio_zero_means_all_fill_is_import(monkeypatch):
    """Setting ratio 0 → no cut re-used, all fill counted as import."""
    SettingsService().set("strata", "spoil_to_fill_ratio", 0.0)

    cut = 100.0
    fill = 60.0
    res = balance_cut_fill(cut, fill)

    assert res["import_volume"] == pytest.approx(fill)
    # none of the cut is reused, everything is exported
    assert res["reused_cut_volume"] == pytest.approx(0.0)
    assert res["export_volume"] == pytest.approx(cut)


def test_default_ratio_one_uses_cut_to_satisfy_fill():
    """Default ratio 1.0 should reuse cut before importing."""
    # Ensure default (1.0) in SettingsService
    cut = 100.0
    fill = 60.0
    res = balance_cut_fill(cut, fill, ratio=1.0)
    assert res["import_volume"] == pytest.approx(0.0)
    assert res["reused_cut_volume"] == pytest.approx(fill)
    assert res["export_volume"] == pytest.approx(cut - fill) 