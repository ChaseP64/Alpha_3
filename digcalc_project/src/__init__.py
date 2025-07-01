"""DigCalc source package.

This module exposes high-level feature flags derived from environment
variables so that scattered modules (UI, tests, services) can rely on a
single definition and stay in-sync.
"""

import os

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

# PDF Vectorizer toggle – controlled via the *DIGCALC_PDF_VEC* environment
# variable.  The default is **enabled** (``True``) unless the variable is set
# to the string ``"0"``.

PDF_VECTORIZER_ENABLED: bool = os.getenv("DIGCALC_PDF_VEC") == "1"

__all__ = [
    "PDF_VECTORIZER_ENABLED",
]
