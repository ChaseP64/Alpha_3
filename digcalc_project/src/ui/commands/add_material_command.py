"""Undo-able command to add a *Material* to a :class:`StrataStack`."""

from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from digcalc_project.src.models.strata_models import Material, StrataStack


class AddMaterialCommand(QUndoCommand):
    """Push-once command that adds a material; undo removes it again."""

    def __init__(self, stack: StrataStack, material: Material):
        super().__init__(f"Add material: {material.name}")
        self._stack = stack
        # Store *copy* to avoid mutation from outside
        self._material = Material(
            id=material.id,
            name=material.name,
            colour=material.colour,
            density_pcft=material.density_pcft,
        )
        self._executed = False

    # ------------------------------------------------------------------
    def redo(self) -> None:  # noqa: D401  # PyQt naming convention
        if not self._executed:
            # First execution – ensure unique id
            if any(m.id == self._material.id for m in self._stack.materials):
                self._material.id = self._stack.next_material_id()
            self._executed = True
        self._stack.add_material(self._material)

    # ------------------------------------------------------------------
    def undo(self) -> None:  # noqa: D401
        self._stack.remove_material(self._material.id) 