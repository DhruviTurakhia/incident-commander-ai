from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from incident_commander.config import Settings
from incident_commander.service import IncidentService


@dataclass
class TemporalIncidentRequest:
    scenario_id: str
    approved_by: str | None = None


async def run_worker(settings: Settings | None = None) -> None:
    """Run the optional durable worker with a signal-backed human approval gate."""
    try:
        from temporalio import activity, workflow
        from temporalio.client import Client
        from temporalio.worker import Worker
    except ImportError as error:
        raise RuntimeError('Install Temporal support with: pip install -e ".[temporal]"') from error

    settings = settings or Settings()
    service = IncidentService(settings)

    @activity.defn(name="investigate_incident")
    async def investigate_incident(scenario_id: str) -> dict:
        summary = await service.start_demo(scenario_id)
        return summary.model_dump(mode="json")

    @activity.defn(name="execute_approved_remediation")
    async def execute_approved_remediation(payload: dict) -> dict:
        summary = await service.approve(payload["run_id"], payload["approved_by"])
        return summary.model_dump(mode="json")

    @workflow.defn(name="DurableIncidentInvestigation")
    class DurableIncidentInvestigation:
        def __init__(self) -> None:
            self.approved_by: str | None = None

        @workflow.signal
        async def approve(self, approved_by: str) -> None:
            self.approved_by = approved_by

        @workflow.run
        async def run(self, scenario_id: str) -> dict:
            summary = await workflow.execute_activity(
                investigate_incident,
                scenario_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=None,
            )
            if summary["status"] != "awaiting_approval":
                return summary

            await workflow.wait_condition(
                lambda: self.approved_by is not None,
                timeout=timedelta(minutes=30),
            )
            return await workflow.execute_activity(
                execute_approved_remediation,
                {"run_id": summary["run_id"], "approved_by": self.approved_by},
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=None,
            )

    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[DurableIncidentInvestigation],
        activities=[investigate_incident, execute_approved_remediation],
    )
    await worker.run()
