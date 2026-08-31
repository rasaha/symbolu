"""SQLAlchemy ORM models for the Phase 3B chat safety layer.

Seven tables build a safety/moderation layer on top of the Phase 3A secure chat:

- ``chat_user_blocks`` — directional user block (user-facing to the blocker only);
- ``chat_reports`` — a message/conversation report (reporter-visible status only);
- ``chat_report_evidence`` — immutable, INTERNAL-only preserved evidence snapshot;
- ``chat_safety_cases`` — INTERNAL moderation case;
- ``chat_safety_case_events`` — immutable, body-free INTERNAL case event log;
- ``chat_conversation_retention`` — explicit retention state (purge-worker seam);
- ``chat_rate_limits`` — concurrency-safe fixed-window abuse counters.

Privacy invariants encoded here (enforced additionally by RLS, see the migration):

- The **blocked** user has no visibility of a block against them (RLS: blocker-only).
- **Evidence, cases, and case events are INTERNAL**: the application role may only
  INSERT them (atomically, inside the reporter's request transaction) and can never
  SELECT/UPDATE/DELETE them — mirroring the Phase 3A outbox posture. Only the
  ``dilchat_safety`` role may read them.
- Evidence bodies and reporter descriptions are SENSITIVE: never logged, audited,
  traced, or placed in the outbox.
- A report never copies data the reporter was not authorized to access.
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, JSONVariant, TimestampMixin, UTCDateTime, utcnow, uuid_pk
from ..domain import enums

# Reuse classification metadata + the enum-check helper from the Phase A/B models,
# and guarantee the base + chat tables are registered on ``Base.metadata``.
from . import chat_orm as _chat_orm  # noqa: F401  (register chat tables)
from .orm import INTERNAL, PUBLIC, SENSITIVE, _enum_check  # noqa: F401


class ChatUserBlock(Base, TimestampMixin):
    """A directional block: ``blocker_user_id`` blocks ``blocked_user_id``.

    Exactly one row per ordered pair; re-blocking reactivates the same row. The
    blocked user has no visibility of this record (enforced by RLS: blocker-only).
    """

    __tablename__ = "chat_user_blocks"

    id: Mapped[uuid.UUID] = uuid_pk()
    blocker_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    blocked_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.BlockStatus.ACTIVE.value, info=INTERNAL
    )
    # Optional INTERNAL-only safety reason; never required, never disclosed.
    reason_code: Mapped[str | None] = mapped_column(sa.String(32), info=INTERNAL)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        sa.UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_chat_block_pair"),
        sa.CheckConstraint("blocker_user_id <> blocked_user_id", name="ck_chat_block_not_self"),
        _enum_check("status", enums.BlockStatus),
        sa.Index("ix_chat_block_blocked", "blocked_user_id", "status"),
    )


class ChatReport(Base, TimestampMixin):
    """A user report of a message or conversation they were authorized to access."""

    __tablename__ = "chat_reports"

    id: Mapped[uuid.UUID] = uuid_pk()
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    couple_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    target_message_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    # Optional, bounded reporter description. SENSITIVE: never logged/audited/outboxed.
    description: Mapped[str | None] = mapped_column(sa.Text, info=SENSITIVE)
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.ReportStatus.SUBMITTED.value, info=PUBLIC
    )
    # Internal moderation case this report belongs to (not exposed to the reporter).
    case_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("chat_safety_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Client-supplied idempotency key; scope (reporter, conversation, key).
    client_report_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        sa.UniqueConstraint(
            "reporter_user_id", "conversation_id", "client_report_id",
            name="uq_chat_report_idempotency",
        ),
        _enum_check("target_type", enums.ReportTargetType),
        _enum_check("reason", enums.ReportReason),
        _enum_check("status", enums.ReportStatus),
    )


class ChatReportEvidence(Base):
    """Immutable, INTERNAL-only preserved evidence snapshot for a report.

    Created atomically with the report inside the reporter's request transaction
    (the app role may only INSERT — never SELECT/UPDATE/DELETE). Bodies are SENSITIVE.
    """

    __tablename__ = "chat_report_evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    report_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("chat_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_sequence: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    source_conversation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    source_sender_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    source_server_sequence: Mapped[int | None] = mapped_column(sa.BigInteger)
    # Snapshot of the message body at report time. SENSITIVE. Empty if already
    # tombstoned/unavailable — never reconstructed from logs.
    body_snapshot: Mapped[str] = mapped_column(sa.Text, nullable=False, default="", info=SENSITIVE)
    source_deleted_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    source_created_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    # SHA-256 integrity marker over the snapshotted fields (repository-approved
    # primitive; NOT a custom encryption scheme).
    integrity_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False, info=INTERNAL)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow
    )

    __table_args__ = (
        sa.UniqueConstraint("report_id", "evidence_sequence", name="uq_chat_evidence_seq"),
    )


class ChatSafetyCase(Base, TimestampMixin):
    """INTERNAL moderation case. Never readable by the application (user) role."""

    __tablename__ = "chat_safety_cases"

    id: Mapped[uuid.UUID] = uuid_pk()
    state: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.SafetyCaseState.OPEN.value, info=INTERNAL
    )
    resolution: Mapped[str | None] = mapped_column(sa.String(40), info=INTERNAL)
    # Denormalised for internal triage; NOT exposed to any user API.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("chat_conversations.id", ondelete="SET NULL"), index=True
    )
    couple_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="SET NULL"), index=True
    )

    __table_args__ = (
        _enum_check("state", enums.SafetyCaseState),
    )


class ChatSafetyCaseEvent(Base):
    """Immutable, body-free INTERNAL case event. IDs/codes only — never content."""

    __tablename__ = "chat_safety_case_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("chat_safety_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    actor_internal_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)
    # Minimal structured metadata: IDs/codes only. Never a body or a description.
    meta: Mapped[dict | None] = mapped_column(JSONVariant, info=INTERNAL)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, index=True
    )

    __table_args__ = (
        _enum_check("event_type", enums.SafetyCaseEventType),
        _enum_check("actor_type", enums.SafetyActorType),
    )


class ChatConversationRetention(Base):
    """Explicit per-conversation retention state (purge-worker selection seam)."""

    __tablename__ = "chat_conversation_retention"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False
    )
    couple_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default=enums.RetentionState.ACTIVE.value, info=INTERNAL
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        sa.UniqueConstraint("conversation_id", name="uq_chat_retention_conversation"),
        _enum_check("state", enums.RetentionState),
        sa.Index("ix_chat_retention_state", "state"),
    )


class ChatRateLimit(Base):
    """Concurrency-safe fixed-window abuse counter, keyed by (subject, action, window).

    The key never contains message text or an unsalted content hash. Rows are the
    acting user's own (RLS: subject-only) so there is no cross-user interference.
    """

    __tablename__ = "chat_rate_limits"

    id: Mapped[uuid.UUID] = uuid_pk()
    subject_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Opaque action/window key, e.g. "send:<conversation_id>" or "report" or
    # "block_mut" — never derived from message content.
    action_key: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    window_start: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False)
    window_seconds: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    count: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)

    __table_args__ = (
        sa.UniqueConstraint(
            "subject_user_id", "action_key", "window_start", "window_seconds",
            name="uq_chat_rate_limit_window",
        ),
        sa.CheckConstraint("count >= 0", name="ck_chat_rate_limit_count"),
    )
