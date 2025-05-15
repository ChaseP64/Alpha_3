#!/usr/bin/env python3
from __future__ import annotations  # Postpones evaluation of type hints

"""
PDF Rendering Module for DigCalc.

Uses PyMuPDF (fitz) to load and render PDF pages as QImage objects.
"""

import logging
import sys
import typing  # Import typing
from typing import List, Optional

# --- Dependency Handling ---
# Check for PyMuPDF (fitz)
if typing.TYPE_CHECKING:
    import fitz  # Move import here
else:
    try:
        import fitz  # PyMuPDF - Requires `pip install PyMuPDF`
    except ImportError:
        print("Error: PyMuPDF (fitz) library not found.", file=sys.stderr)
        print("Please install it: pip install PyMuPDF", file=sys.stderr)
        fitz = None  # Indicate missing library

# Check for PySide6
try:
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication  # Needed for __main__ test
    # QPixmap can be created from QImage if needed later
except ImportError:
    print("Error: PySide6 library not found.", file=sys.stderr)
    print("Please install it: pip install PySide6", file=sys.stderr)
    QImage = None # Indicate missing library
    QApplication = None # Indicate missing library
# --- End Dependency Handling ---


class PDFRendererError(Exception):
    """Custom exception for PDF Renderer errors."""



class PDFRenderer:
    """Handles loading PDF files and rendering pages as QImage objects using PyMuPDF.

    Attributes:
        pdf_path (str): Path to the loaded PDF file.
        dpi (int): Resolution used for rendering pages.
        scale (float): Placeholder for horizontal scale factor (for future calibration).
        rotation_angle (float): Placeholder for rotation angle in degrees (for future calibration).
        offset_x (float): Placeholder for X offset (for future calibration).
        offset_y (float): Placeholder for Y offset (for future calibration).
        doc: The loaded PyMuPDF document object.

    """

    logger = logging.getLogger(__name__)

    def __init__(self, pdf_path: str, dpi: int = 150):
        """Initialize the PDFRenderer, load the PDF, and render its pages.

        Args:
            pdf_path (str): The full path to the PDF file.
            dpi (int): The resolution (dots per inch) to use for rendering pages.
                       Higher values produce larger, more detailed images. Defaults to 150.

        Raises:
            PDFRendererError: If PyMuPDF or PySide6 is not installed, or if the
                              PDF file cannot be opened or rendered.
            FileNotFoundError: If the pdf_path does not exist.

        """
        if fitz is None or QImage is None:
            raise PDFRendererError("Required libraries (PyMuPDF, PySide6) not available.")

        self.pdf_path: str = pdf_path
        self.dpi: int = dpi
        self.logger.info(f"PDFRenderer initialized with DPI: {self.dpi}")
        self._rendered_pages: List[QImage] = []
        self.doc = None

        # Placeholders for future calibration/alignment
        self.scale: float = 1.0
        self.rotation_angle: float = 0.0
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0

        self.logger.info(f"Initializing PDFRenderer for: {self.pdf_path}")

        try:
            self.doc = fitz.open(self.pdf_path)
            self.logger.info(f"Successfully opened PDF. Pages: {self.doc.page_count}")
            self._load_and_render_pages()
        except FileNotFoundError:
            self.logger.error(f"PDF file not found: {self.pdf_path}")
            raise # Re-raise FileNotFoundError
        except Exception as e:
            self.logger.error(f"Failed to open or process PDF '{self.pdf_path}': {e}", exc_info=True)
            # Ensure doc is closed if partially opened before error
            if self.doc:
                try:
                    self.doc.close()
                except Exception:
                    pass # Ignore errors during close on error path
                self.doc = None
            raise PDFRendererError(f"Failed to open or process PDF: {e}") from e

    def _load_and_render_pages(self):
        """Internal method to iterate through pages and render them."""
        if not self.doc:
            return # Should not happen if __init__ succeeded

        # Type check hint for self.doc within the method if needed
        if typing.TYPE_CHECKING:
            assert self.doc is not None

        self._rendered_pages = [] # Clear any previous renders
        self.logger.info(f"Rendering {self.doc.page_count} pages at {self.dpi} DPI...")

        for i, page in enumerate(self.doc):
            page_num = i + 1
            try:
                # Render page to a pixmap using specified DPI
                # Using matrix allows for future scaling/rotation during render if needed
                self.logger.debug(f"Calculating matrix for page {page_num} using self.dpi = {self.dpi}")
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72) # Standard conversion
                pix = page.get_pixmap(matrix=mat, alpha=False) # Render as RGB for simplicity now
                self.logger.debug(f"Page {page_num}: Got pixmap (w={pix.width}, h={pix.height}, colorspace={pix.colorspace.name})")

                # Determine QImage format - Assuming RGB for now
                fmt = QImage.Format.Format_RGB888

                # Create QImage from pixmap data
                qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)

                # Important: Make a copy! The pix.samples buffer might be temporary.
                self._rendered_pages.append(qimage.copy())
                self.logger.debug(f"Page {page_num} rendered and converted to QImage.")

            except Exception as e:
                self.logger.error(f"Failed to render or convert page {page_num}: {e}", exc_info=True)
                # Append None for failed pages to keep indices correct?
                # For now, just skip adding it, but log the error.

        self.logger.info(f"Finished rendering. Stored {len(self._rendered_pages)} page images.")


    def get_page_image(self, page_number: int) -> Optional[QImage]:
        """Retrieves the rendered QImage for a specific page.

        Args:
            page_number (int): The page number to retrieve (1-based index).

        Returns:
            Optional[QImage]: The rendered QImage for the page, or None if the
                              page number is invalid or rendering failed for that page.

        """
        if not 1 <= page_number <= len(self._rendered_pages):
            self.logger.warning(f"Invalid page number requested: {page_number}. Max page: {len(self._rendered_pages)}")
            return None

        # Return the QImage (0-based index)
        return self._rendered_pages[page_number - 1]

    def get_page_count(self) -> int:
        """Returns the total number of pages successfully rendered and stored.
        May be less than doc.page_count if errors occurred.
        """
        return len(self._rendered_pages)

    def get_original_page_count(self) -> int:
        """Returns the total number of pages in the original PDF document."""
        return self.doc.page_count if self.doc else 0

    def close(self):
        """Closes the underlying PDF document to release resources."""
        if self.doc:
            self.logger.info(f"Closing PDF document: {self.pdf_path}")
            try:
                self.doc.close()
                self.doc = None
            except Exception as e:
                self.logger.error(f"Error closing PDF document: {e}", exc_info=True)
        self._rendered_pages = [] # Clear rendered images on close


# --- Example Usage / Basic Test ---
if __name__ == "__main__":
    # Basic logging setup for testing
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Ensure libraries loaded for test execution
    if fitz is None or QImage is None or QApplication is None:
        sys.exit("Exiting: Required libraries not found.")

    # Need a QApplication instance for QImage handling, even if not showing GUI
    app = QApplication.instance() # Check if already exists
    if not app:
        app = QApplication(sys.argv)

    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    else:
        pdf_file = input("Enter the path to a PDF file: ")

    renderer: Optional[PDFRenderer] = None
    try:
        # Create renderer instance (loads and renders pages)
        renderer = PDFRenderer(pdf_path=pdf_file, dpi=96) # Lower DPI for faster testing

        if renderer:
            orig_pages = renderer.get_original_page_count()
            rendered_pages = renderer.get_page_count()
            print("\n--- PDF Renderer Test ---")
            print(f"PDF Path: {renderer.pdf_path}")
            print(f"Original Page Count: {orig_pages}")
            print(f"Successfully Rendered Pages: {rendered_pages}")

            if rendered_pages > 0:
                # Try getting the first page image
                first_page_img = renderer.get_page_image(1)
                if first_page_img:
                    print(f"First page image dimensions: {first_page_img.width()}x{first_page_img.height()}")
                    # Optionally save the image for verification
                    # save_path = "test_page_1.png"
                    # first_page_img.save(save_path)
                    # print(f"Saved first page image to {save_path}")
                else:
                    print("Could not retrieve the first page image (check logs for errors).")
            print("-------------------------\n")

    except FileNotFoundError:
        print(f"Error: The specified file was not found: {pdf_file}")
    except PDFRendererError as e:
        print(f"PDF Renderer Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        logging.exception("Unexpected error in main test block.")
    finally:
        # Ensure the PDF is closed
        if renderer:
            renderer.close()

    # No app.exec() needed as this is just a console test
    sys.exit(0)
