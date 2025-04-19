# tests/test_surface_rebuild.py

import pytest
import time
from collections import defaultdict
from unittest.mock import patch, MagicMock # Use unittest.mock

# PySide6 imports (optional if fully mocked)
# from PySide6.QtCore import QTimer, QCoreApplication

# Adjust relative paths based on your test structure
# If tests/ is alongside digcalc_project/, this should work:
from digcalc_project.src.models.project import Project, PolylineData
from digcalc_project.src.models.surface import Surface
from digcalc_project.src.core.geometry.surface_builder import SurfaceBuilder, SurfaceBuilderError


# Mock QTimer for testing without actual UI event loop
class MockQTimer:
    def __init__(self, parent=None, interval=0, singleShot=False):
        self._interval = interval
        self._singleShot = singleShot
        self._active = False
        self._timeout_callback = None
        print(f"MockQTimer created (interval={self._interval}, singleShot={self._singleShot})")

    def setInterval(self, msec):
        self._interval = msec

    def setSingleShot(self, singleShot):
        self._singleShot = singleShot

    def timeout(self):
        class MockSignal:
            def __init__(self, outer_instance):
                self._outer = outer_instance
                self._callback = None
            def connect(self, slot):
                print(f"MockQTimer connecting timeout to: {slot.__name__ if hasattr(slot, '__name__') else slot}")
                self._outer._timeout_callback = slot # Store on outer instance
            def disconnect(self, slot):
                if self._outer._timeout_callback == slot:
                    self._outer._timeout_callback = None
        if not hasattr(self, '_signal'):
             self._signal = MockSignal(self)
        return self._signal

    def start(self, msec=None):
        if msec is not None:
            self._interval = msec
        print(f"MockQTimer start() called (interval={self._interval})")
        self._active = True
        # Do not trigger timeout automatically here

    def stop(self):
        print("MockQTimer stop() called")
        self._active = False

    def isActive(self):
        return self._active

    def trigger_timeout(self):
         """Manually trigger the connected callback."""
         print(f"MockQTimer manually triggering timeout (active={self._active}, callback={self._timeout_callback})")
         if self._active and self._timeout_callback:
              if self._singleShot:
                  self._active = False
              print("MockQTimer executing callback")
              self._timeout_callback()
         else:
              print("MockQTimer NOT executing callback (inactive or no callback)")

# Mock parts of MainWindow relevant to the rebuild process
# Patches are now applied to the test function directly
class MockMainWindowForRebuild:
    def __init__(self, project=None):
        self.current_project = project
        self._rebuild_needed_layers = set()
        # Note: We rely on the test function's patch to provide MockQTimer
        self._rebuild_timer = MockQTimer(interval=250, singleShot=True)
        self._rebuild_timer.timeout().connect(self._process_rebuild_queue)
        self.visualization_panel = MagicMock() # Mock visualization panel
        self.project_panel = MagicMock() # Mock project panel
        self.statusBar = MagicMock() # Mock status bar
        self.statusBar().showMessage = MagicMock()
        print("MockMainWindowForRebuild initialized")

    def _queue_surface_rebuilds_for_layer(self, layer_name: str):
        if layer_name:
            print(f"Mock Queueing rebuild for layer: {layer_name}")
            self._rebuild_needed_layers.add(layer_name)
            self._rebuild_timer.start() # Will use the interval set

    def _process_rebuild_queue(self):
        print("Mock Processing rebuild queue...")
        if not self.current_project or not self._rebuild_needed_layers:
            self._rebuild_needed_layers.clear()
            print("  -> No project or no layers queued. Aborting process.")
            return
        layers_to_process = self._rebuild_needed_layers.copy()
        self._rebuild_needed_layers.clear()
        print(f"  -> Layers to process: {layers_to_process}")
        surfaces_to_check = list(self.current_project.surfaces.values())
        rebuilt_count = 0
        for surf in surfaces_to_check:
             if surf.name not in self.current_project.surfaces: continue
             if surf.source_layer_name in layers_to_process:
                 print(f"  -> Found matching surface '{surf.name}' for layer '{surf.source_layer_name}'. Calling _rebuild_surface_now.")
                 self._rebuild_surface_now(surf.name)
                 rebuilt_count += 1
        print(f"Mock Finished processing rebuild queue. Rebuilt {rebuilt_count} surfaces.")

    def _rebuild_surface_now(self, surface_name: str):
        print(f"Mock Rebuilding surface: {surface_name}")
        proj = self.current_project
        surf = proj.surfaces.get(surface_name)
        if not surf or not surf.source_layer_name:
            print(f"  -> Surface '{surface_name}' not found or has no source layer.")
            return
        layer = surf.source_layer_name
        current_rev = proj.layer_revisions.get(layer, 0)
        print(f"  -> Current Layer Rev: {current_rev}, Surface Saved Rev: {surf.source_layer_revision}")

        if surf.source_layer_revision is not None and surf.source_layer_revision == current_rev:
             print(f"Mock Surface '{surface_name}' already up-to-date.")
             if surf.is_stale:
                  surf.is_stale = False # Ensure stale flag is cleared
                  # Simulate UI update for state change
                  self.project_panel._update_tree_item_text(surf.name)
             return

        polys = proj.traced_polylines.get(layer, [])
        valid = [p for p in polys if isinstance(p, dict) and p.get("elevation") is not None]
        if not valid or len(valid) < 3:
             print(f"Mock No valid polylines (count={len(valid)}) to rebuild '{surface_name}'. Marking stale.")
             surf.is_stale = True
             # Simulate UI update for stale state
             self.project_panel._update_tree_item_text(surf.name)
             return

        new_surf = None
        try:
            print(f"  -> Calling ACTUAL SurfaceBuilder for layer '{layer}' rev {current_rev}")
            new_surf = SurfaceBuilder.build_from_polylines(layer, valid, current_rev)
            new_surf.name = surface_name # Preserve original name
            new_surf.is_stale = False # Mark as not stale after successful build
            proj.surfaces[surface_name] = new_surf # Update project
            proj.is_modified = True
            print(f"  -> Mock Successfully rebuilt '{surface_name}'")

            # Simulate calls to mocked panels AFTER successful build
            self.visualization_panel.update_surface_mesh(new_surf)
            self.project_panel._update_tree_item_text(new_surf.name)

        except SurfaceBuilderError as e:
            # Handle expected build errors -> Mark stale
            print(f"Mock Rebuild failed for '{surface_name}' with SurfaceBuilderError: {e}")
            if surf: surf.is_stale = True
            # Simulate UI update for stale state
            self.project_panel._update_tree_item_text(surf.name)
            # Do not raise here, allow test to check project state

        except Exception as e:
            # Handle unexpected errors during build -> Mark stale and log
            # Note: Errors during the *simulation* calls above will propagate normally
            print(f"Mock Rebuild failed for '{surface_name}' with unexpected error during build: {e}")
            if surf: surf.is_stale = True
            # Simulate UI update for stale state
            self.project_panel._update_tree_item_text(surf.name)
            # Log or handle unexpected build error, but maybe don't crash mock process
            # Depending on test needs, could re-raise: raise e

    # Simulate the method that triggers the change
    def mock_apply_elevation_edit(self, layer_name, index, new_elevation):
         print(f"\n--- Simulating elevation edit: Layer='{layer_name}', Index={index}, NewElev={new_elevation} ---")
         poly_list = self.current_project.traced_polylines.get(layer_name)
         if poly_list and isinstance(poly_list[index], dict):
              poly_list[index]["elevation"] = new_elevation
              new_rev = self.current_project._bump_layer_revision(layer_name) # Bump revision
              print(f"  -> Bumped revision to {new_rev}")
              self._queue_surface_rebuilds_for_layer(layer_name) # Queue rebuild
         print("--- End Simulation ---\n")

# Test function using the mocked MainWindow
@patch('digcalc_project.src.ui.main_window.QTimer', MockQTimer)
# @patch('digcalc_project.src.ui.main_window.SurfaceBuilder', MagicMock())
@patch('digcalc_project.src.ui.main_window.QMessageBox', MagicMock())
def test_surface_rebuild_workflow():
    """Tests the automatic surface rebuild workflow using mocks."""
    print("\n=== Starting test_surface_rebuild_workflow ===")
    # Instantiate the mock class directly
    mock_main_window_instance = MockMainWindowForRebuild()

    # 1. Create Project and add layer data
    project = Project("Rebuild Test")
    mock_main_window_instance.current_project = project # Assign project
    layer_name = "Existing"
    poly1: PolylineData = {"points": [(0,0), (10,0)], "elevation": 10.0}
    poly2: PolylineData = {"points": [(0,10), (10,10)], "elevation": 11.0}
    poly3: PolylineData = {"points": [(5, 0), (5, 10)], "elevation": 10.5}

    # Add polylines (this bumps revision via project method)
    project.add_traced_polyline(poly1, layer_name)
    project.add_traced_polyline(poly2, layer_name)
    project.add_traced_polyline(poly3, layer_name)
    initial_revision = project.layer_revisions[layer_name]
    print(f"Initial data added. Layer '{layer_name}' revision: {initial_revision}")
    assert initial_revision == 3

    # 2. Build initial surface using the *actual* builder
    polys = project.traced_polylines.get(layer_name, [])
    valid_polys = [p for p in polys if isinstance(p, dict) and p.get("elevation") is not None]
    try:
         surface = SurfaceBuilder.build_from_polylines(layer_name, valid_polys, initial_revision)
         surface.name = "Existing_TIN"
         project.add_surface(surface)
         print(f"Initial surface built: {surface.name} from layer '{layer_name}' rev {initial_revision}")
    except SurfaceBuilderError as e:
         pytest.fail(f"Initial surface build failed: {e}")

    assert surface.source_layer_name == layer_name
    assert surface.source_layer_revision == initial_revision
    assert not surface.is_stale

    # 3. Simulate an elevation edit using the mock window's method
    new_elevation = 12.0
    poly_index_to_edit = 1 # Edit poly2 (which was added second)
    mock_main_window_instance.mock_apply_elevation_edit(layer_name, poly_index_to_edit, new_elevation)

    # 4. Assert revision bumped and rebuild queued
    expected_revision = initial_revision + 1
    assert project.layer_revisions[layer_name] == expected_revision
    assert layer_name in mock_main_window_instance._rebuild_needed_layers
    assert mock_main_window_instance._rebuild_timer.isActive()
    print(f"Revision bumped to {expected_revision} and timer active. OK.")

    # 5. Manually process the rebuild queue (simulate timer firing)
    mock_main_window_instance._rebuild_timer.trigger_timeout()

    # 5b. Assert that the UI panels were updated after rebuild
    # Retrieve the rebuilt surface to pass to the assertion
    rebuilt_surface_for_assert = project.surfaces.get("Existing_TIN")
    assert rebuilt_surface_for_assert is not None, "Surface 'Existing_TIN' not found after rebuild for assertion."
    mock_main_window_instance.visualization_panel.update_surface_mesh.assert_called_with(rebuilt_surface_for_assert)
    mock_main_window_instance.project_panel._update_tree_item_text.assert_called_with(rebuilt_surface_for_assert.name)
    print("Mock UI panel update calls verified. OK.")

    # 6. Assert surface was rebuilt and is up-to-date
    # This check is now somewhat redundant with the mock check above, but verifies project state
    rebuilt_surface = project.surfaces.get("Existing_TIN")
    assert rebuilt_surface is not None, "Surface 'Existing_TIN' not found after rebuild."
    print(f"Surface after rebuild: Name='{rebuilt_surface.name}', SourceLayer='{rebuilt_surface.source_layer_name}', SourceRev={rebuilt_surface.source_layer_revision}, IsStale={rebuilt_surface.is_stale}")
    assert rebuilt_surface.source_layer_name == layer_name
    assert rebuilt_surface.source_layer_revision == expected_revision # Check it has the NEW revision
    assert not rebuilt_surface.is_stale
    print("Surface rebuilt correctly with new revision and not stale. OK.")

    # 7. Test stale flag on load (simulate loading)
    print("\n--- Testing Stale Flag on Load Simulation ---")
    # Get the state *before* bumping revision again
    original_surface_revision = rebuilt_surface.source_layer_revision
    # Simulate revisions changing *after* the surface was 'saved' (imagine loading)
    newer_project_revisions = project.layer_revisions.copy()
    newer_project_revisions[layer_name] += 5 # Simulate several more changes

    print(f"  -> Surface original revision: {original_surface_revision}")
    print(f"  -> Simulated loaded layer revisions: {dict(newer_project_revisions)}")

    # Simulate the stale check part of Project.load()
    surf_to_check = rebuilt_surface # Use the surface we have
    if surf_to_check.source_layer_name:
        current_loaded_rev = newer_project_revisions.get(surf_to_check.source_layer_name, 0)
        saved_rev = surf_to_check.source_layer_revision # This is original_surface_revision
        print(f"  -> Comparing SavedRev={saved_rev} vs CurrentLoadedRev={current_loaded_rev}")
        if saved_rev is None or saved_rev != current_loaded_rev:
            print("  -> Marking surface as stale.")
            surf_to_check.is_stale = True
        else:
            surf_to_check.is_stale = False

    assert surf_to_check.is_stale, "Surface should be marked stale on load simulation if revisions differ"
    print("Stale flag test passed. OK.")
    print("=== Finished test_surface_rebuild_workflow ===\n") 