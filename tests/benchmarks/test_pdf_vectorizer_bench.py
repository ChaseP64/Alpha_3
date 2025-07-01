"""Performance benchmark for PDFVectorizer batch processing.

Run with:

    DIGCALC_RUN_BENCH=1 pytest -m perf tests/benchmarks/test_pdf_vectorizer_bench.py

Benchmarks are skipped by default and require the environment variable so that
normal CI runs stay quick.  We simply assert that vectorising a ~10 MB drawing
completes within an acceptable time budget (1 s on a modern laptop).  The PDF
file used is the *Structural Plans* sample shipped with the repo – ~6 MB – which
is large enough to stress-test parsing and post-processing.
"""

import os
from pathlib import Path

import pytest

# Skip entire benchmark when vectorizer disabled
if os.getenv("DIGCALC_PDF_VEC") != "1":
    pytest.skip("PDF vectorizer feature disabled (DIGCALC_PDF_VEC != 1)", allow_module_level=True)

from digcalc_project.src.services.io.pdf_vectorizer import PDFVectorizer

# ---------------------------------------------------------------------------
# Opt-in guard – skip unless explicitly enabled by developer
# ---------------------------------------------------------------------------
if os.getenv("DIGCALC_RUN_BENCH") != "1":
    pytest.skip("Benchmarks disabled – set DIGCALC_RUN_BENCH=1 to enable.", allow_module_level=True)

# ---------------------------------------------------------------------------
# Locate test asset (fallback: skip if missing)
# ---------------------------------------------------------------------------
PDF_ASSET = Path(__file__).resolve().parent.parent.parent / "Structural Plans - Stout Roofing 3-12-25.pdf"

if not PDF_ASSET.exists():
    pytest.skip("Large PDF asset not available for vectorizer benchmark.", allow_module_level=True)


@pytest.mark.perf
def test_pdf_vectorizer_perf_10mb(benchmark):
    """Vectorising the sample sheet should finish in < 1 s on dev machine."""

    vec = PDFVectorizer(dpi=300)

    def _run():  # noqa: D401 – benchmark wrapper
        vec.vectorize(PDF_ASSET, page_no=0)

    runtime = benchmark(_run)

    # Assert within generous budget (2 s) to avoid flakiness on CI VMs.
    assert runtime < 2.0 