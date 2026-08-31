"""Phase 3B safety API behaviour (blocks, reports, rate limits, retention).

Ratified semantics under test (DILCHAT-D3B-1..5): a block denies sends in BOTH
directions with one identical generic error and never unpairs; reports are
durable, idempotent, stay SUBMITTED, and never echo evidence or internal case
state; rate limits enforce the schema defaults through the canonical
RATE_LIMITED contract without weakening authorization; retention transitions
are explicit and PRESERVED_FOR_REPORT is never downgraded.
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa

from helpers import register_and_login
from ugence_dilchat.base import utcnow
from ugence_dilchat.infrastructure.chat_orm import ChatConversation
from ugence_dilchat.infrastructure.chat_safety_orm import (
    ChatConversationRetention,
    ChatRateLimit,
    ChatReport,
    ChatReportEvidence,
    ChatSafetyCase,
    ChatSafetyCaseEvent,
)
from ugence_dilchat.infrastructure.orm import AuditEvent


def _hdr(auth: dict) -> dict:
    return {"Authorization": auth["Authorization"]}


async def _pair(client) -> tuple[dict, dict, dict]:
    a = await register_and_login(client)
    b = await register_and_login(client)
    token = (await client.post("/v1/couples/invitations", headers=_hdr(a))).json()["token"]
    couple = (
        await client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    ).json()
    return a, b, couple


async def _me_id(client, auth) -> str:
    return (await client.get("/v1/users/me", headers=_hdr(auth))).json()["id"]


async def _conversation(client, auth) -> dict:
    r = await client.get("/v1/conversations/current", headers=_hdr(auth))
    assert r.status_code == 200, r.text
    return r.json()


async def _send(client, auth, conv_id, cid, body):
    return await client.post(
        f"/v1/conversations/{conv_id}/messages",
        headers=_hdr(auth),
        json={"client_message_id": cid, "body": body},
    )


async def _block(client, auth, blocked_user_id) -> dict:
    r = await client.post(
        "/v1/blocks", headers=_hdr(auth), json={"blocked_user_id": blocked_user_id}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _report_payload(conv_id: str, **over) -> dict:
    payload = {
        "conversation_id": conv_id,
        "target_type": "CONVERSATION",
        "reason": "HARASSMENT",
        "client_report_id": f"r-{uuid.uuid4().hex[:10]}",
    }
    payload.update(over)
    return payload


async def _seed_rate_limit(ctx, user_id: str, action_key: str, window_seconds: int, count: int):
    """Pre-fill the current AND next fixed windows so a boundary roll during the
    test cannot un-trip the limit (deterministic, no sleeping)."""
    epoch = int(utcnow().timestamp())
    start = epoch - (epoch % window_seconds)
    async with ctx.sessionmaker() as s:
        for window_epoch in (start, start + window_seconds):
            s.add(
                ChatRateLimit(
                    subject_user_id=uuid.UUID(user_id),
                    action_key=action_key,
                    window_start=dt.datetime.fromtimestamp(window_epoch, tz=dt.UTC),
                    window_seconds=window_seconds,
                    count=count,
                )
            )
        await s.commit()


# --- blocks ----------------------------------------------------------------- #
async def test_block_denies_sends_both_directions_with_identical_generic_error(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    b_id = await _me_id(ctx.client, b)
    assert (await _send(ctx.client, a, conv["conversation_id"], "k0", "before")).status_code == 201

    block = await _block(ctx.client, a, b_id)
    assert block["status"] == "ACTIVE"

    denied_blocker = await _send(ctx.client, a, conv["conversation_id"], "k1", "from blocker")
    denied_blocked = await _send(ctx.client, b, conv["conversation_id"], "k2", "from blocked")
    assert denied_blocker.status_code == 403
    assert denied_blocked.status_code == 403
    # One identical, non-disclosing error for both directions: nothing in the
    # surface says who blocked whom (only correlation ids may differ).
    pa, pb = denied_blocker.json(), denied_blocked.json()
    for key in ("status", "code", "title", "detail"):
        assert pa[key] == pb[key]
    assert "block" not in (pa["detail"] or "").lower()

    # Revoking restores messaging for both.
    r = await ctx.client.post(f"/v1/blocks/{block['block_id']}/revoke", headers=_hdr(a))
    assert r.status_code == 200 and r.json()["status"] == "REVOKED"
    assert (await _send(ctx.client, a, conv["conversation_id"], "k3", "again")).status_code == 201
    assert (await _send(ctx.client, b, conv["conversation_id"], "k4", "again")).status_code == 201


async def test_block_replay_of_committed_send_still_returns_original(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    first = await _send(ctx.client, a, conv["conversation_id"], "kr", "committed")
    assert first.status_code == 201
    await _block(ctx.client, a, await _me_id(ctx.client, b))
    # A timeout-retry of an ALREADY-COMMITTED message must keep returning that
    # message (idempotent replay) even though new sends are now denied.
    replay = await _send(ctx.client, a, conv["conversation_id"], "kr", "committed")
    assert replay.status_code == 201
    assert replay.json()["message_id"] == first.json()["message_id"]


async def test_block_is_idempotent_scoped_to_partner_and_never_unpairs(ctx):
    a, b, couple = await _pair(ctx.client)
    b_id = await _me_id(ctx.client, b)
    first = await _block(ctx.client, a, b_id)
    again = await _block(ctx.client, a, b_id)  # re-block: same row, no error
    assert again["block_id"] == first["block_id"]

    # Blocking anyone who is not the current partner is 404 (no enumeration).
    r = await ctx.client.post(
        "/v1/blocks", headers=_hdr(a), json={"blocked_user_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404
    # Blocking yourself is a validation error.
    a_id = await _me_id(ctx.client, a)
    r = await ctx.client.post("/v1/blocks", headers=_hdr(a), json={"blocked_user_id": a_id})
    assert r.status_code == 422
    # An unpaired user has no partner to block.
    c = await register_and_login(ctx.client)
    r = await ctx.client.post("/v1/blocks", headers=_hdr(c), json={"blocked_user_id": b_id})
    assert r.status_code == 404

    # D3B-2: the block did NOT change pairing state.
    r = await ctx.client.get("/v1/couples/current", headers=_hdr(a))
    assert r.status_code == 200 and r.json()["couple_id"] == couple["couple_id"]
    assert r.json()["status"] == "ACTIVE"


async def test_block_surface_is_blocker_only(ctx):
    a, b, _couple = await _pair(ctx.client)
    block = await _block(ctx.client, a, await _me_id(ctx.client, b))
    # The blocked user's own list shows nothing, and they cannot address the
    # block by id (404, not 403 — no existence disclosure).
    r = await ctx.client.get("/v1/blocks", headers=_hdr(b))
    assert r.status_code == 200 and r.json()["blocks"] == []
    r = await ctx.client.post(f"/v1/blocks/{block['block_id']}/revoke", headers=_hdr(b))
    assert r.status_code == 404
    # The blocker sees exactly their block; revoke is idempotent.
    r = await ctx.client.get("/v1/blocks", headers=_hdr(a))
    assert [x["block_id"] for x in r.json()["blocks"]] == [block["block_id"]]
    for _ in range(2):
        r = await ctx.client.post(f"/v1/blocks/{block['block_id']}/revoke", headers=_hdr(a))
        assert r.status_code == 200 and r.json()["status"] == "REVOKED"


# --- reports ---------------------------------------------------------------- #
async def test_report_creates_case_evidence_retention_and_stays_submitted(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    cid = conv["conversation_id"]
    m1 = (await _send(ctx.client, a, cid, "m1", "first")).json()
    m2 = (await _send(ctx.client, a, cid, "m2", "second — will be deleted")).json()
    await _send(ctx.client, b, cid, "m3", "third")
    # Tombstone m2 so its evidence snapshot must be empty, never reconstructed.
    r = await ctx.client.delete(
        f"/v1/conversations/{cid}/messages/{m2['message_id']}", headers=_hdr(a)
    )
    assert r.status_code == 200

    payload = _report_payload(
        cid,
        target_type="MESSAGE",
        target_message_id=m1["message_id"],
        description="secret-report-description",
    )
    r = await ctx.client.post("/v1/reports", headers=_hdr(b), json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "SUBMITTED"
    assert body["target_message_id"] == m1["message_id"]
    # D3B-5: no internal state and no sensitive echo in the response.
    for absent in ("case_id", "description", "evidence"):
        assert absent not in body

    async with ctx.sessionmaker() as s:
        report = (await s.execute(sa.select(ChatReport))).scalar_one()
        case = (await s.execute(sa.select(ChatSafetyCase))).scalar_one()
        assert case.state == "OPEN" and report.case_id == case.id
        evidence = (
            (await s.execute(
                sa.select(ChatReportEvidence).order_by(ChatReportEvidence.evidence_sequence)
            )).scalars().all()
        )
        assert len(evidence) == 3  # all three messages are inside the window
        by_msg = {e.source_message_id: e for e in evidence}
        assert by_msg[uuid.UUID(m1["message_id"])].body_snapshot == "first"
        assert by_msg[uuid.UUID(m2["message_id"])].body_snapshot == ""  # tombstone
        assert all(len(e.integrity_sha256) == 64 for e in evidence)
        events = (await s.execute(sa.select(ChatSafetyCaseEvent))).scalars().all()
        kinds = sorted(e.event_type for e in events)
        assert kinds == ["CASE_OPENED", "EVIDENCE_PRESERVED", "REPORT_LINKED"]
        retention = (
            (await s.execute(
                sa.select(ChatConversationRetention).where(
                    ChatConversationRetention.conversation_id == uuid.UUID(cid)
                )
            )).scalar_one()
        )
        assert retention.state == "PRESERVED_FOR_REPORT"
        # The SENSITIVE description exists on the report row ONLY — never in
        # evidence meta, case events, or audit rows.
        assert report.description == "secret-report-description"
        audits = (await s.execute(sa.select(AuditEvent))).scalars().all()
        assert any(x.action == "CHAT_REPORT_CREATED" for x in audits)
        assert any(x.action == "SAFETY_CASE_OPENED" for x in audits)
        for x in audits:
            assert "secret-report-description" not in str(x.__dict__)


async def test_report_is_idempotent_and_conflicts_on_key_reuse(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    await _send(ctx.client, a, conv["conversation_id"], "m1", "hello")
    payload = _report_payload(conv["conversation_id"], client_report_id="fixed-key")
    first = await ctx.client.post("/v1/reports", headers=_hdr(b), json=payload)
    replay = await ctx.client.post("/v1/reports", headers=_hdr(b), json=payload)
    assert first.status_code == 201 and replay.status_code == 201
    assert replay.json()["report_id"] == first.json()["report_id"]
    async with ctx.sessionmaker() as s:
        cases = await s.execute(sa.select(sa.func.count()).select_from(ChatSafetyCase))
        assert cases.scalar_one() == 1

    conflicting = dict(payload, reason="SPAM")
    r = await ctx.client.post("/v1/reports", headers=_hdr(b), json=conflicting)
    assert r.status_code == 409
    assert r.json()["code"] == "IDEMPOTENCY_CONFLICT"


async def test_report_validation_and_stranger_denial(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    cid = conv["conversation_id"]
    msg = (await _send(ctx.client, a, cid, "m1", "hello")).json()

    cases = [
        _report_payload(cid, reason="NOT_A_REASON"),
        _report_payload(cid, target_type="MESSAGE"),  # missing target_message_id
        _report_payload(cid, target_message_id=msg["message_id"]),  # CONVERSATION + target
        _report_payload(cid, description="x" * 1001),
        _report_payload(cid, client_report_id="bad key with spaces!"),
    ]
    for payload in cases:
        r = await ctx.client.post("/v1/reports", headers=_hdr(b), json=payload)
        assert r.status_code == 422, (payload, r.text)

    # A MESSAGE report must target a message of THIS conversation.
    r = await ctx.client.post(
        "/v1/reports",
        headers=_hdr(b),
        json=_report_payload(cid, target_type="MESSAGE", target_message_id=str(uuid.uuid4())),
    )
    assert r.status_code == 404

    # A stranger addressing the conversation gets 404 — no existence disclosure.
    c = await register_and_login(ctx.client)
    r = await ctx.client.post("/v1/reports", headers=_hdr(c), json=_report_payload(cid))
    assert r.status_code == 404
    # And sees no reports of others.
    r = await ctx.client.get("/v1/reports", headers=_hdr(c))
    assert r.status_code == 200 and r.json()["reports"] == []


async def test_former_member_reports_within_window_without_evidence(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    cid = conv["conversation_id"]
    msg = (await _send(ctx.client, a, cid, "m1", "hello")).json()
    r = await ctx.client.post(f"/v1/couples/{couple['couple_id']}/unpair", headers=_hdr(b))
    assert r.status_code in (200, 204)

    # Inside the 30-day window: a CONVERSATION report succeeds with NO evidence
    # (message access is revoked and reporting does not resurrect it)...
    r = await ctx.client.post("/v1/reports", headers=_hdr(b), json=_report_payload(cid))
    assert r.status_code == 201, r.text
    async with ctx.sessionmaker() as s:
        count = (
            await s.execute(sa.select(sa.func.count()).select_from(ChatReportEvidence))
        ).scalar_one()
        assert count == 0
    # ...but a MESSAGE-target report is rejected.
    r = await ctx.client.post(
        "/v1/reports",
        headers=_hdr(b),
        json=_report_payload(cid, target_type="MESSAGE", target_message_id=msg["message_id"]),
    )
    assert r.status_code == 422

    # Outside the window: denied (403, matching former-member authz posture).
    async with ctx.sessionmaker() as s:
        conv_row = await s.get(ChatConversation, uuid.UUID(cid))
        conv_row.revoked_at = utcnow() - dt.timedelta(days=31)
        await s.commit()
    r = await ctx.client.post(
        "/v1/reports", headers=_hdr(b), json=_report_payload(cid, client_report_id="late-key")
    )
    assert r.status_code == 403


# --- retention -------------------------------------------------------------- #
async def test_retention_lifecycle_and_preserved_is_never_downgraded(ctx):
    # Pairing provisions an ACTIVE retention row alongside the conversation.
    a, b, couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    cid = uuid.UUID(conv["conversation_id"])
    async with ctx.sessionmaker() as s:
        row = (
            await s.execute(
                sa.select(ChatConversationRetention).where(
                    ChatConversationRetention.conversation_id == cid
                )
            )
        ).scalar_one()
        assert row.state == "ACTIVE"

    # A report preserves; a later unpair must NOT downgrade the preserved state.
    await _send(ctx.client, a, str(cid), "m1", "hello")
    r = await ctx.client.post("/v1/reports", headers=_hdr(b), json=_report_payload(str(cid)))
    assert r.status_code == 201
    r = await ctx.client.post(f"/v1/couples/{couple['couple_id']}/unpair", headers=_hdr(a))
    assert r.status_code in (200, 204)
    async with ctx.sessionmaker() as s:
        row = (
            await s.execute(
                sa.select(ChatConversationRetention).where(
                    ChatConversationRetention.conversation_id == cid
                )
            )
        ).scalar_one()
        assert row.state == "PRESERVED_FOR_REPORT"

    # An unreported conversation transitions to REVOKED_PENDING_POLICY.
    a2, b2, couple2 = await _pair(ctx.client)
    conv2 = await _conversation(ctx.client, a2)
    r = await ctx.client.post(f"/v1/couples/{couple2['couple_id']}/unpair", headers=_hdr(a2))
    assert r.status_code in (200, 204)
    async with ctx.sessionmaker() as s:
        row = (
            await s.execute(
                sa.select(ChatConversationRetention).where(
                    ChatConversationRetention.conversation_id
                    == uuid.UUID(conv2["conversation_id"])
                )
            )
        ).scalar_one()
        assert row.state == "REVOKED_PENDING_POLICY"


# --- rate limits ------------------------------------------------------------ #
async def test_send_rate_limit_enforced_via_canonical_contract(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    a_id = await _me_id(ctx.client, a)
    # Trip the HOURLY window deterministically (current + next window seeded to
    # the configured limit — enforcement is proven independently of the value;
    # the ratified defaults themselves are pinned in test_ratified_rate_limits).
    await _seed_rate_limit(ctx, a_id, "send", 3600, ctx.settings.ratelimit_send_per_hour)
    r = await _send(ctx.client, a, conv["conversation_id"], "k1", "limited")
    assert r.status_code == 429
    assert r.json()["code"] == "RATE_LIMITED"
    # The limit is per subject: the partner can still send.
    assert (await _send(ctx.client, b, conv["conversation_id"], "k2", "fine")).status_code == 201


async def test_report_and_block_rate_limits(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    b_id = await _me_id(ctx.client, b)
    a_id = await _me_id(ctx.client, a)

    await _seed_rate_limit(ctx, b_id, "report", 86400, ctx.settings.ratelimit_report_per_day)
    r = await ctx.client.post(
        "/v1/reports", headers=_hdr(b), json=_report_payload(conv["conversation_id"])
    )
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"

    await _seed_rate_limit(
        ctx, a_id, "block_mut", 3600, ctx.settings.ratelimit_block_mutations_per_hour
    )
    r = await ctx.client.post("/v1/blocks", headers=_hdr(a), json={"blocked_user_id": b_id})
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"

    # A 429 never substitutes for authorization: a stranger's unauthorized
    # report attempt is still 404 even when their own budget is exhausted.
    c = await register_and_login(ctx.client)
    c_id = await _me_id(ctx.client, c)
    await _seed_rate_limit(ctx, c_id, "report", 86400, ctx.settings.ratelimit_report_per_day)
    r = await ctx.client.post(
        "/v1/reports", headers=_hdr(c), json=_report_payload(conv["conversation_id"])
    )
    assert r.status_code == 404
