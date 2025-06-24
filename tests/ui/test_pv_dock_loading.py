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
        """Return a lightweight stub that supports `SetEnabled` and calls the callback."""

        class _DummyPlaneWidget:
            def __init__(self, cb):
                self._enabled = True
                self._cb = cb

            def SetEnabled(self, flag: bool):  # noqa: D401
                self._enabled = flag
                # When the widget is enabled/disabled, PvDock expects the callback to be fired.
                if self._cb and flag:
                    self._cb((0, 0, 1), (0, 0, 0))

            def GetEnabled(self):  # noqa: D401
                return self._enabled

            # Convenience for tests to mimic VTK API
            enabled = property(GetEnabled, SetEnabled)

        widget = _DummyPlaneWidget(callback)
        # Immediately invoke callback once to simulate initial placement
        if callback:
            callback((0, 0, 1), (0, 0, 0))
        return widget

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
        # Just store entries for inspection, and add it as a fake actor.
        actor = {"entries": entries, "_is_legend": True}
        # Use a consistent key for the legend actor so we can find it
        self.renderer.actors["legend"] = actor
        return actor

    def remove_actor(self, actor):  # noqa: D401
        # Find actor by dict value, since it's a mock
        key_to_del = None
        for k, v in self.renderer.actors.items():
            if v == actor:
                key_to_del = k
                break
        if key_to_del:
            del self.renderer.actors[key_to_del]


@pytest.fixture(autouse=True)
def _patch_pyvistaqt(monkeypatch):
    """Replace the heavy pyvistaqt module with a lightweight stub and inject into singleton."""

    dummy_mod = ModuleType("pyvistaqt")
    dummy_plotter_instance = _DummyPlotter()
    dummy_mod.BackgroundPlotter = lambda: dummy_plotter_instance
    monkeypatch.setitem(sys.modules, "pyvistaqt", dummy_mod)

    # Forcefully inject our test-specific dummy plotter into the singleton module
    # to override its "CI" detection logic.
    import digcalc_project.src.ui.pv_plotter_singleton as plotter_singleton
    monkeypatch.setattr(plotter_singleton, "_plotter", dummy_plotter_instance, raising=True)

    # Provide a minimal stub for 'vtk' if not available on CI
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
    if "digcalc_project.src.ui.pv_plotter_singleton" in sys.modules:
        del sys.modules["digcalc_project.src.ui.pv_plotter_singleton"]
    if "digcalc_project.src.ui.docks.pv_dock" in sys.modules:
        del sys.modules["digcalc_project.src.ui.docks.pv_dock"]

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
    """Mock project with one surface and dictionary for bookmarks."""
    p = MagicMock()
    p.surfaces = {"Sample": sample_surface}
    p.camera_bookmarks = {}  # Use a real dict here
    p.get_surface.return_value = sample_surface
    return p

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

@pytest.fixture
def pv_dock_with_parent(qtbot):
    """Create a PvDock with a persistent parent widget for testing."""
    # The parent widget must be kept alive for the duration of the test.
    parent_widget = QWidget()
    qtbot.addWidget(parent_widget) # Register for cleanup

    from digcalc_project.src.ui.docks.pv_dock import PvDock
    dock = PvDock(parent_widget)
    qtbot.addWidget(dock) # Also register the dock itself
    
    # Yield both so the test can use them, and they are not garbage collected
    yield dock, parent_widget

def test_first_surface_visible(qtbot, tmp_project, pv_dock_with_parent, sample_surface):  # noqa: ANN001
    """
    Test that PvDock loads the first surface of a project, it's visible,
    and has Z-variation.
    """
    dock, _ = pv_dock_with_parent
    # Set the project on the dock's parent (mock main_window)
    dock.main.project_controller = MagicMock()
    dock.main.project_controller.get_current_project.return_value = tmp_project
    
    dock.load_project(tmp_project)

    # Assert that one mesh actor was added to the dock's registry.
    # This is more specific than checking the raw plotter actors, which might include HUD elements.
    assert len(dock.mesh_actors) == 1, "Should have loaded one surface into the dock's actor registry."
    
    # Assert actor is visible and has scale
    actor = list(dock.mesh_actors.values())[0].actor
    assert actor.GetVisibility(), "Surface actor should be visible by default."
    # The default Z-exaggeration is 1.0, so we check that it's set.
    # The dummy actor scale is (1.0, 1.0, 1.0) by default. The logic to apply Z-scale happens on change.
    # Let's verify the initial state is as expected.
    assert actor.GetScale()[2] == 1.0, "Surface actor should have initial Z-scale of 1.0."

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
    """Mock project with three surfaces for section-plane testing."""
    p = MagicMock()
    p.surfaces = {
        "LayerA": _make_surface(0.0),
        "LayerB": _make_surface(5.0),
        "LayerC": _make_surface(10.0),
    }
    p.camera_bookmarks = {} # Ensure bookmarks attribute exists
    return p


# @pytest.mark.skip(reason="Temporarily disabled to unblock MainWindow refactoring. Needs fix.")
def test_section_plane_clips(qtbot, three_layer_project, pv_dock_with_parent):  # noqa: ANN001
    """Check that enabling the section plane clips all visible actors."""
    dock, _ = pv_dock_with_parent
    # Load project with three surfaces
    dock.load_project(three_layer_project)
    qtbot.wait(10)  # Allow signals to process

    # All three mesh actors should be in the dummy plotter
    assert len(dock.plotter.renderer.actors) == 3

    # Enable the section widget via the action
    print("Enabling section action...")
    dock.section_act.setChecked(True)
    qtbot.wait(10)

    # Manually trigger the callback to simulate the widget moving
    dock._on_plane_moved(normal=(0, 0, 1), origin=(0, 0, 0))
    qtbot.wait(10)

    # Check that the callback was fired and all actors have a clipping plane
    for actor in dock.plotter.renderer.actors.values():
        print(f"Checking actor {actor}. Mapper: {actor.mapper}")
        if hasattr(actor, "mapper"):
            num_planes = actor.mapper.GetNumberOfClippingPlanes()
            print(f"Actor has {num_planes} clipping planes.")
            assert num_planes == 1
        else:
            print("Actor has no mapper attribute.")

# -----------------------------------------------------------------------------
# Z-exaggeration slider test – Task 8-D
# -----------------------------------------------------------------------------

def test_z_slider_scales_actors(qtbot, three_layer_project, pv_dock_with_parent):  # noqa: ANN001
    dock, _ = pv_dock_with_parent
    dock.main.project_controller = MagicMock()
    dock.main.project_controller.get_current_project.return_value = three_layer_project
    dock.load_project(three_layer_project)

    # Move the slider
    dock.z_slider.setValue(3)

    # Check that all actors in the dock's registry were rescaled
    for mesh_actor in dock.mesh_actors.values():
        if mesh_actor.actor is None:
            continue
        assert mesh_actor.actor.GetScale()[2] == 3.0, "Actor Z-scale should match slider value."

# -----------------------------------------------------------------------------
# Draft quality mode test – Task 9-E
# -----------------------------------------------------------------------------

def test_draft_toggle_disables_aa(qtbot, three_layer_project, pv_dock_with_parent):  # noqa: ANN001
    """Verify that toggling Draft Mode on disables AA/EDL and toggling off re-enables it."""
    dock, _ = pv_dock_with_parent
    # Load project and ensure plotter exists
    dock.load_project(three_layer_project)
    qtbot.wait(10)
    plotter = dock.plotter
    assert plotter is not None

    # 1. Initial state: AA should be ON
    print(f"Initial AA state: {plotter._aa_on}")
    assert plotter._aa_on is True, "Plotter should have AA enabled by default"

    # 2. Enable Draft Mode -> AA should be OFF
    print("Enabling draft mode...")
    dock.draft_chk.setChecked(True)
    qtbot.wait(10)
    print(f"AA state after enabling draft mode: {plotter._aa_on}")
    assert plotter._aa_on is False, "Draft mode should disable AA"

    # 3. Disable Draft Mode -> AA should be ON again
    print("Disabling draft mode...")
    dock.draft_chk.setChecked(False)
    qtbot.wait(10)
    print(f"AA state after disabling draft mode: {plotter._aa_on}")
    assert plotter._aa_on is True, "Disabling draft mode should re-enable AA"

# -----------------------------------------------------------------------------
# Camera bookmark test – Task 10-D
# -----------------------------------------------------------------------------

def test_bookmark_added(qtbot, tmp_project, pv_dock_with_parent, monkeypatch):  # noqa: ANN001
    dock, _ = pv_dock_with_parent
    # Mock the project controller on the parent
    dock.main.project_controller = MagicMock()
    dock.main.project_controller.get_current_project.return_value = tmp_project
    # Mock the input dialog to return a name
    monkeypatch.setattr("PySide6.QtWidgets.QInputDialog.getText", lambda *args, **kwargs: ("My View", True))
    
    dock.load_project(tmp_project)
    dock._add_bookmark()

    assert "My View" in tmp_project.camera_bookmarks
    # Also check that the menu was updated
    assert len(dock.book_menu.actions()) > 0
    assert dock.book_menu.actions()[-1].text() == "My View"

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

def test_legend_shows_with_two_layers(qtbot, two_layer_project, pv_dock_with_parent):  # noqa: ANN001
    dock, _ = pv_dock_with_parent
    dock.main.project_controller = MagicMock()
    dock.main.project_controller.get_current_project.return_value = two_layer_project
    dock.load_project(two_layer_project)

    legend_actor = None
    for actor in dock.plotter.renderer.actors.values():
        if isinstance(actor, dict) and "_is_legend" in actor:
            legend_actor = actor
            break

    assert legend_actor is not None, "Legend actor should be present."
    assert len(legend_actor["entries"]) == 2, "Legend should have two entries."
    assert legend_actor["entries"][0][0].startswith("Layer")
    assert len({e[0] for e in legend_actor["entries"]}) == 2

# -----------------------------------------------------------------------------
# Decimation unit test – Task 12-D
# -----------------------------------------------------------------------------


def test_oversize_mesh_is_decimated(pv_dock_with_parent):
    import importlib
    pv_spec = importlib.util.find_spec("pyvista")
    if pv_spec is None:
        import pytest
        pytest.skip("pyvista not available; skipping decimation test")
    import pyvista as pv

    from digcalc_project.src.ui.docks.pv_dock import MAX_FACES_FOR_FULL_RENDER

    dock, _ = pv_dock_with_parent
    # Create a sphere with faces > threshold
    res = int((MAX_FACES_FOR_FULL_RENDER ** 0.5) + 100)  # ensure larger
    big = pv.Sphere(theta_resolution=res, phi_resolution=res)
    dec = dock._prepare_display_mesh(big)
    assert dec.n_faces < big.n_faces, "Decimation should reduce face count" 