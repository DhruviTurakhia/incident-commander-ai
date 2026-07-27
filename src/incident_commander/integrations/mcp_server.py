from incident_commander.config import Settings
from incident_commander.service import IncidentService


def build_mcp_server(settings: Settings | None = None):
    """Create the MCP mediator lazily so the core demo does not require MCP packages."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise RuntimeError('Install MCP support with: pip install -e ".[mcp]"') from error

    service = IncidentService(settings or Settings())
    mcp = FastMCP("Incident Commander", json_response=True)

    @mcp.tool()
    def discover_sre_tools() -> list[dict]:
        """List the operational tools available to the workflow compiler."""
        return service.tools.catalog()

    @mcp.tool()
    def get_compiled_workflow() -> dict:
        """Return the validated workflow version currently used for incident runs."""
        return service.workflow.model_dump(mode="json")

    @mcp.tool()
    async def investigate_incident(scenario_id: str) -> dict:
        """Execute a deterministic investigation and pause before remediation."""
        result = await service.start_demo(scenario_id)
        return result.model_dump(mode="json")

    @mcp.tool()
    async def approve_remediation(run_id: str, approved_by: str) -> dict:
        """Approve and resume a paused remediation workflow."""
        result = await service.approve(run_id, approved_by)
        return result.model_dump(mode="json")

    return mcp


def main() -> None:
    build_mcp_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()
