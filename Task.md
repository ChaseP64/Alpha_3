## Purpose
This document tracks current tasks, backlog items, and sub-tasks for the DigCalc project. It includes a bullet list of active work, milestones, and any discoveries made during the development process. Use the prompt "Update TASK.md to mark XYZ as done and add ABC as a new task" to update this file.

---

## Active Tasks

- [x] **Project Setup & Requirements Finalization**
  - [x] Define overall project scope and success criteria.
  - [x] Finalize high-level vision, architecture, constraints, and tech stack.
  
- [x] **UI Prototyping & Workflow Planning**
  - [x] Create detailed wireframes and mockups.
  - [x] Define user navigation and interactive elements.
  
- [x] **Data Import Module Development**
  - [x] Implement file selection UI.
  - [x] Develop parsers for CSV and LandXML; stub for DWG/DXF and PDF.
  - [x] Validate imported data for unit consistency. (Basic CSV header/column selection)
  
- [x] **Surface Modeling & TIN Generation Module**
  - [x] Generate TIN using Delaunay triangulation.
  - [x] Create models for "Existing" and "Proposed" surfaces.
  - [ ] Enable node editing and boundary clipping.
  
- [x] **Volume Calculation Engine Development**
  - [x] Implement grid method with user-configurable grid sizes.
  - [ ] Develop TIN differencing for volume calculations.
  - [ ] Integrate adjustable parameters (swell/shrink, topsoil stripping, subgrade adjustments).
  
- [ ] **Visualization Module Development**
  - [ ] Build 2D plan view with overlays (grids, contours, cut/fill maps).
  - [x] Integrate VTK for interactive 3D visualization.
  - [ ] Add interactive features like node inspection and dynamic cross-section generation.
    - [x] interactive zoom & pan in 2-D plan view
  - [x] Implement InteractiveGraphicsView with Ctrl+Wheel zoom and Middle-mouse / Alt+Left panning.
  
- [x] **Reporting Module Development**
  - [x] Basic volume report dialog implemented.
  - [ ] Design report templates with project metadata and visual snapshots.
  - [ ] Implement export functionality for PDF, CSV, and Excel.
  
- [x] **Integration & Workflow Assembly**
  - [x] Integrate all modules into the main application. (Project management, Import, Viz, Calc, basic Report integrated)
  - [x] Develop the main UI shell with navigation, settings, and status indicators.
  - [x] Refactor MainWindow: remove temporary QML test actions/menus and related logging.
  
- [x] **Testing, Quality Assurance, and Debugging**
  - [x] Manual test procedures added (as code comments).
  - [ ] Write and run unit and integration tests using pytest.
  - [ ] Conduct performance and error handling tests.
  
- [ ] **Documentation & Finalization**
  - [x] README updated for core features (import, calc, reporting).
  - [x] UI polished for consistency (dialogs, layout).
  - [ ] Write user and developer documentation.
  - [ ] Prepare demo guides, finalize UI polish, and package the build.
  
- [ ] **Manual PDF Tracing & Elevation Extraction Module**
  - [ ] Implement PDF rendering to display scanned grading plans (using PyMuPDF).
  - [ ] Develop a drawing/tracing interface that allows users to manually trace lines and areas over the PDF.
  - [ ] Support different tools (polyline, polygon, freehand) for tracing.
  - [ ] Incorporate snapping, grid, and alignment aids to improve tracing accuracy.
  - [ ] Enable assignment of elevation data:
    - [ ] Constant elevation assignment for features (e.g., a contour line).
    - [ ] Per-vertex elevation input for variable features (e.g., breaklines).
  - [ ] Organize traced elements into semantic layers (Existing Surface, Proposed Surface, Subgrade, Annotations, Report Regions).
  - [ ] Integrate traced data with the Surface Modeling module to generate 2D/3D terrain.
  - [ ] Include functionality for manual editing (moving vertices, reassigning elevations).
  - [ ] Provide UI controls for saving, loading, and exporting traced data (e.g., to JSON or DXF).
  - [ ] Document manual testing steps for PDF tracing and elevation assignment.

---

## Backlog Tasks
- [ ] Develop enhanced DWG/DXF parser using ezdxf.
- [ ] Expand PDF parsing capabilities (e.g., auto-calibration features).
- [ ] Improve UI accessibility (keyboard shortcuts, clear icons).
- [ ] Integrate continuous integration (CI) for automated testing.
- [ ] Add advanced AI-assisted features for error correction.
- [ ] Explore additional reporting customization options (e.g., export formats, visual snapshots).
- [ ] Implement TIN differencing volume calculation method.
- [ ] Implement automated tracing and OCR-based elevation extraction for PDFs (future enhancement).

---

## Milestones
- **Milestone 1:** Project Setup, Requirements, and UI Prototyping Complete (Day 5)
- **Milestone 2:** Core Modules (Data Import, Surface Modeling, Volume Calculation) Developed (Day 13)
- **Milestone 3:** Full Integration and Basic Testing Completed (Day 20) <- Approaching
- **Milestone 4:** Final Testing, Documentation, and Packaging Complete (Day 24)

---

## Mid-Process Discoveries & Notes
- Ensure early integration of version control (Git) and CI for testing.
- Maintain a modular design to support future enhancements (e.g., mobile, cloud, automated tracing).
- Leverage AI tools (GitHub Copilot, ChatGPT) to accelerate repetitive coding tasks.
- Use clear error logging and exception handling for improved stability.
- Regularly update and review this document to reflect new tasks and adjustments.
- Basic report dialog added; needs enhancement for export and visuals.
- UI polishing improved consistency, but continuous review and potential UI accessibility improvements are needed.
- Formal automated testing is still pending; manual test procedures are currently in place.
- Refactored dialogs (VolumeCalc, ImportOptions, Report) into separate files for modularity.
- **Manual PDF Tracing and Elevation Extraction:** Manual tracing is planned as a core feature, with future capabilities for automated tracing and OCR for elevation extraction.

---

## Global Update Rules
- **Marking a Task as Done:** Change the checkbox from `[ ]` to `[x]`.
- **Adding a New Task:** Insert a new bullet point in the appropriate section.
- **Example Prompt:** "Update TASK.md to mark 'UI Prototyping' as done and add 'Implement dark theme' as a new task."

---

# End of TASK.md
