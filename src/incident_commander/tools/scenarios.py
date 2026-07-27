import json
from pathlib import Path
from typing import Any


class ScenarioStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._scenarios: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        self._scenarios = {}
        for path in sorted(self.directory.glob("*.json")):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            self._scenarios[scenario["id"]] = scenario

    def get(self, scenario_id: str) -> dict[str, Any]:
        try:
            return self._scenarios[scenario_id]
        except KeyError as error:
            raise KeyError(f"unknown demo scenario: {scenario_id}") from error

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "id": scenario["id"],
                "title": scenario["title"],
                "description": scenario["description"],
                "severity": scenario["alert"]["severity"],
                "affected_service": scenario["alert"]["service"],
                "fault_type": scenario["fault_type"],
            }
            for scenario in self._scenarios.values()
        ]
