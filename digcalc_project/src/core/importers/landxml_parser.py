#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LandXML parser for the DigCalc application.

This module provides functionality to import surface data from LandXML files
and convert it to DigCalc Surface models.
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from src.core.importers.file_parser import FileParser, FileParserError
from src.models.surface import Surface, Point3D, Triangle


class LandXMLParser(FileParser):
    """
    Parser for LandXML files containing surface data.
    
    Supports parsing of:
    - TIN surfaces (<Surface><Definition><Pnts>/<Faces>)
    - Grid surfaces (<Grid>)
    - Point groups (<CgPoints>)
    """
    
    def __init__(self):
        """Initialize the LandXML parser."""
        super().__init__()
        self._root = None
        self._ns = {}  # XML namespaces
        self._points = []
        self._triangles = []
        self._contours = {}
        self._surfaces = []
        
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
        return ['.xml', '.landxml']
    
    def parse(self, file_path: str) -> bool:
        """
        Parse the given LandXML file and extract surface data.
        
        Args:
            file_path: Path to the LandXML file
            
        Returns:
            bool: True if parsing succeeded, False otherwise
        """
        self.logger.info(f"Parsing LandXML file: {file_path}")
        self._file_path = file_path
        self._points = []
        self._triangles = []
        self._contours = {}
        self._surfaces = []
        
        try:
            # Parse XML
            tree = ET.parse(file_path)
            self._root = tree.getroot()
            
            # Extract namespace if present
            if '}' in self._root.tag:
                ns = self._root.tag.split('}')[0].strip('{')
                self._ns = {'ns': ns}
                self.logger.debug(f"Found XML namespace: {ns}")
            
            # Check if this is a valid LandXML file
            if not self._is_landxml():
                self.log_error("Not a valid LandXML file")
                return False
            
            # Parse surface data
            self._parse_surfaces()
            
            # If no surfaces were found, try to parse point data
            if not self._points and not self._triangles:
                self._parse_point_groups()
            
            self.logger.info(f"Parsed {len(self._points)} points and {len(self._triangles)} triangles from LandXML")
            return self.validate()
            
        except Exception as e:
            self.log_error("Error parsing LandXML file", e)
            return False
    
    def validate(self) -> bool:
        """
        Validate the parsed data.
        
        Returns:
            bool: True if data is valid, False otherwise
        """
        if not self._points:
            self.log_error("No valid points found in LandXML file")
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
        
        Returns:
            Dictionary mapping elevations to lists of polylines
        """
        return self._contours
    
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
            # If we already have triangles from the LandXML file, use them
            if self._triangles:
                self.logger.info(f"Creating surface '{name}' with {len(self._points)} points and {len(self._triangles)} triangles from LandXML")
                
                # Create a new surface with the correct type
                surface = Surface(name, Surface.SURFACE_TYPE_TIN)
                
                # Add all points and triangles
                for point in self._points:
                    surface.add_point(point)
                
                for triangle in self._triangles:
                    surface.add_triangle(triangle)
                    
                return surface
            
            # If no triangles were parsed, generate them using the TIN generator
            else:
                self.logger.info(f"No triangles found in LandXML data. Generating TIN from {len(self._points)} points")
                
                # Use the stored TINGenerator class
                tin_generator = self._TINGenerator()
                
                # Generate surface with triangulation from points
                surface = tin_generator.generate_from_points(self._points, name)
                
                # Validate the generated surface
                if not surface.triangles:
                    self.logger.warning(f"TIN generation produced no triangles for surface '{name}'")
                
                self.logger.info(f"Created surface '{name}' from LandXML data with {len(surface.points)} points and {len(surface.triangles)} triangles")
                return surface
            
        except Exception as e:
            self.log_error(f"Error creating surface from LandXML data: {e}", e)
            return None
    
    def get_available_surfaces(self) -> List[str]:
        """
        Get the names of surfaces defined in the LandXML file.
        
        Returns:
            List of surface names
        """
        return self._surfaces
    
    def _is_landxml(self) -> bool:
        """
        Check if the parsed file is a valid LandXML file.
        
        Returns:
            bool: True if valid, False otherwise
        """
        if self._root is None:
            return False
        
        # Check root tag
        if 'LandXML' not in self._root.tag:
            return False
        
        return True
    
    def _parse_surfaces(self) -> None:
        """Parse surface elements from LandXML."""
        # Find all Surface elements
        xpath = './/ns:Surface' if self._ns else './/Surface'
        surface_elements = self._root.findall(xpath, self._ns)
        
        # If we have multiple surfaces, only parse the first one for now
        # Store all surface names for reference
        for i, surface_elem in enumerate(surface_elements):
            # Get surface name
            name = surface_elem.get('name', f"Surface_{i+1}")
            self._surfaces.append(name)
            
            # If this is the first surface, parse its points and faces
            if i == 0:
                self.logger.info(f"Parsing surface: {name}")
                # Parse points
                self._parse_surface_points(surface_elem)
                
                # Parse faces (triangles)
                self._parse_surface_faces(surface_elem)
    
    def _parse_surface_points(self, surface_elem: ET.Element) -> None:
        """
        Parse points from a Surface element.
        
        Args:
            surface_elem: Surface XML element
        """
        # Find the Points element
        xpath = './/ns:Pnts/ns:P' if self._ns else './/Pnts/P'
        point_elements = surface_elem.findall(xpath, self._ns)
        
        # Map point IDs to Point3D objects
        point_map = {}
        
        for i, point_elem in enumerate(point_elements):
            try:
                # Point coordinates are space-separated in the element text
                coords = point_elem.text.strip().split()
                if len(coords) < 3:
                    continue
                
                x = float(coords[0])
                y = float(coords[1])
                z = float(coords[2])
                
                # Get point ID
                point_id = point_elem.get('id') or str(i + 1)
                
                # Create point
                point = Point3D(x, y, z, point_id)
                self._points.append(point)
                point_map[point_id] = point
                
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Error parsing point: {e}")
                continue
        
        # Store point map for triangle creation
        self._point_map = point_map
    
    def _parse_surface_faces(self, surface_elem: ET.Element) -> None:
        """
        Parse faces (triangles) from a Surface element.
        
        Args:
            surface_elem: Surface XML element
        """
        # Find the Faces element
        xpath = './/ns:Faces/ns:F' if self._ns else './/Faces/F'
        face_elements = surface_elem.findall(xpath, self._ns)
        
        for i, face_elem in enumerate(face_elements):
            try:
                # Face vertices are space-separated point IDs in the element text
                vertex_ids = face_elem.text.strip().split()
                if len(vertex_ids) < 3:
                    self.logger.warning(f"Face element has less than 3 vertex IDs: {face_elem.text}")
                    continue
                
                # Get points by ID from the map created in _parse_surface_points
                if not hasattr(self, '_point_map') or not self._point_map:
                    self.logger.warning("Point map not available for triangle creation")
                    continue
                    
                points = []
                for vid in vertex_ids[:3]:
                    if vid in self._point_map:
                        points.append(self._point_map[vid])
                    else:
                        self.logger.warning(f"Point ID {vid} not found in point map")
                        break
                
                # Only create triangle if we have all three points
                if len(points) == 3:
                    triangle = Triangle(points[0], points[1], points[2])
                    self._triangles.append(triangle)
                
            except Exception as e:
                self.logger.warning(f"Error parsing face element {i}: {e}")
                continue
    
    def _parse_point_groups(self) -> None:
        """Parse point groups from LandXML."""
        # Find all CgPoints elements
        xpath = './/ns:CgPoints/ns:CgPoint' if self._ns else './/CgPoints/CgPoint'
        point_elements = self._root.findall(xpath, self._ns)
        
        for i, point_elem in enumerate(point_elements):
            try:
                # Point coordinates are space-separated in the element text
                coords = point_elem.text.strip().split()
                if len(coords) < 3:
                    continue
                
                y = float(coords[0])  # Note: LandXML CgPoint uses North, East, Elev order
                x = float(coords[1])
                z = float(coords[2])
                
                # Get point ID
                point_id = point_elem.get('id') or str(i + 1)
                
                # Create point
                point = Point3D(x, y, z, point_id)
                self._points.append(point)
                
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Error parsing point: {e}")
                continue 