from fastapi.testclient import TestClient

from incident_commander.api import create_app


def test_api_demo_flow(settings):
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200

        scenarios = client.get("/api/scenarios").json()
        assert len(scenarios) == 5

        started = client.post(
            "/api/incidents/demo",
            json={"scenario_id": "expired-credential"},
        )
        assert started.status_code == 200
        payload = started.json()
        assert payload["status"] == "awaiting_approval"

        approved = client.post(
            f"/api/incidents/{payload['run_id']}/approve",
            json={"approved_by": "Dhruvi Turakhia"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "completed"


def test_api_rejects_unknown_scenario(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/incidents/demo",
            json={"scenario_id": "does-not-exist"},
        )
        assert response.status_code == 404
