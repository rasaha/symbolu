"""Retention purge DRY-RUN report: ``python -m ugence_dilchat.scripts_retention_report``.

Prints a content-free JSON summary of what a purge WOULD consider under the
ratified DEC-PR-3 rule, and **deletes nothing** — this is the only executable
retention path in this round. Output carries conversation ids, counts, and
machine-style blocking codes; never a message, evidence, report description,
token, or user identifier.

Run under the ``dilchat_worker`` database posture (like the relay); the report
is infrastructure, never a user- or reporter-facing surface. Exit code is 0
whenever evaluation succeeds, whatever the outcome — this is a report, not a gate.
"""

from __future__ import annotations

import asyncio
import json

from .config import Settings
from .db import get_sessionmaker, init_engine
from .services.retention import RetentionPurgeService


async def build_report(settings: Settings | None = None) -> dict:
    settings = settings or Settings()
    init_engine(settings)
    service = RetentionPurgeService(settings=settings, sessionmaker=get_sessionmaker())
    report = await service.report_only()
    return report.as_dict()


def main() -> None:
    print(json.dumps(asyncio.run(build_report()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
