import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from digcalc_project.src.services.pdf_service import PdfService
from digcalc_project.src.ui.docks.pdf_thumbnail_dock import PdfThumbnailDock


@pytest.fixture(autouse=True)
def _app(qtbot):  # ensure QApplication
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def svc():
    return PdfService()


@pytest.fixture
def dock(qtbot, svc):
    d = PdfThumbnailDock()
    svc.documentLoaded.connect(d.model.set_page_count)
    svc.thumbnailReady.connect(d.model.update_thumbnail)
    qtbot.addWidget(d)
    return d


def test_model_row_count_after_load(svc, dock):
    svc.documentLoaded.emit(5)
    assert dock.model.rowCount() == 5


def test_update_thumbnail_creates_decoration(svc, dock):
    pix = QPixmap(10, 10)
    svc.documentLoaded.emit(3)
    svc.thumbnailReady.emit(2, pix)
    idx = dock.model.index(2, 0)
    dec = dock.model.data(idx, Qt.DecorationRole)
    assert isinstance(dec, QPixmap)
    assert not dec.isNull()


def test_page_clicked_signal(qtbot, svc, dock):
    svc.documentLoaded.emit(3)
    assert dock.model.rowCount() == 3
    with qtbot.waitSignal(dock.pageClicked):
        idx = dock.model.index(1, 0)
        dock.view.clicked.emit(idx) 