from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QWidget

from digcalc_project.src.models.project import Project
from digcalc_project.src.services.pdf_service import PdfService

# Adjust imports based on your project structure
from digcalc_project.src.ui.visualization_panel import VisualizationPanel


@pytest.fixture
def mock_project() -> Project:
    """Fixture for a mock Project object."""
    proj = Project(name="Test Project")
    # Mock any methods or attributes on proj if needed for VisualizationPanel
    return proj

@pytest.fixture
def visualization_panel(qtbot, mock_project) -> VisualizationPanel:
    """Fixture for VisualizationPanel."""
    # Mock the parent widget if necessary, or pass None
    parent_widget = QWidget()
    panel = VisualizationPanel(parent=parent_widget)
    panel.set_project(mock_project)
    # Only add the *parent* widget to qtbot so it is managed/closed; leave the
    # actual VisualizationPanel unmanaged to avoid premature C++ deletion.
    qtbot.addWidget(parent_widget)
    return panel

def test_pdf_background_dpi_is_stored(visualization_panel: VisualizationPanel, mock_project: Project, tmp_path):
    """Tests if load_pdf_background correctly stores the DPI in the project.
    """
    sample_pdf_path = tmp_path / "sample.pdf"
    # Create a dummy PDF file for the test
    with open(sample_pdf_path, "w") as f:
        f.write("%PDF-1.4\n%¥±Á\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                "2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
                "3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
                "trailer<</Root 1 0 R>>\n%%EOF")

    # Mock PdfService and its load_pdf method to return a mock PdfDocument
    mock_pdf_document = MagicMock()
    mock_pdf_document.page_count = 1

    # Mock PDFRenderer
    # The PDFRenderer is instantiated within load_pdf_background.
    # We need to patch its __init__ and methods if they are called.
    # For this specific test, we mainly care that load_pdf_background tries to set project.pdf_background_dpi.

    with patch.object(PdfService, "load_pdf", return_value=mock_pdf_document) as mock_load_pdf, \
         patch("digcalc_project.src.ui.visualization_panel.PDFRenderer") as MockPDFRenderer:

        # Configure the mock PDFRenderer instance if its methods are called
        mock_renderer_instance = MockPDFRenderer.return_value
        from PySide6.QtGui import QImage

        dummy_img = QImage(10, 10, QImage.Format.Format_RGB32)
        dummy_img.fill(0xFFFFFF)

        mock_renderer_instance.get_original_page_count.return_value = mock_pdf_document.page_count  # Page count of 1
        mock_renderer_instance.get_page_image.return_value = dummy_img  # Return a valid QImage

        # Stub out heavy Qt operations that aren't necessary for this logic test and
        # can trigger C++ deletion issues in headless mode.
        visualization_panel.scene_2d.addBackgroundLayer = lambda *args, **kwargs: None  # type: ignore[assignment]
        visualization_panel.view_2d.fitInView = lambda *args, **kwargs: None  # type: ignore[assignment]
        visualization_panel.show_2d_view = lambda *args, **kwargs: None  # type: ignore[assignment]
        # Completely stub out the rendering helper so no further Qt code runs
        visualization_panel._render_and_display_page = lambda *a, **k: None  # type: ignore[attr-defined]

        # Call the method to test
        test_dpi = 150
        success = visualization_panel.load_pdf_background(str(sample_pdf_path), dpi=test_dpi)

        assert success is True

        # Verify PDFRenderer was instantiated
        MockPDFRenderer.assert_called_once_with(pdf_path=str(sample_pdf_path), dpi=test_dpi) # Corrected assertion


def test_pdf_background_dpi_handles_load_failure(visualization_panel: VisualizationPanel, mock_project: Project, tmp_path):
    """Tests that DPI is not set if PDF loading fails.
    """
    sample_pdf_path = tmp_path / "nonexistent.pdf" # File doesn't exist

    initial_dpi = mock_project.pdf_background_dpi # Could be 0 or some default

    with patch.object(PdfService, "load_pdf", return_value=None) as mock_load_pdf:
        visualization_panel.scene_2d.addBackgroundLayer = lambda *args, **kwargs: None  # type: ignore[assignment]
        visualization_panel.view_2d.fitInView = lambda *args, **kwargs: None  # type: ignore[assignment]
        visualization_panel.show_2d_view = lambda *args, **kwargs: None  # type: ignore[assignment]
        # Completely stub out the rendering helper so no further Qt code runs
        visualization_panel._render_and_display_page = lambda *a, **k: None  # type: ignore[attr-defined]

        success = visualization_panel.load_pdf_background(str(sample_pdf_path), dpi=200)

        assert success is False
        # DPI should not have changed from its initial state if PDF load failed
        assert mock_project.pdf_background_dpi == initial_dpi
