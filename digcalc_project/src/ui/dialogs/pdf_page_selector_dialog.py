#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialog for selecting pages from a PDF document for tracing.

Placeholder implementation.
"""

import logging
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QWidget
)

# Placeholder for the actual PDF document object type (e.g., fitz.Document or QPdfDocument)
# from fitz import Document as FitzDocument # If using PyMuPDF
# from PySide6.QtPdf import QPdfDocument # If using QtPdf

logger = logging.getLogger(__name__)


class PdfPageSelectorDialog(QDialog):
    """A dialog to allow users to select pages from a loaded PDF."""

    # Replace 'object' with the actual PDF document type annotation
    def __init__(self, pdf_document: object, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Select PDF Pages for Tracing")
        self.pdf_document = pdf_document
        self._selected_indices: List[int] = []

        layout = QVBoxLayout(self)

        # --- Placeholder UI --- 
        # TODO: Replace with actual page selection UI (e.g., QListWidget with checkboxes)
        label = QLabel("PDF Page Selection UI Placeholder")
        layout.addWidget(label)
        # --- End Placeholder --- 

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        # Set a reasonable default size or make it dynamic
        self.resize(400, 300) 

    def _on_accept(self):
        """Called when OK is clicked. Populate _selected_indices."""
        # TODO: Implement logic to get selected page indices from the UI
        logger.warning("PdfPageSelectorDialog: _on_accept needs implementation!")
        # For now, let's assume pages 1 and 3 are selected (0-based index 0 and 2)
        self._selected_indices = [0, 2] 
        self.accept()

    def get_selected_pages(self) -> List[int]:
        """Returns a list of selected 0-based page indices."""
        return self._selected_indices 