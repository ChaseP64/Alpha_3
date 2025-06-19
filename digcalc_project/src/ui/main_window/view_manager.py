from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .main_window import MainWindow


class ViewManager:
    """Owns 2-D / 3-D mode toggling and view-related helpers."""

    def __init__(self, mw: "MainWindow") -> None:
        self.mw = mw                # keep back-ref for scene / panel access

    # ---------- public slots ---------- #
    def view_2d(self) -> None:
        """Switch main stack to 2-D view and update UI state."""
        vp = self.mw.visualization_panel
        if hasattr(vp, "show_2d_view"):
            vp.show_2d_view()
        self._update_view_mode(is_3d=False)

    def view_3d(self) -> None:
        """Switch main stack to 3-D PyVista tab."""
        vp = self.mw.visualization_panel
        if hasattr(vp, "show_3d_view"):
            vp.show_3d_view()
        self._update_view_mode(is_3d=True)

    def fit_view_to_scene(self) -> None:
        """Zoom extents in current view."""
        vp = self.mw.visualization_panel
        if hasattr(vp, 'is_2d') and vp.is_2d():
            if hasattr(vp, "view_2d") and hasattr(vp.view_2d, "fit_to_scene"):
                vp.view_2d.fit_to_scene()
        else:
            if hasattr(vp, "view_3d") and hasattr(vp.view_3d, "reset_camera"):
                vp.view_3d.reset_camera()

    # ---------- internal helpers ---------- #
    def _update_view_mode(self, *, is_3d: bool) -> None:
        """Enable / disable toolbar actions & docks."""
        if hasattr(self.mw, "view_2d_action"):
            self.mw.view_2d_action.setChecked(not is_3d)
        if hasattr(self.mw, "view_3d_action"):
            self.mw.view_3d_action.setChecked(is_3d)

        # Example: only show the PvDock in "3-D mode"
        if hasattr(self.mw, "pv_dock"):
            self.mw.pv_dock.setVisible(is_3d) 