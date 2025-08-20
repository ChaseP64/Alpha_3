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
# variable. Default: enabled. Set DIGCALC_PDF_VEC=0 to disable.
PDF_VECTORIZER_ENABLED: bool = os.getenv("DIGCALC_PDF_VEC", "1") != "0"

__all__ = [
    "PDF_VECTORIZER_ENABLED",
]
