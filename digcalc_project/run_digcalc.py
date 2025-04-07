#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DigCalc Application Launcher

This script provides an easy way to launch the DigCalc application
by setting up the Python path correctly.
"""

import os
import sys
from pathlib import Path

# Add the current directory to the Python path
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

# Now import and run the main function
if __name__ == "__main__":
    try:
        from src.main import main
        sys.exit(main())
    except ImportError as e:
        print(f"Error importing application modules: {e}")
        print("Make sure all dependencies are installed by running: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error launching application: {e}")
        sys.exit(1) 