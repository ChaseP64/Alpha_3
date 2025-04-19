import pytest
import numpy as np
from PySide6.QtWidgets import QWidget, QApplication, QGraphicsScene
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QSize

# Mock necessary Qt and visualization components if not running full GUI tests
# For simplicity, assume necessary Qt components are available via pytest-qt
# Mock pyqtgraph.opengl if not installed or for isolation
try:
    from pyqtgraph.opengl import GLMeshItem
    import pyqtgraph.opengl as gl
    HAS_GL = True
except ImportError:
    HAS_GL = False
    class GLMeshItem:
        def __init__(self, *args, **kwargs): pass
        def setVisible(self, visible): self._visible = visible
        def isVisible(self): return getattr(self, '_visible', False)
        def setMeshData(self, *args, **kwargs): pass

# Mock the color map utility
# Import the actual panel relative to the test directory structure
# Assumes tests/ is at the same level as src/
# from ..src.ui.visualization_panel import VisualizationPanel
# from ..src.utils import color_maps # Import the real module
from digcalc_project.src.ui.visualization_panel import VisualizationPanel
from digcalc_project.src.utils import color_maps

# Fixture to create a basic VisualizationPanel instance
@pytest.fixture
def panel(qtbot) -> VisualizationPanel:
    # Need a QGraphicsScene for the 2D view
    scene = QGraphicsScene()
    # Create panel instance. It might need more setup depending on __init__
    # Pass a dummy parent or None
    vp = VisualizationPanel(parent=None)
    # Manually assign the scene if not done in init
    # vp.scene_2d = scene 
    # Ensure the UI (views) are initialized if _init_ui isn't called by default
    # vp._init_ui() # This might try to create OpenGL widgets
    # For isolated testing, we might skip full _init_ui
    # Manually create essential components if needed
    vp.scene_2d = scene # Ensure scene exists
    vp.view_2d = None # Mock or skip view dependencies if possible
    vp.view_3d = None # Mock or skip
    
    # Mock the GLMeshItem add/remove on view_3d if it's accessed
    if HAS_GL:
         # If view_3d is expected to be a GLViewWidget, mock its methods
         # Inherit from gl.GLViewWidget to pass isinstance check
         class MockGLView(gl.GLViewWidget):
             def __init__(self):
                 # Need to call super().__init__() if inheriting QWidget based class
                 try:
                     super().__init__() 
                 except Exception as e:
                     # Catch potential issues if super init needs specific args or environment
                     print(f"Warning: MockGLView super().__init__() failed: {e}")
                 self.items = []
             def addItem(self, item):
                  self.items.append(item)
                  # Maybe call super if needed? For testing, just track.
                  # super().addItem(item) 
             def removeItem(self, item):
                 if item in self.items:
                      self.items.remove(item)
                      # Maybe call super if needed?
                      # super().removeItem(item)
             def update(self): pass # Mock update method
             # Add other methods if VisualizationPanel calls them on view_3d

         vp.view_3d = MockGLView()
    
    return vp

# Test data
@pytest.fixture
def dummy_dz_data():
    dz = np.array([[-2.0, 0.0, 2.0], [-2.0, 0.0, 2.0]], dtype=np.float32)
    # Ensure gx, gy match dz dimensions (gx = cols, gy = rows)
    gx = np.array([0.0, 10.0, 20.0]) # 3 columns
    gy = np.array([50.0, 60.0])    # 2 rows
    return dz, gx, gy

# Test the update_cutfill_map function
def test_update_cutfill_map_creates_items(panel: VisualizationPanel, dummy_dz_data, mocker):
    """Test that update_cutfill_map creates 2D and 3D items the first time."""
    dz, gx, gy = dummy_dz_data
    
    # Mock the color conversion to avoid dependency on matplotlib
    # Return a plausible RGBA array matching dz shape
    mock_rgba = np.random.randint(0, 255, size=(dz.shape[0], dz.shape[1], 4), dtype=np.uint8)
    mock_rgba[..., 3] = 180 # Set alpha
    mocker.patch.object(color_maps, 'dz_to_rgba', return_value=mock_rgba)
    
    assert panel._dz_image_item is None
    if HAS_GL:
        assert panel._dz_mesh_item is None
        
    panel.update_cutfill_map(dz, gx, gy)
    
    assert panel._dz_image_item is not None
    assert isinstance(panel._dz_image_item.pixmap(), QPixmap)
    # Check pixmap size based on dz shape (h, w)
    expected_h, expected_w = dz.shape
    assert panel._dz_image_item.pixmap().size() == QSize(expected_w, expected_h)
    # Check it was added to the scene
    assert panel._dz_image_item in panel.scene_2d.items()
    
    if HAS_GL:
        assert panel._dz_mesh_item is not None
        # Check it was added to the mock view_3d
        assert panel._dz_mesh_item in panel.view_3d.items

def test_update_cutfill_map_updates_items(panel: VisualizationPanel, dummy_dz_data, mocker):
    """Test that update_cutfill_map updates existing items."""
    dz, gx, gy = dummy_dz_data
    mock_rgba = np.random.randint(0, 255, size=(dz.shape[0], dz.shape[1], 4), dtype=np.uint8)
    mock_rgba[..., 3] = 180
    mocker.patch.object(color_maps, 'dz_to_rgba', return_value=mock_rgba)
    
    # Call once to create
    panel.update_cutfill_map(dz, gx, gy)
    initial_pixmap = panel._dz_image_item.pixmap()
    initial_mesh_item = panel._dz_mesh_item
    
    # Mock mesh item's setMeshData to check if it's called
    if HAS_GL and initial_mesh_item:
        mocker.spy(initial_mesh_item, 'setMeshData')
        
    # Prepare slightly different data for update
    dz_new = dz + 1
    mock_rgba_new = np.random.randint(0, 255, size=(dz_new.shape[0], dz_new.shape[1], 4), dtype=np.uint8)
    mock_rgba_new[..., 3] = 180
    mocker.patch.object(color_maps, 'dz_to_rgba', return_value=mock_rgba_new)
    
    # Call again to update
    panel.update_cutfill_map(dz_new, gx, gy)
    
    assert panel._dz_image_item is not None
    assert panel._dz_image_item.pixmap() is not initial_pixmap # Pixmap should be replaced
    # Check new pixmap size (should be same dimensions)
    expected_h, expected_w = dz_new.shape
    assert panel._dz_image_item.pixmap().size() == QSize(expected_w, expected_h)

    if HAS_GL and initial_mesh_item:
        assert panel._dz_mesh_item is initial_mesh_item # Mesh item should be reused
        assert initial_mesh_item.setMeshData.call_count == 1 # Check if update method was called

def test_set_cutfill_visible(panel: VisualizationPanel, dummy_dz_data, mocker):
    """Test that set_cutfill_visible toggles item visibility."""
    dz, gx, gy = dummy_dz_data
    mock_rgba = np.random.randint(0, 255, size=(dz.shape[0], dz.shape[1], 4), dtype=np.uint8)
    mock_rgba[..., 3] = 180
    mocker.patch.object(color_maps, 'dz_to_rgba', return_value=mock_rgba)

    # Create items first
    panel.update_cutfill_map(dz, gx, gy)
    assert panel._dz_image_item is not None
    if HAS_GL:
        assert panel._dz_mesh_item is not None
        # Spy on the setVisible method of the mesh item
        mocker.spy(panel._dz_mesh_item, 'setVisible')

    # Initial state check (panel flag)
    assert not panel._cutfill_visible
    assert not panel._dz_image_item.isVisible()
    # Cannot directly check mesh_item.isVisible(), assume it matches panel._cutfill_visible initially

    # Toggle ON
    panel.set_cutfill_visible(True)
    assert panel._cutfill_visible
    assert panel._dz_image_item.isVisible()
    if HAS_GL:
        # Check that setVisible(True) was called on the mesh item
        panel._dz_mesh_item.setVisible.assert_called_once_with(True)
        panel._dz_mesh_item.setVisible.reset_mock() # Reset mock for next call

    # Toggle OFF
    panel.set_cutfill_visible(False)
    assert not panel._cutfill_visible
    assert not panel._dz_image_item.isVisible()
    if HAS_GL:
        # Check that setVisible(False) was called
        panel._dz_mesh_item.setVisible.assert_called_once_with(False)
        panel._dz_mesh_item.setVisible.reset_mock()

    # Toggle ON again
    panel.set_cutfill_visible(True)
    assert panel._cutfill_visible
    assert panel._dz_image_item.isVisible()
    if HAS_GL:
        # Check that setVisible(True) was called again
        panel._dz_mesh_item.setVisible.assert_called_once_with(True)

def test_clear_cutfill_map(panel: VisualizationPanel, dummy_dz_data, mocker):
    """Test that clear_cutfill_map removes items."""
    dz, gx, gy = dummy_dz_data
    mock_rgba = np.random.randint(0, 255, size=(dz.shape[0], dz.shape[1], 4), dtype=np.uint8)
    mock_rgba[..., 3] = 180
    mocker.patch.object(color_maps, 'dz_to_rgba', return_value=mock_rgba)

    # Create items
    panel.update_cutfill_map(dz, gx, gy)
    assert panel._dz_image_item is not None
    image_item = panel._dz_image_item # Keep reference
    assert image_item in panel.scene_2d.items()
    mesh_item = None
    if HAS_GL:
        assert panel._dz_mesh_item is not None
        mesh_item = panel._dz_mesh_item # Keep reference
        assert mesh_item in panel.view_3d.items
        
    # Clear the map
    panel.clear_cutfill_map()
    
    assert panel._dz_image_item is None
    assert image_item not in panel.scene_2d.items() # Should be removed from scene
    if HAS_GL:
        assert panel._dz_mesh_item is None
        assert mesh_item not in panel.view_3d.items # Should be removed from mock view 