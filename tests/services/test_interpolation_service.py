from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import numpy as np

from digcalc_project.src.models.strata_models import Material, BoreholeLog, StrataLayer, StrataStack
from digcalc_project.src.services.interpolation_service import IDWInterpolator


class TestInterpolationService(unittest.TestCase):

    def test_generate_surfaces_rmse_for_perfect_plane(self):
        """
        Tests that the RMSE is close to zero when interpolating a perfectly flat plane.
        """
        # 1. Arrange
        mock_project = MagicMock()
        mock_project.id = "test_project"
        mock_existing_surface = MagicMock()
        mock_existing_surface.bounds = (0, 0, 0, 100, 100, 0)
        mock_existing_surface.crs = "EPSG:32610"

        # Create a simple strata stack with one material and boreholes on a plane
        material = Material(id=1, name="Sand", colour="#EDC9AF")
        boreholes = [
            BoreholeLog(id=1, x=10, y=10, layers=[StrataLayer(material_id=1, top_z=50.0)]),
            BoreholeLog(id=2, x=90, y=10, layers=[StrataLayer(material_id=1, top_z=50.0)]),
            BoreholeLog(id=3, x=50, y=90, layers=[StrataLayer(material_id=1, top_z=50.0)]),
            BoreholeLog(id=4, x=10, y=90, layers=[StrataLayer(material_id=1, top_z=50.0)]),
        ]
        stack = StrataStack(materials=[material], boreholes=boreholes)

        interpolator = IDWInterpolator()

        # 2. Act
        surfaces, rmse = interpolator.generate_surfaces(
            project=mock_project,
            stack=stack,
            existing_surface=mock_existing_surface,
        )

        # 3. Assert
        self.assertEqual(len(surfaces), 1)
        self.assertAlmostEqual(rmse, 0.0, places=6, msg="RMSE for a perfect plane should be ~0.0")

        # Also check that the grid itself is flat
        generated_grid = surfaces[0].grid_data
        self.assertTrue(np.allclose(generated_grid[~np.isnan(generated_grid)], 50.0))

if __name__ == '__main__':
    unittest.main() 