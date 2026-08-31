"""Phase 3C relay behaviour against the in-memory engine (invariants I1–I8).

The transport double records ONLY what the port can carry — token lists — so
these tests also prove content-freedom by construction (I7): no message id,
body, sender, or sequence can reach a transport through the interface.
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa

from helpers import register_and_login
from ugence_dilchat.base import utcnow
from ugence_dilchat.domain.enums import OutboxEventType
from ugence_dilchat.infrastructure.chat_orm import ChatOutbox
from ugence_dilchat.infrastructure.devices_orm import ChatDevice
from ugence_dilchat.relay import worker as relay_worker
from ugence_dilchat.relay.transports import TokenResult, TransportError
from ugence_dilchat.relay.worker import RelayService


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
    r = await client.post(
        f"/v1/conversations/{conv_id}/messages",
        headers=_hdr(auth),
        json={"client_message_id": cid, "body": body},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _register_device(client, auth, token: str) -> dict:
    r = await client.post(
        "/v1/devices", headers=_hdr(auth), json={"push_token": token, "platform": "ANDROID"}
    )
    assert r.status_code == 201, r.text
    return r.json()


class RecordingTransport:
    """Accepts everything; records exactly what crossed the port (tokens only)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.reject: set[str] = set()

    async def send_new_message(self, tokens: list[str]) -> list[TokenResult]:
        self.calls.append(list(tokens))
        return [
            TokenResult(token=t, accepted=t not in self.reject,
                        permanently_rejected=t in self.reject)
            for t in tokens
        ]


class FailingTransport:
    async def send_new_message(self, tokens: list[str]) -> list[TokenResult]:
        raise TransportError("TRANSPORT_UNAVAILABLE")


def _relay(ctx, transport) -> RelayService:
    return RelayService(settings=ctx.settings, sessionmaker=ctx.sessionmaker, transport=transport)


async def _outbox_rows(ctx) -> list[ChatOutbox]:
    async with ctx.sessionmaker() as s:
        return list((await s.execute(sa.select(ChatOutbox))).scalars().all())


async def test_all_event_types_drain_but_only_message_created_notifies(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    cid = conv["conversation_id"]
    await _register_device(ctx.client, b, "ExponentPushToken[recipient-b]")
    await _register_device(ctx.client, a, "ExponentPushToken[sender-a]")

    msg = await _send(ctx.client, a, cid, "m1", "hello")
    r = await ctx.client.put(
        f"/v1/conversations/{cid}/read-state", headers=_hdr(b), json={"last_read_sequence": 1}
    )
    assert r.status_code == 200
    r = await ctx.client.delete(
        f"/v1/conversations/{cid}/messages/{msg['message_id']}", headers=_hdr(a)
    )
    assert r.status_code == 200
    # A second couple whose unpair produces a CONVERSATION_REVOKED event.
    a2, _b2, couple2 = await _pair(ctx.client)
    r = await ctx.client.post(f"/v1/couples/{couple2['couple_id']}/unpair", headers=_hdr(a2))
    assert r.status_code in (200, 204)

    types = sorted(row.event_type for row in await _outbox_rows(ctx))
    assert types == sorted([
        OutboxEventType.CONVERSATION_CREATED.value,
        OutboxEventType.CONVERSATION_CREATED.value,
        OutboxEventType.MESSAGE_CREATED.value,
        OutboxEventType.READ_STATE_UPDATED.value,
        OutboxEventType.MESSAGE_DELETED.value,
        OutboxEventType.CONVERSATION_REVOKED.value,
    ])

    transport = RecordingTransport()
    published = await _relay(ctx, transport).process_batch()
    assert published == 6  # I3: every known event type drains

    rows = await _outbox_rows(ctx)
    assert all(row.published_at is not None for row in rows)
    # D3C-2: exactly ONE notification — for MESSAGE_CREATED, to the NON-SENDER
    # only — and the port carried nothing but that token (I7 by construction).
    assert transport.calls == [["ExponentPushToken[recipient-b]"]]


async def test_no_registered_device_still_drains_without_transport_call(ctx):
    a, _b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    await _send(ctx.client, a, conv["conversation_id"], "m1", "hello")
    transport = RecordingTransport()
    assert await _relay(ctx, transport).process_batch() >= 1
    assert transport.calls == []
    rows = await _outbox_rows(ctx)
    assert all(row.published_at is not None for row in rows)


async def test_unpaired_before_delivery_publishes_silently(ctx):
    a, _b, couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    await _send(ctx.client, a, conv["conversation_id"], "m1", "hello")
    r = await ctx.client.post(f"/v1/couples/{couple['couple_id']}/unpair", headers=_hdr(a))
    assert r.status_code in (200, 204)
    transport = RecordingTransport()
    await _relay(ctx, transport).process_batch()
    assert transport.calls == []  # silence after revocation; event still drained
    rows = await _outbox_rows(ctx)
    assert all(row.published_at is not None for row in rows)


async def test_transport_failure_parks_with_backoff_then_recovers(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    await _register_device(ctx.client, b, "ExponentPushToken[b]")
    await _send(ctx.client, a, conv["conversation_id"], "m1", "hello")

    await _relay(ctx, FailingTransport()).process_batch()
    async with ctx.sessionmaker() as s:
        row = (
            await s.execute(
                sa.select(ChatOutbox).where(
                    ChatOutbox.event_type == OutboxEventType.MESSAGE_CREATED.value
                )
            )
        ).scalar_one()
        assert row.published_at is None  # I2/I4: not silently published
        assert row.attempt_count == 1
        assert row.next_attempt_at is not None and row.next_attempt_at > utcnow()
        assert row.last_error_code == "TRANSPORT_UNAVAILABLE"
        row_id = row.id

    # Still inside backoff: the row is not reclaimed even by a healthy relay.
    healthy = RecordingTransport()
    await _relay(ctx, healthy).process_batch()
    assert healthy.calls == []

    # Backoff elapsed: the same committed outbox row (I1) delivers.
    async with ctx.sessionmaker() as s:
        row = await s.get(ChatOutbox, row_id)
        row.next_attempt_at = utcnow() - dt.timedelta(seconds=1)
        await s.commit()
    await _relay(ctx, healthy).process_batch()
    assert healthy.calls == [["ExponentPushToken[b]"]]
    async with ctx.sessionmaker() as s:
        row = await s.get(ChatOutbox, row_id)
        assert row.published_at is not None and row.last_error_code is None


async def test_unhandled_event_type_fails_closed(ctx, monkeypatch):
    a, _b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    await _send(ctx.client, a, conv["conversation_id"], "m1", "hello")
    # Simulate enum-version skew: this relay build no longer handles
    # READ_STATE_UPDATED-era rows... here, MESSAGE_CREATED itself.
    monkeypatch.setattr(
        relay_worker, "_HANDLED",
        frozenset({OutboxEventType.CONVERSATION_CREATED.value}),
    )
    transport = RecordingTransport()
    await _relay(ctx, transport).process_batch()
    async with ctx.sessionmaker() as s:
        row = (
            await s.execute(
                sa.select(ChatOutbox).where(
                    ChatOutbox.event_type == OutboxEventType.MESSAGE_CREATED.value
                )
            )
        ).scalar_one()
        assert row.published_at is None  # I4: never silently marked published
        assert row.attempt_count == 1
        assert row.last_error_code == "UNKNOWN_EVENT_TYPE"
    assert transport.calls == []


async def test_provider_rejection_deactivates_device_and_publishes(ctx):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    dead = "ExponentPushToken[dead]"
    device = await _register_device(ctx.client, b, dead)
    await _send(ctx.client, a, conv["conversation_id"], "m1", "hello")
    transport = RecordingTransport()
    transport.reject.add(dead)
    await _relay(ctx, transport).process_batch()
    async with ctx.sessionmaker() as s:
        row = await s.get(ChatDevice, uuid.UUID(device["device_id"]))
        assert row.status == "REVOKED"
        assert row.provider_rejected_at is not None
        out = (
            await s.execute(
                sa.select(ChatOutbox).where(
                    ChatOutbox.event_type == OutboxEventType.MESSAGE_CREATED.value
                )
            )
        ).scalar_one()
        assert out.published_at is not None  # the batch itself was accepted


async def test_pruning_removes_only_old_published_rows(ctx):
    a, _b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    await _send(ctx.client, a, conv["conversation_id"], "m1", "hello")
    old = utcnow() - dt.timedelta(days=ctx.settings.outbox_prune_after_days + 5)
    async with ctx.sessionmaker() as s:
        rows = list((await s.execute(sa.select(ChatOutbox))).scalars().all())
        assert len(rows) >= 2
        # One published long ago, one published recently, one old but UNPUBLISHED.
        rows[0].published_at = old
        rows[1].published_at = utcnow()
        s.add(
            ChatOutbox(
                event_type=OutboxEventType.MESSAGE_CREATED.value,
                conversation_id=rows[1].conversation_id,
                couple_id=rows[1].couple_id,
                payload={"conversation_id": str(rows[1].conversation_id)},
                created_at=old,
            )
        )
        await s.commit()
        before = len(list((await s.execute(sa.select(ChatOutbox))).scalars().all()))

    pruned = await _relay(ctx, RecordingTransport()).prune_published()
    assert pruned == 1  # exactly the old PUBLISHED row
    async with ctx.sessionmaker() as s:
        remaining = list((await s.execute(sa.select(ChatOutbox))).scalars().all())
        assert len(remaining) == before - 1
        # I8: the old-but-unpublished row survived.
        assert any(r.published_at is None and r.created_at <= old for r in remaining)


class LeakyTransport:
    """A misbehaving transport whose failure text carries free text and a token.

    Round PR-A telemetry hardening: even such a transport must not get free
    text or token material into ``last_error_code`` (stored AND logged) — the
    relay clamps anything that is not a machine-style code.
    """

    async def send_new_message(self, tokens: list[str]) -> list[TokenResult]:
        raise TransportError(
            "provider said: upstream 502 for ExponentPushToken[SENTINEL_leaky_token_9d2c]"
        )


async def test_misbehaving_transport_error_text_never_reaches_row_or_logs(ctx, caplog, capfd):
    a, b, _couple = await _pair(ctx.client)
    conv = await _conversation(ctx.client, a)
    await _register_device(ctx.client, b, "ExponentPushToken[SENTINEL_leaky_token_9d2c]")
    await _send(ctx.client, a, conv["conversation_id"], "m1", "SENTINEL_leaky_body_9d2c")

    with caplog.at_level("DEBUG", logger="ugence_dilchat.relay"):
        await _relay(ctx, LeakyTransport()).process_batch()

    rows = await _outbox_rows(ctx)
    parked = [r for r in rows if r.last_error_code is not None]
    assert parked, "the MESSAGE_CREATED event should have parked"
    for row in parked:
        # Clamped to a machine code — the free text was discarded, not truncated.
        assert row.last_error_code == "TRANSPORT_UNAVAILABLE"

    captured = capfd.readouterr()
    for stream in (caplog.text, captured.out, captured.err):
        assert "SENTINEL_leaky_token_9d2c" not in stream
        assert "SENTINEL_leaky_body_9d2c" not in stream
        assert "provider said" not in stream
