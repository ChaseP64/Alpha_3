from __future__ import annotations

"""Smoke test for PolylineItem.sample() compression logic."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QPen  # noqa: E402

from digcalc_project.src.services.settings_service import SettingsService  # noqa: E402
from digcalc_project.src.ui.items.polyline_item import PolylineItem  # noqa: E402


def test_sample_compression(qtbot):
    """Sampling a 100-ft polyline should return fewer than the raw 100 points."""
    pts = [QPointF(x, 0) for x in range(100)]  # 100 ft straight line
    dummy_pen = QPen()  # Pen required by constructor
    poly = PolylineItem(pts, layer_pen=dummy_pen)  # type: ignore[arg-type]

    ss = SettingsService()

    sampled = poly.sample(ss.smooth_sampling_ft())

    assert len(sampled) <= 100
    # Ensure first and last points are preserved
    assert sampled[0][0] == 0
    assert sampled[-1][0] == 99
