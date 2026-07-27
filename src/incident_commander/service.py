from __future__ import annotations

from uuid import uuid4

from incident_commander.config import Settings
from incident_commander.engine.compiler import WorkflowCompiler
from incident_commander.engine.executor import WorkflowExecutor
from incident_commander.models import (
    ApprovalRequest,
    Evidence,
    IncidentSummary,
    NodeStatus,
    Remediation,
    RootCause,
    TimelineEvent,
    WorkflowRun,
    utc_now,
)
from incident_commander.repository import RunRepository
from incident_commander.tools.demo import build_demo_registry
from incident_commander.tools.scenarios import ScenarioStore


class IncidentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.scenarios = ScenarioStore(settings.scenarios_path)
        self.tools = build_demo_registry(self.scenarios)
        self.compiler = WorkflowCompiler(self.tools)
        self.workflow = self.compiler.compile_file(settings.workflow_path)
        self.executor = WorkflowExecutor(self.tools)
        self.repository = RunRepository(settings.database_path)

    async def start_demo(self, scenario_id: str) -> IncidentSummary:
        scenario = self.scenarios.get(scenario_id)
        incident_id = f"INC-{uuid4().hex[:6].upper()}"
        run = WorkflowRun(
            id=f"run_{uuid4().hex}",
            incident_id=incident_id,
            scenario_id=scenario_id,
            workflow_id=self.workflow.id,
            workflow_version=self.workflow.version,
            inputs={
                "scenario_id": scenario_id,
                "incident_id": incident_id,
                "service": scenario["alert"]["service"],
                "title": scenario["title"],
                "severity": scenario["alert"]["severity"],
                "detected_at": scenario["alert"]["detected_at"],
                "slack_channel": "#incident-response",
                "related_services": scenario["services"],
            },
        )
        self.repository.save(run)
        run = await self.executor.execute(self.workflow, run)
        self.repository.save(run)
        return self.summarize(run)

    async def approve(self, run_id: str, approved_by: str) -> IncidentSummary:
        run = self.require_run(run_id)
        awaiting = [
            node_id
            for node_id, state in run.nodes.items()
            if state.status == NodeStatus.AWAITING_APPROVAL
        ]
        if not awaiting:
            raise ValueError("this run is not waiting for approval")

        for node_id in awaiting:
            approval = run.approvals[node_id]
            approval.approved_by = approved_by
            approval.approved_at = utc_now()
            run.approved_nodes.add(node_id)
            run.nodes[node_id].status = NodeStatus.PENDING

        run = await self.executor.execute(self.workflow, run)
        self.repository.save(run)
        return self.summarize(run)

    def require_run(self, run_id: str) -> WorkflowRun:
        run = self.repository.get(run_id)
        if not run:
            raise KeyError(f"workflow run not found: {run_id}")
        return run

    def get_summary(self, run_id: str) -> IncidentSummary:
        return self.summarize(self.require_run(run_id))

    def latest(self) -> list[IncidentSummary]:
        return [self.summarize(run) for run in self.repository.latest()]

    def summarize(self, run: WorkflowRun) -> IncidentSummary:
        scenario = self.scenarios.get(run.scenario_id)
        evidence: list[Evidence] = []
        context = run.steps.get("collect_context", {})
        for result in context.values():
            for item in result.get("evidence", []) if isinstance(result, dict) else []:
                evidence.append(Evidence.model_validate(item))

        correlation = run.steps.get("correlate_incident", {})
        timeline_payload = correlation.get("stages", {}).get("timeline", [])
        timeline = [TimelineEvent.model_validate(item) for item in timeline_payload]
        root_payload = correlation.get("final")
        remediation_payload = run.steps.get("recommend_remediation")
        approval: ApprovalRequest | None = next(iter(run.approvals.values()), None)

        return IncidentSummary(
            incident_id=run.incident_id,
            run_id=run.id,
            scenario_id=run.scenario_id,
            status=run.status,
            title=scenario["title"],
            severity=scenario["alert"]["severity"],
            detected_at=scenario["alert"]["detected_at"],
            affected_service=scenario["alert"]["service"],
            workflow_version=run.workflow_version,
            timeline=timeline,
            evidence=evidence,
            root_cause=RootCause.model_validate(root_payload) if root_payload else None,
            evidence_graph=run.steps.get("build_evidence_graph", {}),
            remediation=(
                Remediation.model_validate(remediation_payload) if remediation_payload else None
            ),
            approval=approval,
            action_result=run.steps.get("execute_rollback"),
            cost_comparison=run.steps.get("estimate_cost", {}),
            workflow_nodes=run.nodes,
        )
