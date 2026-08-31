"""Internal moderation read-back tooling: ``python -m ugence_dilchat.scripts_moderation``.

The operator surface for DEC-PR-4. Deliberately a small internal tool, not an
admin console: it lists cases, reads one case, and reads that case's preserved
evidence. There is no adjudication command because no adjudication exists.

Run it under the ``dilchat_safety`` database posture. That role is enforcement
only — the human is identified by an individual reviewer credential supplied
through the environment:

    DILCHAT_REVIEWER_LABEL=reviewer-01
    DILCHAT_REVIEWER_KEY=…            # never passed as an argument (argv is
                                      # world-readable via the process table)

Commands::

    provision-reviewer --label reviewer-01   # prints the key ONCE
    revoke-reviewer --label reviewer-01
    list-cases --reason PILOT_TRIAGE [--limit 50]
    read-case --case-id <uuid> --reason PILOT_TRIAGE
    read-evidence --report-id <uuid> --reason PILOT_TRIAGE

Every read is recorded against the individual reviewer as an immutable case
event. Report descriptions and evidence bodies are printed to the operator's
terminal — that is the point of the surface — but are never logged, audited, or
written anywhere by this tool.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid

from .config import Settings
from .db import get_sessionmaker, init_engine, set_transaction_context
from .services.moderation import ModerationAccessError, ModerationService


async def _with_safety_session(fn):
    settings = Settings()
    init_engine(settings)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # The safety posture: RLS grants reviewer/case/evidence visibility to
        # this actor type alone. A user-facing request never runs in it.
        await set_transaction_context(session, user_id=None, actor_type="safety")
        try:
            result = await fn(ModerationService(session))
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


def _credentials() -> tuple[str, str]:
    label = os.environ.get("DILCHAT_REVIEWER_LABEL", "")
    key = os.environ.get("DILCHAT_REVIEWER_KEY", "")
    if not label or not key:
        raise ModerationAccessError(
            "set DILCHAT_REVIEWER_LABEL and DILCHAT_REVIEWER_KEY "
            "(never pass a reviewer key as a command-line argument)"
        )
    return label, key


async def _provision(label: str) -> dict:
    async def run(service: ModerationService) -> dict:
        reviewer, key = await service.provision_reviewer(label)
        return {
            "reviewer_id": str(reviewer.id),
            "label": reviewer.label,
            "role": reviewer.role,
            "key": key,
            "notice": "Store this key now — it is shown once and never recoverable.",
        }

    return await _with_safety_session(run)


async def _revoke(label: str) -> dict:
    async def run(service: ModerationService) -> dict:
        return {"label": label, "revoked": await service.revoke_reviewer(label)}

    return await _with_safety_session(run)


async def _list_cases(reason: str, limit: int) -> dict:
    label, key = _credentials()

    async def run(service: ModerationService) -> dict:
        principal = await service.authenticate(label, key)
        cases = await service.list_cases(principal, reason=reason, limit=limit)
        return {
            "reviewer": principal.label,
            "session_id": str(principal.session_id),
            "count": len(cases),
            "cases": [
                {
                    "case_id": str(c.case_id),
                    "state": c.state,
                    "conversation_id": str(c.conversation_id) if c.conversation_id else None,
                    "created_at": c.created_at.isoformat(),
                    "report_count": c.report_count,
                    "reasons": list(c.reasons),
                }
                for c in cases
            ],
        }

    return await _with_safety_session(run)


async def _read_case(case_id: uuid.UUID, reason: str) -> dict:
    label, key = _credentials()

    async def run(service: ModerationService) -> dict:
        principal = await service.authenticate(label, key)
        detail = await service.read_case(principal, case_id, reason=reason)
        return {
            "reviewer": principal.label,
            "session_id": str(principal.session_id),
            "case_id": str(detail.case_id),
            "state": detail.state,
            "conversation_id": str(detail.conversation_id) if detail.conversation_id else None,
            "created_at": detail.created_at.isoformat(),
            "reports": [
                {
                    "report_id": str(r.report_id),
                    "reporter_user_id": str(r.reporter_user_id),
                    "target_type": r.target_type,
                    "target_message_id": str(r.target_message_id)
                    if r.target_message_id
                    else None,
                    "reason": r.reason,
                    "status": r.status,
                    "description": r.description,
                    "created_at": r.created_at.isoformat(),
                }
                for r in detail.reports
            ],
        }

    return await _with_safety_session(run)


async def _read_evidence(report_id: uuid.UUID, reason: str) -> dict:
    label, key = _credentials()

    async def run(service: ModerationService) -> dict:
        principal = await service.authenticate(label, key)
        items = await service.read_evidence(principal, report_id, reason=reason)
        return {
            "reviewer": principal.label,
            "session_id": str(principal.session_id),
            "report_id": str(report_id),
            "count": len(items),
            "evidence": [
                {
                    "evidence_sequence": i.evidence_sequence,
                    "source_message_id": str(i.source_message_id)
                    if i.source_message_id
                    else None,
                    "source_sender_id": str(i.source_sender_id) if i.source_sender_id else None,
                    "source_server_sequence": i.source_server_sequence,
                    "source_created_at": i.source_created_at.isoformat()
                    if i.source_created_at
                    else None,
                    "source_deleted_at": i.source_deleted_at.isoformat()
                    if i.source_deleted_at
                    else None,
                    "body_snapshot": i.body_snapshot,
                }
                for i in items
            ],
        }

    return await _with_safety_session(run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ugence_dilchat.scripts_moderation",
        description="Internal moderation read-back (read-only; no adjudication).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("provision-reviewer", help="create an individual reviewer principal")
    p.add_argument("--label", required=True)

    p = sub.add_parser("revoke-reviewer", help="revoke a reviewer principal")
    p.add_argument("--label", required=True)

    p = sub.add_parser("list-cases", help="list safety cases (audited)")
    p.add_argument("--reason", required=True, help="machine-style access reason, e.g. PILOT_TRIAGE")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("read-case", help="read one case and its reports (audited)")
    p.add_argument("--case-id", required=True)
    p.add_argument("--reason", required=True)

    p = sub.add_parser("read-evidence", help="read a report's preserved evidence (audited)")
    p.add_argument("--report-id", required=True)
    p.add_argument("--reason", required=True)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "provision-reviewer":
            payload = asyncio.run(_provision(args.label))
        elif args.command == "revoke-reviewer":
            payload = asyncio.run(_revoke(args.label))
        elif args.command == "list-cases":
            payload = asyncio.run(_list_cases(args.reason, args.limit))
        elif args.command == "read-case":
            payload = asyncio.run(_read_case(uuid.UUID(args.case_id), args.reason))
        else:
            payload = asyncio.run(_read_evidence(uuid.UUID(args.report_id), args.reason))
    except ModerationAccessError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
