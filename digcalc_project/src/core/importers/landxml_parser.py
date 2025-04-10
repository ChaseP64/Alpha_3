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
import uuid

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
    
    def parse(self, file_path: str, options: Optional[Dict] = None) -> Optional[Surface]:
        """
        Parse the given LandXML file and extract surface data.
        
        Args:
            file_path: Path to the LandXML file
            options: Optional dictionary of parser-specific options (e.g., surface_name_to_load)
            
        Returns:
            Surface object or None if parsing failed.
        """
        self.logger.info(f"Parsing LandXML file: '{file_path}' with options: {options}")
        self._file_path = file_path
        self._points = {} # Use dict for point lookup by ID
        self._triangles = []
        self._surfaces = [] # List of available surface names
        self.selected_surface_name = options.get('surface_name') if options else None # Specific surface to load

        try:
            # Parse XML
            tree = ET.parse(file_path)
            self._root = tree.getroot()
            
            # Extract namespace if present
            self._ns = self._get_namespace(self._root)
            
            # Check if this is a valid LandXML file
            if not self._is_landxml():
                raise FileParserError("Not a valid LandXML file.")
            
            # Find all available surface definitions
            available_surfaces = self._find_available_surfaces()
            self._surfaces = list(available_surfaces.keys())
            
            if not available_surfaces:
                self.logger.warning("No <Surface> elements found. Looking for <CgPoints>.")
                # If no surfaces, try parsing point groups
                cg_points = self._parse_point_groups()
                if not cg_points:
                    raise FileParserError("No surfaces or CgPoints found in LandXML file.")
                # Create a surface from CgPoints
                self.logger.info(f"Creating surface from {len(cg_points)} CgPoints.")
                surface_name = Path(file_path).stem + "_Points"
                surface = Surface(name=surface_name)
                for point in cg_points.values():
                    surface.add_point(point)
                # Optionally generate TIN if enough points? Requires TINGenerator
                # if len(surface.points) > 2:
                #     try: surface.generate_tin() # Assuming method exists
                #     except Exception as tin_e: self.logger.warning(f"Failed to auto-generate TIN for CgPoints: {tin_e}")
                return surface
            
            # Determine which surface to load
            target_surface_name = None
            if self.selected_surface_name and self.selected_surface_name in available_surfaces:
                target_surface_name = self.selected_surface_name
            elif available_surfaces:
                target_surface_name = next(iter(available_surfaces)) # Default to first found
                self.logger.info(f"No specific surface selected, loading the first one found: '{target_surface_name}'")
            else:
                 raise FileParserError("No surfaces available to load.")
                 
            target_surface_elem = available_surfaces[target_surface_name]
            
            # Parse the selected surface definition
            surface_definition = self._parse_surface_definition(target_surface_elem)
            if not surface_definition or not surface_definition.get('points'):
                 raise FileParserError(f"Failed to parse definition for surface '{target_surface_name}'.")
                 
            # Create the Surface object
            surface = Surface(name=target_surface_name)
            point_map = surface_definition.get('points', {})
            triangle_data = surface_definition.get('faces', [])
            
            for point in point_map.values():
                surface.add_point(point)
            
            # Add triangles, linking points
            for face_indices in triangle_data:
                 try:
                      p1 = point_map.get(face_indices[0])
                      p2 = point_map.get(face_indices[1])
                      p3 = point_map.get(face_indices[2])
                      if p1 and p2 and p3:
                           # Only add triangle if all points were found
                           surface.add_triangle(Triangle(p1, p2, p3))
                      else:
                           missing_ids = [idx for idx, p in zip(face_indices, [p1, p2, p3]) if p is None]
                           self.logger.warning(f"Skipping face referencing missing point IDs: {missing_ids}")
                 except IndexError:
                     self.logger.warning(f"Skipping invalid face data: {face_indices}")
                     
            self.logger.info(f"Successfully created surface '{surface.name}' with {len(surface.points)} points and {len(surface.triangles)} triangles.")
            return surface

        except ET.ParseError as pe:
            raise FileParserError(f"Invalid XML structure: {pe}")
        except FileNotFoundError:
            raise FileParserError(f"LandXML file not found: '{file_path}'")
        except FileParserError as fpe:
            self.log_error(str(fpe))
            raise # Re-raise our specific errors
        except Exception as e:
            self.log_error(f"An unexpected error occurred parsing LandXML '{file_path}': {e}", e)
            raise FileParserError(f"Unexpected LandXML parsing error: {e}")
            
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
    
    def _get_namespace(self, element: ET.Element) -> Dict:
        ns = {}
        if '}' in element.tag:
            ns_uri = element.tag.split('}')[0].strip('{')
            ns = {'ns': ns_uri}
            self.logger.debug(f"Found XML namespace: {ns_uri}")
        return ns

    def _find_available_surfaces(self) -> Dict[str, ET.Element]:
        """Finds all <Surface> elements and returns a dict mapping name to element."""
        surfaces = {}
        xpath = './/ns:Surfaces/ns:Surface' if self._ns else './/Surfaces/Surface'
        try:
            surface_elements = self._root.findall(xpath, self._ns)
            for i, surface_elem in enumerate(surface_elements):
                name = surface_elem.get('name', f"Surface_{i+1}")
                surfaces[name] = surface_elem
            self.logger.debug(f"Found available surfaces: {list(surfaces.keys())}")
        except Exception as e:
             self.logger.error(f"Error finding surface elements: {e}")
        return surfaces

    def _parse_surface_definition(self, surface_elem: ET.Element) -> Optional[Dict]:
        """Parses the <Definition> of a <Surface> element for points and faces."""
        xpath_def = 'ns:Definition' if self._ns else 'Definition'
        definition = surface_elem.find(xpath_def, self._ns)
        if definition is None:
             self.logger.warning(f"Surface '{surface_elem.get('name')}' has no <Definition> element.")
             return None
             
        points = self._parse_pnts(definition)
        faces = self._parse_faces(definition)
        
        if not points:
             self.logger.warning(f"Surface '{surface_elem.get('name')}' definition has no points.")
             return None # A surface needs points

        return {'points': points, 'faces': faces}
        
    def _parse_pnts(self, definition_elem: ET.Element) -> Dict[str, Point3D]:
        """Parses <Pnts> within a <Definition> element."""
        points = {}
        xpath_pnts = 'ns:Pnts/ns:P' if self._ns else 'Pnts/P'
        point_elements = definition_elem.findall(xpath_pnts, self._ns)
        for point_elem in point_elements:
            try:
                point_id = point_elem.get('id')
                if point_id is None:
                    self.logger.warning(f"Skipping point without ID: {ET.tostring(point_elem, encoding='unicode')}")
                    continue
                
                coords = point_elem.text.strip().split()
                if len(coords) >= 3:
                    # LandXML order is typically Y X Z (Northing Easting Elevation)
                    y, x, z = map(float, coords[:3])
                    points[point_id] = Point3D(x, y, z, point_id=point_id)
                else:
                    self.logger.warning(f"Skipping point '{point_id}' with invalid coordinate data: {coords}")
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Error parsing point '{point_elem.get('id', 'N/A')}: {e}. Data: '{point_elem.text}'")
        self.logger.debug(f"Parsed {len(points)} points from <Pnts>.")
        return points

    def _parse_faces(self, definition_elem: ET.Element) -> List[Tuple[str, str, str]]:
        """Parses <Faces> within a <Definition> element."""
        faces = []
        xpath_faces = 'ns:Faces/ns:F' if self._ns else 'Faces/F'
        face_elements = definition_elem.findall(xpath_faces, self._ns)
        for face_elem in face_elements:
            try:
                # Indices are 1-based IDs referring to points in <Pnts>
                indices = face_elem.text.strip().split()
                if len(indices) >= 3:
                    # Assuming the IDs match the point IDs from <Pnts>
                    # Store as string IDs
                    p1_id, p2_id, p3_id = indices[0], indices[1], indices[2]
                    faces.append((p1_id, p2_id, p3_id))
                else:
                    self.logger.warning(f"Skipping face with invalid index data: {indices}")
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Error parsing face: {e}. Data: '{face_elem.text}'")
        self.logger.debug(f"Parsed {len(faces)} faces from <Faces>.")
        return faces

    def _parse_point_groups(self) -> Dict[str, Point3D]:
        """Parses <CgPoints> elements."""
        points = {}
        xpath_cg = './/ns:CgPoints/ns:CgPoint' if self._ns else './/CgPoints/CgPoint'
        point_elements = self._root.findall(xpath_cg, self._ns)
        for point_elem in point_elements:
            try:
                point_id = point_elem.get('name') or point_elem.get('oID') # Use name or oID as ID
                if point_id is None:
                     point_id = str(uuid.uuid4()) # Generate if missing
                     
                coords = point_elem.text.strip().split()
                if len(coords) >= 3:
                    # Order Y X Z (Northing Easting Elevation)
                    y, x, z = map(float, coords[:3])
                    points[point_id] = Point3D(x, y, z, point_id=point_id)
                else:
                    self.logger.warning(f"Skipping CgPoint '{point_id}' with invalid coordinate data: {coords}")
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Error parsing CgPoint '{point_elem.get('name', 'N/A')}: {e}. Data: '{point_elem.text}'")
        self.logger.debug(f"Parsed {len(points)} points from <CgPoints>.")
        return points 