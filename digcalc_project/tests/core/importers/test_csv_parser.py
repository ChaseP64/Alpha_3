#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for CSVParser.

This module contains tests for the CSVParser class which handles importing 
point data from CSV files.
"""

import os
import csv
import tempfile
from typing import List, Dict, Optional, Generator
import pytest
from unittest.mock import patch, MagicMock

from core.importers.csv_parser import CSVParser
from models.surface import Point3D


@pytest.fixture
def sample_csv_path() -> Generator[str, None, None]:
    """Create a sample CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(['X', 'Y', 'Z', 'Description'])
        # Write data rows
        writer.writerow([100.0, 200.0, 50.0, 'Point 1'])
        writer.writerow([110.0, 210.0, 55.0, 'Point 2'])
        writer.writerow([120.0, 220.0, 60.0, 'Point 3'])
        writer.writerow(['invalid', 230.0, 65.0, 'Invalid Point'])  # Invalid row
        writer.writerow([140.0, 240.0, 70.0, 'Point 5'])
    
    yield f.name
    
    # Clean up the temporary file
    os.unlink(f.name)


@pytest.fixture
def custom_headers_csv_path() -> Generator[str, None, None]:
    """Create a CSV file with custom headers for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        writer = csv.writer(f)
        # Write header with non-standard column names
        writer.writerow(['Easting', 'Northing', 'Elevation', 'ID'])
        # Write data rows
        writer.writerow([100.0, 200.0, 50.0, 'P1'])
        writer.writerow([110.0, 210.0, 55.0, 'P2'])
        writer.writerow([120.0, 220.0, 60.0, 'P3'])
    
    yield f.name
    
    # Clean up the temporary file
    os.unlink(f.name)


@pytest.fixture
def no_header_csv_path() -> Generator[str, None, None]:
    """Create a CSV file without headers for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        writer = csv.writer(f)
        # Write data rows without header
        writer.writerow([100.0, 200.0, 50.0])
        writer.writerow([110.0, 210.0, 55.0])
        writer.writerow([120.0, 220.0, 60.0])
    
    yield f.name
    
    # Clean up the temporary file
    os.unlink(f.name)


@pytest.fixture
def invalid_csv_path() -> Generator[str, None, None]:
    """Create an invalid CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write("This is not a valid CSV file")
    
    yield f.name
    
    # Clean up the temporary file
    os.unlink(f.name)


class TestCSVParser:
    """Tests for the CSVParser class."""

    def test_parse_valid_csv(self, sample_csv_path: str):
        """Test parsing a valid CSV file with headers."""
        parser = CSVParser()
        
        # Parse the CSV file
        result = parser.parse(sample_csv_path)
        
        # Verify parse was successful
        assert result is True
        
        # Check if points were extracted correctly
        points = parser.get_points()
        assert len(points) == 4  # One row is invalid and should be skipped
        
        # Verify points have correct coordinates
        assert points[0].x == 100.0
        assert points[0].y == 200.0
        assert points[0].z == 50.0
        
        assert points[1].x == 110.0
        assert points[1].y == 210.0
        assert points[1].z == 55.0

    def test_parse_no_header(self, no_header_csv_path: str):
        """Test parsing a CSV file without headers."""
        parser = CSVParser()
        
        # Parse CSV file with has_header=False
        result = parser.parse(no_header_csv_path, has_header=False)
        
        # Verify parse was successful
        assert result is True
        
        # Check if points were extracted correctly
        points = parser.get_points()
        assert len(points) == 3
        
        # Verify points have correct coordinates (assuming x,y,z order)
        assert points[0].x == 100.0
        assert points[0].y == 200.0
        assert points[0].z == 50.0

    def test_parse_custom_headers(self, custom_headers_csv_path: str):
        """Test parsing a CSV file with custom headers that should be auto-detected."""
        parser = CSVParser()
        
        # Parse the CSV file
        result = parser.parse(custom_headers_csv_path)
        
        # Verify parse was successful
        assert result is True
        
        # Check if points were extracted correctly
        points = parser.get_points()
        assert len(points) == 3
        
        # Verify points have correct coordinates
        assert points[0].x == 100.0
        assert points[0].y == 200.0
        assert points[0].z == 50.0

    def test_parse_custom_column_map(self, sample_csv_path: str):
        """Test parsing with a custom column map."""
        parser = CSVParser()
        
        # Custom column map (switching Y and Z)
        column_map = {'x': 0, 'y': 2, 'z': 1}
        
        # Parse the CSV file with custom column map
        result = parser.parse(sample_csv_path, column_map=column_map)
        
        # Verify parse was successful
        assert result is True
        
        # Check if points were extracted with the custom mapping
        points = parser.get_points()
        
        # With our mapping, Y is now Z and Z is now Y
        assert points[0].x == 100.0
        assert points[0].y == 50.0  # This was Z in the original file
        assert points[0].z == 200.0  # This was Y in the original file

    def test_parse_invalid_csv(self, invalid_csv_path: str):
        """Test parsing an invalid CSV file."""
        parser = CSVParser()
        
        # Parse the invalid CSV file
        result = parser.parse(invalid_csv_path)
        
        # Verify parse failed
        assert result is False
        
        # Verify no points were extracted
        points = parser.get_points()
        assert len(points) == 0

    def test_detect_columns(self, custom_headers_csv_path: str):
        """Test the column detection functionality."""
        parser = CSVParser()
        
        # Parse the CSV file
        parser.parse(custom_headers_csv_path)
        
        # Check that the column mapping was correctly detected
        # We expect 'Easting' -> x, 'Northing' -> y, 'Elevation' -> z
        assert parser._column_map.get('x') == 0  # Easting is in column 0
        assert parser._column_map.get('y') == 1  # Northing is in column 1
        assert parser._column_map.get('z') == 2  # Elevation is in column 2

    def test_validate_with_valid_data(self, sample_csv_path: str):
        """Test validation with valid data."""
        parser = CSVParser()
        
        # Parse the CSV file
        parser.parse(sample_csv_path)
        
        # Validation should pass
        assert parser.validate() is True

    def test_validate_with_empty_data(self):
        """Test validation with empty data."""
        parser = CSVParser()
        
        # No data has been parsed
        assert parser.validate() is False

    def test_get_contours(self, sample_csv_path: str):
        """Test that get_contours returns an empty dict for CSV files."""
        parser = CSVParser()
        
        # Parse the CSV file
        parser.parse(sample_csv_path)
        
        # CSV files don't contain contour data
        contours = parser.get_contours()
        assert isinstance(contours, dict)
        assert len(contours) == 0

    @patch('core.geometry.tin_generator.TINGenerator')
    def test_create_surface(self, mock_tin_generator, sample_csv_path: str):
        """Test creating a surface from parsed CSV data."""
        parser = CSVParser()
        
        # Override the TINGenerator class in the parser instance
        parser._TINGenerator = mock_tin_generator
        
        # Parse the CSV file
        parser.parse(sample_csv_path)
        
        # Set up the mock
        mock_generator_instance = MagicMock()
        mock_tin_generator.return_value = mock_generator_instance
        mock_surface = MagicMock()
        mock_generator_instance.generate_from_points.return_value = mock_surface
        
        # Create surface
        surface = parser.create_surface("Test Surface")
        
        # Verify TINGenerator was called correctly
        mock_tin_generator.assert_called_once()
        mock_generator_instance.generate_from_points.assert_called_once_with(
            parser._points, "Test Surface"
        )
        
        # Verify surface was created
        assert surface is mock_surface

    def test_create_surface_with_no_points(self):
        """Test that create_surface returns None when no points are available."""
        parser = CSVParser()
        
        # Try to create a surface without parsing data first
        surface = parser.create_surface("Test Surface")
        
        # Should return None since no points are available
        assert surface is None 