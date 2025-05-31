from __future__ import annotations

from functools import cached_property
from importlib import import_module
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QLabel,
    QToolBar,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QSlider,
    QCheckBox,
    QToolButton,
    QFileDialog,
    QMenu,
    QInputDialog,
)

# ----------------------------------------------------------------------------
# Local imports
# ----------------------------------------------------------------------------
from ..pv_plotter_singleton import get_plotter

if TYPE_CHECKING:  # pragma: no cover
    from digcalc_project.src.models.mesh_actor import MeshActor

# -----------------------------------------------------------------------------
# Config – Task 12 (auto decimate large meshes for display only)
# -----------------------------------------------------------------------------
MAX_FACES_FOR_FULL_RENDER = 500_000
DECIMATE_RATIO = 0.75  # keep 25 % of faces

class PvDock(QDockWidget):
    """3-D view dock embedding a PyVistaQt interactor.

    Displays a surface in 3-D, supports wire-frame toggling, multi-sample anti-aliasing,
    orientation gizmo, and cut/fill colour-map.  PyVista is imported lazily so that the
    application can still start without the 3-D dependencies.  If PyVista (or
    PyVistaQt) is not available a friendly banner is shown guiding the user to install
    the optional extra::

        pip install "digcalc[3d]"
    """

    def __init__(self, main_window):
        super().__init__("3-D View", main_window)
        self.main = main_window
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # --- Centralized Plotter (Task 1.1 / PLAN.md Phase 1.1) ---
        self.plotter = get_plotter()

        # --- NEW: HUD overlay (Task 8-A) ----------------------------------
        if not getattr(self.plotter, "_digcalc_hud", False):
            try:
                if hasattr(self.plotter, "add_axes"):
                    self.plotter.add_axes(interactive=False)
                if hasattr(self.plotter, "add_scale_bar"):
                    self.plotter.add_scale_bar(color="black", font_size=8)
                self.plotter._digcalc_hud = True  # type: ignore[attr-defined]
            except Exception:
                # Safe-guard: in test/dummy plotter these may be stubs
                self.plotter._digcalc_hud = True  # type: ignore[attr-defined]

        # --- Main widget is the plotter's interactor ---
        self.setWidget(self.plotter.interactor)

        # --- Custom Title Bar with Controls ---
        title_bar_widget = QWidget(self)
        title_bar_layout = QHBoxLayout(title_bar_widget)
        title_bar_layout.setContentsMargins(2, 2, 2, 2)
        title_bar_layout.setSpacing(4)

        # Toolbar for actions
        tb = QToolBar(title_bar_widget)
        self.wire_act = QAction("Wireframe", self, checkable=True)
        self.wire_act.toggled.connect(self._toggle_wire)
        tb.addAction(self.wire_act)

        self.refresh_act = QAction("Refresh (F5)", self)
        self.refresh_act.setShortcut(QKeySequence.Refresh)
        self.refresh_act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.refresh_act.triggered.connect(
            lambda: self._load_surface(self.surf_cb.currentText()),
        )
        tb.addAction(self.refresh_act)

        # --- NEW: Section-plane toggle (Task 6-B) ---
        self.section_act = QAction("✂ Section", self, checkable=True)
        self.section_act.setShortcut(QKeySequence("S"))
        self.section_act.setToolTip("Toggle section plane on/off")
        self.section_act.toggled.connect(self._toggle_section)
        tb.addAction(self.section_act)

        # --- NEW: Draft quality toggle (Task 9-A) --------------------------
        self.draft_chk = QCheckBox("Draft")
        self.draft_chk.setToolTip("Lower quality (no AA, flat shading) for performance")
        self.draft_chk.toggled.connect(self._apply_quality_mode)
        title_bar_layout.addWidget(self.draft_chk)

        # --- NEW: Screenshot & Bookmark buttons (Task 10-A) -----------------
        self.btn_snap = QToolButton(title_bar_widget)
        self.btn_snap.setText("📷")
        self.btn_snap.setToolTip("Save screenshot (PNG)")
        self.btn_snap.clicked.connect(self._take_screenshot)
        title_bar_layout.addWidget(self.btn_snap)

        self.btn_book = QToolButton(title_bar_widget)
        self.btn_book.setText("★")
        self.btn_book.setToolTip("Add camera bookmark")
        self.btn_book.setPopupMode(QToolButton.InstantPopup)
        self.book_menu = QMenu(self)
        self.btn_book.setMenu(self.book_menu)
        self.btn_book.clicked.connect(self._add_bookmark)
        title_bar_layout.addWidget(self.btn_book)

        title_bar_layout.addWidget(tb)

        # Surface selector
        title_bar_layout.addWidget(QLabel("Surface:", title_bar_widget))
        self.surf_cb = QComboBox(title_bar_widget)
        self.surf_cb.currentTextChanged.connect(self._load_surface)
        title_bar_layout.addWidget(self.surf_cb)

        # --- NEW: Z-exaggeration slider (Task 8-B) -------------------------
        self.z_factor: float = 1.0
        title_bar_layout.addWidget(QLabel("Z×", title_bar_widget))
        self.z_slider = QSlider(Qt.Orientation.Horizontal, title_bar_widget)
        self.z_slider.setRange(1, 5)
        self.z_slider.setFixedWidth(80)
        self.z_slider.setValue(1)
        self.z_slider.setToolTip("Vertical exaggeration (1× – 5×)")
        self.z_slider.valueChanged.connect(self._on_z_factor_changed)
        title_bar_layout.addWidget(self.z_slider)

        title_bar_layout.addStretch()

        self.setTitleBarWidget(title_bar_widget)

        # ------------------------------------------------------------------
        #  Post-UI initialisation helpers
        # ------------------------------------------------------------------

        # Apply default high-quality rendering (Task 9-C)
        self._set_high_quality()

        # Actor handle for the displayed mesh
        self._current_actor = None

        # MeshActor registry
        self.mesh_actors: dict[str, "MeshActor"] = {}

        # State holders for section-plane tool
        self._plane_widget = None  # type: ignore
        self._vtk_plane = None     # type: ignore

        # Initial population and loading
        self._populate_combo()
        if self.surf_cb.count() > 0:
            self._load_surface(self.surf_cb.currentText())
        else:
            self.plotter.clear_actors()
            self.plotter.reset_camera()

        # Connect project signals
        if hasattr(self.main, "project_controller"):
            pc = self.main.project_controller
            if hasattr(pc, "surfaces_rebuilt"): pc.surfaces_rebuilt.connect(self._on_surfaces_rebuilt)
            if hasattr(pc, "project_modified"): pc.project_modified.connect(self._on_surfaces_rebuilt)
            if hasattr(pc, "surfacesChanged"): pc.surfacesChanged.connect(self._on_surfaces_rebuilt)
            if hasattr(pc, "project_loaded"): pc.project_loaded.connect(self.load_project)

        # --- NEW: Connect layer-dock signals for sync with 3-D actors (Task 7-A) ---
        for dock_name in ("layer_dock", "legend_dock"):
            dock_obj = getattr(main_window, dock_name, None)
            if dock_obj is None:
                continue
            # Visibility signal
            for sig_name in ("layerVisibilityChanged", "layerVisibilityToggled"):
                signal = getattr(dock_obj, sig_name, None)
                if signal is not None:
                    try:
                        signal.connect(self._on_layer_visibility)
                    except Exception:
                        pass
            # Colour signal
            if hasattr(dock_obj, "layerColorChanged"):
                try:
                    dock_obj.layerColorChanged.connect(self._on_layer_color)
                except Exception:
                    pass

        # After other init operations, refresh bookmark menu for current project
        self._refresh_bookmark_menu()

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _populate_combo(self) -> None:
        """Populate the surface combo-box with project surfaces that exist."""
        self.surf_cb.clear()
        proj = None
        if hasattr(self.main, "project_controller"):
            proj = self.main.project_controller.get_current_project()
        if proj is None:
            return
        if hasattr(proj, "surfaces") and isinstance(proj.surfaces, dict):
            for surf_name in sorted(proj.surfaces.keys()):
                self.surf_cb.addItem(surf_name)
        else:
            for legacy in ("Existing", "Design", "Stripping", "Lowest"):
                if getattr(proj, f"{legacy.lower()}_surface", None):
                    self.surf_cb.addItem(legacy)
        if self.surf_cb.count() and self.surf_cb.currentIndex() < 0:
            self.surf_cb.setCurrentIndex(0)

    def _load_surface(self, name: str) -> None:
        """Load *name* surface into the 3-D view."""
        if not name: 
            return
        proj = None
        if hasattr(self.main, "project_controller"):
            proj = self.main.project_controller.get_current_project()
        if proj is None:
            return
        surf = None
        if hasattr(proj, "surfaces") and isinstance(proj.surfaces, dict):
            surf = proj.surfaces.get(name)
        if surf is None:
            surf = getattr(proj, f"{name.lower()}_surface", None)
        if surf is None:
            if self._current_actor:
                try: self._current_actor.SetVisibility(False)
                except Exception: pass
            return

        from digcalc_project.src.utils.surface_to_polydata import surface_to_polydata

        try:
            mesh = surface_to_polydata(surf)
        except ValueError as exc:
            print(f"Error converting surface '{name}' to PolyData: {exc}")
            return

        # Validate mesh before sending to VTK
        try:
            self._validate_polydata(mesh)
        except ValueError as exc:
            print(f"Surface '{name}' validation failed: {exc}")
            return  # Skip rendering invalid mesh

        try:
            if self._current_actor is not None:
                try: self._current_actor.SetVisibility(False)
                except Exception: pass
            disp_mesh = self._prepare_display_mesh(mesh)
            self._current_actor = self.plotter.add_mesh(disp_mesh, scalars="dz", cmap="RdYlGn_r")
            try:
                self._current_actor.SetScale(1.0, 1.0, getattr(self, "z_factor", 1.0))
            except Exception:
                pass
        except Exception as exc:
            print(f"3-D view fallback due to error hiding actor: {exc}")
            self.plotter.clear()
            self._current_actor = self.plotter.add_mesh(mesh, scalars="dz", cmap="RdYlGn_r")

        if not getattr(self, "_axes_added", False):
            try:
                if hasattr(self.plotter, "add_axes"):
                    self.plotter.add_axes()
                else:
                    import pyvista as pv 
                    axes_actor = pv.Arrow() if hasattr(pv, "Arrow") else None
                    self.plotter.add_orientation_widget(axes_actor)
            except Exception as exc:
                print(f"Warning: could not add orientation widget: {exc}")
            self._axes_added = True

        # MSAA (if available) - Note: This is also set in plotter.enable_anti_aliasing()
        if self.plotter.ren_win:
            self.plotter.ren_win.SetMultiSamples(4) # Explicitly set samples if desired
        
        # Camera defaults (Task 4 / PLAN.md Phase 3.1)
        self.plotter.camera_position = 'iso'
        # Reset camera to frame the current scene content tightly
        # It's good to do this after all actors for the current view are set up.
        if self.plotter.renderer.actors: # Only reset if there are actors
            self.plotter.reset_camera(bounds=self.plotter.renderer.bounds)
        else: # Fallback if no actors, e.g. after a clear
            self.plotter.reset_camera()

    def _toggle_wire(self, on: bool) -> None:
        """Toggle between wire-frame and shaded surface representation."""
        if self._current_actor:
            representation = "wireframe" if on else "surface"
            self._current_actor.prop.representation = representation
            # Force a render to see the change immediately if plotter doesn't auto-update on actor prop change
            self.plotter.render()

    # ------------------------------------------------------------------
    #   Project-signal handlers
    # ------------------------------------------------------------------
    def load_project(self, project) -> None:
        """Load the first surface of a project with specific defaults."""
        self.mesh_actors.clear()
        self.plotter.clear()  # Wipe entire scene as per user snippet

        if not project or not hasattr(project, "surfaces") or not project.surfaces:
            self.surf_cb.clear()
            self._current_actor = None
            self.hide()
            self.plotter.reset_camera() # Reset camera for empty scene
            return

        self.show() # Ensure dock is visible if it was hidden

        # Populate the combobox with the new project's surfaces
        # This assumes project_controller.get_current_project() now returns this 'project'
        # or that _populate_combo can work with the main controller state.
        self._populate_combo()

        # Use the correct import path
        from digcalc_project.src.utils.surface_to_polydata import surface_to_polydata

        # ------------------------------------------------------------------
        #   Task 5 – Opacity ladder for multi-strata
        # ------------------------------------------------------------------
        import numpy as _np  # local heavy import
        from digcalc_project.src.models.mesh_actor import MeshActor

        # Determine ordering – shallowest (highest Z) first
        def _avg_z(surf):
            return _np.mean([v[2] for v in surf.vertices]) if getattr(surf, "vertices", None) else 0.0

        ordered_surfs = sorted(project.surfaces.values(), key=_avg_z, reverse=True)

        # Simple fallback colour palette if project doesn\'t provide colours
        fallback_palette = [
            "#A67C52",  # brown
            "#D1B280",  # lighter brown
            "#B0C4DE",  # slate blue (clay)
            "#708090",  # grey (rock)
        ]
        layer_color_map = {
            surf.name: fallback_palette[idx % len(fallback_palette)] for idx, surf in enumerate(ordered_surfs)
        }

        BASE_OPACITY = 1.0
        STEP = 0.3

        self.mesh_actors.clear()
        self._current_actor = None

        for idx, surf in enumerate(ordered_surfs):
            opacity = max(0.1, BASE_OPACITY - idx * STEP)

            try:
                mesh = surface_to_polydata(surf)
                self._validate_polydata(mesh)
            except ValueError as err:
                print(f"Skipping surface '{surf.name}': {err}")
                continue

            ma = MeshActor(
                surface_name=surf.name,
                mesh=mesh,
                color=None,  # Will convert below
                opacity=opacity,
            )
            # QColor import lazily
            from PySide6.QtGui import QColor  # type: ignore
            ma.color = QColor(layer_color_map.get(surf.name, fallback_palette[0]))

            self.add_actor(ma)
            # Set the first (top) actor as current_actor for toggle logic
            if self._current_actor is None:
                self._current_actor = ma.actor

        # After adding all actors, reset camera once
        if self.plotter.renderer.actors:
            self.plotter.camera_position = "iso"
            self.plotter.reset_camera(bounds=self.plotter.renderer.bounds)
            self.plotter.enable_parallel_projection()

        # Update combobox selection to reflect the loaded surface
        if self.surf_cb.findText(ordered_surfs[0].name) != -1:
            self.surf_cb.setCurrentText(ordered_surfs[0].name)
        elif self.surf_cb.count() > 0:
            self.surf_cb.setCurrentIndex(0) # Fallback to first item if name not found

        # --- Task 6-A: ensure section-plane widget exists ---
        self._ensure_plane_widget()

        # --- Task 11-C: sync legend after actors are ready ---
        self._sync_plotter_legend()

    def _on_surfaces_rebuilt(self):
        """Refresh combo and ensure a visible mesh afterwards."""
        old_selection = self.surf_cb.currentText()
        current_idx = self.surf_cb.currentIndex()
        self.surf_cb.blockSignals(True)
        self._populate_combo()
        self.surf_cb.blockSignals(False)

        new_idx = self.surf_cb.findText(old_selection)
        if new_idx != -1:
            if new_idx != current_idx:
                self.surf_cb.setCurrentIndex(new_idx)
            elif not self._current_actor or not self._current_actor.GetVisibility():
                self._load_surface(old_selection)
        elif self.surf_cb.count() > 0:
            self.surf_cb.setCurrentIndex(0)
        else:
            if self._current_actor:
                try:
                    self._current_actor.SetVisibility(False)
                except Exception:
                    pass
            self.plotter.clear_actors()
            self.plotter.reset_camera()
            self._current_actor = None

    # ------------------------------------------------------------------
    #   Event handlers
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:
        """Override close event to only hide the dock.

        This prevents destruction of the singleton plotter when the dock is closed.
        The plotter is managed by the application lifecycle (on quit).
        """
        self.hide()
        event.ignore() # Ignore the event to prevent widget deletion

    # ------------------------------------------------------------------
    #   Mesh validation helper (Task 3)
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_polydata(mesh: "pv.PolyData") -> None:  # type: ignore[name-defined]
        """Raise ``ValueError`` for empty, faceless, or flat meshes.

        Args:
            mesh: A ``pyvista.PolyData`` instance to validate.

        Raises:
            ValueError: If the mesh lacks points, cells, or vertical relief.
        """
        import numpy as np  # Local import to avoid mandatory NumPy at module load
        import pyvista as pv  # Local import; heavy but only needed when validating

        if mesh is None or mesh.n_points == 0:
            raise ValueError("Mesh has no points")

        if not (mesh.faces.size or mesh.lines.size):
            raise ValueError("Mesh has no cells (faces/lines)")

        z = np.asarray(mesh.points)[:, 2]
        if np.isclose(np.ptp(z), 0.0, atol=1e-6):
            raise ValueError("Mesh appears flat (no Z variation)")

    # ------------------------------------------------------------------
    #   Task 12 – Display decimation helper
    # ------------------------------------------------------------------
    def _prepare_display_mesh(self, mesh):  # noqa: ANN001
        """Return mesh or a decimated copy if face-count exceeds threshold.

        Decimation is *display-only* – a deep copy is made so the underlying
        project data remain untouched.  Any failure falls back to the original
        mesh and logs a warning.
        """
        try:
            import pyvista as pv  # Local heavy import
        except ModuleNotFoundError:
            return mesh  # PyVista not available (e.g., tests)

        if not isinstance(mesh, pv.PolyData):
            return mesh

        if getattr(mesh, "n_faces", 0) <= MAX_FACES_FOR_FULL_RENDER:
            return mesh

        try:
            mesh_copy = mesh.copy(deep=True)
            decimated = mesh_copy.decimate_pro(
                target_reduction=DECIMATE_RATIO,
                preserve_topology=True,
                splitting=False,
            )
            # Provide feedback for manual smoke-tests
            print(
                f"[PvDock] Decimated mesh from {mesh.n_faces} to {decimated.n_faces} faces",
            )
            return decimated
        except Exception as exc:  # pragma: no cover
            print(f"[PvDock] Warning: decimation failed – using full mesh. ({exc})")
            return mesh

    # ---------- NEW: Task 5-A: Actor Management -------------
    def add_actor(self, mesh_actor: MeshActor) -> None:
        """Adds a MeshActor to the plotter and registry.

        Validates the mesh, adds it to the PyVista plotter, stores the
        PyVista actor in mesh_actor.actor, and registers the MeshActor.
        Assumes the mesh in mesh_actor is already a pv.PolyData object.
        """
        if not mesh_actor or not mesh_actor.mesh or not hasattr(mesh_actor.mesh, "n_points"):
            print(f"Invalid MeshActor or mesh provided for surface: {mesh_actor.surface_name if mesh_actor else 'Unknown'}")
            return

        try:
            self._validate_polydata(mesh_actor.mesh)
        except ValueError as e:
            print(f"Mesh validation failed for '{mesh_actor.surface_name}': {e}")
            # Potentially remove from registry if it was somehow pre-added, or mark as invalid
            return

        # If an actor with the same name already exists, remove it first
        if mesh_actor.surface_name in self.mesh_actors:
            print(f"Removing existing actor for '{mesh_actor.surface_name}' before adding new one.")
            self.remove_actor(mesh_actor.surface_name)

        try:
            # Prepare mesh for display – decimate if necessary (Task 12)
            disp_mesh = self._prepare_display_mesh(mesh_actor.mesh)

            # Add mesh to the plotter using MeshActor properties
            # Note: self.plotter.add_mesh returns the vtkActor
            pv_actor = self.plotter.add_mesh(
                disp_mesh,
                color=mesh_actor.color.name() if mesh_actor.color else None, # QColor to hex/name string
                style=mesh_actor.representation, # 'surface', 'wireframe', 'points'
                opacity=mesh_actor.opacity,
                show_edges=mesh_actor.representation == "surface_with_edges", # Custom handling might be needed for this style
                edge_color=mesh_actor.edge_color.name() if mesh_actor.edge_color else None,
                line_width=mesh_actor.line_width,
                point_size=mesh_actor.point_size,
                name=mesh_actor.surface_name,
                smooth_shading=True # Defaulting to smooth shading, can be a MeshActor property
            )
            # Apply current Z-exaggeration factor
            try:
                pv_actor.SetScale(1.0, 1.0, getattr(self, "z_factor", 1.0))
            except Exception:
                pass
            pv_actor.SetVisibility(mesh_actor.visible)
            mesh_actor.actor = pv_actor # Store the PyVista actor back into our dataclass
            self.mesh_actors[mesh_actor.surface_name] = mesh_actor
            print(f"Actor for '{mesh_actor.surface_name}' added to plotter and registry.")

            # Ensure quality mode persists for new actor
            if not self.draft_chk.isChecked():
                self._set_high_quality()

        except Exception as e:
            print(f"Error adding mesh '{mesh_actor.surface_name}' to plotter: {e}")
            # Clean up if partial add occurred, though add_mesh usually handles its errors

    # ------------------------------------------------------------------
    #   Section-plane (clip) widget helpers – Task 6
    # ------------------------------------------------------------------
    def _ensure_plane_widget(self) -> None:
        """Create the shared VTK plane and PyVista widget once per viewer.

        The widget is instantiated lazily and re-used for subsequent projects.
        """
        if self._plane_widget is not None:
            return  # Already created

        # Local (lazy) imports to avoid heavy VTK/PyVista cost on module load
        import vtk  # type: ignore

        # Shared geometric plane (stores origin/normal)
        self._vtk_plane = vtk.vtkPlane()

        # Determine sensible defaults for origin/bounds from the current scene
        origin = getattr(self.plotter, "center", (0, 0, 0))
        bounds = getattr(self.plotter, "bounds", None)

        # PyVista add_plane_widget returns a vtkImplicitPlaneWidget2-like helper
        self._plane_widget = self.plotter.add_plane_widget(
            callback=self._on_plane_moved,
            normal=(0, 0, 1),  # Clip along Z
            assign_to_axis="z",
            origin=origin,
            bounds=bounds,
            color="yellow",
            implicit=False,
            tubing=False,
        )

        # Start disabled – becomes active when the toolbar toggle is on.
        try:
            self._plane_widget.SetEnabled(False)  # type: ignore[attr-defined]
        except AttributeError:
            # Some backends expose `.enabled` instead of `SetEnabled`.
            setattr(self._plane_widget, "enabled", False)

    def _on_plane_moved(self, normal, origin):  # noqa: ANN001
        """Callback – apply clipping to all actors when the plane moves."""
        if self._vtk_plane is None:
            return

        # Update the shared plane object (VTK expects a point + normal)
        self._vtk_plane.SetOrigin(origin)
        self._vtk_plane.SetNormal(normal)

        # Apply clipping to every registered actor
        for ma in self.mesh_actors.values():
            if ma.actor is None:
                continue
            mapper = getattr(ma.actor, "mapper", None)
            if mapper is None:
                continue
            # Remove previous clipping planes to keep only the current one
            if hasattr(mapper, "RemoveAllClippingPlanes"):
                mapper.RemoveAllClippingPlanes()
            # Add the updated plane
            if hasattr(mapper, "AddClippingPlane"):
                mapper.AddClippingPlane(self._vtk_plane)

        # Redraw scene
        self.plotter.render()

        # Persist last origin so the slice is restored when reopening
        if hasattr(self.main, "project_controller"):
            proj = self.main.project_controller.get_current_project()
            if proj is not None and hasattr(proj, "metadata"):
                proj.metadata["3d_section_plane"] = {"origin": origin, "normal": normal}

    # ------------------------------------------------------------------
    #   Toolbar/menu actions
    # ------------------------------------------------------------------
    def _toggle_section(self, enabled: bool) -> None:
        """Enable/disable the section-plane widget and clipping."""
        # Lazily create the widget on first use
        self._ensure_plane_widget()

        if self._plane_widget is None:
            return

        # Enable/disable the interactive widget itself
        try:
            self._plane_widget.SetEnabled(enabled)  # type: ignore[attr-defined]
        except AttributeError:
            setattr(self._plane_widget, "enabled", enabled)

        if enabled and self._vtk_plane is not None:
            try:
                normal = self._vtk_plane.GetNormal()  # type: ignore[attr-defined]
                origin = self._vtk_plane.GetOrigin()  # type: ignore[attr-defined]
                self._on_plane_moved(normal, origin)
            except Exception:  # pragma: no cover
                pass

        # When disabling, remove clipping planes from all actors
        if not enabled:
            for ma in self.mesh_actors.values():
                if ma.actor is None:
                    continue
                mapper = getattr(ma.actor, "mapper", None)
                if mapper and hasattr(mapper, "RemoveAllClippingPlanes"):
                    mapper.RemoveAllClippingPlanes()
            self.plotter.render()

    def _reset_section_plane(self) -> None:
        """Re-centre the section plane and clear all clipping."""
        if self._vtk_plane is None:
            return

        # Calculate middle of current Z bounds
        zmin, zmax = self.plotter.bounds[4:6]
        zmid = (zmin + zmax) / 2.0
        origin = (0, 0, zmid)

        # Perform reset via the common callback to ensure state sync
        self._on_plane_moved((0, 0, 1), origin)

        # Ensure widget itself moves visually (if backend supports it)
        try:
            if hasattr(self._plane_widget, "SetOrigin"):
                self._plane_widget.SetOrigin(origin)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------
    #   Layer-dock sync handlers – Task 7-B
    # ------------------------------------------------------------------
    def _on_layer_color(self, layer_id: str, new_hex: str):  # noqa: ANN001
        """Update mesh actor colour in response to layer colour edits."""
        from PySide6.QtGui import QColor  # Local import to avoid heavy Qt early

        new_qcolor = QColor(new_hex)
        for ma in self.mesh_actors.values():
            if ma.surface_name == layer_id:
                ma.color = new_qcolor
                if ma.actor is not None and hasattr(ma.actor, "prop"):
                    # Most backends expose prop.color or SetColor – we use attr.
                    try:
                        ma.actor.prop.color = new_qcolor.name()
                    except Exception:  # pragma: no cover
                        pass
        self._sync_plotter_legend()
        self.plotter.render()

    def _on_layer_visibility(self, layer_id: str, visible: bool):  # noqa: ANN001
        """Show or hide 3-D actors when layer visibility toggles."""
        for ma in self.mesh_actors.values():
            if ma.surface_name == layer_id:
                ma.visible = visible
                if ma.actor is not None:
                    try:
                        ma.actor.SetVisibility(visible)
                    except Exception:  # pragma: no cover
                        pass
        self._sync_plotter_legend()
        self.plotter.render()

    # ------------------------------------------------------------------
    #   Z-exaggeration slider handler
    # ------------------------------------------------------------------
    def _on_z_factor_changed(self, value: int):
        """Apply vertical exaggeration to all current actors."""
        self.z_factor = float(value)

        for ma in self.mesh_actors.values():
            if ma.actor is not None and hasattr(ma.actor, "SetScale"):
                try:
                    ma.actor.SetScale(1.0, 1.0, self.z_factor)
                except Exception:  # pragma: no cover
                    pass

        # Store factor so new actors adopt it in add_actor / load_surface
        self.plotter.render()

    # ------------------------------------------------------------------
    #   Draft quality toggle handler & helpers – Task 9-B
    # ------------------------------------------------------------------
    def _apply_quality_mode(self, draft: bool) -> None:
        """Toggle between draft and high-quality rendering."""
        if draft:
            self._set_draft_quality()
        else:
            self._set_high_quality()
        self.plotter.render()

    def _set_high_quality(self) -> None:
        """Enable anti-aliasing and eye-dome lighting once."""
        pl = self.plotter
        if not getattr(pl, "_aa_on", False):
            # Enable MSAA / FXAA if available
            if hasattr(pl, "enable_anti_aliasing"):
                try:
                    pl.enable_anti_aliasing()
                except Exception:
                    pass
            # Eye-dome lighting for depth shading (if supported)
            if hasattr(pl, "enable_eye_dome_lighting"):
                try:
                    pl.enable_eye_dome_lighting()
                except Exception:
                    pass
            pl._aa_on = True  # type: ignore[attr-defined]

    def _set_draft_quality(self) -> None:
        """Disable AA & EDL for faster rendering."""
        pl = self.plotter
        if getattr(pl, "_aa_on", False):
            if hasattr(pl, "disable_anti_aliasing"):
                try:
                    pl.disable_anti_aliasing()
                except Exception:
                    pass
            if hasattr(pl, "disable_eye_dome_lighting"):
                try:
                    pl.disable_eye_dome_lighting()
                except Exception:
                    pass
            pl._aa_on = False  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    #   Screenshot & Camera bookmark helpers – Task 10-B/C
    # ------------------------------------------------------------------
    def _take_screenshot(self):
        """Prompt user for PNG path and save a screenshot."""
        path, _ = QFileDialog.getSaveFileName(self, "Save PNG", "digcalc_view.png", "PNG files (*.png)")
        if path:
            try:
                if hasattr(self.plotter, "screenshot"):
                    self.plotter.screenshot(path, transparent_background=True)
                # Optionally: status bar message
                if hasattr(self.main, "statusBar"):
                    self.main.statusBar().showMessage(f"Saved screenshot to {path}", 3000)
            except Exception as exc:  # pragma: no cover
                print(f"Screenshot failed: {exc}")

    def _add_bookmark(self):
        """Ask name and store current camera position to project metadata."""
        name, ok = QInputDialog.getText(self, "Bookmark Name", "Enter a name:")
        if not ok or not name:
            return
        cam = self.plotter.camera_position

        proj = None
        if hasattr(self.main, "project_controller"):
            proj = self.main.project_controller.get_current_project()
        if proj is None:
            return

        if not hasattr(proj, "metadata"):
            proj.metadata = {}  # type: ignore[attr-defined]
        bm = proj.metadata.setdefault("3d_bookmarks", {})
        bm[name] = cam
        self._refresh_bookmark_menu()

    def _refresh_bookmark_menu(self):
        """Populate bookmark dropdown from current project's metadata."""
        if not hasattr(self, "book_menu"):
            return
        self.book_menu.clear()

        proj = None
        if hasattr(self.main, "project_controller"):
            proj = self.main.project_controller.get_current_project()
        if proj is None:
            return
        if not hasattr(proj, "metadata"):
            return
        for name, cam in proj.metadata.get("3d_bookmarks", {}).items():  # type: ignore[attr-defined]
            act = self.book_menu.addAction(name)
            act.triggered.connect(lambda _chk=False, c=cam: self._goto_camera(c))

    def _goto_camera(self, cam_pos):  # noqa: ANN001
        """Jump to a stored camera position."""
        try:
            self.plotter.camera_position = cam_pos
            self.plotter.render()
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------
    #   Legend helpers – Task 11
    # ------------------------------------------------------------------
    def _current_legend_entries(self):
        """Return list of (name, "#RRGGBB") for visible MeshActors."""
        return [
            (ma.surface_name, ma.color.name() if ma.color else "#ffffff")
            for ma in self.mesh_actors.values()
            if ma.visible
        ]

    def _sync_plotter_legend(self) -> None:
        """Add or remove the in-scene legend to mirror 2-D layer dock."""
        # Remove existing legend actor if present
        if getattr(self.plotter, "_digcalc_legend_actor", None) is not None:
            try:
                self.plotter.remove_actor(self.plotter._digcalc_legend_actor)  # type: ignore[attr-defined]
            except Exception:
                pass
            self.plotter._digcalc_legend_actor = None  # type: ignore[attr-defined]

        entries = self._current_legend_entries()
        if len(entries) >= 2 and hasattr(self.plotter, "add_legend"):
            try:
                self.plotter._digcalc_legend_actor = self.plotter.add_legend(
                    entries,
                    face="rectangle",
                    bcolor="white",
                    border=True,
                    size=(0.15, 0.12),
                    loc="lower right",
                )
            except Exception:  # pragma: no cover
                self.plotter._digcalc_legend_actor = None  # type: ignore[attr-defined]

        self.plotter.render()
