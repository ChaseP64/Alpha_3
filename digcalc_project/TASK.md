# DigCalc Project Tasks

## Current Sprint Tasks

### 3-D Viewer Overhaul
- [x] Task 0: Add MeshActor dataclass & registry stub – 2025-05-30
- [x] Task 1.1: Add pv_plotter_singleton helper – 2025-05-30
- [x] Task 1.2: Refactor PvDock to use singleton plotter – 2025-05-30
- [x] Task 2: Add explicit closeEvent + aboutToQuit cleanup – 2025-05-30
- [x] Task 3: Mesh validation gate before add_mesh – 2025-05-30
- [x] Task 4: Plot first surface with camera defaults (from PLAN.md) – 2025-05-30
- [x] Task 4.1: Add surface_to_polydata utility and tests – 2025-05-30
- [x] Task 4.2: Implement PvDock.load_project for initial surface display – 2025-05-30
- [x] Task 4.3: GUI Test for first surface visibility and camera – 2025-05-30

### Data Import Module
- [x] Create base FileParser interface
- [x] Implement CSV import functionality
- [x] Create LandXML parser
- [ ] Create DXF parser (basic)
- [ ] Create PDF parser (stub)
- [x] Update main window to use parsers
- [x] Create unit tests for parsers

### Surface Modeling & TIN Generation
- [x] Create Surface model with points and triangles
- [ ] Implement TIN generation
- [ ] Create contour generation functionality
- [ ] Implement volumetric analysis

### Volume Calculation Module
- [ ] Implement cut/fill calculation
- [ ] Create volume reporting

### User Interface
- [x] Create basic main window
- [x] Implement project panel
- [x] Create visualization panel
- [ ] Add reporting functionality

### GUI Testing
- [x] Task 12: GUI Tests for Two-Tab Scale Dialog (World-units, Ratio, Invalid input) - 2025-05-23

### PDF Vectorizer MVP (Phase 1 – 2025-07-01)
- [ ] Step 0: Pre-flight (branch, deps, fixtures)
- [ ] Step 1: Module Scaffold
- [ ] Step 2: Extraction & Flattening
- [ ] Step 3: Dash detection & Join helpers
- [ ] Step 4: Vectorizer API + Serialization
- [ ] Step 5: Import Vector Dialog UI
- [ ] Step 6: Integration with TracingScene
- [ ] Step 7: Performance guard & batching
- [ ] Step 8: DevOps & Feature flag
- [ ] Step 9: Docs & Samples
- [ ] Step 10: Fuzz + PR merge

## Discovered During Work
- [x] Recreate Python files as UTF-8 text files to remove null bytes and invalid characters
- [x] Reset `__init__.py` files to clean UTF-8 files
- [x] Fix import paths to be consistent (use 'src.' prefix for absolute imports) - 2025-06-28
- [x] Add SURFACE_TYPE_TIN constant to Surface class
- [ ] Update Surface model implementation to match test assumptions
- [ ] Fix issues with LandXML parser tests
- [x] 2025-05-10 Disable tracing at startup to prevent accidental tracing before user enables mode
- [x] 2025-05-16 Fix pytest failures related to ScaleCalibrationDialog, ProjectScale, and VisualizationPanel mocks (TypeError, ValidationError, C++ object deletion)
- [x] 2025-06-05 Fix UnboundLocalError in VisualizationPanel.display_surface (plotter variable)
- [x] 2025-06-05 Update surface_to_polydata to support legacy vertex/triangle lists and pass all unit tests

## Next Steps
1. **Fix Remaining Test Issues**:
   - Focus on resolving the remaining test failures, particularly for the LandXML parser and PDF parser
   - Update the implementations to match the test expectations

2. **Complete Unit Tests**:
   - Ensure all files in the importers module have proper unit tests
   - Add tests for the Surface model

3. **Connect Data Import with Surface Modeling**:
   - Ensure imported data can be properly converted to Surface models
   - Implement TIN generation for point cloud data

4. **Implement Volume Calculation**:
   - Create core functionality for cut/fill analysis
   - Add visualization of cut/fill areas

5. **Enhance User Interface**:
   - Add more interactive controls for surface visualization
   - Implement reporting functionality

## Completed Tasks
- Set up the foundation for the DigCalc application
- Created the main window structure with panels
- Implemented basic data import functionality with file parsers
- Developed a clean Surface model for TIN representation
- Resolved encoding issues in Python files
- Fixed unit tests for FileParser class
- 2025-05-12 Fixed "Pick Points" dead-click issue in Scale Calibration by auto-switching to 2-D view and visibility fallback

# Added Phase 3 helper tools
- [x] Add daylight_offset_tool geometry helpers (offset_polygon, project_to_slope)
- [ ] Implement TIN generation

## MainWindow Method Inventory (Phase 1 – 2025-06-23)
The table below groups *remaining* methods in `MainWindow` by primary concern. This inventory is used by the allow-list test added in Phase 1 and serves as the refactor checklist for upcoming phases.

| Concern | Methods |
|---------|---------|
| Polyline Interaction | `_on_polyline_drawn`, `_on_pad_drawn`, `_apply_elevation_edit`, `_delete_selected_polyline`, `_on_item_selected` |
| View & Input | `on_view_2d`, `on_view_3d`, `_fit_view_to_scene`, `_toggle_other_layers_visibility`, `_set_tracing_elev_mode`, `_create_shortcuts`, `keyPressEvent` |
| Scale Calibration | `on_scale_calibration`, `_on_scale_dialog_done` |
| Layer Legend / Visibility | `_on_legend_layers_count`, `_on_layer_visibility_toggled`, `_trigger_layer_visibility_update`, `_on_layer_visibility_changed`, `_update_layer_tree` |
| PDF Navigation & Controls | `on_load_pdf_background`, `on_clear_pdf_background`, `on_next_pdf_page`, `on_prev_pdf_page`, `on_set_pdf_page_from_spinbox`, `_on_pdf_page_selected`, `_on_document_loaded` |
| Surface Rebuild & Update | `_queue_surface_rebuilds_for_layer`, `_process_rebuild_queue`, `_rebuild_surface_now`, `_on_surfaces_rebuilt` |
| Volume & Reporting | `on_volume_computed`, `_clear_cutfill_state`, `_on_volume_computed` |
| Strata Settings | `_on_strata_settings` |
| Miscellaneous | `closeEvent`, `on_about`, `on_open_3d` |

## MainWindow Refactor (Completed 2025-06-23)
- [x] Phase 1: Inventory & Safety Net
- [x] Phase 2: PolylineInteractionHandler
- [x] Phase 3: View & Input Handlers
- [x] Phase 4: Scale & Legend Controllers
- [x] Phase 5: PDF Navigation Cleanup
- [x] Phase 6: UI Builder Extraction Finish
- [x] Phase 7: Final Cleanup & Size Check 