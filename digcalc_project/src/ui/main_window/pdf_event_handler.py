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

import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from ...ui.dialogs.pdf_page_selector_dialog import PdfPageSelectorDialog
from ...visualization.pdf_renderer import PDFRendererError

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
        controller = getattr(mw, "pdf_controller", None)
        if controller is not None:
            controller.pageSelected.connect(self._on_pdf_page_selected)

        # PdfService emits documentLoaded(page_count) → used to resize spin-box
        if hasattr(mw, "pdf_service") and mw.pdf_service is not None:
            mw.pdf_service.documentLoaded.connect(self._on_document_loaded)

        # *Trace from PDF* toolbar button / menu item
        act = getattr(mw, "trace_pdf_action", None)
        if act is not None:
            act.triggered.connect(self._on_trace_from_pdf)

        # NEW: Vectorize current PDF page
        act = getattr(mw, "vectorize_pdf_action", None)
        if act is not None:
            act.triggered.connect(self.on_vectorize_page)

        self.logger.debug("PDFEventHandler signals bound.")

    # ------------------------------------------------------------------
    # Public slots – delegating to legacy MainWindow implementations for now
    # ------------------------------------------------------------------
    def on_load_pdf_background(self) -> None:  # noqa: D401
        self.logger.debug("on_load_pdf_background slot entered.")
        filename, _ = QFileDialog.getOpenFileName(
            self._mw,
            "Load PDF Background",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )

        if filename:
            self.logger.info(f"User selected PDF for background: {filename}")
            self._mw.statusBar().showMessage(
                f"Loading PDF background '{Path(filename).name}'...", 0
            )
            success = False
            try:
                success = self._mw.visualization_panel.load_pdf_background(
                    filename, dpi=self._mw.pdf_dpi_setting
                )
                if success:
                    project = self._mw.project_controller.get_current_project()
                    if project:
                        project.pdf_background_path = filename
                        project.pdf_background_page = self._mw.visualization_panel.current_pdf_page
                        project.pdf_background_dpi = self._mw.pdf_dpi_setting
                        project.clear_traced_polylines()
                        self._mw.visualization_panel.clear_polylines_from_scene()

                    page_count = (
                        self._mw.visualization_panel.pdf_renderer.get_page_count()
                        if self._mw.visualization_panel.pdf_renderer
                        else 0
                    )
                    self._mw.statusBar().showMessage(
                        f"Loaded PDF background '{Path(filename).name}' ({page_count} pages).", 5000
                    )
                    self.logger.info(
                        f"Successfully loaded PDF background '{Path(filename).name}' with {page_count} pages."
                    )
                    self._mw.ui_state.update_ui_for_project(project)
                else:
                    raise PDFRendererError("Loading or rendering PDF background failed.")

            except (FileNotFoundError, PDFRendererError, Exception) as e:
                self.logger.exception(f"Failed to load PDF background: {e}")
                QMessageBox.critical(
                    self._mw, "PDF Load Error", f"Failed to load PDF background:\n{e}"
                )
                self._mw.statusBar().showMessage("Failed to load PDF background.", 5000)
                project = self._mw.project_controller.get_current_project()
                if project and project.pdf_background_path == filename:
                    project.pdf_background_path = None
                    project.pdf_background_page = 0
                    project.pdf_background_dpi = 0
            finally:
                self._mw.ui_state.update_pdf_controls()
                self._mw.ui_state.update_view_actions_state()
        else:
            self.logger.info("Load PDF background cancelled by user.")
            self._mw.statusBar().showMessage("Load cancelled.", 3000)

    def on_clear_pdf_background(self) -> None:  # noqa: D401
        self.logger.debug("Clearing PDF background via MainWindow action.")
        self._mw.visualization_panel.clear_pdf_background()
        self._mw._clear_cutfill_state()
        self._mw.ui_state.update_pdf_controls()

    def on_next_pdf_page(self) -> None:  # noqa: D401
        if self._mw.visualization_panel.pdf_renderer:
            current = self._mw.visualization_panel.current_pdf_page
            total = self._mw.visualization_panel.pdf_renderer.get_page_count()
            if current < total:
                self._mw.visualization_panel.set_pdf_page(current + 1)
                project = self._mw.project_controller.get_current_project()
                if project:
                    project.pdf_background_page = current + 1
                self._mw.ui_state.update_pdf_controls()
                self._mw.statusBar().showMessage(f"Showing PDF page {current + 1}/{total}", 3000)

    def on_prev_pdf_page(self) -> None:  # noqa: D401
        if self._mw.visualization_panel.pdf_renderer:
            current = self._mw.visualization_panel.current_pdf_page
            total = self._mw.visualization_panel.pdf_renderer.get_page_count()
            if current > 1:
                self._mw.visualization_panel.set_pdf_page(current - 1)
                project = self._mw.project_controller.get_current_project()
                if project:
                    project.pdf_background_page = current - 1
                self._mw.ui_state.update_pdf_controls()
                self._mw.statusBar().showMessage(f"Showing PDF page {current - 1}/{total}", 3000)

    def on_set_pdf_page_from_spinbox(self, page_number: int) -> None:  # noqa: D401
        if self._mw.pdf_page_spinbox.isEnabled() and page_number > 0:
            self.logger.debug(f"Setting PDF page from spinbox to: {page_number}")
            self._mw.visualization_panel.set_pdf_page(page_number)
            project = self._mw.project_controller.get_current_project()
            if project:
                project.pdf_background_page = page_number
            self._mw.ui_state.update_pdf_controls()
            total = (
                self._mw.visualization_panel.pdf_renderer.get_page_count()
                if self._mw.visualization_panel.pdf_renderer
                else 0
            )
            self._mw.statusBar().showMessage(f"Showing PDF page {page_number}/{total}", 3000)

    # ------------------------------------------------------------------
    # Private slots mirrored from MainWindow (kept private here too)
    # ------------------------------------------------------------------
    def _on_pdf_page_selected(self, page_index: int) -> None:  # noqa: D401
        self.logger.info(f"PDFEventHandler received pageSelected signal for index: {page_index}")
        page_number = page_index + 1
        self._mw.visualization_panel.set_pdf_page(page_number)

    def _on_document_loaded(self, page_count: int) -> None:  # noqa: D401
        self.logger.debug(f"Document loaded with {page_count} pages, updating scale action.")
        self._mw.ui_state.update_scale_action_enabled(True)

    def _on_trace_from_pdf(self) -> None:  # noqa: D401
        self.logger.info("Trace from PDF action triggered.")
        project = self._mw.project_controller.get_project()
        if not project:
            QMessageBox.warning(self._mw, "No Project", "Please open or create a project first.")
            return

        file_path_tuple = QFileDialog.getOpenFileName(
            self._mw,
            "Select PDF for Tracing",
            self._mw.project_controller.get_last_directory(),
            "PDF Files (*.pdf)",
        )
        file_path_str = file_path_tuple[0]
        if not file_path_str:
            self.logger.info("PDF selection cancelled.")
            return

        file_path = Path(file_path_str)
        self._mw.project_controller.set_last_directory(str(file_path.parent))

        try:
            self._mw.pdf_service.load_pdf(str(file_path))
            if not self._mw.pdf_service.current_document:
                raise PDFRendererError("Failed to load document object after loading path.")
            self.logger.info(f"PDF loaded via PdfService: {file_path}")
        except PDFRendererError as e:
            self.logger.error(f"Error loading PDF for tracing: {e}")
            QMessageBox.critical(self._mw, "PDF Load Error", f"Could not load PDF: {e}")
            return
        except Exception as e:
            self.logger.exception(f"Unexpected error loading PDF '{file_path}': {e}")
            QMessageBox.critical(
                self._mw,
                "PDF Load Error",
                f"An unexpected error occurred while loading the PDF: {e}",
            )
            return

        self._mw.visualization_panel.load_pdf_background(str(file_path))

        dialog = PdfPageSelectorDialog(self._mw.pdf_service.current_document, self._mw)
        if dialog.exec() == QDialog.Accepted:
            selected_indices = dialog.get_selected_pages()
            if not selected_indices:
                self.logger.info("No pages selected for tracing.")
                self._mw.statusBar().showMessage("No pages selected for tracing.", 3000)
                return

            self.logger.info(
                f"Selected PDF pages for tracing (0-based indices): {selected_indices}"
            )
            added_layers_count = 0
            project = self._mw.project_controller.get_project()
            if not project:
                self.logger.error("Project became unavailable after PDF selection.")
                QMessageBox.critical(
                    self._mw, "Error", "Project not available. Cannot create layers."
                )
                return

            for index in selected_indices:
                try:
                    page_label = self._mw.pdf_service.current_document.page_label(index)
                    base_layer_name = f"PDF Trace - {file_path.name} - Page {page_label}"
                    unique_layer_name = project.get_unique_layer_name(base_layer_name)

                    if unique_layer_name not in project.traced_polylines:
                        project.traced_polylines[unique_layer_name] = []
                    else:
                        self.logger.warning(
                            f"Layer '{unique_layer_name}' already exists. Adding PDF source info."
                        )

                    project.add_pdf_trace_source(unique_layer_name, str(file_path), index)
                    added_layers_count += 1
                except Exception as e:
                    self.logger.error(
                        f"Error processing page index {index} for tracing: {e}", exc_info=True
                    )
                    QMessageBox.warning(
                        self._mw,
                        "Layer Creation Error",
                        f"Could not create tracing layer for page {index + 1}.\nError: {e}",
                    )

            if added_layers_count > 0:
                self._mw._update_layer_tree()
                self._mw.project_controller.set_project_modified(True)
                self._mw.statusBar().showMessage(
                    f"Added {added_layers_count} PDF trace layer(s).", 5000
                )
                self.logger.info(f"Successfully added {added_layers_count} PDF trace sources.")
                self._mw.trace_pdf_action.setEnabled(True)

                if selected_indices:
                    first_page_number = selected_indices[0] + 1
                    self.logger.info(
                        f"Automatically displaying first selected PDF page: {first_page_number}"
                    )
                    self._mw.visualization_panel.set_pdf_page(first_page_number)
            else:
                self.logger.warning("No trace layers were added despite page selection.")
                if selected_indices:
                    QMessageBox.warning(
                        self._mw,
                        "No Layers Added",
                        "Could not add tracing layers for the selected pages. Check logs for details.",
                    )
        else:
            self.logger.info("PDF page selection cancelled.")

    # ------------------------------------------------------------------
    # Vectorize Page -----------------------------------------------------
    # ------------------------------------------------------------------
    def on_vectorize_page(self) -> None:
        """Action slot to vectorize the currently displayed PDF page."""
        mw = self._mw
        if not mw.visualization_panel or not mw.visualization_panel.pdf_renderer:
            QMessageBox.warning(mw, "Vectorize Page", "No PDF page loaded.")
            return

        page_no = mw.visualization_panel.current_pdf_page - 1  # renderer is 0-based

        pdf_path = Path(mw.project_controller.get_current_project().pdf_background_path)

        from ...ui.dialogs.import_vector import ImportVectorDialog

        dlg = ImportVectorDialog(mw)

        # Run vectorization with progress feedback & guard
        try:
            success = dlg.run_vectorization(str(pdf_path), page_no, dpi=mw.visualization_panel.pdf_renderer.dpi)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.error("Vectorization failed: %s", exc, exc_info=True)
            QMessageBox.critical(mw, "Vectorize Page", f"Vectorization failed:\n{exc}")
            return

        if not success:
            # User cancelled from bail-out prompt.
            mw.statusBar().showMessage("Vectorization cancelled by user.", 3000)
            return

        dlg.vectorized_polylines_ready.connect(self._on_polylines_ready)  # type: ignore[arg-type]
        dlg.exec()

    # ----------------------------------------------
    def _on_polylines_ready(self, polylines, mapping):  # noqa: D401
        """Convert polylines to scene items and push undo command."""
        mw = self._mw
        scene = mw.visualization_panel.scene_2d

        # Build dict layer -> list of point tuples
        grouped: Dict[str, List[Dict[str, Union[List[Tuple[float, float]], Optional[float]]]]] = (
            defaultdict(list)
        )

        for pl in polylines:
            key = (pl.stroke_rgb, tuple(pl.dash or ()))
            layer = mapping.get(key, "Imported")
            points = [(float(x), float(y)) for x, y in pl.vertices]
            grouped[layer].append({"points": points, "elevation": None})

        # Use existing loader – wraps items & handles selection
        scene.load_polylines_with_layers(grouped)  # type: ignore[arg-type]

        # Push one undo command for the whole import if undo stack exists
        if hasattr(mw, "undoStack"):
            from PySide6.QtGui import QUndoCommand

            class _ImportCmd(QUndoCommand):
                def __init__(self, scene, data):
                    super().__init__("Import Vector Lines")
                    self.scene = scene
                    self.data = data

                def redo(self):
                    self.scene.load_polylines_with_layers(self.data)

                def undo(self):
                    self.scene.clear_finalized_polylines()

            mw.undoStack.push(_ImportCmd(scene, grouped))
