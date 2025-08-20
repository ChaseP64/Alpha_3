from __future__ import annotations

"""Centralises the verbose Qt-signal wiring previously in ``MainWindow._connect_signals``."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class SignalBinder:  # noqa: D101
    def __init__(self, mw: "MainWindow") -> None:  # noqa: D401
        self.mw = mw
        self._bind()

    # ------------------------------------------------------------------
    def _bind(self) -> None:  # noqa: C901 – verbose but isolated
        mw = self.mw
        logger.debug("Binding MainWindow signals …")

        # Project controller shortcuts ---------------------------------
        mw.new_project_action.triggered.connect(mw.project_controller.on_new_project)
        mw.open_project_action.triggered.connect(mw.project_controller.on_open_project)
        mw.save_project_action.triggered.connect(mw.project_controller.on_save_project)
        mw.save_project_as_action.triggered.connect(
            lambda: mw.project_controller.on_save_project(save_as=True)
        )
        mw.exit_action.triggered.connect(mw.close)

        # Trace-PDF action
        pdf = getattr(mw, "pdf_handler", None)
        if pdf is not None:
            mw.trace_pdf_action.triggered.connect(pdf._on_trace_from_pdf)

        # Visualization feedback
        if hasattr(mw.visualization_panel, "surface_visualization_failed"):
            mw.visualization_panel.surface_visualization_failed.connect(mw._on_visualization_failed)

        # Tracing scene signals
        scene2d = getattr(mw.visualization_panel, "scene_2d", None)
        if scene2d is not None:
            scene2d.polyline_finalized.connect(mw.polyline_handler._on_polyline_drawn)
            scene2d.selectionChanged.connect(mw.polyline_handler._on_item_selected)
            if hasattr(scene2d, "pageRectChanged"):
                scene2d.pageRectChanged.connect(mw.view_mode_handler._fit_view_to_scene)
            if hasattr(scene2d, "padDrawn"):
                scene2d.padDrawn.connect(mw.polyline_handler._on_pad_drawn)
        else:
            logger.warning("scene_2d unavailable for signal hookup")

        # Layer-tree visibility toggles
        mw.layer_tree.itemChanged.connect(mw.layer_legend_controller._on_layer_visibility_changed)

        # Properties dock signals
        mw.prop_dock.polylineEdited.connect(mw.polyline_handler._apply_elevation_edit)
        mw.prop_dock.settingsChanged.connect(mw.project_controller.trigger_rebuild_if_needed)

        # View-mode actions
        mw.view_2d_action.triggered.connect(mw.view_mode_handler.on_view_2d)
        mw.view_3d_action.triggered.connect(mw.view_mode_handler.on_view_3d)

        # PDF actions
        pdf = getattr(mw, "pdf_handler", None)
        if pdf is not None:
            mw.load_pdf_background_action.triggered.connect(pdf.on_load_pdf_background)
            mw.clear_pdf_background_action.triggered.connect(pdf.on_clear_pdf_background)
            mw.prev_pdf_page_action.triggered.connect(pdf.on_prev_pdf_page)
            mw.next_pdf_page_action.triggered.connect(pdf.on_next_pdf_page)

        mw.toggle_trace_mode_action.toggled.connect(mw.scene_handler.on_toggle_tracing_mode)

        # Analysis actions
        ah = mw.action_handler
        if hasattr(ah, "calculate_volume"):
            mw.calculate_volume_action.triggered.connect(ah.calculate_volume)
        if hasattr(ah, "build_surface"):
            mw.build_surface_action.triggered.connect(ah.build_surface)
        if hasattr(ah, "generate_report"):
            mw.generate_report_action.triggered.connect(ah.generate_report)
        if hasattr(ah, "export_report"):
            mw.export_action.triggered.connect(ah.export_report)
        if hasattr(ah, "daylight_offset"):
            mw.daylight_action.triggered.connect(ah.daylight_offset)
        if hasattr(ah, "mass_haul"):
            mw.masshaul_action.triggered.connect(ah.mass_haul)
        if hasattr(ah, "smart_clean"):
            mw.smart_clean_action.triggered.connect(ah.smart_clean)
        if hasattr(ah, "bulk_assign_surfaces") and hasattr(mw, "bulk_assign_surface_action"):
            mw.bulk_assign_surface_action.triggered.connect(ah.bulk_assign_surfaces)
        if hasattr(mw, "templates_action") and hasattr(ah, "open_template_library"):
            mw.templates_action.triggered.connect(ah.open_template_library)

        mw.about_action.triggered.connect(mw.on_about)

        # Project-controller emitted signals
        pc = mw.project_controller
        pc.project_loaded.connect(mw._update_ui_for_project)
        pc.project_closed.connect(lambda: mw._update_ui_for_project(None))
        pc.project_modified.connect(mw._update_window_title)
        pc.surfaces_rebuilt.connect(mw._on_surfaces_rebuilt)

        # Import shortcuts
        mw.import_csv_action.triggered.connect(lambda: pc.on_import_file("csv"))
        mw.import_dxf_action.triggered.connect(lambda: pc.on_import_file("dxf"))
        mw.import_landxml_action.triggered.connect(lambda: pc.on_import_file("landxml"))

        # PDF controller
        if mw.pdf_controller is not None:
            pdf = getattr(mw, "pdf_handler", None)
            if pdf is not None:
                mw.pdf_controller.pageSelected.connect(pdf._on_pdf_page_selected)

        # Tracing-mode radio buttons update SettingsService
        mw.trace_point_action.triggered.connect(
            lambda _=False: mw.view_mode_handler._set_tracing_elev_mode("point")
        )
        mw.trace_interpolate_action.triggered.connect(
            lambda _=False: mw.view_mode_handler._set_tracing_elev_mode("interpolate")
        )
        mw.trace_line_action.triggered.connect(
            lambda _=False: mw.view_mode_handler._set_tracing_elev_mode("line")
        )

        logger.debug("Signal binding complete")
