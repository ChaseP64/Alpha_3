#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for PDFParser stub implementation.

This module contains tests for the PDFParser class which handles importing
data from PDF files.
"""

import os
import tempfile
from typing import List, Dict, Optional
import pytest
from unittest.mock import patch, MagicMock

from src.core.importers.pdf_parser import PDFParser
from src.models.surface import Point3D, Surface


class TestPDFParser:
    """Tests for the PDFParser stub implementation."""

    def test_supported_extensions(self):
        """Test the supported file extensions for PDFParser."""
        extensions = PDFParser.get_supported_extensions()
        assert ".pdf" in extensions

    def test_parse(self):
        """Test parsing a PDF file."""
        parser = PDFParser()
        
        # Create a temp file path
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            # Parse the file
            result = parser.parse(temp_file.name)
            
            # Verify parse was successful (stub implementation always returns True)
            assert result is True
            
            # Verify dummy point was created
            points = parser.get_points()
            assert len(points) == 1
            assert points[0].x == 0
            assert points[0].y == 0
            assert points[0].z == 0

    def test_parse_with_options(self):
        """Test parsing a PDF file with additional options."""
        parser = PDFParser()
        
        # Create a temp file path
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            # Parse the file with custom options
            result = parser.parse(
                temp_file.name,
                page_number=2,
                scale=10.0,
                origin=(100, 200)
            )
            
            # Verify parse was successful
            assert result is True
            
            # Stub implementation doesn't actually use these parameters,
            # but we can verify the file path was set
            assert parser._file_path == temp_file.name

    def test_validate(self):
        """Test that validate always returns True for the stub implementation."""
        parser = PDFParser()
        
        # Validate should always return True for the stub
        assert parser.validate() is True
        
        # Even with no data
        parser._points = []
        assert parser.validate() is True

    def test_get_contours(self):
        """Test that get_contours returns an empty dict."""
        parser = PDFParser()
        
        contours = parser.get_contours()
        assert isinstance(contours, dict)
        assert len(contours) == 0

    def test_create_surface(self):
        """Test creating a surface (should always return None for PDF stub)."""
        parser = PDFParser()
        
        # Create surface
        surface = parser.create_surface("Test Surface")
        
        # Stub implementation always returns None
        assert surface is None

    def test_get_page_count(self):
        """Test getting page count."""
        parser = PDFParser()
        parser._pages = 5
        
        # Get page count
        page_count = parser.get_page_count()
        assert page_count == 5

    def test_get_pdf_page_count(self):
        """Test the internal method to get PDF page count."""
        parser = PDFParser()
        
        # Create a temp file path
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            # This method would normally use PyPDF2, but the stub always returns 1
            page_count = parser._get_pdf_page_count(temp_file.name)
            assert page_count == 1

    @patch('logging.Logger.warning')
    def test_logs_warning_for_unimplemented_features(self, mock_warning):
        """Test that the stub logs appropriate warnings."""
        parser = PDFParser()
        
        # Create a temp file path
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            # Parse the file
            parser.parse(temp_file.name)
            
            # Create surface (should log warning)
            parser.create_surface("Test Surface")
            
            # Verify warning was logged
            mock_warning.assert_any_call("PDF parsing not implemented")
            mock_warning.assert_any_call("Creating surfaces from PDF data is not implemented") 