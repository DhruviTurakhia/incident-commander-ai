from __future__ import annotations

import asyncio
import time
from typing import Any

from incident_commander.engine.templates import evaluate_condition, resolve
from incident_commander.models import (
    ApprovalRequest,
    NodeExecution,
    NodeStatus,
    PrimitiveType,
    RunStatus,
    ToolResult,
    WorkflowBlueprint,
    WorkflowNode,
    WorkflowRun,
    utc_now,
)
from incident_commander.tools.registry import ToolRegistry


class WorkflowExecutor:
    """Executes a compiled workflow without requiring an LLM in the runtime loop."""

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    async def execute(self, blueprint: WorkflowBlueprint, run: WorkflowRun) -> WorkflowRun:
        run.status = RunStatus.RUNNING
        for node in blueprint.nodes:
            run.nodes.setdefault(node.id, NodeExecution())

        while True:
            pending = [
                node
                for node in blueprint.nodes
                if run.nodes[node.id].status in {NodeStatus.PENDING, NodeStatus.AWAITING_APPROVAL}
            ]
            if not pending:
                run.status = (
                    RunStatus.FAILED
                    if any(state.status == NodeStatus.FAILED for state in run.nodes.values())
                    else RunStatus.COMPLETED
                )
                run.updated_at = utc_now()
                return run

            ready = [
                node
                for node in pending
                if all(
                    run.nodes[dependency].status in {NodeStatus.SUCCEEDED, NodeStatus.SKIPPED}
                    for dependency in node.depends_on
                )
            ]
            if not ready:
                if any(
                    state.status == NodeStatus.AWAITING_APPROVAL for state in run.nodes.values()
                ):
                    run.status = RunStatus.AWAITING_APPROVAL
                    run.updated_at = utc_now()
                    return run
                run.status = RunStatus.FAILED
                run.updated_at = utc_now()
                return run

            await asyncio.gather(*(self._execute_node(node, run) for node in ready))
            if any(state.status == NodeStatus.FAILED for state in run.nodes.values()):
                run.status = RunStatus.FAILED
                run.updated_at = utc_now()
                return run
            if any(state.status == NodeStatus.AWAITING_APPROVAL for state in run.nodes.values()):
                run.status = RunStatus.AWAITING_APPROVAL
                run.updated_at = utc_now()
                return run

    async def _execute_node(self, node: WorkflowNode, run: WorkflowRun) -> None:
        state = run.nodes[node.id]
        if state.status == NodeStatus.SUCCEEDED:
            return

        context = {"inputs": run.inputs, "steps": run.steps}
        if node.when and not evaluate_condition(node.when, context):
            state.status = NodeStatus.SKIPPED
            state.finished_at = utc_now()
            run.steps[node.id] = {"skipped": True, "reason": "condition evaluated to false"}
            return

        if node.kind == PrimitiveType.APPROVAL and node.id not in run.approved_nodes:
            policy = node.approval
            if not policy:
                raise ValueError(f"approval policy missing for node {node.id}")
            run.approvals[node.id] = ApprovalRequest(
                node_id=node.id,
                title=policy.title,
                description=policy.description,
                required_role=policy.required_role,
            )
            state.status = NodeStatus.AWAITING_APPROVAL
            return

        state.status = NodeStatus.RUNNING
        state.started_at = utc_now()
        started = time.perf_counter()

        for attempt in range(1, node.retry.attempts + 1):
            state.attempts = attempt
            try:
                run.steps[node.id] = await self._dispatch(node, run)
                state.status = NodeStatus.SUCCEEDED
                state.error = None
                break
            except Exception as error:  # noqa: BLE001 - persisted as workflow failure state
                state.error = f"{type(error).__name__}: {error}"
                if attempt == node.retry.attempts:
                    state.status = NodeStatus.FAILED
                    break
                await asyncio.sleep(node.retry.backoff_seconds * attempt)

        state.duration_ms = int((time.perf_counter() - started) * 1000)
        state.finished_at = utc_now()

    async def _dispatch(self, node: WorkflowNode, run: WorkflowRun) -> Any:
        context = {"inputs": run.inputs, "steps": run.steps}
        approved = not node.requires_approval or any(
            dependency in run.approved_nodes for dependency in node.depends_on
        )

        if node.kind == PrimitiveType.CALL:
            result = await self.tools.call(
                node.tool or "", resolve(node.args, context), approved=approved
            )
            return self._unpack(result)

        if node.kind == PrimitiveType.PARALLEL:

            async def invoke(call: Any) -> tuple[str, Any]:
                result = await self.tools.call(
                    call.tool, resolve(call.args, context), approved=approved
                )
                return call.alias, self._unpack(result)

            entries = await asyncio.gather(*(invoke(call) for call in node.calls))
            return dict(entries)

        if node.kind == PrimitiveType.LOOP:
            items = resolve(node.items, context)

            async def invoke_item(item: Any) -> Any:
                item_context = {**context, node.item_name: item}
                result = await self.tools.call(
                    node.tool or "", resolve(node.args, item_context), approved=approved
                )
                return self._unpack(result)

            return await asyncio.gather(*(invoke_item(item) for item in items))

        if node.kind == PrimitiveType.PIPE:
            current: Any = None
            outputs: dict[str, Any] = {}
            for call in node.pipeline:
                pipe_context = {**context, "pipe": current}
                result = await self.tools.call(
                    call.tool, resolve(call.args, pipe_context), approved=approved
                )
                current = self._unpack(result)
                outputs[call.alias] = current
            return {"final": current, "stages": outputs}

        if node.kind == PrimitiveType.COLLECT:
            return resolve(node.sources, context)

        if node.kind == PrimitiveType.CONDITION:
            if not node.condition:
                raise ValueError("condition node has no condition")
            return {"matched": evaluate_condition(node.condition, context)}

        if node.kind == PrimitiveType.APPROVAL:
            approval = run.approvals[node.id]
            return {
                "approved": True,
                "approved_by": approval.approved_by,
                "approved_at": approval.approved_at,
            }

        raise ValueError(f"unsupported node kind: {node.kind}")

    @staticmethod
    def _unpack(result: ToolResult) -> Any:
        if result.evidence:
            return {
                "data": result.data,
                "evidence": [item.model_dump(mode="json") for item in result.evidence],
                "duration_ms": result.duration_ms,
            }
        return result.data
