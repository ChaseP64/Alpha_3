#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pytest configuration for DigCalc tests.

This module contains shared fixtures and configuration for
all test modules in the DigCalc application.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from typing import Generator, Any

# Add the project root to the Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# If src directory exists, add it too
src_dir = root_dir / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

print(f"Python path: {sys.path}")


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """
    Create a temporary directory for test files.
    
    Returns:
        Path to a temporary directory
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir 