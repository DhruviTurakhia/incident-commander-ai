import argparse

import uvicorn

from incident_commander.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Incident Commander locally.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    uvicorn.run(
        "incident_commander.api:app",
        host=args.host or settings.app_host,
        port=args.port or settings.app_port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
