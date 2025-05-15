from digcalc_project.src.controllers.pdf_controller import PdfController


def test_controller_re_emits_page(qtbot):
    """PdfController should forward *pageClicked* → *pageSelected*."""
    ctrl = PdfController()
    received: list[int] = []
    ctrl.pageSelected.connect(lambda p: received.append(p))

    # Simulate a thumbnail click (zero‑based index 7 ⇒ one‑based 8 expected)
    ctrl.on_page_clicked(7)

    assert received == [8], "PdfController must re‑emit the clicked page index as 1‑based"
