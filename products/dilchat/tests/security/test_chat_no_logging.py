"""Message content must never reach logs, outbox payloads, or audit rows (Phase 3A).

A synthetic sentinel body is sent (success path) and rejected (error path); the
captured process output must not contain it, and neither may any transactional
outbox payload or audit record. The message body lives only in the sanctioned
``chat_messages.body`` column.
"""

from __future__ import annotations

import json

import sqlalchemy as sa

from helpers import register_and_login
from ugence_dilchat.infrastructure.chat_orm import ChatMessage, ChatOutbox
from ugence_dilchat.infrastructure.orm import AuditEvent
from ugence_dilchat.logging import _redact

_SENTINEL = "SENTINEL_dilchat_secret_body_7f3a91"


def _hdr(auth: dict) -> dict:
    return {"Authorization": auth["Authorization"]}


async def _pair_conv(client):
    a = await register_and_login(client)
    b = await register_and_login(client)
    token = (await client.post("/v1/couples/invitations", headers=_hdr(a))).json()["token"]
    await client.post(f"/v1/couples/invitations/{token}/accept", headers=_hdr(b))
    conv = (await client.get("/v1/conversations/current", headers=_hdr(a))).json()
    return a, conv["conversation_id"]


async def test_message_body_never_appears_in_logs(ctx, capfd):
    a, conv = await _pair_conv(ctx.client)
    # Success path.
    ok = await ctx.client.post(
        f"/v1/conversations/{conv}/messages",
        headers=_hdr(a),
        json={"client_message_id": "s1", "body": _SENTINEL},
    )
    assert ok.status_code == 201
    # Error paths (oversized + bad control char) also carry the sentinel.
    await ctx.client.post(
        f"/v1/conversations/{conv}/messages",
        headers=_hdr(a),
        json={"client_message_id": "s2", "body": _SENTINEL + "\x00"},
    )
    out, err = capfd.readouterr()
    assert _SENTINEL not in out
    assert _SENTINEL not in err


async def test_body_absent_from_outbox_and_audit_present_only_in_message(ctx):
    a, conv = await _pair_conv(ctx.client)
    await ctx.client.post(
        f"/v1/conversations/{conv}/messages",
        headers=_hdr(a),
        json={"client_message_id": "s1", "body": _SENTINEL},
    )
    async with ctx.sessionmaker() as s:
        outbox = (await s.execute(sa.select(ChatOutbox.payload))).scalars().all()
        audits = (await s.execute(sa.select(AuditEvent.provenance))).scalars().all()
        bodies = (await s.execute(sa.select(ChatMessage.body))).scalars().all()

    for payload in outbox:
        assert _SENTINEL not in json.dumps(payload)
    for prov in audits:
        assert _SENTINEL not in json.dumps(prov or {})
    # The body IS stored, exactly once, in the sanctioned column.
    assert _SENTINEL in bodies


def test_redaction_net_covers_message_content_keys():
    out = _redact(None, "info", {"content": _SENTINEL, "note": _SENTINEL, "body_preview": "x"})
    assert out["content"] == "[REDACTED]"
    assert out["note"] == "[REDACTED]"
