#!/usr/bin/env python3
"""DigCalc - Excavation Takeoff Tool

This is the main entry point for the DigCalc application, which provides
tools for accurate excavation takeoffs from various file formats.

Author: DigCalc Team
"""

import logging
import os
import sys
from pathlib import Path

# Application imports
from PySide6.QtWidgets import QApplication

from .ui.main_window.main_window import MainWindow
from .utils.logging_utils import setup_logging

# Use relative imports within the package
# Setup logging

# from .models.project import Project # Project might not be needed directly here?


def main():
    """Main entry point for the DigCalc application.
    Initializes the application, sets up logging, and launches the UI.

    Returns:
        int: Exit code (0 for success)

    """
    # Initialize logging, explicitly setting a log file
    log_file_path = Path(__file__).parent.parent / "app.log"
    setup_logging(log_file=str(log_file_path))
    logger = logging.getLogger(__name__)
    logger.info("Starting DigCalc application")

    try:
        # Ensure Qt uses the packaged plugins (avoid mixing with system Qt)
        try:
            from PySide6.QtCore import QLibraryInfo

            # Ensure Qt loads the correct plugin dir and DLLs bundled with PySide6
            plugins = QLibraryInfo.location(QLibraryInfo.PluginsPath)
            if plugins and os.path.isdir(plugins):
                os.environ.setdefault("QT_PLUGIN_PATH", plugins)

            # On Windows, add the Qt binaries directory so the right Qt6*.dll are used
            if sys.platform.startswith("win"):
                bin_dir = QLibraryInfo.location(QLibraryInfo.BinariesPath)
                if bin_dir and os.path.isdir(bin_dir):
                    try:
                        os.add_dll_directory(bin_dir)  # type: ignore[attr-defined]
                    except Exception:
                        # Fallback: prepend to PATH if add_dll_directory is unavailable
                        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass

        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("DigCalc")
        app.setOrganizationName("DigCalc Team")

        # Initialize main window
        window = MainWindow()
        window.show()

        # Start the event loop
        exit_code = app.exec()
        logger.info(f"Application exited with code {exit_code}")
        return exit_code

    except Exception as e:
        logger.exception(f"Fatal error in main application: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
