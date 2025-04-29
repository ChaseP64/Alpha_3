from __future__ import annotations

"""settings_service.py
Provides application‑wide persisted settings using a JSON file in the user's
home directory (``~/.digcalc/settings.json``).  Access via the *singleton*
:class:`SettingsService`.

Example
-------
>>> settings = SettingsService()
>>> settings.get("slice_thickness_ft")
0.5
>>> settings.set("slice_thickness_ft", 1.0)
>>> settings.save()
"""

import json
import logging
from pathlib import Path
from typing import Any

from ..utils.singleton import Singleton

__all__ = ["SettingsService"]

logger = logging.getLogger(__name__)


class SettingsService(Singleton):
    """Load/save user settings to *~/.digcalc/settings.json* (singleton)."""

    _path: Path = Path.home() / ".digcalc" / "settings.json"

    _defaults: dict[str, Any] = {
        "slice_thickness_ft": 0.5,
        "default_strip_depth_ft": 0.0,
        "free_haul_distance_ft": 500.0,
        "default_slice_thickness_ft": 0.5,
    }

    # ------------------------------------------------------------------
    def __init__(self) -> None:  # noqa: D401
        # Guard – only run once due to Singleton inheritance
        if getattr(self, "_initialized", False):  # type: ignore[attr-defined]
            return

        # Ensure directory exists
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover – path issues
            logger.warning("Cannot create settings directory %s: %s", self._path.parent, exc)

        # Merge defaults with loaded file
        self._data: dict[str, Any] = {**self._defaults, **self._load()}
        self._initialized = True  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    def _load(self) -> dict[str, Any]:
        """Read JSON file if it exists; return dict or empty on failure."""
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            # Only keep keys we recognise – ignore unknowns
            return {k: data[k] for k in self._defaults.keys() if k in data}
        except Exception as exc:  # pragma: no cover – corrupt file etc.
            logger.error("Failed to load settings file %s: %s", self._path, exc)
            return {}

    # ------------------------------------------------------------------
    def get(self, key: str, default: Any | None = None) -> Any | None:  # noqa: D401 – simple accessor
        """Return setting *key* or *default* if missing."""
        return self._data.get(key, default)

    # ------------------------------------------------------------------
    def set(self, key: str, value: Any) -> None:  # noqa: D401 – simple mutator
        """Update setting value in memory. Call :pymeth:`save` to persist."""
        self._data[key] = value

    # ------------------------------------------------------------------
    def save(self) -> None:  # noqa: D401 – straightforward persist
        """Write current settings to JSON file, creating directories as needed."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as fp:
                json.dump(self._data, fp, indent=2)
            logger.info("Settings saved to %s", self._path)
        except Exception as exc:  # pragma: no cover – disk full etc.
            logger.error("Failed to save settings to %s: %s", self._path, exc)

    # --- Convenience Accessors ---
    def strip_depth_default(self) -> float:
        """Get the default stripping depth in feet."""
        # Ensure we return a float, defaulting to the class default if needed
        return float(self.get("default_strip_depth_ft", self._defaults["default_strip_depth_ft"]))

    def set_strip_depth_default(self, value: float) -> None:
        """Set the default stripping depth in feet."""
        self.set("default_strip_depth_ft", float(value))
        self.save() # Persist immediately?

    def slice_thickness_default(self) -> float:
        """Get the default slice thickness in feet."""
        return float(self.get("default_slice_thickness_ft", self._defaults["default_slice_thickness_ft"]))

    def set_slice_thickness_default(self, val: float) -> None:
        """Set the default slice thickness in feet."""
        self.set("default_slice_thickness_ft", float(val))
        self.save() 