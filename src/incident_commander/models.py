from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class PrimitiveType(StrEnum):
    CALL = "call"
    PARALLEL = "parallel"
    LOOP = "loop"
    PIPE = "pipe"
    COLLECT = "collect"
    CONDITION = "condition"
    APPROVAL = "approval"


class NodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class RetryPolicy(BaseModel):
    attempts: int = Field(default=1, ge=1, le=5)
    backoff_seconds: float = Field(default=0.05, ge=0, le=30)


class InlineCall(BaseModel):
    alias: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class Condition(BaseModel):
    left: Any
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "exists"]
    right: Any | None = None


class ApprovalPolicy(BaseModel):
    title: str
    description: str
    required_role: str = "incident_commander"
    expires_after_minutes: int = Field(default=30, ge=1, le=1440)


class WorkflowNode(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    kind: PrimitiveType
    depends_on: list[str] = Field(default_factory=list)
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    calls: list[InlineCall] = Field(default_factory=list)
    items: Any | None = None
    item_name: str = "item"
    pipeline: list[InlineCall] = Field(default_factory=list)
    sources: dict[str, Any] = Field(default_factory=dict)
    condition: Condition | None = None
    when: Condition | None = None
    approval: ApprovalPolicy | None = None
    requires_approval: bool = False
    retry: RetryPolicy = Field(default_factory=RetryPolicy)

    @model_validator(mode="after")
    def validate_shape(self) -> WorkflowNode:
        if self.kind == PrimitiveType.CALL and not self.tool:
            raise ValueError("call nodes require a tool")
        if self.kind == PrimitiveType.PARALLEL and not self.calls:
            raise ValueError("parallel nodes require calls")
        if self.kind == PrimitiveType.LOOP and (not self.tool or self.items is None):
            raise ValueError("loop nodes require a tool and items")
        if self.kind == PrimitiveType.PIPE and not self.pipeline:
            raise ValueError("pipe nodes require a pipeline")
        if self.kind == PrimitiveType.COLLECT and not self.sources:
            raise ValueError("collect nodes require sources")
        if self.kind == PrimitiveType.CONDITION and not self.condition:
            raise ValueError("condition nodes require a condition")
        if self.kind == PrimitiveType.APPROVAL and not self.approval:
            raise ValueError("approval nodes require an approval policy")
        return self


class WorkflowBlueprint(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str
    name: str
    version: int = Field(ge=1)
    description: str
    trigger: str = "manual"
    nodes: list[WorkflowNode]
    labels: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dag(self) -> WorkflowBlueprint:
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("workflow node ids must be unique")

        known = set(ids)
        for node in self.nodes:
            missing = set(node.depends_on) - known
            if missing:
                raise ValueError(f"node {node.id} has unknown dependencies: {sorted(missing)}")
            if node.id in node.depends_on:
                raise ValueError(f"node {node.id} cannot depend on itself")

        visiting: set[str] = set()
        visited: set[str] = set()
        dependencies = {node.id: node.depends_on for node in self.nodes}

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("workflow must be acyclic")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in dependencies[node_id]:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)
        return self


class Evidence(BaseModel):
    id: str
    source: str
    signal_type: str
    service: str
    observed_at: datetime
    summary: str
    value: str
    anomaly_score: float = Field(ge=0, le=1)
    url: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    occurred_at: datetime
    title: str
    detail: str
    service: str
    evidence_ids: list[str]
    severity: Literal["info", "warning", "critical"] = "info"


class RootCause(BaseModel):
    summary: str
    confidence: float = Field(ge=0, le=1)
    service: str
    causal_chain: list[str]
    evidence_ids: list[str]


class Remediation(BaseModel):
    title: str
    description: str
    command_preview: str
    risk: RiskLevel
    requires_approval: bool = True


class ToolResult(BaseModel):
    data: Any
    evidence: list[Evidence] = Field(default_factory=list)
    duration_ms: int = Field(default=0, ge=0)


class ApprovalRequest(BaseModel):
    node_id: str
    title: str
    description: str
    required_role: str
    created_at: datetime = Field(default_factory=utc_now)
    approved_by: str | None = None
    approved_at: datetime | None = None


class NodeExecution(BaseModel):
    status: NodeStatus = NodeStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempts: int = 0
    duration_ms: int = 0
    error: str | None = None


class WorkflowRun(BaseModel):
    id: str
    incident_id: str
    scenario_id: str
    workflow_id: str
    workflow_version: int
    status: RunStatus = RunStatus.PENDING
    inputs: dict[str, Any]
    steps: dict[str, Any] = Field(default_factory=dict)
    nodes: dict[str, NodeExecution] = Field(default_factory=dict)
    approvals: dict[str, ApprovalRequest] = Field(default_factory=dict)
    approved_nodes: set[str] = Field(default_factory=set)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class IncidentSummary(BaseModel):
    incident_id: str
    run_id: str
    scenario_id: str
    status: RunStatus
    title: str
    severity: str
    detected_at: datetime
    affected_service: str
    workflow_version: int
    timeline: list[TimelineEvent] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    root_cause: RootCause | None = None
    evidence_graph: dict[str, Any] = Field(default_factory=dict)
    remediation: Remediation | None = None
    approval: ApprovalRequest | None = None
    action_result: dict[str, Any] | None = None
    cost_comparison: dict[str, Any] = Field(default_factory=dict)
    workflow_nodes: dict[str, NodeExecution] = Field(default_factory=dict)
