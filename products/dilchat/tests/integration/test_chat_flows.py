"""Secure chat API behaviour (Phase 3A) against the in-memory engine.

Covers conversation provisioning at pairing, message send + idempotency, cursor
pagination, tombstone deletion, read-state, unpair revocation, and transactional
outbox consistency (event rows written in the same transaction, never a body).
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from helpers import register_and_login
from ugence_dilchat.domain.enums import OutboxEventType
from ugence_dilchat.infrastructure.chat_orm import ChatOutbox


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


async def _outbox_counts(ctx) -> dict[str, int]:
    async with ctx.sessionmaker() as s:
        rows = (await s.execute(sa.select(ChatOutbox.event_type))).scalars().all()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r] = counts.get(r, 0) + 1
    return counts


# --- provisioning ---------------------------------------------------------- #
async def test_pairing_creates_one_active_conversation_and_outbox_event(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    assert conv["status"] == "ACTIVE"
    assert conv["couple_id"] == couple["couple_id"]
    assert conv["latest_sequence"] == 0
    assert set(conv["member_user_ids"])  # two members
    assert len(conv["member_user_ids"]) == 2
    # Both partners resolve the SAME conversation.
    conv_b = await _conversation(ctx.client, b)
    assert conv_b["conversation_id"] == conv["conversation_id"]
    counts = await _outbox_counts(ctx)
    assert counts.get(OutboxEventType.CONVERSATION_CREATED.value) == 1


async def test_unpaired_user_has_no_current_conversation(ctx):
    auth = await register_and_login(ctx.client)
    r = await ctx.client.get("/v1/conversations/current", headers=_hdr(auth))
    assert r.status_code == 404


# --- send + idempotency ---------------------------------------------------- #
async def test_send_assigns_monotonic_sequence(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    r1 = await _send(ctx.client, a, conv, "a1", "one")
    r2 = await _send(ctx.client, b, conv, "b1", "two")
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["server_sequence"] == 1
    assert r2.json()["server_sequence"] == 2
    assert r1.json()["body"] == "one"


async def test_idempotent_replay_returns_same_message(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    r1 = await _send(ctx.client, a, conv, "k1", "hello")
    r2 = await _send(ctx.client, a, conv, "k1", "hello")
    assert r1.json()["message_id"] == r2.json()["message_id"]
    assert r1.json()["server_sequence"] == r2.json()["server_sequence"]
    # Exactly one MESSAGE_CREATED outbox event for the idempotent pair.
    counts = await _outbox_counts(ctx)
    assert counts.get(OutboxEventType.MESSAGE_CREATED.value) == 1


async def test_same_key_different_body_conflicts(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    await _send(ctx.client, a, conv, "k1", "hello")
    r = await _send(ctx.client, a, conv, "k1", "changed")
    assert r.status_code == 409
    assert r.json()["code"] == "IDEMPOTENCY_CONFLICT"


async def test_empty_whitespace_and_control_bodies_rejected(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    assert (await _send(ctx.client, a, conv, "e1", "   ")).status_code == 422
    assert (await _send(ctx.client, a, conv, "e2", "bad\x00nul")).status_code == 422
    assert (await _send(ctx.client, a, conv, "e3", "bell\x07")).status_code == 422
    # Newlines/tabs are allowed.
    assert (await _send(ctx.client, a, conv, "ok", "line1\nline2\t!")).status_code == 201


async def test_oversized_body_rejected(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    r = await _send(ctx.client, a, conv, "big", "z" * 4001)
    assert r.status_code == 422


async def test_missing_client_message_id_rejected(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    r = await ctx.client.post(
        f"/v1/conversations/{conv}/messages", headers=_hdr(a), json={"body": "hi"}
    )
    assert r.status_code == 422


# --- pagination ------------------------------------------------------------ #
async def test_cursor_pagination_is_stable_and_bounded(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    for i in range(10):
        assert (await _send(ctx.client, a, conv, f"m{i}", f"msg {i}")).status_code == 201

    seen: list[int] = []
    cursor = None
    pages = 0
    while True:
        url = f"/v1/conversations/{conv}/messages?limit=3"
        if cursor:
            url += f"&cursor={cursor}"
        page = (await ctx.client.get(url, headers=_hdr(a))).json()
        seen.extend(m["server_sequence"] for m in page["messages"])
        pages += 1
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    assert seen == list(range(1, 11))  # every message once, in order
    assert pages == 4


async def test_page_size_maximum_enforced(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    r = await ctx.client.get(
        f"/v1/conversations/{conv}/messages?limit=999", headers=_hdr(a)
    )
    assert r.status_code == 422  # exceeds le=100 bound at the schema layer


async def test_malformed_cursor_returns_400(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    r = await ctx.client.get(
        f"/v1/conversations/{conv}/messages?cursor=not-a-cursor", headers=_hdr(a)
    )
    assert r.status_code == 400
    assert r.json()["code"] == "INVALID_CURSOR"


# --- deletion (tombstone) -------------------------------------------------- #
async def test_delete_is_tombstone_and_hides_body(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    mid = (await _send(ctx.client, a, conv, "d1", "secret text")).json()["message_id"]
    r = await ctx.client.delete(f"/v1/conversations/{conv}/messages/{mid}", headers=_hdr(a))
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert r.json()["body"] is None
    # It still appears in listings as a tombstone (metadata retained, no body).
    page = (await ctx.client.get(f"/v1/conversations/{conv}/messages", headers=_hdr(a))).json()
    tomb = [m for m in page["messages"] if m["message_id"] == mid][0]
    assert tomb["deleted"] is True and tomb["body"] is None
    assert tomb["server_sequence"] == 1


async def test_repeat_delete_is_idempotent_single_event(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    mid = (await _send(ctx.client, a, conv, "d1", "x")).json()["message_id"]
    await ctx.client.delete(f"/v1/conversations/{conv}/messages/{mid}", headers=_hdr(a))
    await ctx.client.delete(f"/v1/conversations/{conv}/messages/{mid}", headers=_hdr(a))
    counts = await _outbox_counts(ctx)
    assert counts.get(OutboxEventType.MESSAGE_DELETED.value) == 1


async def test_only_sender_may_delete(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    mid = (await _send(ctx.client, a, conv, "d1", "x")).json()["message_id"]
    r = await ctx.client.delete(f"/v1/conversations/{conv}/messages/{mid}", headers=_hdr(b))
    assert r.status_code == 403


async def test_delete_unknown_message_404(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    r = await ctx.client.delete(
        f"/v1/conversations/{conv}/messages/{uuid.uuid4()}", headers=_hdr(a)
    )
    assert r.status_code == 404


# --- read state ------------------------------------------------------------ #
async def test_read_state_forward_only_and_idempotent(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    for i in range(3):
        await _send(ctx.client, a, conv, f"m{i}", "x")

    async def put(seq):
        return await ctx.client.put(
            f"/v1/conversations/{conv}/read-state",
            headers=_hdr(b),
            json={"last_read_sequence": seq},
        )

    assert (await put(2)).json()["last_read_sequence"] == 2
    # Backward move is a no-op (stays at 2) and emits no event.
    assert (await put(1)).json()["last_read_sequence"] == 2
    before = (await _outbox_counts(ctx)).get(OutboxEventType.READ_STATE_UPDATED.value, 0)
    await put(2)  # repeat identical: no event
    after = (await _outbox_counts(ctx)).get(OutboxEventType.READ_STATE_UPDATED.value, 0)
    assert before == after


async def test_read_state_cannot_exceed_latest(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    await _send(ctx.client, a, conv, "m0", "x")
    r = await ctx.client.put(
        f"/v1/conversations/{conv}/read-state",
        headers=_hdr(b),
        json={"last_read_sequence": 5},
    )
    assert r.status_code == 422


# --- unpair revocation ----------------------------------------------------- #
async def test_unpair_revokes_conversation_and_blocks_everything(ctx):
    a, b, couple = await _pair(ctx.client)
    conv = (await _conversation(ctx.client, a))["conversation_id"]
    await _send(ctx.client, a, conv, "m0", "x")
    assert (
        await ctx.client.post(f"/v1/couples/{couple['couple_id']}/unpair", headers=_hdr(a))
    ).status_code == 204

    # New messages, listing, read-state all rejected for the former partner.
    assert (await _send(ctx.client, a, conv, "late", "nope")).status_code == 403
    assert (
        await ctx.client.get(f"/v1/conversations/{conv}/messages", headers=_hdr(a))
    ).status_code == 403
    assert (
        await ctx.client.put(
            f"/v1/conversations/{conv}/read-state",
            headers=_hdr(a),
            json={"last_read_sequence": 1},
        )
    ).status_code == 403
    counts = await _outbox_counts(ctx)
    assert counts.get(OutboxEventType.CONVERSATION_REVOKED.value) == 1


async def test_repair_creates_a_new_distinct_conversation(ctx):
    a, b, couple = await _pair(ctx.client)
    conv1 = (await _conversation(ctx.client, a))["conversation_id"]
    await ctx.client.post(f"/v1/couples/{couple['couple_id']}/unpair", headers=_hdr(a))
    # Same two people pair again -> new couple -> new conversation.
    token = (await ctx.client.post("/v1/couples/invitations", headers=_hdr(a))).json()["token"]
    await ctx.client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    conv2 = (await _conversation(ctx.client, a))["conversation_id"]
    assert conv2 != conv1
