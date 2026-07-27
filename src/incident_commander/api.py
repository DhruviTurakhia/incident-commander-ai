from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from incident_commander.config import Settings
from incident_commander.service import IncidentService


class StartIncidentRequest(BaseModel):
    scenario_id: str


class ApprovalRequestBody(BaseModel):
    approved_by: str = Field(min_length=2, max_length=80)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    service = IncidentService(settings)
    static_path = Path(__file__).parent / "static"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(
        title="Incident Commander API",
        version="0.1.0",
        description="Evidence-backed SRE investigations executed as compiled workflows.",
        lifespan=lifespan,
    )
    app.state.service = service
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(static_path / "index.html")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "workflow": service.workflow.id}

    @app.get("/api/scenarios")
    async def scenarios() -> list[dict]:
        return service.scenarios.list()

    @app.get("/api/tools")
    async def tools() -> list[dict]:
        return service.tools.catalog()

    @app.get("/api/workflow")
    async def workflow() -> dict:
        return service.workflow.model_dump(mode="json")

    @app.post("/api/incidents/demo")
    async def start_incident(request: StartIncidentRequest) -> dict:
        try:
            summary = await service.start_demo(request.scenario_id)
            return summary.model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/incidents")
    async def incidents() -> list[dict]:
        return [item.model_dump(mode="json") for item in service.latest()]

    @app.get("/api/incidents/{run_id}")
    async def incident(run_id: str) -> dict:
        try:
            return service.get_summary(run_id).model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/incidents/{run_id}/approve")
    async def approve(
        run_id: str,
        request: Annotated[ApprovalRequestBody, Body()],
    ) -> dict:
        try:
            summary = await service.approve(run_id, request.approved_by)
            return summary.model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


app = create_app()
