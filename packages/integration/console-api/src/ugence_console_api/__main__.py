"""Run the console API: ``python -m ugence_console_api`` (default port 8090)."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "ugence_console_api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=int(os.environ.get("CONSOLE_API_PORT", "8090")),
    )


if __name__ == "__main__":
    main()
