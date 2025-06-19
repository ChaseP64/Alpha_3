from __future__ import annotations
from collections import deque
from typing import Set, TYPE_CHECKING

from PySide6.QtCore import QTimer, QObject, Signal

if TYPE_CHECKING:
    from .main_window import MainWindow


class SurfaceRebuildManager(QObject):
    """Queues layer-ids for surface rebuild, debounces with a single QTimer."""

    rebuild_started = Signal()
    rebuild_finished = Signal(set)          # emits set[str] rebuilt_layers

    def __init__(self, mw: "MainWindow", debounce_ms: int = 250):
        super().__init__(mw)
        self.mw = mw
        self._queue: "deque[str]" = deque()
        self._timer = QTimer(self)
        self._timer.setInterval(debounce_ms)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._process_queue)

    # ---------- public API ----------
    def queue_layer(self, layer_id: str) -> None:
        if layer_id not in self._queue:
            self._queue.append(layer_id)
            self._timer.start()             # restart debounce

    def rebuild_now(self) -> None:
        """Force immediate rebuild of everything currently queued."""
        self._timer.stop()
        self._process_queue()

    # ---------- internal ----------
    def _process_queue(self) -> None:
        if not self._queue:
            return
        layers_to_rebuild: Set[str] = set(self._queue)
        self._queue.clear()

        self.rebuild_started.emit()
        # Delegate to existing core service:
        if hasattr(self.mw.project_controller, "rebuild_surfaces_for_layers"):
            self.mw.project_controller.rebuild_surfaces_for_layers(layers_to_rebuild)
        else:
            # Fallback for older ProjectController implementation
            self.mw.project_controller.rebuild_surfaces()
            
        self.rebuild_finished.emit(layers_to_rebuild) 