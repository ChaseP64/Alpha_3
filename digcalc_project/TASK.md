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

## Discovered During Work
- [x] Recreate Python files as UTF-8 text files to remove null bytes and invalid characters
- [x] Reset `__init__.py` files to clean UTF-8 files
- [ ] Fix import paths to be consistent (use 'src.' prefix for absolute imports)
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