import pytest
from PySide6.QtWidgets import QApplication

from digcalc_project.src.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _app(qtbot):
    """Ensure a QApplication instance is available for all tests."""
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def main_window(qtbot):
    """Create and show a MainWindow instance for the test."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.show()
    return mw


def test_tracing_toggle_respects_enabled_flag(qtbot, main_window):
    """Ensure tracing cannot start when the mode is disabled."""
    panel = main_window.visualization_panel
    scene = panel.scene_2d

    # Tracing should start disabled by default
    assert scene._tracing_enabled is False, "Tracing flag should be disabled on startup."

    # Provide a dummy PDF renderer so enabling tracing is permitted
    panel.pdf_renderer = object()

    # Enable tracing via the panel helper
    panel.set_tracing_mode(True)
    assert scene._tracing_enabled is True, "Tracing flag not set after enabling."

    # Disable tracing via the panel helper
    panel.set_tracing_mode(False)
    assert scene._tracing_enabled is False, "Tracing flag not cleared after disabling."

    # Attempt to start drawing directly – should be blocked because tracing is disabled
    scene.start_drawing()
    assert scene._is_drawing is False, "Drawing started even though tracing is disabled."
