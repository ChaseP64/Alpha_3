# TASK.md

## Purpose
This document tracks current tasks, backlog items, and sub-tasks for the DigCalc project. It includes a bullet list of active work, milestones, and any discoveries made during the development process. Use the prompt "Update TASK.md to mark XYZ as done and add ABC as a new task" to update this file.

---

## Active Tasks
- [x] **Project Setup & Requirements Finalization**
  - Define overall project scope and success criteria.
  - Finalize high-level vision, architecture, constraints, and tech stack.
- [x] **UI Prototyping & Workflow Planning**
  - Create detailed wireframes and mockups.
  - Define user navigation and interactive elements.
- [x] **Data Import Module Development**
  - Implement file selection UI.
  - Develop parsers for CSV and LandXML; stub for DWG/DXF and PDF.
  - Validate imported data for unit consistency.
- [x] **Surface Modeling & TIN Generation Module**
  - Generate TIN using Delaunay triangulation.
  - Create models for "Existing" and "Proposed" surfaces.
  - Enable node editing and boundary clipping.
- [x] **Volume Calculation Engine Development**
  - Implement grid method with user-configurable grid sizes.
  - Develop TIN differencing for volume calculations.
  - Integrate adjustable parameters (swell/shrink, topsoil stripping, subgrade adjustments).
- [ ] **Visualization Module Development**
  - Build 2D plan view with overlays (grids, contours, cut/fill maps).
  - Integrate VTK for interactive 3D visualization.
  - Add interactive features like node inspection and dynamic cross-section generation.
- [ ] **Reporting Module Development**
  - Design report templates with project metadata and visual snapshots.
  - Implement export functionality for PDF, CSV, and Excel.
- [ ] **Integration & Workflow Assembly**
  - Integrate all modules into the main application. (Partially done: Project management, Import, Viz, Calc integrated)
  - Develop the main UI shell with navigation, settings, and status indicators. (Partially done)
- [ ] **Testing, Quality Assurance, and Debugging**
  - Write and run unit and integration tests using pytest.
  - Conduct performance and error handling tests.
- [ ] **Documentation & Finalization**
  - Write user and developer documentation.
  - Prepare demo guides, finalize UI polish, and package the build.

---

## Backlog Tasks
- [ ] Develop enhanced DWG/DXF parser using ezdxf.
- [ ] Expand PDF parsing capabilities (e.g., auto-calibration features).
- [ ] Improve UI accessibility (keyboard shortcuts, clear icons).
- [ ] Integrate continuous integration (CI) for automated testing.
- [ ] Add advanced AI-assisted features for error correction.
- [ ] Explore additional reporting customization options.

---

## Milestones
- **Milestone 1:** Project Setup, Requirements, and UI Prototyping Complete (Day 5)
- **Milestone 2:** Core Modules (Data Import, Surface Modeling, Volume Calculation) Developed (Day 13)
- **Milestone 3:** Full Integration and Basic Testing Completed (Day 20)
- **Milestone 4:** Final Testing, Documentation, and Packaging Complete (Day 24)

---

## Mid-Process Discoveries & Notes
- Ensure early integration of version control (Git) and CI for testing.
- Maintain a modular design to support future enhancements (e.g., mobile, cloud).
- Leverage AI tools (GitHub Copilot, ChatGPT) to accelerate repetitive coding tasks.
- Use clear error logging and exception handling for improved stability.
- Regularly update and review this document to reflect new tasks and adjustments.

---

## Global Update Rules
- **Marking a Task as Done:** Change the checkbox from `[ ]` to `[x]`.
- **Adding a New Task:** Insert a new bullet point in the appropriate section.
- **Example Prompt:** "Update TASK.md to mark 'UI Prototyping' as done and add 'Implement dark theme' as a new task."

---

# End of TASK.md

