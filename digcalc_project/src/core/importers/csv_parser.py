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
    
    def parse(self, file_path: str, options: Optional[Dict[str, Any]] = None) -> Optional[Surface]:
        """
        Parse the given CSV file and return a Surface object.
        
        Args:
            file_path (str): Path to the CSV file.
            options (Optional[Dict[str, Any]]): A dictionary of parsing options.
                Expected keys:
                - 'has_header' (bool): Whether the CSV file has a header row (default: True).
                - 'delimiter' (str): CSV delimiter character (default: ',').
                - 'column_map' (Dict[str, int]): Optional mapping of 'x', 'y', 'z' 
                                                   to 0-based column indices.
                - 'surface_name' (str): Name to assign to the created surface.

        Returns:
            Optional[Surface]: A Surface object if parsing and triangulation succeed, else None.
        """
        self.logger.info(f"Parsing CSV file: {file_path} with options: {options}")
        self._file_path = file_path
        self._points = []
        self._headers = []
        self._column_map = {} 

        # Process options
        if options is None:
            options = {}
        has_header = options.get('has_header', True)
        delimiter = options.get('delimiter', ',')
        user_column_map = options.get('column_map') # User-provided map
        surface_name = options.get('surface_name', Path(file_path).stem) # Get name from options or filename

        try:
            # --- Read File and Headers ---
            with open(file_path, 'r', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=delimiter)
                rows = list(reader)
                
                if not rows:
                    self.log_error("CSV file is empty")
                    return None # Return None on failure
                
                if has_header:
                    if not rows: # Should be caught above, but double-check
                         self.log_error("CSV file has header enabled but is empty")
                         return None
                    self._headers = [h.strip() for h in rows[0]] # Store cleaned headers
                    data_rows = rows[1:]
                    if not data_rows:
                         self.logger.warning("CSV file contains only a header row.")
                         # Allow creating an empty surface if needed, but log it
                else:
                    # Synthesize headers if none exist
                    num_cols = len(rows[0]) if rows else 0
                    self._headers = [f"Column{i+1}" for i in range(num_cols)]
                    data_rows = rows
            
            # --- Determine Column Mapping --- 
            if isinstance(user_column_map, dict) and all(k in user_column_map for k in ['x', 'y', 'z']):
                 # Use user-provided map if valid
                 self.logger.info(f"Using user-provided column map: {user_column_map}")
                 self._column_map = user_column_map
            else:
                 # Attempt auto-detection if no valid user map provided
                 self.logger.info("Attempting to auto-detect columns from headers.")
                 self._column_map = self._detect_columns()

            # --- Validate Mapping and Parse Points ---
            if not self._is_valid_column_map():
                # Log the headers to help diagnose detection issues
                self.log_error(f"Invalid column mapping. Could not identify X, Y, Z columns. Headers: {self._headers}. Detected map: {self._column_map}")
                # Raise error instead of returning None to give more info upstream
                raise FileParserError("Could not determine X, Y, Z column mapping.") 
            
            self.logger.info(f"Using column map: X={self._column_map['x']}, Y={self._column_map['y']}, Z={self._column_map['z']}")
            self._parse_points(data_rows)
            
            self.logger.info(f"Parsed {len(self._points)} points from CSV data rows.")

            # --- Validate Parsed Points --- 
            if not self.validate(): # Validate checks for points and NaN/Inf
                # Error already logged by validate()
                # Raise error if validation fails (e.g., no points or bad data)
                raise FileParserError(self.get_last_error() or "Parsed data validation failed.")

            # --- Create Surface --- 
            # Note: create_surface now happens outside the main parse try-except
            # to separate parsing errors from triangulation errors.
            
        except FileNotFoundError:
            self.log_error(f"File not found: {file_path}")
            raise # Re-raise standard exceptions
        except ValueError as ve:
             # Catch float conversion errors during _parse_points
             self.log_error(f"Data conversion error: {ve}", ve)
             raise FileParserError(f"Could not convert data to numbers. Check CSV format and column selection. Error: {ve}") from ve
        except IndexError as ie:
            # Catch errors if column indices are out of bounds
            self.log_error(f"Column index error during parsing: {ie}", ie)
            raise FileParserError(f"Selected column index is out of bounds for some rows. Check column mapping and CSV structure. Error: {ie}") from ie
        except FileParserError: # Re-raise our specific errors
            raise
        except Exception as e:
            # Catch other potential file reading/parsing errors
            self.log_error(f"Error parsing CSV file: {e}", e)
            raise FileParserError(f"An unexpected error occurred during CSV parsing: {e}") from e
            
        # --- Create Surface (after successful parsing and validation) ---
        try:
             # Create surface using the parsed points
             surface = self.create_surface(surface_name)
             return surface # Return the Surface object on success
        except Exception as e:
             # Catch errors during surface creation/triangulation
             self.log_error(f"Error creating surface '{surface_name}' from parsed data: {e}", e)
             # Raise error to indicate failure after successful parsing
             raise FileParserError(f"Failed to create surface after parsing: {e}") from e

    def get_headers(self) -> List[str]:
        """Returns the detected or synthesized headers."""
        # Ensure headers are populated, e.g., by calling parse first or a dedicated peek method.
        # This might need adjustment if headers are needed before full parsing.
        return self._headers

    def peek_headers(self, file_path: str, has_header: bool = True, delimiter: str = ',') -> List[str]:
        """
        Reads only the first line to get headers or determine column count.

        Args:
            file_path (str): Path to the CSV file.
            has_header (bool): Whether to treat the first line as headers.
            delimiter (str): CSV delimiter character.

        Returns:
            List[str]: List of header strings or synthesized column names.
        
        Raises:
            FileNotFoundError: If the file doesn't exist.
            Exception: For other file reading errors.
        """
        self.logger.debug(f"Peeking headers from: {file_path}")
        try:
            with open(file_path, 'r', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=delimiter)
                first_row = next(reader, None) # Read only the first row
                
                if first_row is None:
                    self.logger.warning(f"Peek headers: File '{file_path}' is empty.")
                    return []
                
                if has_header:
                    headers = [h.strip() for h in first_row]
                    self.logger.debug(f"Peek headers found: {headers}")
                    return headers
                else:
                    # Synthesize headers based on the number of columns in the first row
                    num_cols = len(first_row)
                    headers = [f"Column {i+1}" for i in range(num_cols)]
                    self.logger.debug(f"Peek headers synthesized: {headers}")
                    return headers
        except FileNotFoundError:
            self.log_error(f"Peek headers: File not found: {file_path}")
            raise
        except Exception as e:
            self.log_error(f"Peek headers: Error reading file {file_path}: {e}", e)
            raise FileParserError(f"Could not read headers from file: {e}") from e
    
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
        
        # If we couldn't detect all columns based on common patterns,
        # try positional as a fallback if at least 3 columns exist.
        if len(column_map) < 3 and len(self._headers) >= 3:
            self.logger.warning(
                "Could not reliably detect X, Y, Z columns from headers. "
                "Falling back to positional columns (0=X, 1=Y, 2=Z). "
                "Verify results or provide manual mapping if available."
            )
            # Assume first three columns are X, Y, Z in that order if not already mapped
            if 'x' not in column_map:
                column_map['x'] = 0
            if 'y' not in column_map:
                column_map['y'] = 1
            if 'z' not in column_map:
                column_map['z'] = 2
        
        # Log the final detected map for debugging
        if not column_map or len(column_map) < 3:
             self.logger.warning(f"Column detection resulted in incomplete map: {column_map}")
        else:
             self.logger.debug(f"Final detected column map: {column_map}")
             
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