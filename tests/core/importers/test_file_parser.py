#!/usr/bin/env python3
"""Unit tests for FileParser base class.

This module contains tests for the FileParser abstract base class
and its class methods.
"""

from unittest.mock import MagicMock

from src.core.importers.csv_parser import CSVParser
from src.core.importers.dxf_parser import DXFParser
from src.core.importers.file_parser import FileParser
from src.core.importers.landxml_parser import LandXMLParser
from src.core.importers.pdf_parser import PDFParser
from src.models.surface import Point3D


class TestFileParser:
    """Tests for the FileParser abstract base class."""

    def test_get_parser_for_file(self):
        """Test that get_parser_for_file returns the correct parser based on file extension."""
        # Test CSV parser
        csv_parser = FileParser.get_parser_for_file("test.csv")
        assert isinstance(csv_parser, CSVParser)

        # Test LandXML parser
        landxml_parser = FileParser.get_parser_for_file("test.xml")
        assert isinstance(landxml_parser, LandXMLParser)

        # Test DXF parser
        dxf_parser = FileParser.get_parser_for_file("test.dxf")
        assert isinstance(dxf_parser, DXFParser)

        # Test PDF parser
        pdf_parser = FileParser.get_parser_for_file("test.pdf")
        assert isinstance(pdf_parser, PDFParser)

        # Test unsupported extension
        unknown_parser = FileParser.get_parser_for_file("test.unknown")
        assert unknown_parser is None

    def test_get_bounds(self):
        """Test that get_bounds correctly calculates bounds from points."""
        # Create a mock parser with points
        mock_parser = MagicMock(spec=FileParser)

        # Define get_points method to return test points
        points = [
            Point3D(0, 0, 0),
            Point3D(10, 5, 2),
            Point3D(5, 10, 5),
            Point3D(-5, -5, -1),
        ]
        mock_parser.get_points.return_value = points

        # Use the real get_bounds method
        FileParser.get_bounds.__get__(mock_parser)()

        # Calculate expected bounds
        expected_bounds = (-5, -5, 10, 10)

        # Call get_bounds and check result
        actual_bounds = FileParser.get_bounds(mock_parser)
        assert actual_bounds == expected_bounds

    def test_get_bounds_empty(self):
        """Test that get_bounds returns None for empty points list."""
        # Create a mock parser with no points
        mock_parser = MagicMock(spec=FileParser)
        mock_parser.get_points.return_value = []

        # Call get_bounds and check result
        bounds = FileParser.get_bounds(mock_parser)
        assert bounds is None

    def test_log_error(self):
        """Test that log_error properly logs error messages."""
        # Create a mock parser
        mock_parser = MagicMock(spec=FileParser)
        mock_parser.logger = MagicMock()

        # Test log_error with message only
        message = "Test error message"
        FileParser.log_error(mock_parser, message)
        mock_parser.logger.error.assert_called_with(message)

        # Test log_error with exception
        exception = ValueError("Test exception")
        FileParser.log_error(mock_parser, message, exception)
        mock_parser.logger.error.assert_called_with(f"{message}: {exception!s}")

    def test_supported_extensions(self):
        """Test that get_supported_extensions returns the expected list."""
        # Base class should return empty list
        assert FileParser.get_supported_extensions() == []

        # Specific parsers should return their expected extensions
        assert ".csv" in CSVParser.get_supported_extensions()
        assert ".txt" in CSVParser.get_supported_extensions()
        assert ".xml" in LandXMLParser.get_supported_extensions()
        assert ".landxml" in LandXMLParser.get_supported_extensions()
        assert ".dxf" in DXFParser.get_supported_extensions()
        assert ".pdf" in PDFParser.get_supported_extensions()
