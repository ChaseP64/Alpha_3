"""Compatibility shim for the legacy 'pv_view' module path.

The implementation now lives in
``digcalc_project.src.ui.three_d.pv_view``.  This wrapper simply re-exports
all public names from the new module so existing imports continue to work
without modification.
"""

import sys as _sys
from importlib import import_module as _import_module

_new_mod = _import_module("..three_d.pv_view", package=__name__)

# Add the re-exported module to sys.modules under both the legacy and the
# forwarded name so ``import digcalc_project.src.ui.3d.pv_view as x`` returns
# the correct reference.
_sys.modules[__name__] = _new_mod

globals().update(_new_mod.__dict__)
