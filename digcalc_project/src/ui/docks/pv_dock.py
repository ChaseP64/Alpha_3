from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QComboBox,
    QToolBar,
    QLabel,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from functools import cached_property
from importlib import import_module


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
        v.addWidget(tb)

        # Surface selector ----------------------------------------------------
        self.surf_cb = QComboBox()
        self.surf_cb.currentTextChanged.connect(self._load_surface)
        v.addWidget(self.surf_cb)

        # 3-D viewport / fallback banner --------------------------------------
        if self._pv is None:
            v.addWidget(
                QLabel(
                    "PyVista not available.\nInstall with  pip install \"digcalc[3d]\""
                )
            )
            return

        v.addWidget(self._qtint)
        self._populate_combo()
        self._load_surface(self.surf_cb.currentText())

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
        """Create and cache a :class:`pyvistaqt.QtInteractor`."""
        from pyvistaqt import QtInteractor

        return QtInteractor(self, auto_update=True)

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _populate_combo(self) -> None:
        """Populate the surface combo-box with project surfaces that exist."""
        self.surf_cb.clear()
        proj = self.main.project_controller.project
        for name in ("Existing", "Design", "Stripping", "Lowest"):
            if getattr(proj, f"{name.lower()}_surface", None):
                self.surf_cb.addItem(name)

    def _load_surface(self, name: str) -> None:
        """Load *name* surface into the 3-D view."""
        if self._pv is None or not name:
            return
        proj = self.main.project_controller.project
        surf = getattr(proj, f"{name.lower()}_surface")
        if not surf:
            return

        # Dynamic import to avoid invalid identifier issue with "3d" package name.
        surface_to_polydata = import_module("digcalc_project.src.ui.3d.pv_view").surface_to_polydata

        mesh = surface_to_polydata(surf)
        self._qtint.clear()
        self._qtint.add_mesh(mesh, scalars="dz", cmap="RdYlGn_r")
        # Compass (orientation marker)
        self._qtint.add_orientation_widget()
        # MSAA (if available)
        self._qtint.ren_win.SetMultiSamples(4)
        self._qtint.reset_camera()

    def _toggle_wire(self, on: bool) -> None:
        """Toggle between wire-frame and shaded surface representation."""
        if self._pv is None:
            return
        self._qtint.set_representation("wireframe" if on else "surface")
