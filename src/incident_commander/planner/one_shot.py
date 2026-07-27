from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from incident_commander.engine.compiler import WorkflowCompiler
from incident_commander.models import WorkflowBlueprint
from incident_commander.tools.registry import ToolRegistry

JsonGenerator = Callable[[str], Awaitable[str]]


class OneShotWorkflowPlanner:
    """Uses an injected LLM once, then validates its JSON before any execution."""

    def __init__(
        self,
        tools: ToolRegistry,
        compiler: WorkflowCompiler,
        generate_json: JsonGenerator,
    ) -> None:
        self.tools = tools
        self.compiler = compiler
        self.generate_json = generate_json

    async def plan(self, request: str) -> WorkflowBlueprint:
        prompt = self._prompt(request, self.tools.catalog())
        generated = await self.generate_json(prompt)
        document = json.loads(generated)
        return self.compiler.compile(document)

    @staticmethod
    def _prompt(request: str, catalog: list[dict[str, Any]]) -> str:
        return (
            "Design one reusable incident workflow as strict JSON. "
            "Use only catalogued tools. Read-only calls may run automatically. "
            "Any destructive tool must depend on an approval node. "
            "Prefer parallel collection and keep the runtime deterministic.\n\n"
            f"Request:\n{request}\n\n"
            f"Tool catalog:\n{json.dumps(catalog, indent=2)}\n\n"
            "Return only a WorkflowBlueprint JSON object with schema_version 1.0."
        )
