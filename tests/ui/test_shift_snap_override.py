import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QGraphicsView

from digcalc_project.src.ui.tracing_scene import TracingScene
from digcalc_project.src.services.settings_service import SettingsService


class _Panel:
    current_project = None


@pytest.fixture
def scene(qtbot):
    app = QApplication.instance() or QApplication([])
    view = QGraphicsView()
    scn = TracingScene(view, _Panel())
    qtbot.addWidget(view)
    view.setScene(scn)
    return scn


def test_shift_disables_snapping(scene):
    # Insert reference point at (1,1)
    scene._sp_index.insert(1.0, 1.0, None)

    raw = QPointF(1.2, 1.1)
    # Snap enabled, no modifier ⇒ expect snap
    snapped, did = scene._apply_magnet_snaps(raw, Qt.NoModifier)
    assert did is True
    assert snapped == QPointF(1.0, 1.0)

    # With Shift ⇒ expect no snapping
    not_snapped, did2 = scene._apply_magnet_snaps(raw, Qt.ShiftModifier)
    assert did2 is False
    assert not_snapped == raw


def test_settings_roundtrip():
    s = SettingsService()
    original = s.enable_snap_default()
    s.set_enable_snap_default(not original)
    assert s.enable_snap_default() == (not original)
    # revert
    s.set_enable_snap_default(original) 