from __future__ import annotations

"""Light-weight rule-engine skeleton used by Smart-Clean Phase-2.

Currently this only manages rule registration and sequential evaluation.
Real gap-closing / classification rules will be added in later phases.
"""

from typing import List, Sequence, Type, TypeVar

__all__ = ["BaseRule", "RuleRegistry"]

_T = TypeVar("_T")  # Generic placeholder (Polyline or similar)


class BaseRule:  # noqa: D101 – simple abstract base
    """Abstract base-class for Smart-Clean rules.

    Sub-classes must implement :pymeth:`apply` and *return* a **new list** of
    processed items (typically :class:`~digcalc_project.src.core.geom.polyline.Polyline`
    instances). The engine will feed the output of one rule into the next.
    """

    name: str = "UnnamedRule"

    # Reason: keep signature generic to avoid importing heavy Polyline type
    def apply(self, items: Sequence[_T]) -> List[_T]:  # noqa: D401
        """Return a transformed copy of *items*.

        Args:
            items (Sequence[_T]): Input collection (e.g. polylines).

        Returns:
            List[_T]: Processed items.
        """
        raise NotImplementedError


class RuleRegistry:  # noqa: D101 – simple singleton-style helper
    _rules: List[Type[BaseRule]] = []

    # ------------------------------------------------------------------
    @classmethod
    def register(cls, rule_cls: Type[BaseRule]) -> None:  # noqa: D401
        """Register *rule_cls* for evaluation (idempotent)."""
        if rule_cls not in cls._rules:
            cls._rules.append(rule_cls)

    # ------------------------------------------------------------------
    @classmethod
    def clear(cls) -> None:  # noqa: D401
        """Remove *all* registered rules (useful for unit-tests)."""
        cls._rules.clear()

    # ------------------------------------------------------------------
    @classmethod
    def evaluate(cls, items: Sequence[_T]) -> List[_T]:  # noqa: D401
        """Run all registered rules in sequence over *items*.

        The original list is *not* modified – each rule must return a new list
        (or the same reference if unchanged).
        """
        result: List[_T] = list(items)
        for rule_cls in cls._rules:
            rule = rule_cls()
            result = rule.apply(result)
        return result
