import json

import pytest

from incident_commander.engine.compiler import WorkflowCompiler
from incident_commander.tools.demo import build_demo_registry
from incident_commander.tools.scenarios import ScenarioStore


def test_compiles_versioned_workflow(settings):
    tools = build_demo_registry(ScenarioStore(settings.scenarios_path))
    blueprint = WorkflowCompiler(tools).compile_file(settings.workflow_path)

    assert blueprint.id == "sre_incident_investigation"
    assert blueprint.version == 1
    assert len(blueprint.nodes) == 12
    assert {node.kind.value for node in blueprint.nodes} == {
        "call",
        "parallel",
        "loop",
        "pipe",
        "collect",
        "condition",
        "approval",
    }


def test_rejects_unknown_tool(settings):
    tools = build_demo_registry(ScenarioStore(settings.scenarios_path))
    document = json.loads(settings.workflow_path.read_text(encoding="utf-8"))
    document["nodes"][0]["calls"][0]["tool"] = "unknown.production_tool"

    with pytest.raises(ValueError, match="unknown tool"):
        WorkflowCompiler(tools).compile(document)


def test_rejects_destructive_node_without_approval_ancestor(settings):
    tools = build_demo_registry(ScenarioStore(settings.scenarios_path))
    document = json.loads(settings.workflow_path.read_text(encoding="utf-8"))
    rollback = next(node for node in document["nodes"] if node["id"] == "execute_rollback")
    rollback["depends_on"] = ["assemble_report"]

    with pytest.raises(ValueError, match="requires an approval node"):
        WorkflowCompiler(tools).compile(document)
