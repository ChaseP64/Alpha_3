# DigCalc - Excavation Takeoff Tool

![CI](https://github.com/ChaseP64/Alpha_3/actions/workflows/ci.yml/badge.svg)

DigCalc is a desktop application for calculating earthwork volumes from digital elevation models. It allows engineers and construction professionals to import various data formats, create surfaces, and calculate cut and fill volumes between surfaces.

## Features

- **PDF tracing** with angle-lock, region creation, and numeric daylight offset  
- **Region stripping** & per-region volumes  
- **Auto-pad elevation** with live surface rebuild  
- **Lowest-surface** analysis  
- **Slice-volume** tables + bar-chart  
- **Mass-haul diagram** with free-haul / over-haul  
- **Premium 3-D viewer** (PyVista) – cut/fill shading, compass, wire-frame  
- One-click **Export Report** (PDF + CSV bundle)

### Screenshots

| Feature | Preview |
|---------|---------|
| PDF Tracing | ![PDF Tracing](docs/img/pdf_tracing.png) |
| Slice-Volume Table | ![Slice Volume](docs/img/slice_volume.png) |
| Mass-Haul Diagram | ![Mass Haul](docs/img/mass_haul.png) |

## Installation

### Prerequisites

- Python 3.9 or higher
- PySide6 (Qt for Python)
- Required packages listed in `requirements.txt`

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/digcalc.git
   cd digcalc
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate.bat`
   - macOS/Linux: `source venv/bin/activate`

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

5. **Run the Application:**
   *   Navigate **one directory up** from `digcalc_project` (e.g., to the `Alpha_3` directory if your structure is `Alpha_3/digcalc_project`).
   *   Run the application using Python's module execution flag:
       ```bash
       python -m digcalc_project.run_digcalc
       ```

## Usage

### Importing Data

DigCalc supports importing data from several file formats:

1. **DXF Files**:
   - Click on `Import` → `Import CAD (DXF)` in the main menu
   - Select a DXF file containing 3D entities
   - Configure import options for layers, etc.
   - Click "Import"

2. **LandXML Files**:
   - Click on `Import` → `Import LandXML` in the main menu
   - Select a LandXML file containing surface data
   - Choose the desired surface if multiple surfaces exist
   - Click "Import"

3. **CSV Files**:
   - Click on `Import` → `Import CSV` in the main menu
   - Select a CSV file containing point data
   - Configure column mappings for X, Y, Z coordinates
   - Click "Import"

4. **PDF Files**:
   - Click on `Import` → `Import PDF` in the main menu
   - Select a PDF file containing contour lines or elevation data
   - Set the scale and other conversion parameters
   - Click "Import"

### Calculating Volumes and Viewing Reports

1. Ensure you have at least two surfaces loaded in your project (e.g., an 'Existing Ground' surface and a 'Proposed Design' surface).
2. Go to the `Analysis` menu and select `Calculate Volumes...` (or use the corresponding toolbar button).
3. In the dialog that appears:
    - Select the appropriate surface for `Existing Surface`.
    - Select the appropriate surface for `Proposed Surface`.
    - Enter the desired `Grid Resolution` (the size of the grid squares used for calculation).
    - Click `OK`.
4. The calculation will run. If successful, a **Volume Calculation Report** dialog will automatically appear, showing:
    - Calculation timestamp.
    - Names of the surfaces used.
    - Grid resolution.
    - Calculated Cut, Fill, and Net volumes.
5. Click `OK` to close the report dialog.
6. Status bar messages will indicate the progress and outcome of the calculation.

## Development

### Project Structure

- `src/` - Source code
  - `core/` - Core functionality
    - `importers/` - File import modules
    - `exporters/` - File export modules
    - `calculators/` - Volume calculation logic
    - `