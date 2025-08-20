import json
import pathlib
from pathlib import Path

import numpy as np
import pytest

from digcalc_project.src.core.calculators.volume_calculator import (
    VolumeCalculator,
    calculate_material_cut,
)
from digcalc_project.src.models.project import Project

# Tolerances
TOL_MAT = 0.05  # 5 % per material
TOL_TOTAL = 0.02  # 2 % overall

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"


def _load_demo_project():
    proj_file = FIXTURES / "strata_demo_project.json"
    project = Project.load(str(proj_file))
    assert project is not None, "Fixture project failed to load"
    return project


def test_regression_against_gold(tmp_path):
    """Verify that the volume calculation for a known project matches
    a set of "gold standard" expected volumes from a JSON file.
    """
    # TODO: Regenerate this file with the new calculator
    # pytest.skip("Expected volumes need update after calculator changes")

    # Load the sample project
    project_path = Path(__file__).parent.parent / "fixtures" / "strata_demo_project.json"
    project = Project.load(str(project_path))
    assert project is not None, "Fixture project failed to load"

    # Run grid-based volume calc on the two surfaces
    calc = VolumeCalculator(project)
    surf_exist = project.get_surface("Existing")
    surf_prop = project.get_surface("Proposed")
    assert surf_exist and surf_prop, "Surfaces missing in fixture"

    # Use 1-ft grid so cell area = 1
    res = calc.calculate_grid_method(surf_exist, surf_prop, grid_resolution=1.0)

    # Build per-material cut volumes
    dz_grid = res["dz_grid"]
    # Reconstruct Z arrays for helper (existing = dz, proposed = 0)
    existing_z = dz_grid
    proposed_z = np.zeros_like(dz_grid)

    vols_by_id = calculate_material_cut(
        existing_z,
        proposed_z,
        project.strata,
        cell_area=1.0,
    )
    # Map id→name
    id2name = {m.id: m.name for m in project.strata.materials}
    vols_named = {id2name[i]: v for i, v in vols_by_id.items()}

    # Load expected volumes
    with open(FIXTURES / "expected_volumes.json") as fp:
        expected = json.load(fp)

    # Total check
    total_calc = sum(vols_named.values())
    total_exp = expected["total"]
    if total_exp == 0:
        assert total_calc == 0, "Total calculated volume should be zero"
    else:
        assert (
            abs(total_calc - total_exp) / total_exp <= TOL_TOTAL
        ), "Total volume outside tolerance"

    # Per-material check
    for mat_name, exp_v in expected["materials"].items():
        calc_v = vols_named.get(mat_name)
        assert calc_v is not None, f"Material '{mat_name}' missing in calc"
        if exp_v == 0:
            assert calc_v == 0, f"Volume for {mat_name} should be zero"
        else:
            assert abs(calc_v - exp_v) / exp_v <= TOL_MAT, f"Volume mismatch for {mat_name}"
