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

# REMOVED sys.path manipulation
# Python's -m flag should handle package paths correctly

# Now import and run the main function
if __name__ == "__main__":
    try:
        # Import using relative path from digcalc_project package root
        from .src.main import main
        sys.exit(main())
    except ImportError as e:
        import traceback # Import traceback module
        # Print the specific import error detail AND traceback
        print(f"Caught ImportError: {e}", file=sys.stderr)
        print("--- Traceback ---", file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
        print("-----------------", file=sys.stderr)
        print("Please check imports and ensure all dependencies are installed ('pip install -r digcalc_project/requirements.txt').", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error launching application: {e}", file=sys.stderr)
        sys.exit(1) 