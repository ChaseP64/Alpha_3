import pytest
from pathlib import Path
from digcalc_project.src.services.pdf_service import PdfService
from digcalc_project.src.models.pdf_document import PdfDocument
from PySide6.QtCore import QEventLoop, QTimer
from PyPDF2 import PdfWriter


@pytest.fixture(scope="session")
def fixture_pdf_file(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Generate a simple 3‑page PDF using PyPDF2.

    Relying on :class:`~PyPDF2.PdfWriter` guarantees the resulting file
    is standards‑compliant and readable by :class:`~PySide6.QtPdf.QPdfDocument`
    across operating systems.
    """
    tmp_dir = tmp_path_factory.mktemp("pdfs")
    pdf_path = tmp_dir / "multi_page_test.pdf"

    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=200)

    with pdf_path.open("wb") as f:
        writer.write(f)

    return str(pdf_path)


def test_load_valid_pdf(qtbot, fixture_pdf_file):
    svc = PdfService()
    doc = svc.load_pdf(fixture_pdf_file)
    assert isinstance(doc, PdfDocument)
    assert doc.page_count == 3


def test_request_thumbnail(qtbot, fixture_pdf_file):
    svc = PdfService()
    doc = svc.load_pdf(fixture_pdf_file)
    assert doc and doc.page_count == 3

    # Wait briefly to allow any internal signal delivery (though load is sync)
    loop = QEventLoop()
    QTimer.singleShot(50, loop.quit)
    # Qt6 renamed exec_() → exec(). Keep compatibility with both.
    getattr(loop, "exec", loop.exec_)()

    results = {}

    def on_thumb(page, pixmap):
        results[page] = pixmap

    svc.thumbnailReady.connect(on_thumb)

    svc.request_thumbnail(0, 120)
    qtbot.waitSignal(svc.thumbnailReady, timeout=1000)

    assert 0 in results
    assert not results[0].isNull()
    assert results[0].width() == 120 or results[0].height() > 0


def test_thumbnail_cache(qtbot, fixture_pdf_file):
    svc = PdfService()
    svc.load_pdf(fixture_pdf_file)

    # first render
    svc.request_thumbnail(1, 100)
    qtbot.waitSignal(svc.thumbnailReady, timeout=1000)

    # Set up counter to verify cache hit emits instantly
    count = {"calls": 0}

    def on_thumb(page, pixmap):
        count["calls"] += 1

    svc.thumbnailReady.connect(on_thumb)

    svc.request_thumbnail(1, 100)
    assert count["calls"] == 1 