"""SQLAlchemy ORM models for the Phase 3A secure shared chat backend.

Four relationship-scoped tables sit on top of the existing couple model:

- ``chat_conversations`` — exactly one per couple/relationship instance;
- ``chat_messages`` — durable, text-only, tombstone-deletable messages;
- ``chat_read_states`` — one forward-only read cursor per conversation member;
- ``chat_outbox`` — transactional outbox for later real-time delivery.

Authorization is NEVER derived from a client-supplied conversation/message id;
membership is always resolved from the authoritative ``couple_memberships`` rows
(see ``security/scope.py`` and the RLS policies). ``couple_id`` is denormalised
onto messages/read-states so the same ``app_is_active_member(couple_id)`` RLS
predicate used by ``shared_artifacts`` applies uniformly.

The message ``body`` is classified SENSITIVE and is never written to logs, audit
rows, tracing spans, metrics, or outbox payloads. Tombstoning a message clears the
stored body (physical content erasure) while retaining the row and its metadata.
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, JSONVariant, TimestampMixin, UTCDateTime, utcnow, uuid_pk
from ..domain import enums

# Reuse the classification metadata + enum-check helper from the Phase A/B models.
# Importing ``orm`` here also guarantees the base tables are registered on
# ``Base.metadata`` whenever the chat models are imported.
from .orm import INTERNAL, PUBLIC, SENSITIVE, _enum_check  # noqa: F401

# Recommended initial body limit (Unicode code points). The authoritative value is
# the configurable ``Settings.chat_message_max_code_points``; this DB-level bound is
# a defence-in-depth backstop kept deliberately in sync with the default.
MESSAGE_BODY_MAX_CODE_POINTS = 4000


class ChatConversation(Base, TimestampMixin):
    """A durable, relationship-scoped conversation (at most one per couple).

    ``next_sequence`` is a per-conversation monotonic counter. A message send takes
    a row lock on the conversation, reads ``next_sequence`` as the message's
    ``server_sequence`` and increments it, yielding a gapless, deterministic cursor
    key that is also serialised against unpair revocation (consistent lock order).
    """

    __tablename__ = "chat_conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    couple_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.ConversationStatus.ACTIVE.value, info=PUBLIC
    )
    # Monotonic per-conversation message sequence counter (next value to assign).
    next_sequence: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=1)
    # Optimistic-concurrency version (advisory; row locks are the primary guard).
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        # Exactly one conversation per relationship instance. A later re-pair
        # produces a NEW couple row, hence a new conversation.
        sa.UniqueConstraint("couple_id", name="uq_chat_conversation_couple"),
        _enum_check("status", enums.ConversationStatus),
    )


class ChatMessage(Base):
    """A durable text message. Deletion is a tombstone (body cleared, row kept)."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised authoritative couple id (RLS predicate parity with shared data).
    couple_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Client-generated idempotency key (required). Scope: (conversation, sender, key).
    client_message_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # Monotonic, gapless per-conversation cursor key.
    server_sequence: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    # Message text. SENSITIVE: never logged, audited, traced, or placed in the outbox.
    body: Mapped[str] = mapped_column(sa.Text, nullable=False, info=SENSITIVE)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow
    )
    # Tombstone metadata (retained after deletion; body is cleared on delete).
    deleted_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        # Idempotency scope: one row per (conversation, sender, client_message_id).
        sa.UniqueConstraint(
            "conversation_id",
            "sender_user_id",
            "client_message_id",
            name="uq_chat_message_idempotency",
        ),
        # Stable cursor index (also enforces one sequence value per conversation).
        sa.UniqueConstraint(
            "conversation_id", "server_sequence", name="uq_chat_message_sequence"
        ),
        sa.CheckConstraint(
            f"length(body) <= {MESSAGE_BODY_MAX_CODE_POINTS}", name="ck_chat_message_body_len"
        ),
        sa.CheckConstraint("server_sequence >= 1", name="ck_chat_message_seq_positive"),
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class ChatReadState(Base):
    """One forward-only read cursor per conversation member."""

    __tablename__ = "chat_read_states"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    couple_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    last_read_sequence: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_chat_read_state_member"),
        sa.CheckConstraint("last_read_sequence >= 0", name="ck_chat_read_state_seq"),
    )


class ChatOutbox(Base):
    """Transactional outbox. Committed in the SAME transaction as the state change.

    Payload carries stable internal IDs and minimal metadata only — never a message
    body, birth data, email, or any token. Access is restricted to the internal
    worker role (see RLS policies); it is NOT exposed through the user API surface.
    """

    __tablename__ = "chat_outbox"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    schema_version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), index=True
    )
    couple_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="SET NULL"), index=True
    )
    # IDs + minimal metadata only (validated by the outbox writer). Never a body.
    payload: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, index=True
    )
    # Set by the Phase 3C relay. PUBLISHED means "handed to the configured
    # external transport according to its acknowledgement contract" — it never
    # means the user received or read anything. Correctness (DEC-058) still
    # never depends on it.
    published_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    # At-least-once delivery bookkeeping (Phase 3C). last_error_code is a
    # machine code only — never a body, token, or free-text provider response.
    attempt_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    next_attempt_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    last_error_code: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        _enum_check("event_type", enums.OutboxEventType),
        sa.Index("ix_chat_outbox_unpublished", "published_at", "created_at"),
    )
