"""Backwards-compatibility package.

The UI 3-D utilities were moved from ``digcalc_project.src.ui.3d`` to
``digcalc_project.src.ui.three_d`` during a large refactor.  Several tests
and external scripts still expect the old import path, so we provide this
shim that forwards attribute access to the new package.
"""

import sys as _sys
from importlib import import_module as _import_module

# Import the new package
_new_pkg = _import_module("..three_d", package=__name__)

# Register the new package under the old name so that ``import
# digcalc_project.src.ui.3d`` returns this forwarding module while submodules
# resolve to the actual implementation.
_sys.modules[__name__] = _new_pkg

# Expose public attributes
globals().update(_new_pkg.__dict__)
