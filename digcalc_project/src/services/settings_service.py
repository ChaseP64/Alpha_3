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

    _DEFAULTS: dict[str, Any] = {
        "user_interface": {
            "theme": "light",
            "show_splash_screen": True,
            "recent_files_max": 10,
        },
        "strata": {
            "idw_power": 2,
            "idw_radius_ft": 150,
            "default_cell_size_ft": 1,
            "rmse_threshold": 0.5,
        },
        "performance": {
            "max_threads": -1,
            "use_gpu_acceleration": True,
        },
        "tracing": {
            "snap_sensitivity_px": 10,
            "angle_snap_degrees": 15,
            "background_opacity": 0.5,
            "smooth_default": False,
            "tracing_elev_mode": "point",
            "tracing_enabled": True,
            "smooth_sampling_ft": 1.0,
            "smooth_min_spacing_ft": 0.01,
            "smooth_max_points": 20000,
        },
        "units": {
            "default_length": "ft",
            "default_area": "sqft",
            "default_volume": "cuyd",
        },
        "calibration": {
            "last_scale_world_units": "ft",
            "last_scale_world_per_in": 20.0,
        },
        "legacy": {
            "slice_thickness_ft": 0.5,
            "default_strip_depth_ft": 0.0,
            "free_haul_distance_ft": 500.0,
            "default_slice_thickness_ft": 0.5,
            "vertex_cross_px": 6,
            "vertex_hover_colour": "#ffff00",
            "vertex_line_thickness": 0,
        },
    }

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("Cannot create settings directory %s: %s", self._path.parent, exc)

        self._settings: dict[str, Any] = self._load()
        self._initialized = True

    def _load(self) -> dict[str, Any]:
        """Read JSON file, merge with defaults, and return."""
        if not self._path.exists():
            return self._DEFAULTS.copy()
        try:
            with self._path.open("r", encoding="utf-8") as fp:
                loaded_settings = json.load(fp)
            # Merge loaded settings into defaults to ensure all keys exist
            settings = self._DEFAULTS.copy()
            for key, value in loaded_settings.items():
                if isinstance(value, dict) and isinstance(settings.get(key), dict):
                    settings[key].update(value)
                else:
                    settings[key] = value
            return settings
        except Exception as exc:
            logger.error("Failed to load settings file %s: %s", self._path, exc)
            return self._DEFAULTS.copy()

    def get(self, group: str, key: str, default: Any | None = None) -> Any | None:
        """Return setting `key` from `group` or `default` if missing."""
        return self._settings.get(group, {}).get(key, default)

    def set(self, group: str, key: str, value: Any) -> None:
        """Update setting value in memory. Call `save` to persist."""
        if group not in self._settings:
            self._settings[group] = {}
        self._settings[group][key] = value
        self.save()

    def save(self) -> None:
        """Write current settings to JSON file."""
        try:
            with self._path.open("w", encoding="utf-8") as fp:
                json.dump(self._settings, fp, indent=4)
            logger.info("Settings saved to %s", self._path)
        except Exception as exc:
            logger.error("Failed to save settings to %s: %s", self._path, exc)

    # --------------------------------------------------------------------------
    # Convenience Accessors
    # --------------------------------------------------------------------------
    def get_strata_setting(self, key: str, default=None):
        return self.get("strata", key, default)

    @property
    def strata_idw_power(self) -> int:
        return int(self.get_strata_setting("idw_power", 2))

    @property
    def strata_idw_radius(self) -> float:
        return float(self.get_strata_setting("idw_radius_ft", 150.0))

    @property
    def strata_default_cell_size(self) -> float:
        return float(self.get_strata_setting("default_cell_size_ft", 1.0))

    @property
    def strata_rmse_threshold(self) -> float:
        return float(self.get_strata_setting("rmse_threshold", 0.5))

    def get_ui_setting(self, key: str, default=None):
        return self.get("user_interface", key, default)

    def theme(self) -> str:
        return self.get_ui_setting("theme", "light")
