"""Compatibility shim for legacy `src.*` import paths.

Many older test modules still reference the codebase using the shorthand
```
from src.models.project import Project
```
while the actual implementation now lives inside
```
digcalc_project.src
```
This stub package redirects such imports at *import-time* so they keep
working without modifying every call-site.  It only adds a negligible cost at
startup and avoids IDE/linter complaints about unresolved modules.
"""

import sys as _sys
from importlib import import_module

# Import the real package once and register it under the legacy top-level name
_real_root = import_module("digcalc_project.src")
_sys.modules[__name__] = _real_root  # type: ignore[misc]

# Expose common sub-packages so that `import src.models` etc. succeed.
for _sub in (
    "core",
    "models",
    "services",
    "ui",
    "tools",
    "controllers",
    "visualization",
    "utils",
):
    try:
        _mod = import_module(f"digcalc_project.src.{_sub}")
        _sys.modules[f"{__name__}.{_sub}"] = _mod
    except ModuleNotFoundError:
        continue

del import_module, _sys, _sub, _mod, _real_root
