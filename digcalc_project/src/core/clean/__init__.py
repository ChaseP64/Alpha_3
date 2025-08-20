"""Clean module housing rule engine and future cleaning utilities."""

from .rule_engine import BaseRule, RuleRegistry

# Import side-effect: registers default rules
from .rules import GapCloseRule, LayerClassifyRule  # noqa: F401

__all__ = [
    "BaseRule",
    "RuleRegistry",
    "GapCloseRule",
    "LayerClassifyRule",
]
