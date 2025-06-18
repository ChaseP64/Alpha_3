from __future__ import annotations

"""FeatureHandlers – host slots for core analysis/feature actions.

Extraction step 2-3 of MainWindow refactor.  The real logic still lives in
``main_window.py``; this helper merely forwards calls so that we can later
move the heavy implementations without breaking the application.
"""

from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class FeatureHandlers:  # noqa: D101
    def __init__(self, mw: "MainWindow") -> None:  # noqa: D401 – light init
        self._mw = mw
        self.logger = getattr(mw, "logger", logger)
        self._connect_signals()

    # ------------------------------------------------------------------
    # Internal signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:  # noqa: D401
        mw = self._mw

        # Connect only if attributes exist to avoid brittleness during tests
        def _safe(action_name: str, slot):
            act = getattr(mw, action_name, None)
            if act is not None:
                try:
                    act.triggered.connect(slot)
                except Exception:  # pragma: no cover – defensive
                    self.logger.warning("Failed to connect action '%s'", action_name, exc_info=True)

        _safe("calculate_volume_action", self.on_calculate_volume)
        _safe("build_surface_action", self.on_build_surface)
        _safe("generate_report_action", self.on_generate_report)
        _safe("export_action", self.on_export_report)
        _safe("masshaul_action", self.on_mass_haul)
        _safe("daylight_action", self.on_daylight_offset)
        _safe("scale_calib_act", self.on_scale_calibration)

    # ------------------------------------------------------------------
    # Public slots delegating back to MainWindow for now
    # ------------------------------------------------------------------
    def on_calculate_volume(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_calculate_volume"):
            self._mw.on_calculate_volume()

    def on_build_surface(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_build_surface"):
            self._mw.on_build_surface()

    def on_generate_report(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_generate_report"):
            self._mw.on_generate_report()

    def on_export_report(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_export_report"):
            self._mw.on_export_report()

    def on_mass_haul(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_mass_haul"):
            self._mw.on_mass_haul()

    def on_daylight_offset(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_daylight_offset"):
            self._mw.on_daylight_offset()

    def on_scale_calibration(self) -> None:  # noqa: D401
        if hasattr(self._mw, "on_scale_calibration"):
            self._mw.on_scale_calibration()

    # ------------------------------------------------------------------
    # Private helpers delegating back
    # ------------------------------------------------------------------
    def _on_scale_dialog_done(self, dlg, result):  # noqa: D401
        if hasattr(self._mw, "_on_scale_dialog_done"):
            self._mw._on_scale_dialog_done(dlg, result) 