#!/usr/bin/env python3
"""Logging utilities for the DigCalc application.

This module provides functions for setting up and configuring logging
for the DigCalc application.
"""

import logging
import os
import sys
from typing import Optional


def setup_logging(log_level: int = logging.INFO,
                 log_file: Optional[str] = None) -> None:
    """Set up application logging with the specified configuration.
    
    Args:
        log_level: The logging level (default: logging.INFO)
        log_file: Optional path to a log file. If None, logs to console only.
    
    Returns:
        None

    """
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        # Make sure directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Log initial message
    root_logger.debug("Logging initialized")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.
    
    Args:
        name: Name for the logger (typically __name__)
    
    Returns:
        Logger: Configured logger instance

    """
    return logging.getLogger(name)
