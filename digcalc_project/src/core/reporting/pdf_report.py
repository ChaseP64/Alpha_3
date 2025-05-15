#!/usr/bin/env python3
"""PDF report generator for the DigCalc application.

This module provides functionality to generate PDF reports
of volume calculations and surface data.
"""

import logging
import os
from datetime import datetime
from io import BytesIO

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, Spacer, Table

from ...models.calculation import SliceResult, VolumeCalculation

# In a real implementation, we would use:
# from reportlab.pdfgen import canvas
# from reportlab.lib.pagesizes import letter
# from reportlab.lib import colors
# from reportlab.platypus import Table, TableStyle
# Use relative imports
from ...models.surface import Surface


class PDFReportGenerator:
    """Generator for PDF reports."""

    def __init__(self):
        """Initialize the PDF report generator."""
        self.logger = logging.getLogger(__name__)

    def generate_calculation_report(self, calculation: VolumeCalculation,
                                   output_file: str) -> bool:
        """Generate a PDF report for a volume calculation.
        
        Args:
            calculation: Volume calculation
            output_file: Output file path
            
        Returns:
            bool: True if successful, False otherwise

        """
        self.logger.info(f"Generating PDF report for calculation '{calculation.name}'")

        try:
            # In a real implementation, this would create a PDF file using reportlab
            # c = canvas.Canvas(output_file, pagesize=letter)
            # self._add_header(c, f"Volume Calculation Report: {calculation.name}")
            # self._add_calculation_details(c, calculation)
            # self._add_results_table(c, calculation.results)
            # c.save()

            # For the skeleton, we'll just log what would be done
            self.logger.info(f"Would create PDF at: {output_file}")
            self.logger.info(f"  - Title: Volume Calculation Report: {calculation.name}")
            self.logger.info(f"  - Type: {calculation.calc_type}")
            self.logger.info(f"  - Base Surface: {calculation.base_surface.name}")

            if calculation.comparison_surface:
                self.logger.info(f"  - Comparison Surface: {calculation.comparison_surface.name}")

            if calculation.reference_elevation is not None:
                self.logger.info(f"  - Reference Elevation: {calculation.reference_elevation}")

            self.logger.info(f"  - Results: {calculation.results}")

            # Create a dummy PDF by writing a text file
            self._create_dummy_report(calculation, output_file)

            return True

        except Exception as e:
            self.logger.exception(f"Error generating PDF report: {e}")
            return False

    def generate_surface_report(self, surface: Surface,
                              output_file: str) -> bool:
        """Generate a PDF report for a surface.
        
        Args:
            surface: Surface
            output_file: Output file path
            
        Returns:
            bool: True if successful, False otherwise

        """
        self.logger.info(f"Generating PDF report for surface '{surface.name}'")

        try:
            # In a real implementation, this would create a PDF file using reportlab
            # c = canvas.Canvas(output_file, pagesize=letter)
            # self._add_header(c, f"Surface Report: {surface.name}")
            # self._add_surface_details(c, surface)
            # c.save()

            # For the skeleton, we'll just log what would be done
            self.logger.info(f"Would create PDF at: {output_file}")
            self.logger.info(f"  - Title: Surface Report: {surface.name}")
            self.logger.info(f"  - Type: {surface.surface_type}")
            self.logger.info(f"  - Points: {len(surface.points)}")
            self.logger.info(f"  - Triangles: {len(surface.triangles)}")
            self.logger.info(f"  - Bounds: X({surface.x_min}, {surface.x_max}), Y({surface.y_min}, {surface.y_max}), Z({surface.z_min}, {surface.z_max})")

            # Create a dummy PDF by writing a text file
            self._create_dummy_surface_report(surface, output_file)

            return True

        except Exception as e:
            self.logger.exception(f"Error generating PDF report: {e}")
            return False

    def _create_dummy_report(self, calculation: VolumeCalculation,
                           output_file: str) -> None:
        """Create a dummy report text file for the skeleton implementation.
        
        Args:
            calculation: Volume calculation
            output_file: Output file path

        """
        # Change extension to .txt for the skeleton
        output_file = os.path.splitext(output_file)[0] + ".txt"

        with open(output_file, "w") as f:
            f.write(f"VOLUME CALCULATION REPORT: {calculation.name}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write(f"Calculation Type: {calculation.calc_type}\n")
            f.write(f"Base Surface: {calculation.base_surface.name}\n")

            if calculation.comparison_surface:
                f.write(f"Comparison Surface: {calculation.comparison_surface.name}\n")

            if calculation.reference_elevation is not None:
                f.write(f"Reference Elevation: {calculation.reference_elevation}\n")

            f.write("\nRESULTS:\n")

            if "total_area" in calculation.results:
                f.write(f"Total Area: {calculation.results['total_area']:.2f} sq units\n")

            if "cut_volume" in calculation.results:
                f.write(f"Cut Volume: {calculation.results['cut_volume']:.2f} cubic units\n")

            if "fill_volume" in calculation.results:
                f.write(f"Fill Volume: {calculation.results['fill_volume']:.2f} cubic units\n")

            if "net_volume" in calculation.results:
                f.write(f"Net Volume: {calculation.results['net_volume']:.2f} cubic units\n")

    def _create_dummy_surface_report(self, surface: Surface,
                                   output_file: str) -> None:
        """Create a dummy surface report text file for the skeleton implementation.
        
        Args:
            surface: Surface
            output_file: Output file path

        """
        # Change extension to .txt for the skeleton
        output_file = os.path.splitext(output_file)[0] + ".txt"

        with open(output_file, "w") as f:
            f.write(f"SURFACE REPORT: {surface.name}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write(f"Surface Type: {surface.surface_type}\n")
            f.write(f"Created: {surface.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("STATISTICS:\n")
            f.write(f"Points: {len(surface.points)}\n")
            f.write(f"Triangles: {len(surface.triangles)}\n\n")

            f.write("BOUNDS:\n")
            f.write(f"X Range: {surface.x_min:.2f} to {surface.x_max:.2f}\n")
            f.write(f"Y Range: {surface.y_min:.2f} to {surface.y_max:.2f}\n")
            f.write(f"Z Range: {surface.z_min:.2f} to {surface.z_max:.2f}\n")

    def insert_slice_table(self, slices: list[SliceResult], title: str = "Slice Volumes") -> None:
        """Append a cut/fill *slice table* to the PDF story.

        This helper adds a heading followed by a simple table of slice volume
        data.  It requires ReportLab – if not available the method logs a
        warning and does nothing (so the rest of the report can still be
        generated).
        """
        # Lazy import so we only require ReportLab if this method is used
        try:
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, Spacer, Table
        except ImportError:  # pragma: no cover – optional dependency
            self.logger.warning("ReportLab not available – cannot insert slice table.")
            return

        # Ensure *self.story* exists (skeleton uses a list to collect Flowables)
        if not hasattr(self, "story"):
            self.story: list = []  # type: ignore[attribute-defined-outside-init]

        styles = getSampleStyleSheet()
        self.story.append(Paragraph(title, styles["Heading2"]))

        data = [["Bottom", "Top", "Cut", "Fill"]]
        for s in slices:
            data.append([
                f"{s.z_bottom:.2f}",
                f"{s.z_top:.2f}",
                f"{s.cut:.1f}",
                f"{s.fill:.1f}",
            ])

        table = Table(data, hAlign="LEFT")
        self.story.append(table)
        self.story.append(Spacer(1, 12))

    def insert_mass_haul(self, png_path: str, stations: list, free_ft: float) -> None:
        """Insert a mass-haul diagram section into the PDF story.

        Args:
            png_path: Path to the previously generated PNG of the mass-haul chart.
            stations: List of :class:`core.calculations.mass_haul.HaulStation` objects
                (or duck-typed equivalents). Only used for potential future
                table generation; currently ignored to keep the section
                lightweight.
            free_ft:  Free-haul distance (ft) displayed in the caption.

        """
        # Lazy import – ReportLab is optional at runtime.
        try:
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Image, Paragraph, Spacer
        except ImportError:  # pragma: no cover
            self.logger.warning("ReportLab not available – cannot insert mass-haul diagram.")
            return

        if not hasattr(self, "story"):
            self.story: list = []  # type: ignore[attribute-defined-outside-init]

        styles = getSampleStyleSheet()
        self.story.append(Paragraph("Mass-Haul Diagram", styles["Heading2"]))

        # Embed the PNG. ReportLab uses points; we keep aspect ratio by fixing
        # a width and letting the height auto-scale if PIL is available.
        try:
            # If Pillow is installed we can query the actual image size to scale proportionally.
            from PIL import Image as PILImage

            with PILImage.open(png_path) as img:
                w, h = img.size  # pixels
            target_width = 400  # points (~5.55in) – matches prompt
            target_height = target_width * (h / w)
        except Exception:
            target_width, target_height = 400, 200  # Fallback values

        self.story.append(Image(png_path, width=target_width, height=target_height))
        self.story.append(Paragraph(f"Free-haul distance: {free_ft:.1f} ft", styles["Normal"]))
        self.story.append(Spacer(1, 12))

styles = getSampleStyleSheet()

def h2(txt, story):
    story.append(Paragraph(txt, styles["Heading2"]))

def sp(story, h=12):
    story.append(Spacer(1, h))

def add_job_summary(story, project, settings):
    h2("Job summary", story)
    data=[["Project",project.name],
          ["Date",datetime.now().strftime("%Y-%m-%d %H:%M")],
          ["Default strip depth (ft)",settings.strip_depth_default()],
          ["Slice thickness (ft)",settings.slice_thickness_default()],
          ["Free-haul distance (ft)",settings.slice_thickness_default()]]
    story.append(Table(data,colWidths=[200,200])); sp(story)


def add_region_table(story, region_rows):
    if not region_rows: return
    h2("Region volumes", story)
    data=[["Region","Area","Depth","Cut","Fill","Net"]]
    for r in region_rows:
        data.append([r.name,f"{r.area:.0f}",r.depth or "Def",
                     f"{r.cut:.1f}",f"{r.fill:.1f}",
                     f"{r.fill-r.cut:+.1f}"])
    tbl=Table(data,hAlign="LEFT")
    tbl.setStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey)])
    story.append(tbl); sp(story)


def add_slice_table(story, slices):
    if not slices: return
    h2("Slice volumes", story)
    data=[["Bottom","Top","Cut","Fill"]]
    for s in slices:
        data.append([f"{s.z_bottom:.2f}",f"{s.z_top:.2f}",
                     f"{s.cut:.1f}",f"{s.fill:.1f}"])
    tbl=Table(data,hAlign="LEFT")
    tbl.setStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey)])
    story.append(tbl)

    # bar-chart
    fig,ax=plt.subplots(figsize=(4,2))
    y=[s.z_bottom for s in slices]
    cut=[s.cut for s in slices]
    fill=[s.fill for s in slices]
    ax.barh(y,cut,color="red",label="Cut")
    ax.barh(y,fill,color="green",label="Fill",left=cut)
    ax.invert_yaxis(); ax.set_xlabel("ft³"); ax.legend()
    buf=BytesIO(); fig.savefig(buf,format="png",dpi=150); plt.close(fig)
    buf.seek(0); story.append(Image(buf,width=300,height=150)); sp(story)


def add_mass_haul(story, png_path, free_ft):
    if not png_path: return
    h2("Mass-Haul diagram", story)
    story.append(Image(png_path, width=400, height=200))
    story.append(Paragraph(f"Free-haul distance: {free_ft} ft", styles["Normal"]))
    sp(story)
