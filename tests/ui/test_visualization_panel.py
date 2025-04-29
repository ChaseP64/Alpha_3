import pytest
import fitz # Import the real fitz for monkeypatching
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap

from digcalc_project.src.services.pdf_service import PdfService
from digcalc_project.src.ui.main_window import MainWindow
from digcalc_project.src.visualization.pdf_renderer import PDFRenderer


@pytest.fixture(autouse=True)
def _app(qtbot):
    """Ensure a QApplication instance for all tests in this module."""
    app = QApplication.instance() or QApplication([])
    yield app


def test_page_selected_updates_scene(qtbot, monkeypatch):
    """Emitting *pageSelected* should add/replace the background pixmap."""
    # 1. Stub PdfDocument so we can control render_page
    class _StubPdfDoc:
        page_count = 3 # Add page_count for renderer init
        
        # --- Define a dummy page object --- 
        class _DummyPage:
            def get_pixmap(self, *args, **kwargs):
                # Return a dummy fitz.Pixmap like object
                class DummyPixmap:
                    width = 10
                    height = 5
                    stride = 10 * 3 # Assuming RGB888
                    samples = bytes([255, 0, 0] * (10 * 5)) # Red pixels
                    colorspace = fitz.csRGB
                return DummyPixmap()
        # --- End dummy page --- 

        def __iter__(self):
            # Yield instances of the dummy page object
            for _ in range(self.page_count):
                yield self._DummyPage()

        # Keep render_page stub for PdfService compatibility if needed elsewhere
        def render_page(self, page: int, width: int) -> QPixmap: # noqa: D401
            pix = QPixmap(10, 5)
            pix.fill(Qt.red)
            return pix
        
        def close(self): pass
        def page_label(self, page_index): return f"{page_index+1}"

    # Inject stub into the singleton service
    svc = PdfService()
    stub_doc = _StubPdfDoc()
    svc._current = stub_doc

    # 2. Create the main window (this constructs PdfController + panel)
    mw = MainWindow()
    panel = mw.visualization_panel

    # --- NEW: Monkeypatch fitz.open and manually create PDFRenderer --- 
    # Patch fitz.open to return our stub document instead of opening a file
    def mock_fitz_open(*args, **kwargs):
        return stub_doc
    monkeypatch.setattr(fitz, "open", mock_fitz_open)

    try:
        # Create renderer - path is irrelevant due to patching
        renderer = PDFRenderer(pdf_path="dummy.pdf", dpi=150)
        panel.pdf_renderer = renderer
    except Exception as e:
        pytest.fail(f"Failed to manually create PDFRenderer for test: {e}")
    # --- END NEW ---

    # 3. Emit pageSelected (controller lives on mw)
    qtbot.wait(10)  # allow event loop to settle
    mw.pdf_controller.pageSelected.emit(2)
    qtbot.wait(10)

    # 4. Assert TracingScene background item exists and has correct size
    bg_items = panel.scene_2d._background_items  # type: ignore[attr-defined]
    assert bg_items, "No background items found in scene"
    bg_item = bg_items[-1] # Check the last added item
    assert isinstance(bg_item, QGraphicsPixmapItem)
    assert bg_item.pixmap().size() == QSize(10, 5) 