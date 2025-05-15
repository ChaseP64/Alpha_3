#!/usr/bin/env python3
"""Unit tests for LandXMLParser.

This module contains tests for the LandXMLParser class which handles importing
surface data from LandXML files.
"""

import os
import tempfile
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from core.importers.landxml_parser import LandXMLParser


@pytest.fixture
def sample_landxml_path() -> Generator[str, None, None]:
    """Create a sample LandXML file for testing."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
    <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" date="2023-01-01" time="12:00:00" version="1.2">
      <Project name="Test Project" />
      <Application name="DigCalc Tests" version="1.0" />
      <Surfaces>
        <Surface name="Test Surface">
          <Definition surfType="TIN">
            <Pnts>
              <P id="1">100.0 200.0 50.0</P>
              <P id="2">110.0 210.0 55.0</P>
              <P id="3">120.0 220.0 60.0</P>
              <P id="4">130.0 230.0 65.0</P>
            </Pnts>
            <Faces>
              <F>1 2 3</F>
              <F>1 3 4</F>
            </Faces>
          </Definition>
        </Surface>
        <Surface name="Another Surface">
          <Definition surfType="TIN">
            <Pnts>
              <P id="1">1000.0 2000.0 500.0</P>
              <P id="2">1100.0 2100.0 550.0</P>
              <P id="3">1200.0 2200.0 600.0</P>
            </Pnts>
            <Faces>
              <F>1 2 3</F>
            </Faces>
          </Definition>
        </Surface>
      </Surfaces>
    </LandXML>
    """

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml") as f:
        f.write(xml_content)

    yield f.name

    # Clean up the temporary file
    os.unlink(f.name)


@pytest.fixture
def invalid_landxml_path() -> Generator[str, None, None]:
    """Create an invalid LandXML file for testing."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
    <NotLandXML>
      <SomethingElse />
    </NotLandXML>
    """

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml") as f:
        f.write(xml_content)

    yield f.name

    # Clean up the temporary file
    os.unlink(f.name)


@pytest.fixture
def landxml_with_points_only_path() -> Generator[str, None, None]:
    """Create a LandXML file with points but no faces for testing."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
    <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" date="2023-01-01" time="12:00:00" version="1.2">
      <Surfaces>
        <Surface name="Points Only Surface">
          <Definition surfType="TIN">
            <Pnts>
              <P id="1">100.0 200.0 50.0</P>
              <P id="2">110.0 210.0 55.0</P>
              <P id="3">120.0 220.0 60.0</P>
            </Pnts>
          </Definition>
        </Surface>
      </Surfaces>
    </LandXML>
    """

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml") as f:
        f.write(xml_content)

    yield f.name

    # Clean up the temporary file
    os.unlink(f.name)


@pytest.fixture
def landxml_with_cgpoints_path() -> Generator[str, None, None]:
    """Create a LandXML file with CgPoints for testing."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
    <LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" date="2023-01-01" time="12:00:00" version="1.2">
      <CgPoints>
        <CgPoint id="1">200.0 100.0 50.0</CgPoint>
        <CgPoint id="2">210.0 110.0 55.0</CgPoint>
        <CgPoint id="3">220.0 120.0 60.0</CgPoint>
      </CgPoints>
    </LandXML>
    """

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xml") as f:
        f.write(xml_content)

    yield f.name

    # Clean up the temporary file
    os.unlink(f.name)


class TestLandXMLParser:
    """Tests for the LandXMLParser class."""

    def test_parse_valid_landxml(self, sample_landxml_path: str):
        """Test parsing a valid LandXML file."""
        parser = LandXMLParser()

        # Parse the LandXML file
        result = parser.parse(sample_landxml_path)

        # Verify parse was successful
        assert result is True

        # Check if points were extracted correctly
        points = parser.get_points()
        assert len(points) == 4  # Should have 4 points from first surface

        # Verify surface names were extracted
        assert len(parser._surfaces) == 2
        assert "Test Surface" in parser._surfaces
        assert "Another Surface" in parser._surfaces

    def test_parse_invalid_landxml(self, invalid_landxml_path: str):
        """Test parsing an invalid LandXML file."""
        parser = LandXMLParser()

        # Parse the invalid LandXML file
        result = parser.parse(invalid_landxml_path)

        # Verify parse failed
        assert result is False

        # Verify no points were extracted
        points = parser.get_points()
        assert len(points) == 0

    def test_parse_landxml_with_points_only(self, landxml_with_points_only_path: str):
        """Test parsing a LandXML file with points but no faces."""
        parser = LandXMLParser()

        # Parse the LandXML file
        result = parser.parse(landxml_with_points_only_path)

        # Verify parse was successful
        assert result is True

        # Check if points were extracted correctly
        points = parser.get_points()
        assert len(points) == 3  # Should have 3 points

        # Verify no triangles were created
        assert len(parser._triangles) == 0

    def test_parse_landxml_with_cgpoints(self, landxml_with_cgpoints_path: str):
        """Test parsing a LandXML file with CgPoints."""
        parser = LandXMLParser()

        # Parse the LandXML file
        result = parser.parse(landxml_with_cgpoints_path)

        # Verify parse was successful
        assert result is True

        # Check if points were extracted correctly
        points = parser.get_points()
        assert len(points) == 3  # Should have 3 points

        # Verify the North/East swap (CgPoints use North,East,Elev order)
        assert points[0].x == 100.0  # East
        assert points[0].y == 200.0  # North
        assert points[0].z == 50.0   # Elevation

    def test_validate_with_valid_data(self, sample_landxml_path: str):
        """Test validation with valid data."""
        parser = LandXMLParser()

        # Parse the LandXML file
        parser.parse(sample_landxml_path)

        # Validation should pass
        assert parser.validate() is True

    def test_validate_with_empty_data(self):
        """Test validation with empty data."""
        parser = LandXMLParser()

        # No data has been parsed
        assert parser.validate() is False

    def test_get_contours(self, sample_landxml_path: str):
        """Test that get_contours returns an empty dict for LandXML files."""
        parser = LandXMLParser()

        # Parse the LandXML file
        parser.parse(sample_landxml_path)

        # LandXML parser doesn't currently extract contours
        contours = parser.get_contours()
        assert isinstance(contours, dict)
        assert len(contours) == 0

    @patch("core.geometry.tin_generator.TINGenerator")
    def test_create_surface_with_triangles(self, mock_tin_generator, sample_landxml_path: str):
        """Test creating a surface from parsed LandXML data with triangles."""
        parser = LandXMLParser()

        # Override the TINGenerator class in the parser instance
        parser._TINGenerator = mock_tin_generator

        # Parse the LandXML file
        parser.parse(sample_landxml_path)

        # Create surface
        surface = parser.create_surface("Test Surface")

        # Verify TIN generator was not called (triangles already exist)
        mock_tin_generator.assert_not_called()

        # Verify surface was created
        assert surface is not None
        assert surface.name == "Test Surface"
        assert len(surface.points) > 0
        assert len(surface.triangles) > 0

    @patch("core.geometry.tin_generator.TINGenerator")
    def test_create_surface_without_triangles(self, mock_tin_generator, landxml_with_points_only_path: str):
        """Test creating a surface from parsed LandXML data without triangles."""
        parser = LandXMLParser()

        # Override the TINGenerator class in the parser instance
        parser._TINGenerator = mock_tin_generator

        # Parse the LandXML file
        parser.parse(landxml_with_points_only_path)

        # Set up the mock
        mock_generator_instance = MagicMock()
        mock_tin_generator.return_value = mock_generator_instance
        mock_surface = MagicMock()
        mock_generator_instance.generate_from_points.return_value = mock_surface

        # Create surface
        surface = parser.create_surface("Points Only Surface")

        # Verify TIN generator was called
        mock_tin_generator.assert_called_once()
        mock_generator_instance.generate_from_points.assert_called_once()

        # Verify the generated surface was returned
        assert surface is mock_surface

    def test_create_surface_with_no_points(self):
        """Test that create_surface returns None when no points are available."""
        parser = LandXMLParser()

        # Try to create a surface without parsing data first
        surface = parser.create_surface("Test Surface")

        # Should return None since no points are available
        assert surface is None

    def test_get_available_surfaces(self, sample_landxml_path: str):
        """Test getting available surfaces from a LandXML file."""
        parser = LandXMLParser()

        # Parse the LandXML file
        parser.parse(sample_landxml_path)

        # Get available surfaces
        surfaces = parser.get_available_surfaces()

        # Verify surfaces
        assert len(surfaces) == 2
        assert "Test Surface" in surfaces
        assert "Another Surface" in surfaces
