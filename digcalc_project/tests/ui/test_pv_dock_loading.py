from __future__ import annotations

import pytest
# from pytestqt.qt_compat import qt_api # To get QApplication instance
from PySide6.QtWidgets import QApplication, QWidget # Added QWidget
from unittest.mock import MagicMock
import sys
from types import ModuleType
from typing import TYPE_CHECKING # Added

# Assuming PvDock and Surface model paths are now for type checking only
if TYPE_CHECKING:
    from digcalc_project.src.models.surface import Surface
    from digcalc_project.src.ui.docks.pv_dock import PvDock

# We'll need a mock Project class or a very simple one for testing
# For PyVista related tests, we might need to patch pyvista if it's heavy
# or ensure tests can run headlessly. The pv_plotter_singleton tests handle this.

# -----------------------------------------------------------------------------
# Patch pyvistaqt with a headless dummy so VTK/OpenGL is never touched in CI.
# -----------------------------------------------------------------------------
class _DummyActor:  # Minimal vtkActor stub
    def __init__(self, mesh):
        from types import SimpleNamespace

        class _DummyMapper:
            """Lightweight stand-in for a VTK mapper that tracks clipping planes."""

            def __init__(self, dataset):
                self.dataset = dataset
                self._clipping_planes = []

            # Clipping-plane API subset -------------------------------------------------
            def RemoveAllClippingPlanes(self):  # noqa: D401
                self._clipping_planes.clear()

            def AddClippingPlane(self, plane):  # noqa: D401
                self._clipping_planes.append(plane)

            def GetNumberOfClippingPlanes(self):  # noqa: D401
                return len(self._clipping_planes)

        self._visible = True
        self._mesh = mesh
        self._scale = (1.0, 1.0, 1.0)
        # Mimic PyVista mapper with dataset attribute and clipping-plane helpers
        self.mapper = _DummyMapper(dataset=mesh)
        # Prop stub with representation attribute
        self.prop = SimpleNamespace(representation="surface", color="#ffffff")

    # VTK-actor-like helpers used by PvDock
    def GetVisibility(self):
        return self._visible

    def SetVisibility(self, flag: bool):  # noqa: D401
        self._visible = flag

    @property
    def bounds(self):  # noqa: D401
        return self._mesh.bounds if hasattr(self._mesh, "bounds") else (0, 0, 0, 0, 0, 0)

    # Scale helpers ---------------------------------------------------------
    def SetScale(self, sx: float, sy: float, sz: float):  # noqa: D401
        self._scale = (sx, sy, sz)

    def GetScale(self):  # noqa: D401
        return self._scale


class _DummyPlotter:
    """Headless replacement for pyvistaqt.BackgroundPlotter used in tests."""

    def __init__(self, *args, **kwargs):  # noqa: ANN401
        from PySide6.QtWidgets import QWidget  # Imported here to avoid unused Qt in other tests
        from types import SimpleNamespace

        # Scene bounds – (xmin, xmax, ymin, ymax, zmin, zmax)
        self._bounds = (0.0, 1.0, 0.0, 1.0, 0.0, 1.0)

        # Basic attributes that PvDock expects
        self.interactor = QWidget()
        self.enable_anti_aliasing_called = False
        self.enable_trackball_style_called = False
        # Faux renderer with actors dict & bounds property
        self.renderer = SimpleNamespace(actors={}, bounds=self._bounds)
        # Render window stub with MSAA setter
        self.ren_win = SimpleNamespace(SetMultiSamples=lambda *a, **k: None)
        # Camera stub
        self._parallel = True
        self.camera = SimpleNamespace(GetParallelProjection=lambda: self._parallel)

        # Convenience attributes mirroring real PyVistaPlotter
        self.center = (
            (self._bounds[0] + self._bounds[1]) / 2,
            (self._bounds[2] + self._bounds[3]) / 2,
            (self._bounds[4] + self._bounds[5]) / 2,
        )

        # Quality flags ------------------------------------------------------
        self._aa_on = False  # Tracks anti-aliasing/EDL status

        # Camera position storage
        self._cam_position = "iso"

    # -------------------------------------------------------
    # Properties & simple helpers
    # -------------------------------------------------------
    @property
    def bounds(self):  # noqa: D401
        return self._bounds

    # API methods touched by PvDock
    def enable_anti_aliasing(self):
        self.enable_anti_aliasing_called = True
        self._aa_on = True

    def enable_trackball_style(self):
        self.enable_trackball_style_called = True

    def add_mesh(self, mesh, **kwargs):  # noqa: ANN001
        actor = _DummyActor(mesh)
        # Use id(actor) as key similar to VTK actor hashable behaviour
        self.renderer.actors[id(actor)] = actor
        return actor

    def clear(self):
        self.renderer.actors.clear()

    clear_actors = clear  # Alias PyVista method name

    def reset_camera(self, *args, **kwargs):  # noqa: D401
        pass  # No-op for tests

    def render(self):  # noqa: D401
        pass

    def enable_parallel_projection(self):  # noqa: D401
        self._parallel = True

    def add_axes(self, *args, **kwargs):  # noqa: D401
        pass

    def add_scale_bar(self, *args, **kwargs):  # noqa: D401
        pass

    def add_orientation_widget(self, *args, **kwargs):  # noqa: D401
        pass

    # Convenience so PvDock can call close on quit
    def close(self):  # noqa: D401
        pass

    # Section-plane widget --------------------------------------------------
    def add_plane_widget(
        self,
        callback,  # noqa: ANN001
        **kwargs,  # noqa: ANN401
    ):  # noqa: D401
        """Return a lightweight stub that supports `SetEnabled`."""

        class _DummyPlaneWidget:
            def __init__(self, cb):
                self._enabled = True
                self._cb = cb

            def SetEnabled(self, flag: bool):  # noqa: D401
                self._enabled = flag

            def GetEnabled(self):  # noqa: D401
                return self._enabled

            # Convenience for tests to mimic VTK API
            enabled = property(GetEnabled, SetEnabled)

        return _DummyPlaneWidget(callback)

    # Quality helpers -------------------------------------------------------
    def disable_anti_aliasing(self):
        self._aa_on = False

    # Eye-dome lighting stubs
    def enable_eye_dome_lighting(self):
        self._aa_on = True

    def disable_eye_dome_lighting(self):
        self._aa_on = False

    # Camera position property ---------------------------------------------
    @property
    def camera_position(self):  # noqa: D401
        return self._cam_position

    @camera_position.setter
    def camera_position(self, val):  # noqa: D401
        self._cam_position = val

    # Screenshot stub -------------------------------------------------------
    def screenshot(self, path, transparent_background=True):  # noqa: D401
        # Create an empty file to simulate screenshot saving
        with open(path, "wb") as f:
            f.write(b"")

    # Legend helpers --------------------------------------------------------
    def add_legend(self, entries, **kwargs):  # noqa: ANN001
        # Just store entries for inspection
        actor = {"entries": entries}
        return actor

    def remove_actor(self, actor):  # noqa: D401
        # No-op in tests
        pass


@pytest.fixture(autouse=True)
def _patch_pyvistaqt(monkeypatch):
    """Replace the heavy pyvistaqt module with a lightweight stub."""

    dummy_mod = ModuleType("pyvistaqt")
    dummy_mod.BackgroundPlotter = _DummyPlotter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvistaqt", dummy_mod)

    # -------------------------------------------------------------
    # Provide a minimal stub for 'vtk' if not available on CI
    # -------------------------------------------------------------
    if "vtk" not in sys.modules:
        vtk_stub = ModuleType("vtk")

        class _StubPlane:  # Basic stand-in for vtkPlane
            def __init__(self):
                self._origin = (0, 0, 0)
                self._normal = (0, 0, 1)

            def SetOrigin(self, origin):  # noqa: D401
                self._origin = origin

            def SetNormal(self, normal):  # noqa: D401
                self._normal = normal

            # Accessors for compatibility
            def GetOrigin(self):  # noqa: D401
                return self._origin

            def GetNormal(self):  # noqa: D401
                return self._normal

        vtk_stub.vtkPlane = _StubPlane  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "vtk", vtk_stub)

    # Ensure previous import of the singleton helper is cleared so it picks up the dummy
    sys.modules.pop("digcalc_project.src.ui.pv_plotter_singleton", None)
    yield
    # Cleanup to avoid leakage into other tests
    sys.modules.pop("pyvistaqt", None)
    sys.modules.pop("vtk", None)
    sys.modules.pop("digcalc_project.src.ui.pv_plotter_singleton", None) # Reinstated cleanup

# Import Surface at runtime after pyvistaqt is patched
# The return annotation is a forward reference to avoid mypy issues without import at module level.
@pytest.fixture
def sample_surface() -> "Surface":
    """Returns a sample Surface object with Z-variation."""
    from digcalc_project.src.models.surface import Surface  # Local import after patch

    s = Surface(name="SampleExisting")
    s.vertices = [
        (0, 0, 1), (1, 0, 1.5), (0, 1, 1), (1, 1, 2.0),  # zmin=1, zmax=2
    ]
    s.triangles = [
        (0, 1, 2), (1, 3, 2)
    ]
    return s

# -----------------------------------------------------------------------------
# Project fixture using the dynamic Surface import
# -----------------------------------------------------------------------------

@pytest.fixture
def tmp_project(sample_surface) -> MagicMock:  # noqa: ANN001
    """Returns a mock Project object with one sample surface."""
    project = MagicMock()
    project.name = "TestProject"
    project.surfaces = {"Existing": sample_surface}
    project.metadata = {}
    # Mock other attributes if PvDock initialization or load_project accesses them
    project.path = "dummy/path/project.dcp" 
    return project

# -----------------------------------------------------------------------------
# Mock MainWindow fixture (QWidget subclass)
# -----------------------------------------------------------------------------
@pytest.fixture
def main_window_mock() -> MagicMock:
    """Returns a mock MainWindow instance that is also a QWidget."""
    # Create a real QWidget to satisfy QDockWidget's parent requirement
    mw_widget = QWidget()
    
    # Attach MagicMock attributes for controller access
    mw_widget.project_controller = MagicMock()
    # Ensure that during PvDock.__init__, no faulty project is loaded by default
    mw_widget.project_controller.get_current_project = MagicMock(return_value=None)

    # Mock any other attributes of MainWindow that PvDock might access
    # For example, if it accesses main_window.statusBar():
    # mw_widget.statusBar = MagicMock(return_value=MagicMock())
    
    return mw_widget # Return the QWidget with mocked attributes

def test_first_surface_visible(qtbot, tmp_project: MagicMock, main_window_mock: QWidget, sample_surface):  # noqa: ANN001
    """
    Test that PvDock loads the first surface of a project, it's visible,
    and has Z-variation.
    """
    # Ensure a QApplication instance exists for Qt widgets
    app = QApplication.instance() # Try to get existing instance
    if app is None:
        app = QApplication([]) # Create if none exists

    # Initialize PvDock with the mock main window
    # PvDock's __init__ takes main_window as an argument
    from digcalc_project.src.ui.docks.pv_dock import PvDock  # Import after dummy patch
    dock = PvDock(main_window_mock)
    qtbot.addWidget(dock) # Register dock with qtbot for cleanup

    # Directly call load_project, PvDock's init tries to load from combo if populated.
    # The signal connection for project_loaded -> load_project is what we'd normally rely on,
    # but for a direct unit test of load_project's effect, this is fine.
    dock.load_project(tmp_project)
    dock.show() # Make sure the dock widget itself is shown
    qtbot.waitExposed(dock, timeout=1000) # Wait for the widget to be exposed
    qtbot.wait(200) # Allow render cycles and event processing

    # Assertions
    # 1. An actor for the surface should be present in the plotter.
    #    The orientation widget might also be an actor. We expect at least one data actor.
    #    `_current_actor` should be the one we added.
    assert dock._current_actor is not None, "No current actor set in PvDock"
    assert dock._current_actor in dock.plotter.renderer.actors.values(), "PvDock's current_actor not in plotter"
    
    # Check if there are any actors at all.
    # The orientation widget (axes) is also an actor. So, expect > 1 if data + axes.
    # If only one surface is loaded, and it is the _current_actor
    # If axes are added, total actors could be 2 (surface + axes).
    # Let's check if the specific actor (dock._current_actor) is visible and has geometry.
    
    assert dock._current_actor.GetVisibility(), "Surface actor should be visible"
    assert dock._current_actor.mapper.dataset.n_points > 0, "Actor's mesh has no points"

    # 2. The mesh should have Z-variation (not flat).
    #    The bounds are (xmin, xmax, ymin, ymax, zmin, zmax).
    bounds = dock._current_actor.bounds # Use actor's bounds for precision
    assert bounds[4] < bounds[5], f"Mesh appears flat: zmin={bounds[4]}, zmax={bounds[5]}"

    # 3. Camera should be set correctly (isometric view implies parallel projection)
    # assert dock.plotter.camera_position == 'iso', "Camera position not 'iso'" # Getter returns coords, not string
    assert dock.plotter.camera.GetParallelProjection(), "Camera should be in parallel projection for isometric view"
    
    # Clean up plotter to avoid issues in subsequent tests if any
    dock.plotter.clear()
    if hasattr(dock.plotter, "close"): # Singleton plotter might not be closed by dock itself
        pass # Singleton is closed on app quit 

# -----------------------------------------------------------------------------
# Section-plane GUI test – Task 6-D
# -----------------------------------------------------------------------------

def _make_surface(z_offset: float):
    """Helper to create a simple 1×1 square surface at a given Z."""
    from digcalc_project.src.models.surface import Surface  # Local import after patch

    s = Surface(name=f"Layer{z_offset}")
    s.vertices = [
        (0, 0, z_offset),
        (1, 0, z_offset + 0.2),
        (0, 1, z_offset - 0.1),
    ]
    s.triangles = [(0, 1, 2)]
    return s


@pytest.fixture
def three_layer_project() -> MagicMock:  # noqa: ANN001
    """Project with three stacked layers for clipping tests."""
    project = MagicMock()
    project.name = "ClipTestProject"
    layers = [
        _make_surface(0.0),
        _make_surface(0.5),
        _make_surface(1.0),
    ]
    project.surfaces = {s.name: s for s in layers}
    project.metadata = {}
    return project


def test_section_plane_clips(qtbot, three_layer_project, main_window_mock):  # noqa: ANN001
    """Verify that moving the section plane sets one clipping plane on every actor."""
    app = QApplication.instance() or QApplication([])

    from digcalc_project.src.ui.docks.pv_dock import PvDock  # Import after dummy patch

    dock = PvDock(main_window_mock)
    qtbot.addWidget(dock)

    dock.load_project(three_layer_project)
    dock._ensure_plane_widget()

    # Simulate moving the plane to the midpoint in Z
    normal = (0, 0, 1)
    zmin, zmax = dock.plotter.bounds[4:6]
    zmid = (zmin + zmax) / 2.0
    origin = (0, 0, zmid)
    dock._on_plane_moved(normal, origin)

    clipped_counts = [
        ma.actor.mapper.GetNumberOfClippingPlanes()
        for ma in dock.mesh_actors.values()
        if ma.actor is not None
    ]
    assert clipped_counts and all(c == 1 for c in clipped_counts), "Actors should have exactly one clipping plane"

    # Move plane below model to ensure still exactly one plane but no crash
    new_origin = (0, 0, zmin - 1.0)
    dock._on_plane_moved(normal, new_origin)
    unclipped_counts = [
        ma.actor.mapper.GetNumberOfClippingPlanes()
        for ma in dock.mesh_actors.values()
        if ma.actor is not None
    ]
    assert all(c == 1 for c in unclipped_counts), "Actors should retain a single clipping plane after move" 

# -----------------------------------------------------------------------------
# Z-exaggeration slider test – Task 8-D
# -----------------------------------------------------------------------------

def test_z_slider_scales_actors(qtbot, three_layer_project, main_window_mock):  # noqa: ANN001
    app = QApplication.instance() or QApplication([])

    from digcalc_project.src.ui.docks.pv_dock import PvDock

    dock = PvDock(main_window_mock)
    qtbot.addWidget(dock)

    dock.load_project(three_layer_project)

    # Increase exaggeration to 3×
    dock.z_slider.setValue(3)

    # All actors should report scale z == 3
    for ma in dock.mesh_actors.values():
        if ma.actor is None:
            continue
        sx, sy, sz = ma.actor.GetScale()
        assert sz == 3.0, "Actor Z scale should match slider value" 

# -----------------------------------------------------------------------------
# Draft quality mode test – Task 9-E
# -----------------------------------------------------------------------------

def test_draft_toggle_disables_aa(qtbot, three_layer_project, main_window_mock):  # noqa: ANN001
    app = QApplication.instance() or QApplication([])

    from digcalc_project.src.ui.docks.pv_dock import PvDock

    dock = PvDock(main_window_mock)
    qtbot.addWidget(dock)

    dock.load_project(three_layer_project)

    # High-quality should be enabled by default
    assert getattr(dock.plotter, "_aa_on", False), "AA should be on by default"

    # Toggle draft mode ON
    dock.draft_chk.setChecked(True)
    assert not getattr(dock.plotter, "_aa_on", True), "AA flag should be off in draft mode"

    # Toggle draft mode OFF
    dock.draft_chk.setChecked(False)
    assert getattr(dock.plotter, "_aa_on", False), "AA flag should be back on after disabling draft mode" 

# -----------------------------------------------------------------------------
# Camera bookmark test – Task 10-D
# -----------------------------------------------------------------------------

def test_bookmark_added(qtbot, tmp_project, main_window_mock):  # noqa: ANN001
    app = QApplication.instance() or QApplication([])

    from digcalc_project.src.ui.docks.pv_dock import PvDock

    dock = PvDock(main_window_mock)
    qtbot.addWidget(dock)

    # Ensure the project controller returns our tmp_project
    main_window_mock.project_controller.get_current_project.return_value = tmp_project

    # Load project and refresh bookmarks
    dock.load_project(tmp_project)

    # Simulate programmatic bookmark addition
    cam = dock.plotter.camera_position
    tmp_project.metadata["3d_bookmarks"] = {"ISO": cam}
    dock._refresh_bookmark_menu()

    actions = dock.book_menu.actions()
    assert actions, "Bookmark menu should have at least one action"
    assert actions[0].text() == "ISO", "Bookmark name should match the stored key" 

# -----------------------------------------------------------------------------
# Legend visibility test – Task 11-D
# -----------------------------------------------------------------------------

@pytest.fixture
def two_layer_project(sample_surface) -> MagicMock:  # noqa: ANN001
    """Project with two layers for legend tests."""
    project = MagicMock()
    project.name = "LegendProj"
    from copy import deepcopy
    surf2 = deepcopy(sample_surface)
    surf2.name = "Layer-2"
    project.surfaces = {"Layer-1": sample_surface, "Layer-2": surf2}
    project.metadata = {}
    return project

def test_legend_shows_with_two_layers(qtbot, two_layer_project, main_window_mock):  # noqa: ANN001
    app = QApplication.instance() or QApplication([])

    from digcalc_project.src.ui.docks.pv_dock import PvDock

    dock = PvDock(main_window_mock)
    qtbot.addWidget(dock)

    main_window_mock.project_controller.get_current_project.return_value = two_layer_project

    dock.load_project(two_layer_project)

    # With two visible layers legend actor should exist
    assert getattr(dock.plotter, "_digcalc_legend_actor", None) is not None, "Legend actor should be created"

    # Hide one layer via visibility handler
    dock._on_layer_visibility("Layer-1", False)
    assert getattr(dock.plotter, "_digcalc_legend_actor", None) is None, "Legend actor should be removed when <2 layers visible" 

# -----------------------------------------------------------------------------
# Decimation unit test – Task 12-D
# -----------------------------------------------------------------------------


def test_oversize_mesh_is_decimated():
    import importlib
    pv_spec = importlib.util.find_spec("pyvista")
    if pv_spec is None:
        import pytest
        pytest.skip("pyvista not available; skipping decimation test")
    import pyvista as pv

    from digcalc_project.src.ui.docks.pv_dock import PvDock, MAX_FACES_FOR_FULL_RENDER

    # Create a sphere with faces > threshold
    res = int((MAX_FACES_FOR_FULL_RENDER ** 0.5) + 100)  # ensure larger
    big = pv.Sphere(theta_resolution=res, phi_resolution=res)
    dock = PvDock(main_window_mock := MagicMock())

    dec = dock._prepare_display_mesh(big)
    assert dec.n_faces < big.n_faces, "Decimation should reduce face count" 