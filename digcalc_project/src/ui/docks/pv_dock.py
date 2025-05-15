from functools import cached_property
from importlib import import_module

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QLabel,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


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

        # Body widget ---------------------------------------------------------
        body = QWidget(self)
        self.setWidget(body)
        v = QVBoxLayout(body)

        # Toolbar -------------------------------------------------------------
        tb = QToolBar()
        self.wire_act = QAction("Wireframe", self, checkable=True)
        self.wire_act.toggled.connect(self._toggle_wire)
        tb.addAction(self.wire_act)

        # Refresh action ---------------------------------------------------
        self.refresh_act = QAction("Refresh (F5)", self)
        self.refresh_act.setShortcut(QKeySequence.Refresh)  # F5 on most OSes
        # Ensure the shortcut works even when toolbar is not focused
        self.refresh_act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.refresh_act.triggered.connect(
            lambda: self._load_surface(self.surf_cb.currentText()),
        )
        tb.addAction(self.refresh_act)

        # Add toolbar to layout after actions are set up
        v.addWidget(tb)

        # Surface selector ----------------------------------------------------
        self.surf_cb = QComboBox()
        self.surf_cb.currentTextChanged.connect(self._load_surface)
        v.addWidget(self.surf_cb)

        # Actor handle for the displayed mesh so we can replace without
        # clearing the entire render window (helps avoid WGL driver bugs)
        self._current_actor = None

        # 3-D viewport / fallback banner --------------------------------------
        if self._pv is None:
            v.addWidget(
                QLabel(
                    'PyVista not available.\nInstall with  pip install "digcalc[3d]"',
                ),
            )
            return

        if self._qtint is None:
            v.addWidget(QLabel("PyVistaQt not available.\nInstall with  pip install pyvistaqt"))
            return

        v.addWidget(self._qtint)
        self._populate_combo()
        self._load_surface(self.surf_cb.currentText())

        # --- Keep combo up-to-date when project surfaces change ---
        if hasattr(self.main, "project_controller"):
            pc = self.main.project_controller
            # Re-populate whenever surfaces are rebuilt/modified
            if hasattr(pc, "surfaces_rebuilt"):
                pc.surfaces_rebuilt.connect(self._on_surfaces_rebuilt)  # type: ignore[arg-type]
            if hasattr(pc, "project_modified"):
                # Reload combo *and* mesh whenever project changes (new surfaces added)
                pc.project_modified.connect(self._on_surfaces_rebuilt)  # type: ignore[arg-type]
            # Lowest/composite surfaces update
            if hasattr(pc, "surfacesChanged"):
                pc.surfacesChanged.connect(self._on_surfaces_rebuilt)  # type: ignore[arg-type]
            # When a new project is loaded, refresh everything
            if hasattr(pc, "project_loaded"):
                pc.project_loaded.connect(lambda _p: self._on_surfaces_rebuilt())  # type: ignore[arg-type]

    # ---------------------------------------------------------------------
    # Lazy attributes (deferred imports)
    # ---------------------------------------------------------------------
    @cached_property
    def _pv(self):
        """Return imported PyVista module or *None* if not available."""
        try:
            import pyvista as pv

            return pv
        except ImportError:
            return None

    @cached_property
    def _qtint(self):
        """Create and cache a :class:`pyvistaqt.QtInteractor`, or *None* if package missing."""
        try:
            from pyvistaqt import QtInteractor  # Heavy import – inside try
        except ImportError:
            return None

        return QtInteractor(self, auto_update=True)

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
        # Populate combo with ALL surface names present in the project model
        if hasattr(proj, "surfaces") and isinstance(proj.surfaces, dict):
            for surf_name in sorted(proj.surfaces.keys()):
                self.surf_cb.addItem(surf_name)
        else:
            # Fallback for legacy attributes (Existing, Design…)
            for legacy in ("Existing", "Design", "Stripping", "Lowest"):
                if getattr(proj, f"{legacy.lower()}_surface", None):
                    self.surf_cb.addItem(legacy)

        # When the combo has entries but no active selection "currentIndex" is -1.
        # Selecting the first item guarantees that a mesh is always loaded the
        # first time the dock is opened – this will emit *currentTextChanged*
        # and therefore call :py:meth:`_load_surface` automatically.
        if self.surf_cb.count() and self.surf_cb.currentIndex() < 0:
            self.surf_cb.setCurrentIndex(0)

    def _load_surface(self, name: str) -> None:
        """Load *name* surface into the 3-D view."""
        if self._pv is None or not name:
            return
        proj = None
        if hasattr(self.main, "project_controller"):
            proj = self.main.project_controller.get_current_project()
        if proj is None:
            return
        # Try dictionary lookup first (new project model)
        surf = None
        if hasattr(proj, "surfaces") and isinstance(proj.surfaces, dict):
            surf = proj.surfaces.get(name)
        # Fallback to legacy attribute names if dict lookup failed
        if surf is None:
            surf = getattr(proj, f"{name.lower()}_surface", None)
        if surf is None:
            return

        # Dynamic import to avoid invalid identifier issue with "3d" package name.
        surface_to_polydata = import_module("digcalc_project.src.ui.3d.pv_view").surface_to_polydata

        mesh = surface_to_polydata(surf)

        # --------------------------------------------------------------
        # Replace existing mesh actor WITHOUT clearing the render window
        # Windows users with some GPU drivers hit wglMakeCurrent errors
        # when VTK tears-down the entire render window (Plotter.clear()).
        # Keeping the window alive and just swapping the mesh avoids
        # losing the OpenGL context and makes surface-switching robust.
        # --------------------------------------------------------------
        try:
            # Hide the previous actor instead of removing/clearing to avoid
            # driver-specific context teardown problems on Windows.
            if self._current_actor is not None:
                try:
                    self._current_actor.SetVisibility(False)  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover
                    pass

            # Add the new mesh (visible) and remember the actor
            self._current_actor = self._qtint.add_mesh(mesh, scalars="dz", cmap="RdYlGn_r")
        except Exception as exc:  # pragma: no cover
            # Fallback: clear window one last time if everything else fails
            print(f"3-D view fallback due to error hiding actor: {exc}")
            self._qtint.clear()
            self._current_actor = self._qtint.add_mesh(mesh, scalars="dz", cmap="RdYlGn_r")

        # Only add orientation widget once for the lifetime of the dock
        if not getattr(self, "_axes_added", False):
            try:
                if hasattr(self._qtint, "add_axes"):
                    self._qtint.add_axes()
                else:
                    # Older versions: fall back to add_orientation_widget with default actor
                    axes_actor = self._pv.Arrow() if hasattr(self._pv, "Arrow") else None
                    self._qtint.add_orientation_widget(axes_actor)
            except Exception as exc:  # pragma: no cover
                print(f"Warning: could not add orientation widget: {exc}")
            self._axes_added = True

        # MSAA (if available)
        self._qtint.ren_win.SetMultiSamples(4)
        self._qtint.reset_camera()

    def _toggle_wire(self, on: bool) -> None:
        """Toggle between wire-frame and shaded surface representation."""
        if self._pv is None:
            return
        self._qtint.set_representation("wireframe" if on else "surface")

    # ------------------------------------------------------------------
    #   Project-signal handlers
    # ------------------------------------------------------------------
    def _on_surfaces_rebuilt(self):
        """Refresh combo and ensure a visible mesh afterwards."""
        old = self.surf_cb.currentText()
        self._populate_combo()  # may auto-select first item & trigger _load_surface

        if not old:
            # There was *no* previous selection (viewer opened empty).  If the
            # combo now has entries ensure we show the first surface.
            if self.surf_cb.count():
                self.surf_cb.setCurrentIndex(0)  # Signal loads the mesh.
            return  # Nothing else to do – mesh already loading.

        # There *was* a previous selection – keep it if still present, else
        # fall back to the first surface.
        if self.surf_cb.findText(old) >= 0:
            # If the selection didn't actually change Qt will NOT emit
            # *currentTextChanged* – call _load_surface() explicitly.
            if self.surf_cb.currentText() == old:
                self._load_surface(old)
            else:
                # Setting the text changed the selection → signal will fire.
                self.surf_cb.setCurrentText(old)
        elif self.surf_cb.count():
            self.surf_cb.setCurrentIndex(0)  # First available – loads mesh.
