from digcalc_project.src.core.clean.rule_engine import BaseRule, RuleRegistry


def test_evaluate_no_rules_identity():
    """When no rules are registered, evaluate should return the original list."""
    RuleRegistry.clear()
    data = ["a", "b"]
    assert RuleRegistry.evaluate(data) == data


def test_register_and_apply_rule():
    """A registered rule must be applied in order during evaluation."""

    class AppendRule(BaseRule):
        def apply(self, items):  # type: ignore[override]
            return list(items) + ["X"]

    RuleRegistry.clear()
    RuleRegistry.register(AppendRule)

    result = RuleRegistry.evaluate(["start"])
    assert result[-1] == "X"
    assert len(result) == 2 