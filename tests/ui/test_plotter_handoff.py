import os

import pytest

# Ensure PyVista off-screen rendering so tests do not open a window
os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")  # must be set before first pyvista import

from digcalc_project.src.ui.docks.pv_dock import PvDock
from digcalc_project.src.ui.pv_plotter_singleton import get_plotter
from digcalc_project.src.ui.visualization_panel import VisualizationPanel


@pytest.mark.usefixtures("qtbot")
def test_interactor_handoff(qtbot):
    """Verify the singleton PyVista interactor re-parents correctly between tab and dock."""

    # 1. Create VisualizationPanel and embed plotter in tab
    panel = VisualizationPanel()
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitExposed(panel)

    panel.show_pyvista_in_tab()
    plotter = get_plotter()

    # Assert the interactor is under the tab container
    assert plotter.interactor.parent() is panel.tab_3d_container

    # 2. Create PvDock and show – this should steal the interactor
    dock = PvDock(panel.parent() or panel)  # parent to same top-level for cleanup
    qtbot.addWidget(dock)
    dock.show()
    qtbot.waitExposed(dock)

    assert plotter.interactor.parent() is dock

    # 3. Hide the dock – interactor becomes parent-less
    dock.hide()
    # Process events to allow hideEvent to run
    qtbot.wait(100)
    assert plotter.interactor.parent() is None

    # 4. Switch back to tab – interactor should re-attach
    panel.show_pyvista_in_tab()
    assert plotter.interactor.parent() is panel.tab_3d_container

    # Cleanup plotter explicitly to avoid side-effects between tests
    try:
        plotter.close()
    except Exception:
        pass
