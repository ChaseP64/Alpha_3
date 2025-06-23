import inspect
from typing import Set

# Attempt import using full package path first, fall back to relative if needed
try:
    from digcalc_project.src.ui.main_window.main_window import MainWindow  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from src.ui.main_window.main_window import MainWindow  # type: ignore

# ---------------------------------------------------------------------------
# Public-method inventory for MainWindow
#
# 1.  Update this list whenever **public** methods (i.e. names that do NOT
#     start with an underscore) are added or removed from MainWindow.
# 2.  The accompanying test ensures the list stays in-sync with the class
#     definition, giving us a measurable "definition of done" as we chip away
#     at the large file during the refactor.
# ---------------------------------------------------------------------------

ALLOWLIST: Set[str] = {
    # Qt event overrides
    "closeEvent",
    "keyPressEvent",

    # Misc slots
    "on_about",
    "on_open_3d",
    "on_toggle_tracing_mode",

    # Calculation results
    "on_volume_computed",
}


def _get_public_method_names() -> Set[str]:
    """Return the set of public (non-underscore, non-dunder) method names."""
    return {
        name
        for name, member in inspect.getmembers(MainWindow, inspect.isfunction)
        if not name.startswith("_") and not (name.startswith("__") and name.endswith("__"))
    }


def test_mainwindow_public_api_stable():
    """Fail when MainWindow public API changes without updating ALLOWLIST."""
    public_methods = _get_public_method_names()
    missing = public_methods.difference(ALLOWLIST)
    extra = ALLOWLIST.difference(public_methods)

    debug_msg = (
        f"Unexpected public methods found: {sorted(missing)}\n"
        f"Stale ALLOWLIST entries: {sorted(extra)}"
    )

    assert not missing and not extra, debug_msg


def test_mainwindow_line_count():
    """Fail if MainWindow exceeds the maximum line count."""
    max_lines = 750
    try:
        with open("digcalc_project/src/ui/main_window/main_window.py", "r", encoding="utf-8") as f:
            line_count = len(f.readlines())
    except FileNotFoundError:
        # Fallback for different execution contexts
        with open("src/ui/main_window/main_window.py", "r", encoding="utf-8") as f:
            line_count = len(f.readlines())

    assert line_count < max_lines, (
        f"MainWindow has {line_count} lines, which exceeds the limit of {max_lines}."
    ) 