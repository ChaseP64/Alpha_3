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

## 📏  Set Scale *without* Measuring

DigCalc now lets you skip the two-point pick and simply **type the drawing's scale**.

| Where | Action |
|-------|--------|
| **Toolbar** | Click **Scale…** ![ruler-icon] or press **Ctrl + K** |
| **Dialog – Enter Scale tab** | • *World units / inch* → type `50` & select `ft`<br>• **or** *Ratio* → keep `1` : `600` |
| **Status Pill** | The pill in the status-bar turns <span style="color:#3c9;font-weight:bold;">green</span> → "Scale: 50 ft/in". Red means the PDF DPI no longer matches. |

<figure>
  <img src="docs/gif/scale_entry_ratio.gif" alt="Enter Scale dialog – ratio entry" width="640">
  <figcaption><b>Fig 1.</b> Setting "1 : 600" gives 50 ft&nbsp;/ in at 150 dpi.</figcaption>
</figure>

> **Tip:** If you ever change the PDF render DPI, the pill flips red and tracing is disabled until you recalibrate.

## 🌄 3-D Viewer at a Glance

DigCalc now ships with a production-grade 3-D window powered by **PyVista**:

| Key | Feature |
|-----|---------|
| 📏 **HUD** | Orientation gizmo • scale bar • live XYZ read-out |
| ✂ **Section Plane** | Drag the yellow plane to slice through strata interactively |
| 🖱️ **Trackball / Fly** | Orbit, pan, zoom or click-to-fly (right-click) |
| 🎚️ **Z-Exaggeration** | Slider ×1 – ×5 for flat sites |
| ⚡ **Draft Mode** | One toggle drops AA/EDL for >60 fps on low GPUs |
| 📷 **Screenshot** | One-click PNG export |
| ★ **Bookmarks** | Save & recall camera presets per-project |
| 🖌️ **Layer Sync** | Colors / visibility follow the 2-D Layer dock in real-time |

<figure>
  <img src="docs/gif/3d_viewer_overview.gif"
       alt="Gif demo of DigCalc 3-D viewer: orbit, section-plane, z-slider, screenshot & draft toggle"
       width="720">
  <figcaption><b>Fig X.</b> Orbiting a three-strata site, slicing with the section plane, exaggerating Z, toggling Draft mode, and snapping a PNG.</figcaption>
</figure>

## Generate Strata from Contours

Phase&nbsp;5 introduced *contour-based strata generation* — an alternative to borehole logs for defining material boundaries.

1. Enable **Strata-Contour** in the *Layer Legend* dock (left).  Any closed polyline you trace will now be flagged as a contour for the *current material* (selected in the Strata Manager).
2. Trace or import closed polylines for each material.  They may overlap; DigCalc always keeps the **lowest Z** at any XY when blending with borehole interpolation.
3. Click **Generate Surfaces** in the Strata Manager.  The engine will:
   * triangulate your contour rings (Shapely-powered)
   * blend / trim them with IDW borehole grids
   * write *.npz* caches for fast reloads
4. View results in 3-D or as a heat-map overlay.

> ℹ️  Open *Settings ▸ Strata…* to fine-tune IDW power, search radius, and maximum grid cell size.

### New Settings

| Setting | Location | Default | Notes |
|---------|----------|---------|-------|
| **IDW Power** | Settings ▸ Strata… | 2 | Higher = steeper influence fall-off. |
| **Search Radius** (ft/m) | Settings ▸ Strata… | 150 ft | Samples beyond this distance are ignored. |
| **Max Grid Cell** (ft/m) | Settings ▸ Strata… | 1 ft | Upper bound for adaptive grid resolution. |

![Strata Settings Dialog](docs/img/strata_settings_dialog.png)

---

### Quick Demo (GIFs in *docs/gif*)

| Feature | Preview |
|---------|---------|
| 2-D Strata Heat-map Toggle | ![heatmap](docs/gif/strata_heatmap_toggle.gif) |
| 3-D Layer Cake & Section Plane | ![3-D strata](docs/gif/strata_layers_3d.gif) |
| Per-Material Report Export | ![report](docs/gif/material_report.gif) |

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