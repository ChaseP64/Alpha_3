# DigCalc Application Context Outline

This document provides a comprehensive outline of the DigCalc application's structure, components, and current status. It is intended to be a living document that can be updated as the project evolves.

## High-Level Overview

DigCalc is a desktop application for civil engineering and construction professionals to perform earthwork calculations, including cut and fill volumes, mass haul analysis, and surface modeling. It supports importing data from various file formats (CSV, DXF, LandXML, PDF), generating 3D surfaces (TINs), and visualizing the results.

The application appears to be built with Python, using a GUI framework (likely PyQt or PySide, given the `.ui` files and naming conventions), and PyVista for 3D visualization.

## Project Structure

The project is organized into the following main directories:

-   `digcalc_project/`: The main application module.
-   `tests/`: Unit and integration tests.
-   `.github/`: GitHub-specific files, likely for CI/CD.

### `digcalc_project/src/` Directory Structure

The core application logic resides in the `digcalc_project/src/` directory, which is further divided into the following modules:

-   **`main.py`**: The main entry point of the application.
-   **`exceptions.py`**: Custom exception classes.

-   **`core/`**: Core business logic, independent of the UI.
    -   `importers/`: Parsers for various file formats (CSV, DXF, LandXML, PDF).
    -   `geometry/`: Geometric operations, including TIN generation, surface building, and grid generation.
    -   `calculations/`: Modules for performing calculations like volume and mass haul.
    -   `calculators/`: Higher-level calculator modules.
    -   `reporting/`: Generation of reports, such as haul charts and PDF reports.

-   **`models/`**: Data models for the application's entities.
    -   `project.py`: The main project model.
    -   `surface.py`: Represents a 3D surface.
    -   Other models for layers, calculations, regions, etc.

-   **`services/`**: Services that provide functionalities to the rest of the application.
    -   `interpolation_service.py`: For interpolating data.
    -   `settings_service.py`: For managing application settings.
    -   Other services for handling layers, PDFs, and CSV writing.

-   **`controllers/`**: Controllers that mediate between the models and the UI.
    - `pdf_controller.py`: Handles PDF-related user interactions.

-   **`ui/`**: User interface components.
    -   `main_window.py`: The main application window.
    -   `dialogs/`: Various dialog boxes used in the application.
    -   `3d/`: 3D visualization components, likely using PyVista.
    -   `items/`: Custom graphics items for the UI.
    -   `commands/`: Implementation of the command pattern for undo/redo functionality.
    -   `docks/`: Dockable widgets for the main window.

-   **`utils/`**: Utility functions and helper classes.
    -   `logging_utils.py`: For application logging.
    -   `singleton.py`: A singleton pattern implementation.

-   **`visualization/`**: Visualization-related code.
    -   `pdf_renderer.py`: For rendering PDFs.

-   **`tools/`**: Standalone tools and utilities.

### `tests/` Directory

The `tests/` directory mirrors the structure of the `src/` directory, containing unit tests for the corresponding modules. It uses `pytest` and includes a `conftest.py` for test configuration and fixtures.

## Current Project Status (`TASK.md`)

Based on `TASK.md`, the project is actively being developed. Here's a summary:

### Completed Tasks
-   Foundation of the application is set up.
-   3D viewer has been significantly overhauled.
-   Basic data import for CSV and LandXML is implemented.
-   Surface model and some GUI tests are in place.
-   Several bugs and issues have been addressed.

### In-Progress / To-Do
-   Parsers for DXF and PDF need to be completed.
-   TIN generation from imported data.
-   Implementation of volume calculation (cut/fill).
-   UI enhancements, including reporting functionality.
-   Fixing remaining test issues, especially for LandXML and PDF parsers.

## Potential Issues and Notes

-   **Large File Sizes**: Several files exceed the 500-line limit mentioned in the user rules. These should be considered for refactoring:
    -   `digcalc_project/src/ui/main_window.py` (~2869 lines)
    -   `digcalc_project/src/ui/tracing_scene.py` (~1581 lines)
    -   `digcalc_project/src/ui/visualization_panel.py` (~1253 lines)
    -   `digcalc_project/src/ui/docks/pv_dock.py` (~1012 lines)
    -   `digcalc_project/src/models/project.py` (~710 lines)
    -   `digcalc_project/src/ui/dialogs/scale_calibration_dialog.py` (~594 lines)
    -   `digcalc_project/src/core/calculations/volume_calculator.py` (~513 lines)

-   **GUI Framework**: The UI is likely built with PyQt or PySide. The specific framework should be confirmed.

-   **Dependencies**: The project's dependencies are listed in `digcalc_project/requirements.txt`. 