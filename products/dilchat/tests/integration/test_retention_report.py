"""Retention dry-run report over real flows (round PR-B, DEC-PR-3).

Proves against the real pair → unpair → report paths that:
  - the report is REPORT-ONLY: no row, message, or conversation is deleted;
  - a reported conversation is PRESERVED_FOR_REPORT and never eligible;
  - the reporting-window boundary decides eligibility (day 29 vs 30);
  - a legal/operational hold overrides age;
  - with the ratified flag off, nothing is eligible at all.
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa

from helpers import register_and_login
from ugence_dilchat.base import utcnow
from ugence_dilchat.domain.enums import RetentionState
from ugence_dilchat.infrastructure.chat_orm import ChatConversation, ChatMessage
from ugence_dilchat.infrastructure.chat_safety_orm import ChatConversationRetention
from ugence_dilchat.services.retention import PurgeBlocker, RetentionPurgeService


def _hdr(auth: dict) -> dict:
    return {"Authorization": auth["Authorization"]}


async def _paired_conversation(ctx) -> tuple[dict, dict, dict, str]:
    a = await register_and_login(ctx.client)
    b = await register_and_login(ctx.client)
    token = (await ctx.client.post("/v1/couples/invitations", headers=_hdr(a))).json()["token"]
    couple = (
        await ctx.client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    ).json()
    conv = (await ctx.client.get("/v1/conversations/current", headers=_hdr(a))).json()
    await ctx.client.post(
        f"/v1/conversations/{conv['conversation_id']}/messages",
        headers=_hdr(a),
        json={"client_message_id": f"m-{uuid.uuid4().hex[:8]}", "body": "hello"},
    )
    return a, b, couple, conv["conversation_id"]


async def _unpair(ctx, auth, couple_id) -> None:
    r = await ctx.client.post(f"/v1/couples/{couple_id}/unpair", headers=_hdr(auth))
    assert r.status_code in (200, 204), r.text


def _service(ctx, **overrides) -> RetentionPurgeService:
    settings = ctx.settings.model_copy(update=overrides) if overrides else ctx.settings
    return RetentionPurgeService(settings=settings, sessionmaker=ctx.sessionmaker)


async def _set_revoked_at(ctx, conversation_id: str, when: dt.datetime) -> None:
    async with ctx.sessionmaker() as s:
        await s.execute(
            sa.update(ChatConversation)
            .where(ChatConversation.id == uuid.UUID(conversation_id))
            .values(revoked_at=when)
        )
        await s.commit()


async def _place_hold(ctx, conversation_id: str, reason: str) -> None:
    async with ctx.sessionmaker() as s:
        await s.execute(
            sa.update(ChatConversationRetention)
            .where(ChatConversationRetention.conversation_id == uuid.UUID(conversation_id))
            .values(hold_reason=reason, hold_placed_at=utcnow())
        )
        await s.commit()


async def _counts(ctx) -> tuple[int, int, int]:
    async with ctx.sessionmaker() as s:
        return (
            await s.scalar(sa.select(sa.func.count()).select_from(ChatConversation)),
            await s.scalar(sa.select(sa.func.count()).select_from(ChatMessage)),
            await s.scalar(sa.select(sa.func.count()).select_from(ChatConversationRetention)),
        )


async def test_report_only_deletes_nothing_and_reports_the_ratified_shape(ctx):
    a, _b, couple, conv_id = await _paired_conversation(ctx)
    await _unpair(ctx, a, couple["couple_id"])
    await _set_revoked_at(ctx, conv_id, utcnow() - dt.timedelta(days=45))

    before = await _counts(ctx)
    report = await _service(ctx, retention_purge_enabled=True).report_only()
    after = await _counts(ctx)

    # THE core guarantee of this round: nothing was deleted.
    assert before == after
    assert report.as_dict()["deleted"] == 0
    assert report.as_dict()["mode"] == "REPORT_ONLY"
    assert report.retention_days == 30
    assert report.reporting_window_days == 30
    assert uuid.UUID(conv_id) in report.eligible_conversation_ids


async def test_with_the_ratified_flag_off_nothing_is_eligible(ctx):
    a, _b, couple, conv_id = await _paired_conversation(ctx)
    await _unpair(ctx, a, couple["couple_id"])
    await _set_revoked_at(ctx, conv_id, utcnow() - dt.timedelta(days=999))

    # ctx.settings carries the ratified default (false).
    assert ctx.settings.retention_purge_enabled is False
    report = await _service(ctx).report_only()
    assert report.eligible_count == 0
    assert report.blocked_counts.get(PurgeBlocker.PURGE_DISABLED.value) == 1


async def test_a_reported_conversation_is_preserved_and_never_eligible(ctx):
    a, b, couple, conv_id = await _paired_conversation(ctx)
    r = await ctx.client.post(
        "/v1/reports",
        headers=_hdr(b),
        json={
            "conversation_id": conv_id,
            "target_type": "CONVERSATION",
            "reason": "HARASSMENT",
            "client_report_id": f"r-{uuid.uuid4().hex[:10]}",
        },
    )
    assert r.status_code == 201, r.text
    await _unpair(ctx, a, couple["couple_id"])
    # Ancient revocation: only preservation can be keeping it out of the set.
    await _set_revoked_at(ctx, conv_id, utcnow() - dt.timedelta(days=3650))

    async with ctx.sessionmaker() as s:
        state = await s.scalar(
            sa.select(ChatConversationRetention.state).where(
                ChatConversationRetention.conversation_id == uuid.UUID(conv_id)
            )
        )
    assert state == RetentionState.PRESERVED_FOR_REPORT.value  # unpair never downgrades it

    report = await _service(ctx, retention_purge_enabled=True).report_only()
    assert report.eligible_count == 0
    assert report.blocked_counts.get(PurgeBlocker.PRESERVED_FOR_REPORT.value) == 1


async def test_reporting_window_boundary_decides_eligibility(ctx):
    a, _b, couple, conv_id = await _paired_conversation(ctx)
    await _unpair(ctx, a, couple["couple_id"])
    service = _service(ctx, retention_purge_enabled=True)

    # Day 29 — a former participant may still exercise the reporting right.
    await _set_revoked_at(ctx, conv_id, utcnow() - dt.timedelta(days=29))
    report = await service.report_only()
    assert report.eligible_count == 0
    assert report.blocked_counts.get(PurgeBlocker.WITHIN_RETENTION_WINDOW.value) == 1

    # Day 30 — the window has closed: eligible (still not deleted).
    await _set_revoked_at(ctx, conv_id, utcnow() - dt.timedelta(days=30, seconds=1))
    assert (await service.report_only()).eligible_count == 1

    # Day 31 — remains eligible.
    await _set_revoked_at(ctx, conv_id, utcnow() - dt.timedelta(days=31))
    assert (await service.report_only()).eligible_count == 1


async def test_a_hold_overrides_age(ctx):
    a, _b, couple, conv_id = await _paired_conversation(ctx)
    await _unpair(ctx, a, couple["couple_id"])
    await _set_revoked_at(ctx, conv_id, utcnow() - dt.timedelta(days=400))
    service = _service(ctx, retention_purge_enabled=True)
    assert (await service.report_only()).eligible_count == 1

    await _place_hold(ctx, conv_id, "LEGAL_HOLD")
    report = await service.report_only()
    assert report.eligible_count == 0
    assert report.blocked_counts.get(PurgeBlocker.LEGAL_HOLD.value) == 1


async def test_an_active_pairing_is_never_eligible(ctx):
    await _paired_conversation(ctx)
    report = await _service(ctx, retention_purge_enabled=True).report_only()
    assert report.eligible_count == 0
    assert report.blocked_counts.get(PurgeBlocker.NOT_REVOKED_STATE.value) == 1


async def test_report_output_is_content_free(ctx):
    a, _b, couple, conv_id = await _paired_conversation(ctx)
    await ctx.client.post(
        f"/v1/conversations/{conv_id}/messages",
        headers=_hdr(a),
        json={"client_message_id": "sentinel", "body": "SENTINEL_retention_body_4a1f"},
    )
    await _unpair(ctx, a, couple["couple_id"])
    await _set_revoked_at(ctx, conv_id, utcnow() - dt.timedelta(days=60))

    rendered = repr(
        (await _service(ctx, retention_purge_enabled=True).report_only()).as_dict()
    )
    assert "SENTINEL_retention_body_4a1f" not in rendered
    # Only ids, counts, and machine codes cross the boundary.
    for code in (await _service(ctx).report_only()).blocked_counts:
        assert code == code.upper() and " " not in code
