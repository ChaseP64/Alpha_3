#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV parser for the DigCalc application.

This module provides functionality to import point cloud data from CSV files
and convert it to DigCalc Surface models.
"""

import csv
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np

from src.core.importers.file_parser import FileParser, FileParserError
from src.models.surface import Surface, Point3D


class CSVParser(FileParser):
    """
    Parser for CSV files containing point data.
    
    Supported formats:
    - X,Y,Z columns (with or without headers)
    - Custom column mapping (specified during parsing)
    """
    
    def __init__(self):
        """Initialize the CSV parser."""
        super().__init__()
        self._points = []
        self._headers = []
        self._column_map = {}  # Maps 'x', 'y', 'z' to column indices
        
        # Save reference to TINGenerator class
        # This allows mocking in tests
        from src.core.geometry.tin_generator import TINGenerator
        self._TINGenerator = TINGenerator
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """
        Get the list of file extensions supported by this parser.
        
        Returns:
            List of file extensions
        """
        return ['.csv', '.txt']
    
    def parse(self, file_path: str, column_map: Optional[Dict[str, int]] = None,
             has_header: bool = True, delimiter: str = ',') -> bool:
        """
        Parse the given CSV file and extract point data.
        
        Args:
            file_path: Path to the CSV file
            column_map: Optional mapping of 'x', 'y', 'z' to column indices (0-based)
            has_header: Whether the CSV file has a header row
            delimiter: CSV delimiter character
            
        Returns:
            bool: True if parsing succeeded, False otherwise
        """
        self.logger.info(f"Parsing CSV file: {file_path}")
        self._file_path = file_path
        self._points = []
        
        try:
            with open(file_path, 'r', newline='') as csvfile:
                # Read the entire file as a list of rows
                reader = csv.reader(csvfile, delimiter=delimiter)
                rows = list(reader)
                
                if not rows:
                    self.log_error("CSV file is empty")
                    return False
                
                # Extract headers if present
                if has_header:
                    self._headers = rows[0]
                    data_rows = rows[1:]
                else:
                    self._headers = [f"Column{i+1}" for i in range(len(rows[0]))]
                    data_rows = rows
                
                # Determine column mapping
                if column_map:
                    self._column_map = column_map
                else:
                    # Try to auto-detect columns
                    self._column_map = self._detect_columns()
                
                # Check if we have a valid column mapping
                if not self._is_valid_column_map():
                    self.log_error("Invalid column mapping, could not identify X, Y, Z columns")
                    return False
                
                # Parse points from data rows
                self._parse_points(data_rows)
                
                self.logger.info(f"Parsed {len(self._points)} points from CSV")
                return self.validate()
                
        except Exception as e:
            self.log_error("Error parsing CSV file", e)
            return False
    
    def validate(self) -> bool:
        """
        Validate the parsed data.
        
        Returns:
            bool: True if data is valid, False otherwise
        """
        if not self._points:
            self.log_error("No valid points found in CSV file")
            return False
        
        # Check for any NaN or Inf values
        for point in self._points:
            if (np.isnan(point.x) or np.isnan(point.y) or np.isnan(point.z) or
                np.isinf(point.x) or np.isinf(point.y) or np.isinf(point.z)):
                self.log_error(f"Invalid coordinate values found: {point}")
                return False
        
        return True
    
    def get_points(self) -> List[Point3D]:
        """
        Get points from the parsed data.
        
        Returns:
            List of Point3D objects
        """
        return self._points
    
    def get_contours(self) -> Dict[float, List[List[Point3D]]]:
        """
        Get contour lines from the parsed data.
        
        CSV files typically don't contain contour information,
        so this returns an empty dictionary.
        
        Returns:
            Empty dictionary
        """
        return {}
    
    def create_surface(self, name: str) -> Optional[Surface]:
        """
        Create a surface from the parsed data.
        
        Args:
            name: Name for the created surface
            
        Returns:
            Surface object or None if creation failed
        """
        if not self._points:
            self.log_error("No points available to create surface")
            return None
        
        try:
            # Use the stored TINGenerator class
            tin_generator = self._TINGenerator()
            
            # Generate surface with triangulation from points
            surface = tin_generator.generate_from_points(self._points, name)
            
            # Validate the generated surface
            if not surface.triangles:
                self.logger.warning(f"TIN generation produced no triangles for surface '{name}'")
            
            self.logger.info(f"Created surface '{name}' from CSV data with {len(surface.points)} points and {len(surface.triangles)} triangles")
            return surface
            
        except Exception as e:
            self.log_error(f"Error creating surface from CSV data: {e}", e)
            return None
    
    def _detect_columns(self) -> Dict[str, int]:
        """
        Attempt to detect X, Y, Z columns from headers.
        
        Returns:
            Dict mapping 'x', 'y', 'z' to column indices
        """
        column_map = {}
        
        # Check headers for common patterns
        for i, header in enumerate(self._headers):
            header_lower = header.lower()
            
            if header_lower in ['x', 'easting', 'east', 'lng', 'longitude']:
                column_map['x'] = i
            elif header_lower in ['y', 'northing', 'north', 'lat', 'latitude']:
                column_map['y'] = i
            elif header_lower in ['z', 'elevation', 'elev', 'alt', 'altitude', 'height']:
                column_map['z'] = i
        
        # If we couldn't detect all columns, try positional
        if len(column_map) < 3 and len(self._headers) >= 3:
            # Assume first three columns are X, Y, Z in that order
            if 'x' not in column_map:
                column_map['x'] = 0
            if 'y' not in column_map:
                column_map['y'] = 1
            if 'z' not in column_map:
                column_map['z'] = 2
        
        return column_map
    
    def _is_valid_column_map(self) -> bool:
        """
        Check if we have a valid column mapping.
        
        Returns:
            bool: True if mapping is valid, False otherwise
        """
        return ('x' in self._column_map and 
                'y' in self._column_map and 
                'z' in self._column_map)
    
    def _parse_points(self, data_rows: List[List[str]]) -> None:
        """
        Parse points from data rows.
        
        Args:
            data_rows: List of rows, each a list of string values
        """
        x_col = self._column_map['x']
        y_col = self._column_map['y']
        z_col = self._column_map['z']
        
        for i, row in enumerate(data_rows):
            try:
                # Skip rows that don't have enough columns
                if len(row) <= max(x_col, y_col, z_col):
                    continue
                
                # Parse coordinates
                x = float(row[x_col])
                y = float(row[y_col])
                z = float(row[z_col])
                
                # Add point
                self._points.append(Point3D(x, y, z))
                
            except (ValueError, IndexError) as e:
                # Log but continue processing
                self.logger.warning(f"Error parsing row {i+1}: {e}")
                continue 