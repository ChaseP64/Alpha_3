from __future__ import annotations

"""PDFEventHandler – centralises PDF-related actions & signals.

Phase-2 refactor extracts all PDF background and tracing slots from
``main_window.py`` so they can be unit-tested in isolation and so the
MainWindow becomes a thin orchestrator.

At this step we *delegate* to the legacy implementations still present
on :class:`~ui.main_window.main_window.MainWindow`; the real bodies will
be migrated later.  All Qt signal wiring for PDF actions is performed in
:py:meth:`_connect_signals` so ``SignalBinder`` no longer needs to know
about these controls.
"""

from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class PDFEventHandler:  # noqa: D101
    def __init__(self, mw: "MainWindow") -> None:  # noqa: D401 – simple init
        self._mw = mw
        self.logger = getattr(mw, "logger", logger)
        self._connect_signals()

    # ------------------------------------------------------------------
    # Qt-signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:  # noqa: D401 – internal helper
        """Wire PDF actions & widgets to this handler's slots."""
        mw = self._mw

        # Guard: only wire the signals that actually exist in this context.
        # A few widgets are optional or replaced by mocks during headless
        # test runs, so we check with ``hasattr`` before connecting.
        act = getattr(mw, "load_pdf_background_action", None)
        if act is not None:
            act.triggered.connect(self.on_load_pdf_background)

        act = getattr(mw, "clear_pdf_background_action", None)
        if act is not None:
            act.triggered.connect(self.on_clear_pdf_background)

        act = getattr(mw, "prev_pdf_page_action", None)
        if act is not None:
            act.triggered.connect(self.on_prev_pdf_page)

        act = getattr(mw, "next_pdf_page_action", None)
        if act is not None:
            act.triggered.connect(self.on_next_pdf_page)

        # Spin-box page selector (valueChanged)
        spin = getattr(mw, "pdf_page_spinbox", None)
        if spin is not None:
            spin.valueChanged.connect(self.on_set_pdf_page_from_spinbox)

        # PdfController emits pageSelected (index) signal.
        if mw.pdf_controller is not None:
            mw.pdf_controller.pageSelected.connect(self._on_pdf_page_selected)

        # PdfService emits documentLoaded(page_count) → used to resize spin-box
        if hasattr(mw, "pdf_service") and mw.pdf_service is not None:
            mw.pdf_service.documentLoaded.connect(self._on_document_loaded)

        # *Trace from PDF* toolbar button / menu item
        act = getattr(mw, "trace_pdf_action", None)
        if act is not None:
            act.triggered.connect(self._on_trace_from_pdf)

        self.logger.debug("PDFEventHandler signals bound.")

    # ------------------------------------------------------------------
    # Public slots – delegating to legacy MainWindow implementations for now
    # ------------------------------------------------------------------
    def on_load_pdf_background(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_load_pdf_background"):
            self._mw.on_load_pdf_background()

    def on_clear_pdf_background(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_clear_pdf_background"):
            self._mw.on_clear_pdf_background()

    def on_next_pdf_page(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_next_pdf_page"):
            self._mw.on_next_pdf_page()

    def on_prev_pdf_page(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_prev_pdf_page"):
            self._mw.on_prev_pdf_page()

    def on_set_pdf_page_from_spinbox(self, page_number: int) -> None:  # noqa: D401
        if hasattr(self._mw, "on_set_pdf_page_from_spinbox"):
            self._mw.on_set_pdf_page_from_spinbox(page_number)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Private slots mirrored from MainWindow (kept private here too)
    # ------------------------------------------------------------------
    def _on_pdf_page_selected(self, page_index: int) -> None:  # noqa: D401
        if hasattr(self._mw, "_on_pdf_page_selected"):
            self._mw._on_pdf_page_selected(page_index)  # type: ignore[arg-type]

    def _on_document_loaded(self, page_count: int) -> None:  # noqa: D401
        if hasattr(self._mw, "_on_document_loaded"):
            self._mw._on_document_loaded(page_count)  # type: ignore[arg-type]

    def _on_trace_from_pdf(self) -> None:  # noqa: D401
        if hasattr(self._mw, "_on_trace_from_pdf"):
            self._mw._on_trace_from_pdf() 