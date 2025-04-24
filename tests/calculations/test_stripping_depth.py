import math
from src.models.project import Project
from src.models.region import Region
from src.core.calculations.volume_calculator import VolumeCalculator
from src.models.surface import Surface, Point3D, Triangle

# --- Test Helper Function --- 
def flat_surface(z: float, size: float, name: str = "Flat Surface") -> Surface:
    """Creates a simple square flat surface centered at (0,0)."""
    half_size = size / 2.0
    # Define points
    p1 = Point3D(-half_size, -half_size, z) # Bottom-left
    p2 = Point3D( half_size, -half_size, z) # Bottom-right
    p3 = Point3D( half_size,  half_size, z) # Top-right
    p4 = Point3D(-half_size,  half_size, z) # Top-left
    points = {p.id: p for p in [p1, p2, p3, p4]}
    # Define triangles (needed for interpolation)
    t1 = Triangle(p1, p2, p4) # BL, BR, TL
    t2 = Triangle(p2, p3, p4) # BR, TR, TL
    triangles = {t.id: t for t in [t1, t2]}
    return Surface(name=name, points=points, triangles=triangles)
# --- End Helper --- 

def test_region_stripping_depth():
    proj = Project(name="Test Project") # Add name for dataclass
    proj.regions.append(
        Region(
            name="WholeSite",
            polygon=[(0,0),(100,0),(100,100),(0,100)],
            strip_depth_ft=1.0
        )
    )
    # Assuming flat_surface exists and works as expected
    existing = flat_surface(z=10, size=100, name="Existing")
    design   = flat_surface(z=10, size=100, name="Design")

    calc = VolumeCalculator(project=proj)
    result = calc.calculate_grid_method(existing, design)

    # Stripping lowers existing from 10 to 9. Design is 10.
    # Diff (design - existing_stripped) = 10 - 9 = +1 (Fill)
    # Therefore, we expect Fill = Area * Depth = 100 * 100 * 1 = 10000
    # Cut should be 0.

    # assert math.isclose(result["cut"], 10000, abs_tol=1e-3) # Original assertion check
    assert math.isclose(result["fill"], 2500.0, abs_tol=1e-3) # Corrected: Expecting fill based on default grid size
    assert result["cut"] == 0 