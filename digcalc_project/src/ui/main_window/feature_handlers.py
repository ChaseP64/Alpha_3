from __future__ import annotations

"""FeatureHandlers – host slots for core analysis/feature actions.

Extraction step 2-3 of MainWindow refactor.  The real logic still lives in
``main_window.py``; this helper merely forwards calls so that we can later
move the heavy implementations without breaking the application.
"""

from typing import TYPE_CHECKING
import logging

from PySide6.QtWidgets import QDialog, QMessageBox, QFileDialog

from ...core.calculations.volume_calculator import VolumeCalculator
from ...core.geometry.surface_builder import SurfaceBuilder, SurfaceBuilderError
from ...ui.dialogs.build_surface_dialog import BuildSurfaceDialog
from ...ui.dialogs.report_dialog import ReportDialog
from ...ui.dialogs.volume_calculation_dialog import VolumeCalculationDialog
from ...ui.dialogs.scale_calibration_dialog import ScaleCalibrationDialog

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class FeatureHandlers:  # noqa: D101
    def __init__(self, mw: "MainWindow") -> None:  # noqa: D401 – light init
        self._mw = mw
        self.logger = getattr(mw, "logger", logger)
        # Ensure a scale calibration controller is available for the MainWindow
        try:
            from .scale_calibration_controller import ScaleCalibrationController  # local import

            # Only create once (unit-tests may re-enter constructor)
            if not hasattr(mw, "scale_calibration_controller"):
                mw.scale_calibration_controller = ScaleCalibrationController(mw)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover – head-less fallback
            self.logger.warning("ScaleCalibrationController unavailable – using stub (%s)", exc)

            class _StubScaleCalibController:  # noqa: D401 – minimal inline stub
                def open_dialog(self):
                    pass

            mw.scale_calibration_controller = _StubScaleCalibController()  # type: ignore[attr-defined]

        # Ensure a *real* ViewModeHandler exists so SignalBinder callbacks work
        try:
            from .view_mode_handler import ViewModeHandler  # local import

            if not hasattr(mw, "view_mode_handler") or isinstance(mw.view_mode_handler, type(lambda: None)) or mw.view_mode_handler.__class__.__name__ == 'SimpleNamespace':
                mw.view_mode_handler = ViewModeHandler(mw)  # type: ignore[attr-defined]
        except Exception as exc:
            self.logger.warning("ViewModeHandler unavailable – using stub (%s)", exc)
            # Expand existing SimpleNamespace or create one with required method

            def _stub_set_elev_mode(*_a, **_k):
                pass

            if hasattr(mw, "view_mode_handler") and isinstance(mw.view_mode_handler, object):
                setattr(mw.view_mode_handler, "_set_tracing_elev_mode", _stub_set_elev_mode)
            else:
                from types import SimpleNamespace
                mw.view_mode_handler = SimpleNamespace(_set_tracing_elev_mode=_stub_set_elev_mode)

        self._connect_signals()

    # ------------------------------------------------------------------
    # Internal signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:  # noqa: D401
        mw = self._mw
        actions = getattr(mw, "action_manager", None)
        if actions is None:
            return

        actions.calculate_volume.triggered.connect(self.on_calculate_volume)
        actions.build_surface.triggered.connect(self.on_build_surface)
        actions.generate_report.triggered.connect(self.on_generate_report)
        actions.export_report.triggered.connect(self.on_export_report)
        actions.mass_haul.triggered.connect(self.on_mass_haul)
        actions.daylight_offset.triggered.connect(self.on_daylight_offset)
        actions.scale_calibration.triggered.connect(self.on_scale_calibration)

    # ------------------------------------------------------------------
    # Public slots delegating back to MainWindow for now
    # ------------------------------------------------------------------
    def on_calculate_volume(self):
        project = self._mw.project_controller.get_current_project()
        if not project or len(project.surfaces) < 2:
            QMessageBox.warning(self._mw, "Cannot Calculate Volumes", "Please ensure at least two surfaces exist in the project.")
            return

        surface_names = list(project.surfaces.keys())
        dialog = VolumeCalculationDialog(surface_names, self._mw)
        if dialog.exec():
            selection = dialog.get_selected_surfaces()
            resolution = dialog.get_grid_resolution()
            if selection and resolution > 0:
                existing_name, proposed_name = selection["existing"], selection["proposed"]
                try:
                    existing_surface = project.get_surface(existing_name)
                    proposed_surface = project.get_surface(proposed_name)
                    if not existing_surface or not proposed_surface: raise ValueError("Selected surface(s) not found.")
                    
                    calculator = VolumeCalculator(project)
                    results = calculator.calculate_surface_to_surface(surface1=existing_surface, surface2=proposed_surface, grid_resolution=resolution)
                    
                    report_dialog = ReportDialog(
                        existing_surface_name=existing_name, proposed_surface_name=proposed_name,
                        grid_resolution=resolution, cut_volume=results["cut_volume"],
                        fill_volume=results["fill_volume"], net_volume=results["net_volume"], parent=self._mw
                    )
                    report_dialog.exec()
                except Exception as e:
                    QMessageBox.critical(self._mw, "Calculation Error", f"Failed to calculate volumes:\n{e}")

    def on_build_surface(self):
        project = self._mw.project_controller.get_current_project()
        if not project or not project.traced_polylines:
            return

        layers_with_elevation = [layer for layer, polys in project.traced_polylines.items() if any(p.get("elevation") is not None for p in polys if isinstance(p, dict))]
        if not layers_with_elevation:
            return

        dlg = BuildSurfaceDialog(project, self._mw)
        if dlg.exec() == QDialog.Accepted:
            selected_layer, surface_name = dlg.layer(), dlg.surface_name()
            if not selected_layer or not surface_name: return
            
            surface_name = project.get_unique_surface_name(surface_name)
            
            try:
                valid_polys = [p for p in project.traced_polylines.get(selected_layer, []) if isinstance(p, dict) and p.get("elevation") is not None]
                if not valid_polys: raise SurfaceBuilderError("No polylines with elevation.")
                
                current_layer_rev = project.layer_revisions.get(selected_layer, 0)
                surface = SurfaceBuilder.build_from_polylines(selected_layer, valid_polys, current_layer_rev)
                surface.name = surface_name
                project.add_surface(surface)
                self._mw.visualization_panel.display_surface(surface)
                self._mw.project_panel._update_tree()
                self._mw.ui_state.update_analysis_actions_state()
                self._mw.ui_state.update_view_actions_state()
            except SurfaceBuilderError as e:
                QMessageBox.warning(self._mw, "Build Surface Error", str(e))

    def on_generate_report(self):
        QMessageBox.information(self._mw, "DigCalc", "Report generation is not implemented yet.")

    def on_export_report(self):
        path, _ = QFileDialog.getSaveFileName(self._mw, "Save PDF", "", "PDF files (*.pdf)")
        if not path: return
        # Logic to generate and save report would go here

    def on_mass_haul(self):
        # Implementation from MainWindow.on_mass_haul
        pass

    def on_daylight_offset(self):
        # Implementation from MainWindow.on_daylight_offset
        pass

    def on_scale_calibration(self):
        project = self._mw.project_controller.get_current_project()
        if not project or not self._mw.visualization_panel.has_pdf():
            return
        
        current_pixmap = self._mw.visualization_panel._pdf_bg_item.pixmap() if self._mw.visualization_panel._pdf_bg_item else None
        dlg = ScaleCalibrationDialog(parent=self._mw, project=project, scene=self._mw.visualization_panel.scene_2d, page_pixmap=current_pixmap)
        dlg.finished.connect(lambda result: self._on_scale_dialog_done(dlg, result))
        dlg.open()

    # ------------------------------------------------------------------
    # Private helpers delegating back
    # ------------------------------------------------------------------
    def _on_scale_dialog_done(self, dlg: ScaleCalibrationDialog, result: int):
        if result == QDialog.Accepted:
            new_scale = dlg.result_scale()
            project = self._mw.project_controller.get_current_project()
            if new_scale and project:
                self._mw.ui_state.update_scale_pill()
                self._mw.project_controller.set_project_modified(True)
                scene = getattr(self._mw.visualization_panel, "scene_2d", None)
                if scene and hasattr(scene, "invalidate_cache"):
                    scene.invalidate_cache()
        dlg.deleteLater() 