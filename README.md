- PDF plan import and scaling
- Interactive 2-D tracing of lines and polygons
- Surface generation from traced contour data
- Cut & Fill volume calculations between any two surfaces
- 3-D visualization of all surfaces
- Vectorize *native* PDF strokes into editable polylines – no raster tracing!

### Strata-Aware Earthworks (New!)

DigCalc now supports modeling of subsurface material layers (stratigraphy). This allows for more accurate cut/fill calculations by accounting for the different materials being excavated.

**Key Features:**
- **Material Manager:** Define custom materials with properties like color and opacity.
- **Borehole Logging:** Place borehole locations in the 2-D view and log the depth of each material layer.
- **Surface Generation:** Interpolate borehole data into continuous 3-D surfaces for each material layer using an Inverse Distance Weighting (IDW) algorithm. The generation runs asynchronously to keep the UI responsive.
- **Quality Control:** An RMSE (Root Mean Square Error) value is calculated after generation to provide a metric for how well the generated surfaces fit the original borehole data.
- **3-D Visualization:** View the generated strata layers in the 3D viewer, with each layer colored according to its material. An opacity ladder is automatically applied for better visibility.
- **2-D Heatmap:** Toggle a 2-D heatmap overlay in the tracing view to see the spatial distribution of the uppermost material layer.

## Getting Started

1.  **Installation**: (Instructions to be added)
2.  **Running the Application**: `python -m digcalc_project.run_digcalc`

## Basic Workflow

1.  **Create a Project**: Start by creating a new project.

### Quick Peek – PDF Vectorizer

<p align="center">
  <img src="docs/media/vectorizer_preview.gif" alt="Vectorizing PDF page" width="600"/>
</p>

<p align="center">
  <em>End-to-end import workflow including scale calibration.</em><br/>
  <img src="docs/media/import_workflow.gif" alt="Import workflow" width="600"/>
</p>

### Elevation Tools

DigCalc’s Elevation UX sprint adds dedicated tools for working with vertex elevations:

* **Auto-Increment Wizard** – grade an entire polyline between two known elevations or a target slope.
* **Batch Elevate Dialog** – apply a uniform elevation or slope to multiple selected polylines in one grouped-undo action.
* **Elevation Heat-Map Preview** – blue→red overlay that refreshes in < 100 ms for 10 k vertices so you can spot high and low points instantly.

<p align="center">
  <img src="docs/media/heatmap_preview.png" alt="Elevation heat-map preview" width="600"/>
</p> 