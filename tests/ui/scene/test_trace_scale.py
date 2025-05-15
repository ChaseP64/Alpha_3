from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsView

from digcalc_project.src.models.project import Project
from digcalc_project.src.models.project_scale import ProjectScale
from digcalc_project.src.ui.tracing_scene import TracingScene


def test_scene_world_conversion_uses_world_per_px(qtbot):
    """_scene_to_world should rely on ProjectScale.world_per_px."""
    proj = Project(name="ScaleTest")
    proj.scale = ProjectScale.from_direct(30.0, "ft", render_dpi=150.0)  # 0.2 ft/px

    view = QGraphicsView()
    dummy_panel = type("DummyPanel", (), {})()
    dummy_panel.current_project = proj  # attribute used by TracingScene

    scene = TracingScene(view, dummy_panel)
    qtbot.addWidget(view)

    # 150 px in X should equal 150 * 0.2 = 30 ft
    world_x, world_y = scene._scene_to_world(QPointF(150, 0))
    assert abs(world_x - 30.0) < 1e-6
    assert world_y == 0.0
