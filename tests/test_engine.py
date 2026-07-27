import pytest

from incident_commander.models import RunStatus
from incident_commander.service import IncidentService


@pytest.mark.parametrize(
    "scenario_id",
    [
        "bad-deployment",
        "slow-query",
        "memory-leak",
        "expired-credential",
        "queue-backlog",
    ],
)
async def test_every_fault_reaches_evidence_backed_approval_gate(settings, scenario_id):
    service = IncidentService(settings)

    summary = await service.start_demo(scenario_id)

    assert summary.status == RunStatus.AWAITING_APPROVAL
    assert summary.root_cause is not None
    assert summary.root_cause.confidence >= 0.8
    assert len(summary.root_cause.evidence_ids) >= 5
    assert len(summary.timeline) == 3
    assert len(summary.evidence) >= 6
    assert summary.approval is not None
    assert summary.action_result is None
    assert summary.cost_comparison["compiled_run"]["llm_calls"] == 0


async def test_approval_resumes_and_audits_destructive_action(settings):
    service = IncidentService(settings)
    waiting = await service.start_demo("bad-deployment")

    completed = await service.approve(waiting.run_id, "Dhruvi Turakhia")

    assert completed.status == RunStatus.COMPLETED
    assert completed.approval is not None
    assert completed.approval.approved_by == "Dhruvi Turakhia"
    assert completed.approval.approved_at is not None
    assert completed.action_result["status"] == "rolled_back"
    assert completed.action_result["audit_event"] == "rollback.approved_and_executed"


async def test_completed_run_survives_repository_reload(settings):
    first_service = IncidentService(settings)
    waiting = await first_service.start_demo("queue-backlog")
    await first_service.approve(waiting.run_id, "on-call@example.com")

    reloaded_service = IncidentService(settings)
    persisted = reloaded_service.get_summary(waiting.run_id)

    assert persisted.status == RunStatus.COMPLETED
    assert persisted.action_result["to_version"] == "4.5.3"
