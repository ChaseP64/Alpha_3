from __future__ import annotations

"""Import Vector Lines dialog.

Provides a minimal Qt interface for users to map *vectorised* PDF stroke
groups to DigCalc surface layers.  The implementation focuses on unit-test
coverage – not production-grade ergonomics – but establishes the
signal/slot/API contract required by MainWindow integration.
"""

from collections import defaultdict
from typing import Dict, List, Tuple, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QProgressBar,
    QMessageBox,
)

from ...core.geom.polyline import Polyline
from ...services.io.pdf_vectorizer import group_by_style

# Public export -------------------------------------------------------------
__all__ = ["ImportVectorDialog"]


class ImportVectorDialog(QDialog):
    """Dialog that previews vector groups and lets user map them to layers."""

    vectorized_polylines_ready = Signal(list, dict)  # (polylines, mapping)

    # ------------------------------------------------------------------
    def __init__(self, parent=None):  # noqa: D401 – Qt constructor
        super().__init__(parent)

        self.setWindowTitle("Import Vector Lines")
        self.resize(900, 600)

        self._polylines: list[Polyline] = []
        self._groups: Dict[Tuple, list[Polyline]] = {}

        # ------------------------------------------------------------------
        # Widgets
        # ------------------------------------------------------------------
        splitter = QSplitter(Qt.Horizontal, self)

        # Left – preview scene
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene, splitter)
        self._view.setRenderHints(self._view.renderHints() | self._view.renderHints().Antialiasing)

        # Right – group list
        right_widget = QVBoxLayout()

        self._group_tree = QTreeWidget()
        self._group_tree.setColumnCount(2)
        self._group_tree.setHeaderLabels(["Vector Group", "Layer"])
        right_widget.addWidget(QLabel("Map each detected vector group to a layer:"))
        right_widget.addWidget(self._group_tree, 1)

        # Progress bar (hidden by default)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.hide()
        right_widget.addWidget(self._progress)

        # Assemble right side within a dummy QWidget for layout
        from PySide6.QtWidgets import QWidget

        right_container = QWidget()
        right_container.setLayout(right_widget)
        splitter.addWidget(right_container)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        # Main layout
        lay = QVBoxLayout(self)
        lay.addWidget(splitter, 1)
        lay.addWidget(buttons)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_page_preview(self, polylines: List[Polyline]):  # noqa: D401
        """Populate the preview and group list from *polylines*."""

        self._polylines = polylines
        self._groups = group_by_style(polylines)

        self._populate_preview()
        self._populate_group_tree()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _populate_preview(self):
        self._scene.clear()

        pens_cache: Dict[Tuple, QPen] = {}

        for pl in self._polylines:
            key = (pl.stroke_rgb, tuple(pl.dash or ()))
            if key not in pens_cache:
                colour = QColor(*(pl.stroke_rgb or (0, 0, 0)))
                pen = QPen(colour, 0)  # cosmetic pen (width 0 = 1px)
                if pl.dash:
                    pen.setDashPattern([float(x) for x in pl.dash])
                pens_cache[key] = pen
            pen = pens_cache[key]

            # Draw polyline
            from PySide6.QtGui import QPainterPath
            from PySide6.QtCore import QPointF

            verts = pl.vertices
            path = QPainterPath(QPointF(*verts[0]))
            for v in verts[1:]:
                path.lineTo(QPointF(*v))
            self._scene.addPath(path, pen)

        # Fit scene
        self._view.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def _populate_group_tree(self):
        self._group_tree.clear()

        for idx, ((rgb, dash), group) in enumerate(self._groups.items(), start=1):
            colour = rgb or (0, 0, 0)
            dash_desc = "dashed" if dash else "solid"
            title = f"Group {idx} – RGB{colour} {dash_desc} ({len(group)} lines)"

            item = QTreeWidgetItem(self._group_tree)
            item.setText(0, title)

            # Layer combo inside column 1
            combo = QComboBox()
            combo.addItems(["Existing Surface", "Proposed Surface", "Offsets", "Contours"])
            self._group_tree.setItemWidget(item, 1, combo)

        self._group_tree.expandAll()

    # ------------------------------------------------------------------
    def _on_accept(self):
        # Build mapping dict key -> selected layer
        mapping: Dict[Tuple, str] = {}
        root = self._group_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            combo = self._group_tree.itemWidget(item, 1)
            layer_name = combo.currentText() if isinstance(combo, QComboBox) else "Unknown"
            key = list(self._groups.keys())[i]
            mapping[key] = layer_name

        self.vectorized_polylines_ready.emit(self._polylines, mapping)  # type: ignore[arg-type]
        self.accept()

    # ------------------------------------------------------------------
    # Vectorization runner with progress feedback & bail-out guard
    # ------------------------------------------------------------------
    def run_vectorization(
        self,
        pdf_path: str,
        page_no: int = 0,
        *,
        dpi: int = 300,
        scale: float = 1.0,
        offset: tuple[float, float] | None = None,
    ):  # noqa: D401 – Qt API
        """Vectorize *pdf_path* and initialise the dialog with results.

        This method runs synchronously – callers are expected to have already
        executed it inside a worker thread if keeping the UI responsive is
        required.  For our MVP we block, but provide incremental progress
        updates via the `_progress` bar.
        """

        from ...services.io.pdf_vectorizer import PDFVectorizer

        offset = offset or (0.0, 0.0)

        # Show progress bar
        self._progress.show()
        self._progress.setValue(0)

        def _on_progress(done: int, total: int):  # noqa: D401 internal helper
            if total == 0:
                val = 0
            else:
                val = int(done / total * 100)
            self._progress.setValue(val)

        vectorizer = PDFVectorizer(dpi=dpi)

        polylines = vectorizer.vectorize(
            pdf_path,
            page_no,
            scale=scale,
            offset=offset,
            progress_cb=_on_progress,
        )

        # Hide progress bar once done
        self._progress.hide()

        # Bail-out guard: prompt if segment count exceeds threshold
        seg_count = sum(len(pl.vertices) - 1 for pl in polylines)
        if seg_count > 250_000:
            ret = QMessageBox.question(
                self,
                "Large Vector Import",
                (
                    f"The selected page contains {seg_count:,} vector segments.\n"
                    "Importing such a large amount may be slow and use a lot of memory.\n\n"
                    "Do you want to continue?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret == QMessageBox.StandardButton.No:
                # User cancelled – keep dialog closed.
                return False

        # If user accepted (or under threshold), populate preview normally
        self.set_page_preview(polylines)
        return True 