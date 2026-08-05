"""Repositories for the secure chat tables (conversations, messages, read-state, outbox).

Repositories perform data access only; transactional invariants (locking order,
idempotency, revocation) live in ``services/chat.py``. All queries are
parameterised through SQLAlchemy; no SQL is assembled from user input.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.enums import OutboxEventType
from ..infrastructure.chat_orm import (
    ChatConversation,
    ChatMessage,
    ChatOutbox,
    ChatReadState,
)


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, couple_id: uuid.UUID) -> ChatConversation:
        conv = ChatConversation(couple_id=couple_id)
        self._s.add(conv)
        await self._s.flush()
        return conv

    async def get(self, conversation_id: uuid.UUID) -> ChatConversation | None:
        return await self._s.get(ChatConversation, conversation_id)

    async def get_by_couple(self, couple_id: uuid.UUID) -> ChatConversation | None:
        result = await self._s.execute(
            sa.select(ChatConversation).where(ChatConversation.couple_id == couple_id)
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, conversation_id: uuid.UUID) -> ChatConversation | None:
        """Row-lock the conversation (``SELECT ... FOR UPDATE``; no-op on SQLite).

        This is the single authoritative lock taken by BOTH message send and unpair
        revocation, giving those paths a deterministic, deadlock-free ordering.
        """
        result = await self._s.execute(
            sa.select(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_couple_for_update(self, couple_id: uuid.UUID) -> ChatConversation | None:
        result = await self._s.execute(
            sa.select(ChatConversation)
            .where(ChatConversation.couple_id == couple_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, message: ChatMessage) -> ChatMessage:
        self._s.add(message)
        await self._s.flush()
        return message

    async def get(self, message_id: uuid.UUID) -> ChatMessage | None:
        return await self._s.get(ChatMessage, message_id)

    async def get_by_idempotency(
        self, *, conversation_id: uuid.UUID, sender_user_id: uuid.UUID, client_message_id: str
    ) -> ChatMessage | None:
        result = await self._s.execute(
            sa.select(ChatMessage).where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.sender_user_id == sender_user_id,
                ChatMessage.client_message_id == client_message_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_page(
        self, *, conversation_id: uuid.UUID, after_sequence: int, limit: int
    ) -> list[ChatMessage]:
        """Ascending, deterministic page of messages with sequence > after_sequence."""
        result = await self._s.execute(
            sa.select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.server_sequence > after_sequence,
            )
            .order_by(ChatMessage.server_sequence.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def max_sequence(self, conversation_id: uuid.UUID) -> int:
        result = await self._s.execute(
            sa.select(sa.func.max(ChatMessage.server_sequence)).where(
                ChatMessage.conversation_id == conversation_id
            )
        )
        return int(result.scalar_one() or 0)


class ReadStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self, *, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ChatReadState | None:
        result = await self._s.execute(
            sa.select(ChatReadState).where(
                ChatReadState.conversation_id == conversation_id,
                ChatReadState.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, row: ChatReadState) -> ChatReadState:
        self._s.add(row)
        await self._s.flush()
        return row


class OutboxRepository:
    """Writes transactional-outbox events. Payloads carry IDs/metadata only."""

    # Keys permitted in an outbox payload. A defence-in-depth allow-list so a
    # message body (or any other sensitive value) can never reach the outbox.
    _ALLOWED_PAYLOAD_KEYS = {
        "conversation_id",
        "couple_id",
        "message_id",
        "sender_user_id",
        "user_id",
        "server_sequence",
        "last_read_sequence",
        "deleted_by_user_id",
        "reason",
    }

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(
        self,
        *,
        event_type: OutboxEventType,
        payload: dict,
        conversation_id: uuid.UUID | None = None,
        couple_id: uuid.UUID | None = None,
        schema_version: int = 1,
    ) -> ChatOutbox:
        unexpected = set(payload) - self._ALLOWED_PAYLOAD_KEYS
        if unexpected:
            # Fail closed rather than risk leaking an unexpected field into the outbox.
            raise ValueError(f"outbox payload has disallowed keys: {sorted(unexpected)}")
        row = ChatOutbox(
            event_type=event_type.value,
            schema_version=schema_version,
            conversation_id=conversation_id,
            couple_id=couple_id,
            payload=payload,
        )
        self._s.add(row)
        await self._s.flush()
        return row
