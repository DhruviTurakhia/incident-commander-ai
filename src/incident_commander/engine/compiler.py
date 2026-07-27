import json
from pathlib import Path
from typing import Any

from incident_commander.models import PrimitiveType, RiskLevel, WorkflowBlueprint
from incident_commander.tools.registry import ToolRegistry


class WorkflowCompiler:
    """Validates a workflow before it can be versioned or executed."""

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    def compile(self, document: dict[str, Any]) -> WorkflowBlueprint:
        blueprint = WorkflowBlueprint.model_validate(document)
        node_by_id = {node.id: node for node in blueprint.nodes}

        def tools_for_node(node_id: str) -> list[str]:
            node = node_by_id[node_id]
            names: list[str] = []
            if node.tool:
                names.append(node.tool)
            names.extend(call.tool for call in node.calls)
            names.extend(call.tool for call in node.pipeline)
            return names

        for node in blueprint.nodes:
            for tool_name in tools_for_node(node.id):
                definition = self.tools.get(tool_name)
                if not definition:
                    raise ValueError(f"node {node.id} references unknown tool: {tool_name}")
                if (
                    definition.risk in {RiskLevel.WRITE, RiskLevel.DESTRUCTIVE}
                    and node.requires_approval
                    and not self._has_approval_ancestor(node.id, node_by_id)
                ):
                    raise ValueError(
                        f"write node {node.id} requires an approval node in its dependency chain"
                    )

            if node.kind == PrimitiveType.APPROVAL and node.requires_approval:
                raise ValueError("approval nodes cannot themselves require approval")
        return blueprint

    @staticmethod
    def _has_approval_ancestor(node_id: str, nodes: dict[str, Any]) -> bool:
        queue = list(nodes[node_id].depends_on)
        visited: set[str] = set()
        while queue:
            dependency = queue.pop()
            if dependency in visited:
                continue
            visited.add(dependency)
            if nodes[dependency].kind == PrimitiveType.APPROVAL:
                return True
            queue.extend(nodes[dependency].depends_on)
        return False

    def compile_file(self, path: Path) -> WorkflowBlueprint:
        return self.compile(json.loads(path.read_text(encoding="utf-8")))
