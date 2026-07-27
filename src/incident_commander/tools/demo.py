from __future__ import annotations

from datetime import datetime
from typing import Any

from incident_commander.models import Evidence, RiskLevel, ToolResult
from incident_commander.tools.registry import ToolDefinition, ToolRegistry
from incident_commander.tools.scenarios import ScenarioStore

READ_TOOLS = {
    "deployment.latest": "Read the latest deployment and release metadata for a service.",
    "metrics.query": "Query service-level metrics around an incident window.",
    "logs.search": "Search structured application logs for correlated errors.",
    "traces.search": "Find anomalous distributed traces and dependency spans.",
    "kubernetes.snapshot": "Read pod, deployment, event, and resource state.",
    "github.recent_commits": "Read commits and pull requests included in a deployment.",
    "jira.open_tickets": "Read related incidents, changes, and service tickets.",
    "runbooks.search": "Retrieve the most relevant operational runbook.",
}


def _json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "scenario_id": {"type": "string"},
            "service": {"type": "string"},
            "incident_id": {"type": "string"},
        },
        "required": ["scenario_id"],
    }


def _as_evidence(items: list[dict[str, Any]]) -> list[Evidence]:
    return [
        Evidence(
            **{
                **item,
                "observed_at": datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")),
            }
        )
        for item in items
    ]


def build_demo_registry(scenarios: ScenarioStore) -> ToolRegistry:
    registry = ToolRegistry()

    for tool_name, description in READ_TOOLS.items():

        def handler(
            scenario_id: str,
            service: str | None = None,
            incident_id: str | None = None,
            _tool_name: str = tool_name,
            **_: Any,
        ) -> ToolResult:
            del service, incident_id
            payload = scenarios.get(scenario_id)["tool_outputs"][_tool_name]
            return ToolResult(
                data=payload["data"],
                evidence=_as_evidence(payload.get("evidence", [])),
                duration_ms=payload.get("duration_ms", 30),
            )

        registry.register(
            ToolDefinition(
                name=tool_name,
                description=description,
                risk=RiskLevel.READ,
                input_schema=_json_schema(),
                handler=handler,
            )
        )

    def build_timeline(scenario_id: str, **_: Any) -> ToolResult:
        return ToolResult(data=scenarios.get(scenario_id)["analysis"]["timeline"], duration_ms=42)

    def infer_root_cause(scenario_id: str, **_: Any) -> ToolResult:
        return ToolResult(data=scenarios.get(scenario_id)["analysis"]["root_cause"], duration_ms=58)

    def build_evidence_graph(scenario_id: str, **_: Any) -> ToolResult:
        return ToolResult(
            data=scenarios.get(scenario_id)["analysis"]["evidence_graph"], duration_ms=31
        )

    def recommend_remediation(scenario_id: str, **_: Any) -> ToolResult:
        return ToolResult(
            data=scenarios.get(scenario_id)["analysis"]["remediation"],
            duration_ms=25,
        )

    def estimate_cost(scenario_id: str, tool_count: int = 8, **_: Any) -> ToolResult:
        scenario = scenarios.get(scenario_id)
        agent_calls = tool_count + 5
        tokens_per_call = 620
        return ToolResult(
            data={
                "basis": "Configurable demo estimate, not a production benchmark",
                "agent_loop": {
                    "llm_calls": agent_calls,
                    "estimated_tokens": agent_calls * tokens_per_call,
                    "estimated_latency_seconds": round(agent_calls * 1.8, 1),
                },
                "compiled_run": {
                    "llm_calls": 0,
                    "estimated_tokens": 0,
                    "estimated_latency_seconds": scenario["analysis"]["compiled_latency_seconds"],
                },
                "workflow_reused": True,
            }
        )

    analysis_tools = [
        ("analysis.build_timeline", "Create a time-ordered incident narrative.", build_timeline),
        (
            "analysis.infer_root_cause",
            "Correlate evidence into a ranked, evidence-linked root cause.",
            infer_root_cause,
        ),
        (
            "analysis.build_evidence_graph",
            "Build service and evidence nodes with causal edges.",
            build_evidence_graph,
        ),
        (
            "analysis.recommend_remediation",
            "Select a runbook-backed remediation and risk level.",
            recommend_remediation,
        ),
        (
            "analysis.estimate_cost",
            "Compare a repeated agent loop with a compiled workflow run.",
            estimate_cost,
        ),
    ]
    for name, description, handler in analysis_tools:
        registry.register(
            ToolDefinition(
                name=name,
                description=description,
                risk=RiskLevel.READ,
                input_schema=_json_schema(),
                handler=handler,
            )
        )

    def rollback(scenario_id: str, incident_id: str, service: str, **_: Any) -> ToolResult:
        action = scenarios.get(scenario_id)["analysis"]["action_result"]
        return ToolResult(
            data={
                **action,
                "incident_id": incident_id,
                "service": service,
                "audit_event": "rollback.approved_and_executed",
            },
            duration_ms=110,
        )

    registry.register(
        ToolDefinition(
            name="kubernetes.rollback",
            description="Roll back a Kubernetes deployment to its last known-good revision.",
            risk=RiskLevel.DESTRUCTIVE,
            input_schema=_json_schema(),
            handler=rollback,
        )
    )

    def post_report(
        scenario_id: str, incident_id: str, channel: str = "#incidents", **_: Any
    ) -> ToolResult:
        return ToolResult(
            data={
                "posted": True,
                "simulated": True,
                "channel": channel,
                "incident_id": incident_id,
                "scenario_id": scenario_id,
                "message_ts": "demo.1710000000",
            },
            duration_ms=24,
        )

    registry.register(
        ToolDefinition(
            name="slack.post_report",
            description="Post the evidence-backed incident report to an approved Slack channel.",
            risk=RiskLevel.WRITE,
            input_schema=_json_schema(),
            handler=post_report,
        )
    )
    return registry
