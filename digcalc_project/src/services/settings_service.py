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
        # Whether newly drawn polylines default to *smooth* (spline) mode.
        "smooth_default": False,
        # Tracing elevation prompt mode: "point", "interpolate", "line"
        "tracing_elev_mode": "point",
        # Whether tracing is enabled by default (Ctrl-T toggles)
        "tracing_enabled": True,
        # Catmull / B-spline resampling density in feet
        "smooth_sampling_ft": 1.0,
        # Minimum allowed spacing (ft) between resampled spline points when
        # compression is enabled (T-6 optimisation phase).
        "smooth_min_spacing_ft": 0.01,
        # Maximum number of points returned by spline sampling before further
        # compression / decimation kicks in.
        "smooth_max_points": 20000,
        # Vertex drawing preferences
        "vertex_cross_px": 6,  # Half-length of crosshair in screen pixels
        "vertex_hover_colour": "#ffff00",  # Hover colour (Qt yellow)
        "vertex_line_thickness": 0,  # Cosmetic pen (0 = hairline)
        # --- NEW: last used scale for PDF calibration ---
        "last_scale_world_units": "ft",
        "last_scale_world_per_in": 20.0,
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

    # ------------------------------------------------------------------
    # Spline smoothing preference
    # ------------------------------------------------------------------
    def smooth_default(self) -> bool:  # noqa: D401
        """Return the user's default preference for *smooth* polyline tracing."""

        return bool(self.get("smooth_default", self._defaults["smooth_default"]))

    def set_smooth_default(self, val: bool) -> None:  # noqa: D401
        """Persist the default polyline smoothing preference."""

        self.set("smooth_default", bool(val))
        self.save()

    # ------------------------------------------------------------------
    # Tracing elevation workflow preferences
    # ------------------------------------------------------------------
    def tracing_elev_mode(self) -> str:  # noqa: D401
        """Return current elevation prompt mode (``"point"``, ``"interpolate"``, or ``"line"``)."""

        return str(self.get("tracing_elev_mode", self._defaults["tracing_elev_mode"]))

    def set_tracing_elev_mode(self, mode: str) -> None:  # noqa: D401
        """Persist the elevation prompt mode preference."""

        assert mode in ("point", "interpolate", "line"), "Invalid tracing elevation mode"
        self.set("tracing_elev_mode", mode)
        self.save()

    def tracing_enabled(self) -> bool:  # noqa: D401
        """Return whether tracing is globally enabled."""

        return bool(self.get("tracing_enabled", self._defaults["tracing_enabled"]))

    def set_tracing_enabled(self, flag: bool) -> None:  # noqa: D401
        """Set global tracing enable flag and persist."""

        self.set("tracing_enabled", bool(flag))
        self.save()

    # ------------------------------------------------------------------
    # Spline density (smooth sampling) preference
    # ------------------------------------------------------------------
    def smooth_sampling_ft(self) -> float:  # noqa: D401
        """Return current resample spacing in feet for spline sampling."""

        return float(self.get("smooth_sampling_ft", self._defaults["smooth_sampling_ft"]))

    def set_smooth_sampling_ft(self, val: float) -> None:  # noqa: D401
        """Persist spline resample spacing in feet."""

        self.set("smooth_sampling_ft", float(val))
        self.save()

    # ------------------------------------------------------------------
    # Spline sample compression preferences
    # ------------------------------------------------------------------
    def smooth_min_spacing_ft(self) -> float:  # noqa: D401
        """Return minimum spacing (ft) allowed between sampled spline points."""

        return float(self.get("smooth_min_spacing_ft", self._defaults["smooth_min_spacing_ft"]))

    def smooth_max_points(self) -> int:  # noqa: D401
        """Return maximum allowed number of sampled points before compression."""

        return int(self.get("smooth_max_points", self._defaults["smooth_max_points"]))

    # ------------------------------------------------------------------
    # Vertex drawing preferences
    # ------------------------------------------------------------------
    def vertex_cross_px(self) -> int:  # noqa: D401
        """Return half-length of vertex crosshair in screen pixels."""

        return int(self.get("vertex_cross_px", self._defaults["vertex_cross_px"]))

    def set_vertex_cross_px(self, val: int) -> None:  # noqa: D401
        self.set("vertex_cross_px", int(val))
        self.save()

    def vertex_hover_colour(self) -> str:  # noqa: D401
        """Return colour string for vertex hover state (#RRGGBB)."""

        return str(self.get("vertex_hover_colour", self._defaults["vertex_hover_colour"]))

    def set_vertex_hover_colour(self, colour: str) -> None:  # noqa: D401
        self.set("vertex_hover_colour", str(colour))
        self.save()

    def vertex_line_thickness(self) -> int:  # noqa: D401
        """Return pen width (0 for cosmetic hairline)."""

        return int(self.get("vertex_line_thickness", self._defaults["vertex_line_thickness"]))

    def set_vertex_line_thickness(self, width: int) -> None:  # noqa: D401
        self.set("vertex_line_thickness", int(width))
        self.save()

    # ------------------------------------------------------------------
    # Spline / smoothing preference helpers …
    # ------------------------------------------------------------------

    # ==================================================================
    #  Plan-Scale - remember the most-recent calibration
    # ==================================================================
    def last_scale(self) -> tuple[str, float]:            # noqa: D401
        """
        Return the last scale the user confirmed in *Calibrate Scale…*.

        Returns
        -------
        (units, world_per_in)
            ``units``  – ``"ft"`` or ``"m"``  
            ``world_per_in`` – numeric (e.g. 20.0 ⇒ "20 ft per inch")
        """

        units = self.get("last_scale_world_units",
                         self._defaults["last_scale_world_units"])
        val   = float(self.get("last_scale_world_per_in",
                               self._defaults["last_scale_world_per_in"]))
        return units, val

    def set_last_scale(self, units: str, val: float) -> None:  # noqa: D401
        """
        Persist the *most recently confirmed* plan scale.

        Parameters
        ----------
        units
            ``"ft"`` or ``"m"``
        val
            Real-world length per inch on paper (e.g. 20 → "1" = 20 ft")
        """

        assert units in ("ft", "m"), "units must be 'ft' or 'm'"
        self.set("last_scale_world_units", units)
        self.set("last_scale_world_per_in", float(val))
        self.save()