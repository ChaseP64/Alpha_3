from pathlib import Path
from types import SimpleNamespace

from reportlab.platypus import SimpleDocTemplate
from digcalc_project.src.core.reporting.pdf_report import add_job_summary


def test_pdf_smoke(tmp_path):
    """Smoke-test: ensure a minimal PDF can be produced."""

    pdf: Path = tmp_path / "out.pdf"

    # Compose story.
    story: list = []
    add_job_summary(
        story,
        SimpleNamespace(name="Test Project"),
        SimpleNamespace(
            strip_depth_default=lambda: 1.0,
            slice_thickness_default=lambda: 0.5,
        ),
    )

    # Build PDF.
    SimpleDocTemplate(str(pdf)).build(story)

    # Verify output file exists and is not empty.
    assert pdf.exists() and pdf.stat().st_size > 0 