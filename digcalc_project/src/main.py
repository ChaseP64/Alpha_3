#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DigCalc - Excavation Takeoff Tool

This is the main entry point for the DigCalc application, which provides
tools for accurate excavation takeoffs from various file formats.

Author: DigCalc Team
"""

import sys
import logging
from pathlib import Path

# Add the parent directory to the path so we can use our modules
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
from src.utils.logging_utils import setup_logging

# Application imports
from src.ui.main_window import MainWindow
from src.models.project import Project


def main():
    """
    Main entry point for the DigCalc application.
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
        # Import Qt modules here to avoid circular imports
        from PySide6.QtWidgets import QApplication
        
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