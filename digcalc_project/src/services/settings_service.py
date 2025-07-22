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
            "spoil_to_fill_ratio": 1.0,  # proportion of cut usable as fill (0-1)
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
            # Phase-3 additions (D3)
            "grid_snap_ft": 1.0,  # default grid interval in world units (ft)
            "enable_heatmap_overlay": False,
            # Phase-4 additions
            "enable_snap_default": True,  # global magnet-snap toggle
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
        "clean": {
            "enable_auto_join_v2": True,
            "compress_dist_tol_ft": 0.10,
            "compress_angle_tol_deg": 1.0,
        },
    }

    # Compatibility alias for unit-tests that reference the old flat dict name
    _defaults: dict[str, Any] = {
        k: v
        for group_map in _DEFAULTS.values()
        for k, v in group_map.items()
    }

    def __init__(self, config_path: Path | None = None) -> None:
        if getattr(self, "_initialized", False) and config_path is None:
            return
            
        if config_path:
            self._path = config_path

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

    # type: ignore[override]
    def set(self, group: str, key: Any, value: Any | None = None) -> None:
        """Update a setting and persist immediately.

        This method is **overloaded** for backward-compatibility:

        1.  *Modern* signature ``set(group, key, value)`` — explicit group.
        2.  *Legacy* signature ``set(key, value)`` — the method infers the
            group by searching :pyattr:`_DEFAULTS`.  This mode is only kept to
            support existing unit-tests and should be avoided in new code.
        """

        # Detect legacy 2-argument form: value is None because only two
        # positional args were supplied (group==key, key==value).
        if value is None:
            key_name = group  # actually the *key*
            value = key  # but `key` param holds the intended *value*

            # Find the group containing *key_name* in the defaults map.
            target_group = None
            for g_name, g_map in self._DEFAULTS.items():
                if key_name in g_map:
                    target_group = g_name
                    break
            # Fallback to "tracing" for unknown keys to match historical
            # behaviour of early DigCalc versions.
            if target_group is None:
                target_group = "tracing"

            group = target_group  # type: ignore[assignment]
            key = key_name  # type: ignore[assignment]

        # Ensure nested dict exists
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

    @property
    def strata_spoil_to_fill_ratio(self) -> float:
        """Return spoil→fill utilisation ratio (0 ≤ r ≤ 1)."""
        val = float(self.get_strata_setting("spoil_to_fill_ratio", 1.0))
        # Clamp defensively
        return max(0.0, min(1.0, val))

    def get_ui_setting(self, key: str, default=None):
        return self.get("user_interface", key, default)

    def theme(self) -> str:
        return self.get_ui_setting("theme", "light")

    # ------------------------------------------------------------------
    # Legacy vertex display helpers (used extensively by UI tests)
    # ------------------------------------------------------------------

    # NOTE: These accessors live here rather than in the UI layer because
    # they represent user-configurable *preferences* persisted across
    # sessions.  They used to reside in a dedicated **LegacySettings**
    # class in the original DigCalc code base and were referenced all over
    # the UI.  When the code was refactored the helpers were dropped which
    # now breaks unit-tests expecting them.  We restore them here for full
    # backward-compatibility while keeping data in the *legacy* section of
    # the JSON payload.

    # --- Cross-hair size (px) -----------------------------------------
    def vertex_cross_px(self) -> int:
        """Return half-width of the vertex cross-hair in screen pixels."""
        return int(self.get("legacy", "vertex_cross_px", 6))

    # --- Line (stroke) thickness (px) ---------------------------------
    def vertex_line_thickness(self) -> int:
        """Return outline thickness in pixels (0 == hairline)."""
        return int(self.get("legacy", "vertex_line_thickness", 0))

    def set_vertex_line_thickness(self, value: int) -> None:
        """Persist *value* for vertex outline thickness in the **legacy** group."""
        self.set("legacy", "vertex_line_thickness", int(value))

    # --- Hover colour --------------------------------------------------
    def vertex_hover_colour(self) -> str:
        """Hex string for vertex hover colour (e.g. ``#FFFF00``)."""
        return str(self.get("legacy", "vertex_hover_colour", "#ffff00"))

    def set_vertex_hover_colour(self, hex_colour: str) -> None:
        """Persist *hex_colour* for vertex hover state in the **legacy** group."""
        self.set("legacy", "vertex_hover_colour", str(hex_colour))

    # ------------------------------------------------------------------
    # Clean / Smart-Clean settings
    # ------------------------------------------------------------------
    def enable_auto_join_v2(self) -> bool:  # noqa: D401 – simple accessor
        """Return True when Automatic Join V2 is enabled (default True)."""
        return bool(self.get("clean", "enable_auto_join_v2", True))

    def compress_dist_tol_ft(self) -> float:
        """Distance tolerance used by Polyline.compress (default 0.10 ft)."""
        return float(self.get("clean", "compress_dist_tol_ft", 0.10))

    def compress_angle_tol_deg(self) -> float:
        """Angle tolerance (degrees) for Polyline.compress (default 1.0°)."""
        return float(self.get("clean", "compress_angle_tol_deg", 1.0))

    # ------------------------------------------------------------------
    # Tracing global enable/disable flag
    # ------------------------------------------------------------------
    def tracing_enabled(self) -> bool:
        """Return global tracing enable flag (defaults to True)."""
        return bool(self.get("tracing", "tracing_enabled", True))

    def set_tracing_enabled(self, flag: bool) -> None:
        """Persist *flag* controlling whether tracing is globally enabled."""
        self.set("tracing", "tracing_enabled", bool(flag))

    # ------------------------------------------------------------------
    # Calibration helpers – last used printed scale
    # ------------------------------------------------------------------

    def last_scale(self) -> tuple[str, float]:
        """Return tuple ``(units, world_per_in)`` from the *calibration* group.

        *units* is either ``"ft"`` or ``"m"`` (legacy tests use only these),
        and *world_per_in* is a floating-point distance in the corresponding
        units represented by one *printed* inch.
        """
        units = str(self.get("calibration", "last_scale_world_units", "ft"))
        value = float(self.get("calibration", "last_scale_world_per_in", 20.0))
        return units, value

    def set_last_scale(self, units: str, world_per_in: float) -> None:
        """Persist the last used printed scale (*units* per inch)."""
        if units not in ("ft", "m", "yd"):
            raise ValueError("units must be 'ft', 'm', or 'yd'")
        self.set("calibration", "last_scale_world_units", units)
        self.set("calibration", "last_scale_world_per_in", float(world_per_in))

    # ------------------------------------------------------------------
    # Tracing sampling / elevation mode helpers (used heavily by UI tests)
    # ------------------------------------------------------------------

    def smooth_sampling_ft(self) -> float:
        """Return Catmull-Rom spline sampling distance in *ft*."""
        return float(self.get("tracing", "smooth_sampling_ft", 1.0))

    def set_smooth_sampling_ft(self, value: float) -> None:
        self.set("tracing", "smooth_sampling_ft", float(value))

    def tracing_elev_mode(self) -> str:
        """Return tracing elevation mode ("point", "line", "interpolate")."""
        return str(self.get("tracing", "tracing_elev_mode", "point"))

    def set_tracing_elev_mode(self, mode: str) -> None:
        if mode not in ("point", "line", "interpolate"):
            raise ValueError("mode must be 'point', 'line', or 'interpolate'")
        self.set("tracing", "tracing_elev_mode", mode)

    # ------------------------------------------------------------------
    # Spline smoothing toggle
    # ------------------------------------------------------------------

    def smooth_default(self) -> bool:
        """Return default state for *smooth* polyline drawing."""
        return bool(self.get("tracing", "smooth_default", False))

    def set_smooth_default(self, flag: bool) -> None:
        self.set("tracing", "smooth_default", bool(flag))

    # ------------------------------------------------------------------
    # Stripping depth default (legacy earthworks settings)
    # ------------------------------------------------------------------

    def strip_depth_default(self) -> float:
        """Return global stripping depth in feet (legacy setting)."""
        return float(self.get("legacy", "default_strip_depth_ft", 0.0))

    def set_strip_depth_default(self, depth_ft: float) -> None:
        self.set("legacy", "default_strip_depth_ft", float(depth_ft))

    # Backward-compatibility helper for older unit-tests – historically this was a method.
    def smooth_min_spacing_ft(self) -> float:  # noqa: D401 – simple accessor
        """Return minimum point spacing (ft) used by Polyline sampling compression."""
        return float(self.get("tracing", "smooth_min_spacing_ft", 0.01))

    def smooth_max_points(self) -> int:
        """Return maximum number of points allowed in compressed polyline."""
        return int(self.get("tracing", "smooth_max_points", 20000))

    # ------------------------------------------------------------------
    # Phase-3 grid-snap helpers
    # ------------------------------------------------------------------
    def grid_snap_ft(self) -> float:
        """Return grid snap spacing in *world* units (ft)."""
        return float(self.get("tracing", "grid_snap_ft", 1.0))

    def enable_heatmap_overlay(self) -> bool:
        """Return True when heat-map overlay is enabled."""
        return bool(self.get("tracing", "enable_heatmap_overlay", False))

    def set_enable_heatmap_overlay(self, flag: bool) -> None:
        """Persist heat-map overlay enable flag."""
        self.set("tracing", "enable_heatmap_overlay", bool(flag))

    # ------------------------------------------------------------------
    # Phase-4 magnet snap default toggle
    # ------------------------------------------------------------------
    def enable_snap_default(self) -> bool:
        """Return True when magnet snapping is enabled by default."""
        return bool(self.get("tracing", "enable_snap_default", True))

    def set_enable_snap_default(self, flag: bool) -> None:
        """Persist default snap enable flag."""
        self.set("tracing", "enable_snap_default", bool(flag))
