#!/usr/bin/env python3
"""File parser interface for the DigCalc application.

This module defines the abstract base class for all file parsers
that import data into the DigCalc application.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Use absolute import assuming 'digcalc_project' is the top-level package
from digcalc_project.src.models.surface import Point3D, Surface


class FileParserError(Exception):
    """Exception raised for errors during file parsing."""



class FileParser(ABC):
    """Abstract base class for file parsers.
    
    All file parsers should inherit from this class and implement
    the required methods for parsing and validating data files.
    """

    def __init__(self):
        """Initialize the file parser."""
        self.logger = logging.getLogger(__name__)
        self._file_path = None
        self._data = None
        self._last_error = None  # Track the last error message

    @abstractmethod
    def parse(self, file_path: str, options: Optional[Dict] = None) -> Optional[Surface]:
        """Parse the given file and extract data, returning a Surface object.
        
        Args:
            file_path: Path to the file to parse
            options: Optional dictionary of parser-specific options
            
        Returns:
            Surface object containing parsed data, or None if parsing failed.

        """

    @abstractmethod
    def validate(self) -> bool:
        """Validate the parsed data.
        
        Returns:
            bool: True if data is valid, False otherwise

        """

    @abstractmethod
    def get_points(self) -> List[Point3D]:
        """Get points from the parsed data.
        
        Returns:
            List of Point3D objects

        """

    @abstractmethod
    def get_contours(self) -> Dict[float, List[List[Point3D]]]:
        """Get contour lines from the parsed data.
        
        Returns:
            Dictionary mapping elevations to lists of polylines

        """

    def get_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """Get the bounds of the parsed data.
        
        Returns:
            Tuple (xmin, ymin, xmax, ymax) or None if not available

        """
        points = self.get_points()
        if not points:
            return None

        xmin = min(p.x for p in points)
        ymin = min(p.y for p in points)
        xmax = max(p.x for p in points)
        ymax = max(p.y for p in points)

        return (xmin, ymin, xmax, ymax)

    def log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log an error message.
        
        Args:
            message: Error message
            exception: Optional exception

        """
        error_msg = message
        if exception:
            error_msg = f"{message}: {exception!s}"
            self.logger.error(error_msg)
        else:
            self.logger.error(message)

        # Store the error message
        self._last_error = error_msg

    def get_last_error(self) -> Optional[str]:
        """Get the last error message.
        
        Returns:
            Last error message or None if no error occurred

        """
        return self._last_error

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Get the list of file extensions supported by this parser.
        
        Returns:
            List of file extensions (e.g., ['.csv', '.txt'])

        """
        return []

    @staticmethod
    def get_parser_for_file(file_path: str) -> Optional["FileParser"]:
        """Get the appropriate parser for the given file based on its extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            FileParser instance or None if no suitable parser is found

        """
        # Use relative imports
        from .csv_parser import CSVParser
        from .dxf_parser import DXFParser
        from .landxml_parser import LandXMLParser
        from .pdf_parser import PDFParser

        # Get file extension
        file_extension = Path(file_path).suffix.lower()

        # Map file extensions to parser classes
        parsers = [CSVParser, LandXMLParser, DXFParser, PDFParser]

        for parser_class in parsers:
            if file_extension in parser_class.get_supported_extensions():
                return parser_class()

        return None
