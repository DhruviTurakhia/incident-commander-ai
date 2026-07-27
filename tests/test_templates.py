from incident_commander.engine.templates import evaluate_condition, resolve
from incident_commander.models import Condition


def test_exact_template_preserves_object_type():
    context = {"steps": {"metrics": {"latency": 3820}}}

    assert resolve("{{ steps.metrics }}", context) == {"latency": 3820}
    assert resolve("latency={{ steps.metrics.latency }}", context) == "latency=3820"


def test_condition_uses_resolved_value():
    condition = Condition(
        left="{{ steps.root.confidence }}",
        operator="gte",
        right=0.8,
    )

    assert evaluate_condition(condition, {"steps": {"root": {"confidence": 0.96}}})
