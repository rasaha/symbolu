"""Outbox relay (Phase 3C): claims committed outbox work and delivers pushes.

Ratified invariants implemented here:

- I1: delivery work originates ONLY from durably committed outbox rows.
- I2: at-least-once — a crash after transport acceptance but before commit
  redelivers; duplicate pushes are permitted and exactly-once is not claimed.
- I3: ALL five known event types are consumed and marked published, even though
  only MESSAGE_CREATED produces a push (D3C-2).
- I4: an unknown event type is never silently marked published — it is parked
  with a content-free error code and bounded retries.
- I6: only the worker posture claims/publishes (RLS-enforced); each event that
  needs member resolution sets the transaction context to the SENDER from the
  payload, mirroring the scope-revalidation worker pattern — the relay never
  widens read access beyond what that member context plus the worker device
  policies grant.
- I7: logs and error codes are machine codes and row ids only — never a body
  (the outbox cannot carry one), never a token.
- I8: pruning removes PUBLISHED rows only (also DB-enforced by the worker's
  DELETE policy) and only past the ratified retention window.

Concurrency: multiple relay processes may run concurrently without publishing
the same claimed row under normal processing. On PostgreSQL that is realised
with row locks that skip already-claimed rows; the product decision is the
invariant, not the SQL mechanism.

``published_at`` means: handed to the configured external transport according
to its acknowledgement contract. It never means received or read (I5).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..base import utcnow
from ..config import Settings
from ..db import set_transaction_context
from ..domain.enums import DeviceStatus, MembershipStatus, OutboxEventType
from ..infrastructure.chat_orm import ChatOutbox
from ..repositories.couples import MembershipRepository
from ..repositories.devices import DeviceRepository
from .transports import DeliveryTransport, TransportError

log = logging.getLogger("ugence_dilchat.relay")

# Event types this relay build knows how to drain. A row whose type is not
# here fails closed (I4) — it is parked, never published.
_HANDLED: frozenset[str] = frozenset(e.value for e in OutboxEventType)
# The only event type that produces a user notification (D3C-2).
_NOTIFYING = OutboxEventType.MESSAGE_CREATED.value

# I7 by construction: last_error_code is stored and logged, so it may only ever
# be a machine-style code. Anything else — a provider message, free text, a
# token that leaked into an exception — is replaced wholesale, never truncated
# into the row.
_SAFE_ERROR_CODE = re.compile(r"^[A-Z0-9_]{1,64}$")


def _safe_error_code(code: str) -> str:
    return code if _SAFE_ERROR_CODE.fullmatch(code) else "TRANSPORT_UNAVAILABLE"


class RelayService:
    def __init__(
        self,
        *,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
        transport: DeliveryTransport,
    ) -> None:
        self._settings = settings
        self._sessionmaker = sessionmaker
        self._transport = transport

    # -- claiming ------------------------------------------------------------ #
    def _backoff(self, attempt_count: int) -> dt.datetime:
        delay = min(
            self._settings.relay_backoff_base_seconds * (2 ** max(0, attempt_count - 1)),
            self._settings.relay_backoff_cap_seconds,
        )
        return utcnow() + dt.timedelta(seconds=delay)

    async def _claim(self, session: AsyncSession) -> list[ChatOutbox]:
        now = utcnow()
        stmt = (
            sa.select(ChatOutbox)
            .where(
                ChatOutbox.published_at.is_(None),
                ChatOutbox.attempt_count < self._settings.relay_max_attempts,
                sa.or_(
                    ChatOutbox.next_attempt_at.is_(None), ChatOutbox.next_attempt_at <= now
                ),
            )
            .order_by(ChatOutbox.created_at)
            .limit(self._settings.relay_batch_size)
        )
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    # -- processing ---------------------------------------------------------- #
    async def process_batch(self) -> int:
        """Claim and process one batch; returns the number of rows published."""
        published = 0
        async with self._sessionmaker() as session:
            try:
                await set_transaction_context(session, user_id=None, actor_type="worker")
                for event in await self._claim(session):
                    if await self._process_event(session, event):
                        published += 1
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return published

    async def _process_event(self, session: AsyncSession, event: ChatOutbox) -> bool:
        if event.event_type not in _HANDLED:
            # I4: fail closed — parked with bounded retries, never published.
            self._park(event, "UNKNOWN_EVENT_TYPE")
            log.warning("relay parked unknown event type outbox_id=%s", event.id)
            return False
        if event.event_type != _NOTIFYING:
            event.published_at = utcnow()  # I3: known, non-notifying types drain
            return True
        try:
            await self._deliver_new_message(session, event)
        except TransportError as exc:
            self._park(event, str(exc) or "TRANSPORT_UNAVAILABLE")
            log.warning(
                "relay transport failure outbox_id=%s attempt=%s code=%s",
                event.id, event.attempt_count, event.last_error_code,
            )
            return False
        event.published_at = utcnow()
        event.last_error_code = None
        return True

    def _park(self, event: ChatOutbox, code: str) -> None:
        event.attempt_count += 1
        event.next_attempt_at = self._backoff(event.attempt_count)
        event.last_error_code = _safe_error_code(code)

    async def _deliver_new_message(self, session: AsyncSession, event: ChatOutbox) -> None:
        payload = event.payload or {}
        sender_raw = payload.get("sender_user_id")
        couple_id = event.couple_id
        if not sender_raw or couple_id is None:
            # Malformed for this build — park like an unknown type (fail closed).
            raise TransportError("EVENT_PAYLOAD_INCOMPLETE")
        sender_id = uuid.UUID(str(sender_raw))
        # Member resolution needs a member context under RLS; the sender is the
        # authorising member for this event (scope-revalidation pattern).
        await set_transaction_context(
            session, user_id=sender_id, actor_type="worker", couple_id=couple_id
        )
        memberships = MembershipRepository(session)
        recipients = [
            m.user_id
            for m in await memberships.for_couple(couple_id)
            if m.user_id != sender_id and m.status == MembershipStatus.ACTIVE.value
        ]
        if not recipients:
            # Unpaired before delivery: silence, matching the no-revocation-push
            # ruling. The event still drains (I3).
            return
        devices_repo = DeviceRepository(session)
        devices = [
            d for r in recipients for d in await devices_repo.active_tokens_for_user(r)
        ]
        if not devices:
            return  # nothing registered: drain without notification
        results = await self._transport.send_new_message([d.push_token for d in devices])
        by_token = {d.push_token: d for d in devices}
        for result in results:
            if result.permanently_rejected:
                device = by_token.get(result.token)
                if device is not None:
                    device.status = DeviceStatus.REVOKED.value
                    device.provider_rejected_at = utcnow()
                    device.revoked_at = utcnow()

    # -- pruning (D3C-3 / I8) ------------------------------------------------- #
    async def prune_published(self) -> int:
        """Delete PUBLISHED rows past the retention window. Never unpublished work."""
        cutoff = utcnow() - dt.timedelta(days=self._settings.outbox_prune_after_days)
        async with self._sessionmaker() as session:
            try:
                await set_transaction_context(session, user_id=None, actor_type="worker")
                res = await session.execute(
                    sa.delete(ChatOutbox).where(
                        ChatOutbox.published_at.is_not(None),
                        ChatOutbox.published_at <= cutoff,
                    )
                )
                await session.commit()
                return int(getattr(res, "rowcount", 0) or 0)
            except Exception:
                await session.rollback()
                raise
