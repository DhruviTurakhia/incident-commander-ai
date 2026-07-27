import sqlite3
from pathlib import Path

from incident_commander.models import WorkflowRun, utc_now


class RunRepository:
    """Small SQLite repository that keeps local demo runs across restarts."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON workflow_runs(updated_at DESC)"
            )

    def save(self, run: WorkflowRun) -> WorkflowRun:
        run.updated_at = utc_now()
        payload = run.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_runs
                    (id, incident_id, scenario_id, status, created_at, updated_at, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (
                    run.id,
                    run.incident_id,
                    run.scenario_id,
                    run.status.value,
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                    payload,
                ),
            )
        return run

    def get(self, run_id: str) -> WorkflowRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM workflow_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return WorkflowRun.model_validate_json(row["payload"]) if row else None

    def latest(self, limit: int = 20) -> list[WorkflowRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM workflow_runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [WorkflowRun.model_validate_json(row["payload"]) for row in rows]
