# This file makes digcalc_project a Python package

"""digcalc_project package

This package exposes its main codebase under *digcalc_project.src.* but many
legacy modules (and some tests) still import using the shorthand::

    import digcalc_project.core.xxx
    from digcalc_project.models import ...

To maintain backwards compatibility we alias these top-level sub-packages to
their real locations under :pymod:`digcalc_project.src` at import time.
"""

from importlib import import_module
import sys as _sys

_subs = [
    "core",
    "models",
    "services",
    "ui",
    "tools",
    "controllers",
    "visualization",
    "utils",
]

for _sub in _subs:
    try:
        _module = import_module(f"{__name__}.src.{_sub}")
        _sys.modules[f"{__name__}.{_sub}"] = _module
    except ModuleNotFoundError:
        # If a sub-package doesnʼt exist we silently ignore to avoid import
        # errors when optional features are missing.
        continue

# Clean-up namespace
del import_module, _sys, _sub, _module, _subs 