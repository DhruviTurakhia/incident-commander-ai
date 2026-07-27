from __future__ import annotations

import asyncio

from incident_commander.config import Settings
from incident_commander.service import IncidentService


def _blocks(summary: dict) -> list[dict]:
    root = summary.get("root_cause") or {}
    remediation = summary.get("remediation") or {}
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{summary['severity']} · {summary['title']}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Incident*\n`{summary['incident_id']}`"},
                {"type": "mrkdwn", "text": f"*Service*\n`{summary['affected_service']}`"},
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence*\n{root.get('confidence', 0):.0%}",
                },
                {"type": "mrkdwn", "text": f"*Workflow*\nv{summary['workflow_version']}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Likely root cause*\n{root.get('summary')}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Recommended action*\n{remediation.get('title')}",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "approve_remediation",
                    "style": "danger",
                    "text": {"type": "plain_text", "text": "Approve rollback"},
                    "value": summary["run_id"],
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Approve rollback?"},
                        "text": {
                            "type": "mrkdwn",
                            "text": "This action changes production state and is audit logged.",
                        },
                        "confirm": {"type": "plain_text", "text": "Approve"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                }
            ],
        },
    ]


async def run_slack_bot(settings: Settings | None = None) -> None:
    try:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
        from slack_bolt.async_app import AsyncApp
    except ImportError as error:
        raise RuntimeError('Install Slack support with: pip install -e ".[slack]"') from error

    settings = settings or Settings()
    if not settings.slack_bot_token or not settings.slack_app_token:
        raise RuntimeError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN are required")

    service = IncidentService(settings)
    app = AsyncApp(token=settings.slack_bot_token)

    @app.command("/investigate")
    async def investigate(ack, command, client):
        await ack("Investigation started. I am collecting evidence in parallel.")
        scenario_id = command.get("text", "").strip() or "bad-deployment"
        summary = await service.start_demo(scenario_id)
        await client.chat_postMessage(
            channel=command["channel_id"],
            text=f"Investigation ready for {summary.incident_id}",
            blocks=_blocks(summary.model_dump(mode="json")),
        )

    @app.action("approve_remediation")
    async def approve(ack, body, client):
        await ack()
        run_id = body["actions"][0]["value"]
        approver = body["user"]["username"]
        summary = await service.approve(run_id, approver)
        await client.chat_postMessage(
            channel=body["channel"]["id"],
            text=(
                f"{summary.incident_id}: remediation approved by {approver}; "
                f"status is {summary.status.value}."
            ),
        )

    await AsyncSocketModeHandler(app, settings.slack_app_token).start_async()


if __name__ == "__main__":
    asyncio.run(run_slack_bot())
