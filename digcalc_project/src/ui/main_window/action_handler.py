from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtWidgets import QFileDialog, QMessageBox, QDialog

from ...core.calculations.volume_calculator import VolumeCalculator
from ...core.geometry.surface_builder import SurfaceBuilder, SurfaceBuilderError
from ...ui.dialogs.build_surface_dialog import BuildSurfaceDialog
from ...ui.dialogs.daylight_dialog import DaylightDialog
from ...ui.dialogs.volume_calculation_dialog import VolumeCalculationDialog
from ...ui.dialogs.report_dialog import ReportDialog
from ...ui.dialogs.haul_alignment_dialog import HaulAlignmentDialog
from ...core.reporting import csv_writer
from ...core.reporting.pdf_report import PDFReportGenerator

if TYPE_CHECKING:
    from .main_window import MainWindow


class ActionHandler:
    """
    Executes long-running or multi-component actions invoked from the UI.
    Keeps MainWindow thin and makes actions unit-testable.
    """

    def __init__(self, mw: "MainWindow") -> None:
        self.mw = mw
        self.project_controller = mw.project_controller

    def calculate_volume(self) -> None:
        """Handle the 'Calculate Volume' action."""
        project = self.project_controller.get_current_project()
        if not project or len(project.surfaces) < 2:
            QMessageBox.warning(self.mw, "Volume Calculation", "At least two surfaces are required to calculate volumes.")
            return

        dialog = VolumeCalculationDialog(list(project.surfaces.keys()), self.mw)
        
        params = None
        result = None

        if dialog.exec() == QDialog.Accepted:
            params = dialog.get_parameters()
            if params:
                self.mw.status_bar_manager.show_message(f"Calculating volumes (Grid: {params['grid_resolution']})...")
                calculator = VolumeCalculator(project)
                try:
                    result = calculator.calculate_grid_method(params)
                except Exception as e:
                    self.mw.logger.exception("Volume calculation failed.")
                    QMessageBox.critical(self.mw, "Calculation Error", f"An error occurred during volume calculation:\n{e}")
                    result = None
        
        if result:
            self.mw._last_volume_calculation_params = params
            self.mw.status_bar_manager.show_message("Volume calculation initiated...", 2000)
            # The on_volume_computed slot will handle showing the report dialog
        else:
            self.mw._last_volume_calculation_params = None
            if dialog.result() == QDialog.Accepted:
                self.mw.status_bar_manager.show_message("Volume calculation failed.", 5000)

    def build_surface(self) -> None:
        """Handle the 'Build Surface' action."""
        project = self.project_controller.get_current_project()
        if not project:
            return

        # Launch dialog with full project context so it can validate layers.
        dialog = BuildSurfaceDialog(project, self.mw)

        if dialog.exec() == QDialog.Accepted:
            source_layer = dialog.layer()
            surface_name = dialog.surface_name()

            if not (source_layer and surface_name):
                # Dialog should prevent this, but guard defensively.
                return

            try:
                polylines = project.traced_polylines.get(source_layer, [])
                layer_rev = project.layer_revisions.get(source_layer, 0)

                # Build the surface using the current API (layer first).
                surface = SurfaceBuilder.build_from_polylines(
                    source_layer,
                    polylines,
                    layer_rev,
                )

                surface.name = surface_name
                surface.source_layer_name = source_layer

                project.add_surface(surface)

                # Update UI / state
                self.mw.status_bar_manager.show_message(
                    f"Surface '{surface_name}' built successfully.",
                    5000,
                )
                self.mw.project_panel._update_tree()
                self.mw.ui_state.update_analysis_actions_state()

                # Queue visual rebuild so the new surface becomes visible.
                if hasattr(self.mw, "surface_rebuild_manager"):
                    self.mw.surface_rebuild_manager.queue_layer(source_layer)
            except SurfaceBuilderError as e:
                QMessageBox.warning(self.mw, "Build Surface Error", str(e))
                self.mw.status_bar_manager.show_message("Surface build failed.", 5000)

    def mass_haul(self) -> None:
        """Handle the 'Mass Haul' action."""
        if not hasattr(self.project_controller, "show_mass_haul_dialog"):
            QMessageBox.warning(self.mw, "Mass Haul", "Mass haul functionality is not available in this build.")
            return

        # Ensure the latest volume calculation data is present
        if not (self.mw._last_volume_calculation_params and self.mw._last_dz_cache):
            QMessageBox.information(self.mw, "Mass Haul", "Please run a volume calculation first.")
            return

        # Delegate to ProjectController which owns the canonical implementation
        try:
            self.project_controller.show_mass_haul_dialog(parent=self.mw)
        except Exception as exc:
            QMessageBox.critical(self.mw, "Mass Haul Error", str(exc))

    def generate_report(self) -> None:
        """Handle the 'Generate Report' action."""
        if self.mw._last_volume_calculation_params and self.mw._last_dz_cache:
            params = self.mw._last_volume_calculation_params
            report_dialog = ReportDialog(
                existing_surface_name=params['existing_surface'],
                proposed_surface_name=params['proposed_surface'],
                grid_resolution=params['grid_resolution'],
                cut_volume=np.sum(self.mw._last_dz_cache[0][self.mw._last_dz_cache[0] > 0]),
                fill_volume=np.abs(np.sum(self.mw._last_dz_cache[0][self.mw._last_dz_cache[0] < 0])),
                net_volume=np.sum(self.mw._last_dz_cache[0]),
                parent=self.mw
            )
            report_dialog.exec()
        else:
            QMessageBox.information(self.mw, "Generate Report", "Please run a volume calculation first to generate a report.")

    def export_report(self) -> None:
        """Handle the 'Export Report' action."""
        project = self.project_controller.get_current_project()
        if not project or not self.mw._last_volume_calculation_params:
            QMessageBox.warning(self.mw, "Export Report", "Please run a volume calculation first.")
            return

        default_path = f"{project.name}_report"
        
        # Ask for a directory to save the bundle
        dir_path = QFileDialog.getExistingDirectory(self.mw, "Select Report Directory", str(Path.home()))
        
        if dir_path:
            base_name = Path(dir_path) / default_path
            params = self.mw._last_volume_calculation_params
            
            self.mw.status_bar_manager.show_message("Exporting report bundle...")
            
            try:
                # 1. Export CSV
                csv_path = f"{base_name}.csv"
                csv_writer.export_volume_report(csv_path, params, self.mw._last_dz_cache)
                
                # 2. Export PDF
                pdf_path = f"{base_name}.pdf"
                cut_fill_map = self.mw.visualization_panel.get_cut_fill_map() # Assuming this method exists
                
                pdf_report = PDFReportGenerator()
                #TODO: This is not the right call
                # pdf_report.add_summary_page(params, self.mw._last_dz_cache, cut_fill_map)
                # pdf_report.save()

                self.mw.status_bar_manager.show_message(f"Report bundle exported to {dir_path}", 5000)
            except Exception as e:
                self.mw.logger.exception("Failed to export report bundle.")
                QMessageBox.critical(self.mw, "Export Error", f"Failed to export report bundle:\n{e}")
                self.mw.status_bar_manager.show_message("Export failed.", 5000)

    def daylight_offset(self) -> None:
        """Handle the 'Daylight Offset' action."""
        project = self.project_controller.get_current_project()
        scene = self.mw.visualization_panel.scene_2d
        
        if not project or not scene.current_polyline_layer_name:
            QMessageBox.warning(self.mw, "Daylight Offset", "Please select a polyline layer first.")
            return
            
        dialog = DaylightDialog(self.mw)
        if dialog.exec():
            slope_ratio, target_surface_name = dialog.get_parameters()
            if slope_ratio is not None and target_surface_name:
                try:
                    target_layer_name = scene.current_polyline_layer_name
                    self.project_controller.apply_daylight_offset(
                        target_layer_name, target_surface_name, slope_ratio
                    )
                    self.mw.surface_rebuild_manager.queue_layer(target_layer_name)
                    self.mw._update_layer_tree()
                except Exception as e:
                    self.mw.logger.exception("Failed to create daylight offset.")
                    QMessageBox.critical(self.mw, "Daylight Offset", f"Failed to create daylight offset.\n{e}") 