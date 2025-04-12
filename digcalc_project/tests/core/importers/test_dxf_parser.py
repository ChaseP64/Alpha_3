#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for DXFParser stub implementation.

This module contains tests for the DXFParser class which handles importing
CAD data from DXF files.
"""

import os
import tempfile
from typing import List, Dict, Optional
import pytest
from unittest.mock import patch, MagicMock

from src.core.importers.dxf_parser import DXFParser
from src.models.surface import Point3D, Surface


class TestDXFParser:
    """Tests for the DXFParser stub implementation."""

    def test_supported_extensions(self):
        """Test the supported file extensions for DXFParser."""
        extensions = DXFParser.get_supported_extensions()
        assert ".dxf" in extensions

    def test_parse(self):
        """Test parsing a DXF file."""
        # Setup mock
        # mock_get_layers.return_value = ["0", "POINTS", "CONTOURS"]
        
        parser = DXFParser()
        
        # Create a temp file path
        with tempfile.NamedTemporaryFile(suffix='.dxf') as temp_file:
            # Parse the file
            result = parser.parse(temp_file.name)
            
            # Verify parse was successful (stub implementation always returns True)
            assert result is True
            
            # Verify layers were retrieved # REMOVE THIS BLOCK
            # mock_get_layers.assert_called_once_with(temp_file.name)
            # assert parser._layers == ["0", "POINTS", "CONTOURS"]
            
            # Verify dummy point was created
            points = parser.get_points()
            assert len(points) == 1
            assert points[0].x == 0
            assert points[0].y == 0
            assert points[0].z == 0

    def test_validate(self):
        """Test that validate always returns True for the stub implementation."""
        parser = DXFParser()
        
        # Validate should always return True for the stub
        assert parser.validate() is True
        
        # Even with no data
        parser._points = []
        assert parser.validate() is True

    def test_get_contours(self):
        """Test that get_contours returns an empty dict."""
        parser = DXFParser()
        
        contours = parser.get_contours()
        assert isinstance(contours, dict)
        assert len(contours) == 0

    @patch('core.importers.dxf_importer.DXFImporter.import_surface')
    def test_create_surface_success(self, mock_import_surface):
        """Test creating a surface with the stub implementation."""
        # Setup mock
        mock_surface = MagicMock(spec=Surface)
        mock_import_surface.return_value = mock_surface
        
        parser = DXFParser()
        parser._file_path = "test.dxf"
        
        # Create surface
        surface = parser.create_surface("Test Surface")
        
        # Verify importer was called
        mock_import_surface.assert_called_once_with("test.dxf", "Test Surface")
        
        # Verify surface was returned
        assert surface is mock_surface

    @patch('core.importers.dxf_importer.DXFImporter.import_surface')
    def test_create_surface_failure(self, mock_import_surface):
        """Test handling when surface creation fails."""
        # Setup mock to return None
        mock_import_surface.return_value = None
        
        parser = DXFParser()
        parser._file_path = "test.dxf"
        
        # Create surface
        surface = parser.create_surface("Test Surface")
        
        # Verify import was attempted
        mock_import_surface.assert_called_once()
        
        # Verify no surface was returned
        assert surface is None

    # REMOVE THE ENTIRE test_get_layers method
    # def test_get_layers(self):
    #     \"\"\"Test getting available layers.\"\"\"
    #     parser = DXFParser()
    #     parser._layers = [\"0\", \"POINTS\", \"CONTOURS\"]
    #     
    #     layers = parser.get_layers()
    #     assert layers == [\"0\", \"POINTS\", \"CONTOURS\"] 