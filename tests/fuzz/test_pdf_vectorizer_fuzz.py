"""Fuzz test for PDFVectorizer using Radamsa-generated corrupt inputs.

Run only when (a) the vectorizer feature is enabled and (b) the external
`radamsa` binary is available in PATH.  The goal is to ensure the
vectorizer never seg-faults on malformed PDFs – Python exceptions are
acceptable.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from digcalc_project.src import PDF_VECTORIZER_ENABLED

# Skip when vectorizer disabled via env flag
if not PDF_VECTORIZER_ENABLED:
    pytest.skip("PDF vectorizer feature disabled", allow_module_level=True)

RADAMSA = shutil.which("radamsa")
if RADAMSA is None:
    pytest.skip("Radamsa not found in PATH – fuzz test skipped.", allow_module_level=True)

from digcalc_project.src.services.io.pdf_vectorizer import PDFVectorizer
import fitz  # runtime heavy but only if test runs

ITERATIONS = int(os.getenv("PDF_VEC_FUZZ_ITERS", "50"))


def _make_minimal_pdf(path: Path) -> None:
    """Create a 1-page minimal PDF with a single stroke (for mutation)."""
    doc = fitz.open()
    page = doc.new_page(width=72, height=72)
    page.draw_line((0, 0), (72, 0))
    doc.save(path)
    doc.close()


@pytest.mark.perf
def test_vectorizer_radamsa_fuzz(tmp_path: Path):
    src_pdf = tmp_path / "seed.pdf"
    _make_minimal_pdf(src_pdf)

    vec = PDFVectorizer(dpi=72)

    crashes = 0
    for i in range(ITERATIONS):
        fuzz_pdf = tmp_path / f"fuzz_{i}.pdf"
        # Run radamsa to mutate bytes
        subprocess.run([RADAMSA, src_pdf, "-o", fuzz_pdf], check=True)

        try:
            vec.vectorize(fuzz_pdf, page_no=0)
        except Exception:
            # Any Python-level exception is acceptable; just continue
            continue

    assert crashes == 0  # process would have aborted on segfault 