import re
from typing import Any

from incident_commander.models import Condition

TEMPLATE = re.compile(r"^\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}$")
EMBEDDED_TEMPLATE = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")


class TemplateResolutionError(ValueError):
    pass


def lookup(path: str, context: dict[str, Any]) -> Any:
    value: Any = context
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise TemplateResolutionError(f"unknown template path: {path}")
    return value


def resolve(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        exact = TEMPLATE.match(value)
        if exact:
            return lookup(exact.group(1), context)
        return EMBEDDED_TEMPLATE.sub(lambda match: str(lookup(match.group(1), context)), value)
    if isinstance(value, dict):
        return {key: resolve(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, context) for item in value]
    return value


def evaluate_condition(condition: Condition, context: dict[str, Any]) -> bool:
    left = resolve(condition.left, context)
    right = resolve(condition.right, context)
    operator = condition.operator
    if operator == "eq":
        return left == right
    if operator == "ne":
        return left != right
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    if operator == "contains":
        return right in left
    if operator == "exists":
        return left is not None
    raise ValueError(f"unsupported condition operator: {operator}")
