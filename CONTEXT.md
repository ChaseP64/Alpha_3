# Application Outline

This document provides a high-level overview of the `DigCalc` application structure.

## Project Root (`DigCalc/`)

- **`.git/`**: Git version control directory.
- **`digcalc_project/`**: Main application package.
- **`tests/`**: Test suite for the application.
- **`.github/`**: GitHub-specific files (e.g., workflows).
- **`pyproject.toml`**: Project metadata and dependencies.
- **`README.md`**: Project overview and setup instructions.
- **`CONTEXT.md`**: This file, outlining the application structure.

## Application Package (`digcalc_project/`)

- **`src/`**: Source code for the application.
- **`tests/`**: Duplicated tests directory (potential cleanup candidate).
- **`run_digcalc.py`**: Entry point to run the application.

### Source Code (`digcalc_project/src/`)

- **`main.py`**: Main application entry point.
- **`core/`**: Core business logic (calculations, geometry, etc.).
- **`models/`**: Data models and structures.
- **`services/`**: Application services (e.g., interpolation, settings).
- **`ui/`**: User interface components (windows, dialogs, etc.).
- **`controllers/`**: Application controllers.
- **`utils/`**: Utility functions and helper classes.
- **`visualization/`**: Visualization components.
- **`tools/`**: Various application tools.

#### Core (`digcalc_project/src/core/`)

- **`calculations/`**: Volume and mass haul calculations.
  - `volume_calculator.py` (**VIOLATION**: >500 lines)
- **`calculators/`**: Additional calculator utilities.
- **`geometry/`**: Geometric operations (TIN generation, surface building).
- **`importers/`**: Data importers (CSV, DXF, LandXML).
- **`reporting/`**: Reporting tools (CSV, PDF).

#### Models (`digcalc_project/src/models/`)

- `project.py` (**VIOLATION**: >500 lines)
- `surface.py`
- `strata_models.py`
- `calculation.py`
- ...and other data models.

#### Services (`digcalc_project/src/services/`)

- `interpolation_service.py` (**VIOLATION**: >500 lines)
- `settings_service.py`
- ...and other services.

#### UI (`digcalc_project/src/ui/`)

- `main_window.py` (**VIOLATION**: >2500 lines)
- `visualization_panel.py` (**VIOLATION**: >1000 lines)
- `tracing_scene.py` (**VIOLATION**: >1500 lines)
- **`dialogs/`**: Application dialogs.
  - `scale_calibration_dialog.py` (**VIOLATION**: >500 lines)
- **`docks/`**: Dockable widgets.
  - `pv_dock.py` (**VIOLATION**: >1000 lines)
- **`3d/`**, **`items/`**, **`commands/`**: Other UI components.

## Test Suite (`tests/`)

The test suite mirrors the structure of the `src` directory, with tests for each component.

- **`core/`**, **`models/`**, **`services/`**, etc.

## Rule Violations

The following files violate the "no file longer than 500 lines" rule:

- `digcalc_project/src/core/calculations/volume_calculator.py`
- `digcalc_project/src/models/project.py`
- `digcalc_project/src/services/interpolation_service.py`
- `digcalc_project/src/ui/main_window.py`
- `digcalc_project/src/ui/visualization_panel.py`
- `digcalc_project/src/ui/tracing_scene.py`
- `digcalc_project/src/ui/dialogs/scale_calibration_dialog.py`
- `digcalc_project/src/ui/docks/pv_dock.py`

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