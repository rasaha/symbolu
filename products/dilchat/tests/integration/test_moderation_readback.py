"""Minimal moderation read-back over real reporting flows (round PR-D, DEC-PR-4).

Drives the real report path, then exercises the reviewer surface: individual
authentication, audited reads, content-free audit metadata, and the absence of
any adjudication effect (reports stay SUBMITTED; case state is untouched).
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from helpers import register_and_login
from ugence_dilchat.domain.enums import (
    ReportStatus,
    SafetyActorType,
    SafetyCaseEventType,
)
from ugence_dilchat.infrastructure.chat_safety_orm import (
    ChatReport,
    ChatSafetyCase,
    ChatSafetyCaseEvent,
)
from ugence_dilchat.services.moderation import ModerationAccessError, ModerationService

_SENTINEL_BODY = "SENTINEL_moderation_body_5b2e"
_SENTINEL_DESCRIPTION = "SENTINEL_moderation_description_5b2e"


def _hdr(auth: dict) -> dict:
    return {"Authorization": auth["Authorization"]}


async def _reported_conversation(ctx) -> tuple[dict, str, str]:
    """Pair two users, send a message, and file a report against the conversation."""
    a = await register_and_login(ctx.client)
    b = await register_and_login(ctx.client)
    token = (await ctx.client.post("/v1/couples/invitations", headers=_hdr(a))).json()["token"]
    await ctx.client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    conv = (await ctx.client.get("/v1/conversations/current", headers=_hdr(a))).json()
    cid = conv["conversation_id"]
    await ctx.client.post(
        f"/v1/conversations/{cid}/messages",
        headers=_hdr(a),
        json={"client_message_id": f"m-{uuid.uuid4().hex[:8]}", "body": _SENTINEL_BODY},
    )
    r = await ctx.client.post(
        "/v1/reports",
        headers=_hdr(b),
        json={
            "conversation_id": cid,
            "target_type": "CONVERSATION",
            "reason": "HARASSMENT",
            "description": _SENTINEL_DESCRIPTION,
            "client_report_id": f"r-{uuid.uuid4().hex[:10]}",
        },
    )
    assert r.status_code == 201, r.text
    return b, cid, r.json()["report_id"]


async def _service_and_principal(ctx, label="reviewer-01"):
    async with ctx.sessionmaker() as session:
        service = ModerationService(session)
        _reviewer, key = await service.provision_reviewer(label)
        await session.commit()
    session = ctx.sessionmaker()
    service = ModerationService(session)
    principal = await service.authenticate(label, key)
    return session, service, principal, key


async def _events(ctx, **where) -> list[ChatSafetyCaseEvent]:
    async with ctx.sessionmaker() as s:
        stmt = sa.select(ChatSafetyCaseEvent)
        for col, val in where.items():
            stmt = stmt.where(getattr(ChatSafetyCaseEvent, col) == val)
        return list((await s.execute(stmt)).scalars().all())


# --- reviewer principals ----------------------------------------------------- #


async def test_provisioned_key_is_returned_once_and_only_hashed_at_rest(ctx):
    async with ctx.sessionmaker() as session:
        service = ModerationService(session)
        reviewer, key = await service.provision_reviewer("reviewer-01")
        await session.commit()
        assert key and len(key) >= 32
        # The plaintext key is nowhere in the stored row.
        assert reviewer.credential_hash != key
        assert key not in reviewer.credential_hash
        assert reviewer.credential_hash.startswith("$argon2")


async def test_authentication_requires_the_individual_credential(ctx):
    session, _service, principal, _key = await _service_and_principal(ctx)
    async with session:
        assert principal.label == "reviewer-01"
        assert principal.reviewer_id is not None
        # A per-invocation session id makes each access attributable to one sitting.
        assert principal.session_id is not None


async def test_wrong_key_unknown_label_and_revoked_all_fail_identically(ctx):
    async with ctx.sessionmaker() as session:
        service = ModerationService(session)
        _r, key = await service.provision_reviewer("reviewer-01")
        await session.commit()

    async with ctx.sessionmaker() as session:
        service = ModerationService(session)
        messages = []
        for label, attempt in (
            ("reviewer-01", "wrong-key"),
            ("no-such-reviewer", key),
        ):
            with pytest.raises(ModerationAccessError) as exc:
                await service.authenticate(label, attempt)
            messages.append(str(exc.value))
        assert messages[0] == messages[1]  # no oracle about which part was wrong

    async with ctx.sessionmaker() as session:
        service = ModerationService(session)
        assert await service.revoke_reviewer("reviewer-01") is True
        await session.commit()
    async with ctx.sessionmaker() as session:
        service = ModerationService(session)
        with pytest.raises(ModerationAccessError) as exc:
            await service.authenticate("reviewer-01", key)
        assert str(exc.value) == messages[0]  # revocation is not distinguishable either


# --- audited reads ------------------------------------------------------------ #


async def test_listing_cases_records_an_individual_attributed_access(ctx):
    await _reported_conversation(ctx)
    session, service, principal, _ = await _service_and_principal(ctx)
    async with session:
        cases = await service.list_cases(principal, reason="PILOT_TRIAGE")
        await session.commit()
    assert len(cases) == 1
    assert cases[0].report_count == 1
    assert cases[0].reasons == ("HARASSMENT",)

    events = await _events(ctx, event_type=SafetyCaseEventType.CASE_ACCESSED.value)
    assert len(events) == 1
    event = events[0]
    assert event.actor_type == SafetyActorType.SAFETY.value
    assert event.actor_internal_id == principal.reviewer_id  # the INDIVIDUAL, not the role
    assert event.meta["reviewer_label"] == "reviewer-01"
    assert event.meta["access_reason"] == "PILOT_TRIAGE"
    assert event.meta["access_scope"] == "LIST"


async def test_reading_a_case_returns_reports_and_records_the_access(ctx):
    await _reported_conversation(ctx)
    session, service, principal, _ = await _service_and_principal(ctx)
    async with session:
        cases = await service.list_cases(principal, reason="PILOT_TRIAGE")
        detail = await service.read_case(principal, cases[0].case_id, reason="PILOT_TRIAGE")
        await session.commit()

    assert len(detail.reports) == 1
    report = detail.reports[0]
    assert report.reason == "HARASSMENT"
    # The reporter's own words are readable HERE and only here (DEC-3B-5).
    assert report.description == _SENTINEL_DESCRIPTION

    detail_events = [
        e
        for e in await _events(ctx, event_type=SafetyCaseEventType.CASE_ACCESSED.value)
        if e.meta.get("access_scope") == "DETAIL"
    ]
    assert len(detail_events) == 1
    assert detail_events[0].actor_internal_id == principal.reviewer_id


async def test_reading_evidence_returns_snapshots_and_records_a_content_free_event(ctx):
    _reporter, _cid, report_id = await _reported_conversation(ctx)
    session, service, principal, _ = await _service_and_principal(ctx)
    async with session:
        items = await service.read_evidence(
            principal, uuid.UUID(report_id), reason="PILOT_TRIAGE"
        )
        await session.commit()

    assert items, "the report preserved evidence"
    assert any(_SENTINEL_BODY in i.body_snapshot for i in items)

    events = await _events(ctx, event_type=SafetyCaseEventType.EVIDENCE_ACCESSED.value)
    accessed = [e for e in events if e.meta and e.meta.get("access_reason") == "PILOT_TRIAGE"]
    assert len(accessed) == 1
    meta = accessed[0].meta
    assert meta["evidence_count"] == len(items)
    # THAT it was read, never WHAT it said.
    assert _SENTINEL_BODY not in repr(meta)
    assert _SENTINEL_DESCRIPTION not in repr(meta)


async def test_all_audit_metadata_stays_content_free(ctx):
    _r, _cid, report_id = await _reported_conversation(ctx)
    session, service, principal, _ = await _service_and_principal(ctx)
    async with session:
        cases = await service.list_cases(principal, reason="PILOT_TRIAGE")
        await service.read_case(principal, cases[0].case_id, reason="PILOT_TRIAGE")
        await service.read_evidence(principal, uuid.UUID(report_id), reason="PILOT_TRIAGE")
        await session.commit()

    for event in await _events(ctx):
        rendered = repr(event.meta)
        assert _SENTINEL_BODY not in rendered
        assert _SENTINEL_DESCRIPTION not in rendered


async def test_access_reason_must_be_a_machine_code(ctx):
    await _reported_conversation(ctx)
    session, service, principal, _ = await _service_and_principal(ctx)
    async with session:
        for bad in ("", "because alice was mean", "lower_case", "a"):
            with pytest.raises(ModerationAccessError, match="machine-style"):
                await service.list_cases(principal, reason=bad)


# --- no adjudication ---------------------------------------------------------- #


async def test_reading_never_changes_report_status_or_case_state(ctx):
    _r, _cid, report_id = await _reported_conversation(ctx)

    async with ctx.sessionmaker() as s:
        before_status = await s.scalar(
            sa.select(ChatReport.status).where(ChatReport.id == uuid.UUID(report_id))
        )
        before_state = await s.scalar(sa.select(ChatSafetyCase.state))
    assert before_status == ReportStatus.SUBMITTED.value

    session, service, principal, _ = await _service_and_principal(ctx)
    async with session:
        cases = await service.list_cases(principal, reason="PILOT_TRIAGE")
        await service.read_case(principal, cases[0].case_id, reason="PILOT_TRIAGE")
        await service.read_evidence(principal, uuid.UUID(report_id), reason="PILOT_TRIAGE")
        await session.commit()

    async with ctx.sessionmaker() as s:
        after_status = await s.scalar(
            sa.select(ChatReport.status).where(ChatReport.id == uuid.UUID(report_id))
        )
        after_state = await s.scalar(sa.select(ChatSafetyCase.state))
    # DEC-3B-3 holds: reading a case is not deciding it.
    assert after_status == before_status == ReportStatus.SUBMITTED.value
    assert after_state == before_state


async def test_missing_case_and_report_fail_closed(ctx):
    session, service, principal, _ = await _service_and_principal(ctx)
    async with session:
        with pytest.raises(ModerationAccessError):
            await service.read_case(principal, uuid.uuid4(), reason="PILOT_TRIAGE")
        with pytest.raises(ModerationAccessError):
            await service.read_evidence(principal, uuid.uuid4(), reason="PILOT_TRIAGE")
