import pytest
from pytestqt.qt_compat import qt_api

from digcalc_project.src.ui.main_window import MainWindow


@pytest.mark.skipif(not qt_api, reason="pytest-qt not available")
def test_calibrate_action_enabled(qtbot):
    """Scale-calibration menu item toggles based on PDF load signal."""
    win = MainWindow()
    qtbot.addWidget(win)

    act = win.scale_calib_act
    # Initially disabled when no PDF is loaded
    assert not act.isEnabled()

    # Simulate PDF load – PdfService.documentLoaded(int page_count) is connected
    win.pdf_service.documentLoaded.emit(5)  # non-zero page count
    qtbot.wait(10)
    assert act.isEnabled()

    # Simulate clearing background via MainWindow helper to verify disable
    win.on_clear_pdf_background()
    qtbot.wait(10)
    assert not act.isEnabled()
