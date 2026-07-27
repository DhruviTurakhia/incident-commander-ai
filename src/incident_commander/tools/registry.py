from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from incident_commander.models import RiskLevel, ToolResult

ToolHandler = Callable[..., ToolResult | Awaitable[ToolResult]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    risk: RiskLevel
    input_schema: dict[str, Any]
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool already registered: {definition.name}")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "risk": tool.risk.value,
                "input_schema": tool.input_schema,
            }
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    async def call(self, name: str, args: dict[str, Any], *, approved: bool = False) -> ToolResult:
        definition = self.get(name)
        if not definition:
            raise KeyError(f"unknown tool: {name}")
        if definition.risk == RiskLevel.DESTRUCTIVE and not approved:
            raise PermissionError(f"destructive tool requires approval: {name}")
        if definition.risk == RiskLevel.WRITE and not approved:
            raise PermissionError(f"write tool requires approval: {name}")

        started = time.perf_counter()
        result = definition.handler(**args)
        if inspect.isawaitable(result):
            result = await result
        elapsed = int((time.perf_counter() - started) * 1000)
        if not isinstance(result, ToolResult):
            result = ToolResult(data=result)
        result.duration_ms = max(result.duration_ms, elapsed)
        return result
