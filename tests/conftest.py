from pathlib import Path

import pytest

from incident_commander.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "incident_commander.db",
        workflow_path=PROJECT_ROOT / "workflows" / "incident-investigation.v1.json",
        scenarios_path=PROJECT_ROOT / "fixtures" / "scenarios",
    )
