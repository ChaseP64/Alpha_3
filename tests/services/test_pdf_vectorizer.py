import tempfile
from pathlib import Path

import numpy as np
import fitz

from digcalc_project.src.services.io.pdf_vectorizer import PDFVectorizer


def _create_tiny_pdf(tmp_path: Path) -> Path:
    """Create a 1-page PDF containing two simple stroke lines."""
    pdf_path = tmp_path / "two_lines.pdf"
    doc = fitz.open()
    page = doc.new_page(width=72, height=72)  # 1x1 inch at 72 dpi
    # Draw two orthogonal lines starting at the origin
    page.draw_line((0, 0), (72, 0))  # horizontal
    page.draw_line((0, 0), (0, 72))  # vertical
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def test_pdf_vectorizer_two_lines(tmp_path):
    pdf_path = _create_tiny_pdf(Path(tmp_path))

    vec = PDFVectorizer(dpi=72)
    polylines = vec.vectorize(pdf_path, page_no=0)

    # Expect exactly two polylines
    assert len(polylines) == 2
    # Each should have 2 vertices and be axis-aligned
    for pl in polylines:
        assert pl.vertices.shape == (2, 2)
    # Combined bounding-box should match page extent
    all_pts = np.vstack([pl.vertices for pl in polylines])
    min_x, min_y = all_pts.min(axis=0)
    max_x, max_y = all_pts.max(axis=0)
    assert np.isclose(min_x, 0.0)
    assert np.isclose(min_y, 0.0)
    assert np.isclose(max_x, 72.0) or np.isclose(max_y, 72.0) 