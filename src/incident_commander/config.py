from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_path: Path = PROJECT_ROOT / "data" / "incident_commander.db"
    workflow_path: Path = PROJECT_ROOT / "workflows" / "incident-investigation.v1.json"
    scenarios_path: Path = PROJECT_ROOT / "fixtures" / "scenarios"

    openai_api_key: str | None = None
    openai_model: str | None = None
    slack_bot_token: str | None = None
    slack_app_token: str | None = None

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "incident-commander"
