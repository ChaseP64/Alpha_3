# DigCalc - Excavation Takeoff Tool

DigCalc is a desktop application for calculating earthwork volumes from digital elevation models. It allows engineers and construction professionals to import various data formats, create surfaces, and calculate cut and fill volumes between surfaces.

## Features

- **Surface Import**: Import surfaces from various file formats:
  - DXF files (AutoCAD)
  - LandXML files
  - CSV point data
  - PDF drawings (with optical recognition)
- **Surface Creation and Editing**: Create, modify, and analyze terrain surfaces
- **TIN Generation**: Generate Triangulated Irregular Networks from point data
- **Volume Calculation**: Calculate cut and fill volumes between surfaces
- **Grid Generation**: Generate regular grids for volume calculations
- **3D Visualization**: Visualize surfaces and volume calculations in 3D
- **Report Generation**: Generate PDF reports with volume calculations

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

5. Run the application:
   ```
   python src/main.py
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

### Creating Volume Calculations

1. Import or create at least two surfaces (e.g., existing ground and design surface)
2. Select both surfaces in the project panel
3. Click "Calculate Volume"
4. Configure calculation settings
5. View results in the visualization panel and generate reports

## Development

### Project Structure

- `src/` - Source code
  - `core/` - Core functionality
    - `importers/` - File import modules
    - `exporters/` - File export modules
    - `calculators/` - Volume calculation logic
    - `generators/` - Grid and TIN generation
  - `models/` - Data models
  - `ui/` - User interface components
  - `utils/` - Utility functions
- `tests/` - Unit tests
- `docs/` - Documentation

### Testing

Run the test suite:

```
pytest tests/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- Thanks to all the open-source libraries that made this project possible 