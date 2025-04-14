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
from io import StringIO

import numpy as np

# Use relative imports
from .file_parser import FileParser, FileParserError
from ...models.surface import Surface, Point3D


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
        # Use relative import
        from ..geometry.tin_generator import TINGenerator
        self._TINGenerator = TINGenerator
    
    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """
        Get the list of file extensions supported by this parser.
        
        Returns:
            List of file extensions
        """
        return ['.csv', '.txt']
    
    def parse(self, file_path: str, options: Optional[Dict] = None) -> Optional[Surface]:
        """
        Parse the CSV file and create a Surface object.

        Args:
            file_path (str): Path to the CSV file.
            options (Optional[Dict]): Dictionary with parsing options like 
                                      'delimiter', 'skip_rows', 'x_col', 'y_col', 'z_col'.

        Returns:
            Optional[Surface]: A Surface object populated with points from the CSV, or None on failure.
        """
        self.logger.info(f"Parsing CSV file: '{file_path}' with options: {options}")
        self._file_path = file_path
        self._points = []
        options = options or {} # Ensure options is a dict

        # Determine parameters from options or use defaults/auto-detection
        delimiter = options.get('delimiter', ',')
        skip_rows = options.get('skip_rows', 0)
        x_col_name = options.get('x_col')
        y_col_name = options.get('y_col')
        z_col_name = options.get('z_col')

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                # Read header row if needed to determine column indices
                header = None
                if x_col_name or y_col_name or z_col_name: # If specific columns are requested
                    for _ in range(skip_rows):
                        f.readline()
                    reader = csv.reader(StringIO(f.readline()), delimiter=delimiter)
                    header = next(reader)
                    self.logger.debug(f"CSV Header found: {header}")
                    
                    x_col = header.index(x_col_name) if x_col_name in header else None
                    y_col = header.index(y_col_name) if y_col_name in header else None
                    z_col = header.index(z_col_name) if z_col_name in header else None
                    
                    if x_col is None or y_col is None or z_col is None:
                        missing = [name for name, idx in [('X', x_col), ('Y', y_col), ('Z', z_col)] if idx is None]
                        raise FileParserError(f"Required columns not found in header: {missing}")
                    self.logger.info(f"Using columns - X: {x_col}, Y: {y_col}, Z: {z_col}")
                else:
                     # Basic auto-detect: Assume first three columns are X, Y, Z
                     x_col, y_col, z_col = 0, 1, 2
                     self.logger.info(f"No columns specified, assuming X={x_col}, Y={y_col}, Z={z_col}")
                     # Skip rows if no header was read
                     for _ in range(skip_rows):
                         f.readline()
                
                # Read data rows
                reader = csv.reader(f, delimiter=delimiter)
                line_num = skip_rows + (1 if header else 0) # Adjust starting line number
                for row in reader:
                    line_num += 1
                    if len(row) <= max(x_col, y_col, z_col): # Basic check for row length
                        self.logger.warning(f"Skipping short row {line_num}: {row}")
                        continue
                    try:
                        x = float(row[x_col])
                        y = float(row[y_col])
                        z = float(row[z_col])
                        self._points.append(Point3D(x, y, z))
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"Skipping invalid data in row {line_num}: {row}. Error: {e}")
                        continue 
            
            if not self._points:
                self.logger.warning(f"No valid points found in CSV file '{file_path}'.")
                return None

            self.logger.info(f"Successfully parsed {len(self._points)} points from CSV.")
            
            # Create and return the Surface object directly
            surface_name = Path(file_path).stem # Use filename as default name
            surface = Surface(name=surface_name)
            for point in self._points:
                 surface.add_point(point)
            # Optionally trigger TIN generation here if points > 2?
            # if len(surface.points) > 2:
            #     surface.generate_tin() # Assuming such a method exists
            return surface

        except FileNotFoundError:
            raise FileParserError(f"CSV file not found: '{file_path}'")
        except ValueError as ve:
            raise FileParserError(f"Invalid numeric data found in CSV '{file_path}': {ve}")
        except IndexError as ie:
             # This might occur if a specific column index is invalid for a row
             raise FileParserError(f"Column index error while parsing CSV '{file_path}'. Check column configuration and data consistency. Error: {ie}")
        except FileParserError as fpe: # Re-raise specific parser errors
             raise fpe
        except Exception as e:
            raise FileParserError(f"An unexpected error occurred parsing CSV '{file_path}': {e}")
            
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