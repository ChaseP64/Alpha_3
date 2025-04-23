import pytest
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap

from digcalc_project.src.services.pdf_service import PdfService
from digcalc_project.src.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _app(qtbot):
    """Ensure a QApplication instance for all tests in this module."""
    app = QApplication.instance() or QApplication([])
    yield app


def test_page_selected_updates_scene(qtbot):
    """Emitting *pageSelected* should add/replace the background pixmap."""
    # 1. Stub PdfDocument so we can control render_page
    class _StubPdfDoc:
        def render_page(self, page: int, width: int) -> QPixmap:  # noqa: D401
            pix = QPixmap(10, 5)
            pix.fill(Qt.red)
            return pix

    # Inject stub into the singleton service
    svc = PdfService()
    svc._current = _StubPdfDoc()  # type: ignore[attr-defined]

    # 2. Create the main window (this constructs PdfController + panel)
    mw = MainWindow()
    panel = mw.visualization_panel

    # 3. Emit pageSelected (controller lives on mw)
    qtbot.wait(10)  # allow event loop to settle
    mw.pdf_controller.pageSelected.emit(2)
    qtbot.wait(10)

    # 4. Assert TracingScene background item exists and has correct size
    bg_item = panel.scene_2d._background_item  # type: ignore[attr-defined]
    assert isinstance(bg_item, QGraphicsPixmapItem)
    assert bg_item.pixmap().size() == QSize(10, 5) 