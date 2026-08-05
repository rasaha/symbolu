"""Secure chat authorization matrix (Phase 3A).

Every operation must flow: authenticated user -> authoritative ACTIVE membership ->
conversation owned by that relationship -> operation authorization. A conversation
id, message id, or client-supplied sender never establishes access.
"""

from __future__ import annotations

import uuid

from helpers import register_and_login


def _hdr(auth: dict) -> dict:
    return {"Authorization": auth["Authorization"]}


async def _pair(client):
    a = await register_and_login(client)
    b = await register_and_login(client)
    token = (await client.post("/v1/couples/invitations", headers=_hdr(a))).json()["token"]
    couple = (
        await client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    ).json()
    conv = (await client.get("/v1/conversations/current", headers=_hdr(a))).json()
    return a, b, couple, conv["conversation_id"]


async def _send(client, auth, conv, cid, body="hi"):
    return await client.post(
        f"/v1/conversations/{conv}/messages",
        headers=_hdr(auth),
        json={"client_message_id": cid, "body": body},
    )


async def _list(client, auth, conv):
    return await client.get(f"/v1/conversations/{conv}/messages", headers=_hdr(auth))


# --- stranger / other pair ------------------------------------------------- #
async def test_stranger_cannot_touch_conversation(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    stranger = await register_and_login(ctx.client)
    assert (await _list(ctx.client, stranger, conv)).status_code == 404
    assert (await _send(ctx.client, stranger, conv, "s1")).status_code == 404
    assert (
        await ctx.client.put(
            f"/v1/conversations/{conv}/read-state",
            headers=_hdr(stranger),
            json={"last_read_sequence": 0},
        )
    ).status_code == 404


async def test_user_in_another_pair_is_denied(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    c, d, couple2, conv2 = await _pair(ctx.client)
    # c (member of couple2) cannot read couple1's conversation.
    assert (await _list(ctx.client, c, conv)).status_code == 404
    assert (await _send(ctx.client, c, conv, "x1")).status_code == 404


async def test_forged_conversation_id_returns_404(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    fake = uuid.uuid4()
    assert (await _send(ctx.client, a, str(fake), "f1")).status_code == 404
    assert (await _list(ctx.client, a, str(fake))).status_code == 404


async def test_forged_message_id_and_cross_conversation_delete(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    c, d, couple2, conv2 = await _pair(ctx.client)
    mid2 = (await _send(ctx.client, c, conv2, "m1")).json()["message_id"]
    # a is a member of conv, but that message belongs to conv2 -> 404 via a's path.
    r = await ctx.client.delete(f"/v1/conversations/{conv}/messages/{mid2}", headers=_hdr(a))
    assert r.status_code == 404
    # a cannot reach conv2 at all (not a member) -> 404.
    r2 = await ctx.client.delete(f"/v1/conversations/{conv2}/messages/{mid2}", headers=_hdr(a))
    assert r2.status_code == 404


async def test_sender_identity_cannot_be_forged(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    resp = (await _send(ctx.client, a, conv, "s1", "hi")).json()
    me = ctx.app.state.token_service.verify_access_token(a["Authorization"].split()[1])["sub"]
    assert resp["sender_user_id"] == me  # server-derived, never client-supplied


async def test_cross_couple_cursor_fails_closed(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    c, d, couple2, conv2 = await _pair(ctx.client)
    for i in range(5):
        await _send(ctx.client, c, conv2, f"m{i}")
    page = (
        await ctx.client.get(f"/v1/conversations/{conv2}/messages?limit=2", headers=_hdr(c))
    ).json()
    cursor = page["next_cursor"]
    assert cursor
    # Present conv2's cursor against conv (a's conversation): rejected, no leakage.
    r = await ctx.client.get(
        f"/v1/conversations/{conv}/messages?cursor={cursor}", headers=_hdr(a)
    )
    assert r.status_code == 400
    assert r.json()["code"] == "INVALID_CURSOR"


# --- session / token lifecycle -------------------------------------------- #
async def test_unauthenticated_rejected(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    assert (await ctx.client.get(f"/v1/conversations/{conv}/messages")).status_code == 401


async def test_revoked_session_rejected_on_chat(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    await ctx.client.post("/v1/auth/logout", headers=_hdr(a))
    r = await ctx.client.get(f"/v1/conversations/{conv}/messages", headers=_hdr(a))
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_SESSION_REVOKED"


async def test_former_partner_after_unpair_denied(ctx):
    a, b, couple, conv = await _pair(ctx.client)
    await _send(ctx.client, a, conv, "m0")
    await ctx.client.post(f"/v1/couples/{couple['couple_id']}/unpair", headers=_hdr(a))
    # Access token still valid, but membership is revoked -> denied.
    assert (await _list(ctx.client, b, conv)).status_code == 403
    assert (await _send(ctx.client, b, conv, "late")).status_code == 403
