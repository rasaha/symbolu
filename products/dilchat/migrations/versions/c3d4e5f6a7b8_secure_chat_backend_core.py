"""secure shared chat backend core (Phase 3A)

Adds the relationship-scoped secure-chat tables, their constraints/indexes, the
active-pair conversation backfill, and PostgreSQL row-level security:

- ``chat_conversations`` — one per couple (unique ``couple_id``);
- ``chat_messages`` — text messages; idempotency + cursor unique keys;
- ``chat_read_states`` — one forward-only read cursor per member;
- ``chat_outbox`` — transactional outbox (internal worker role only).

RLS reuses the existing ``app_is_active_member(couple_id)`` SECURITY DEFINER helper
and the transaction-local ``app.current_user_id`` / ``app.current_actor_type``
context (DEC-030/DEC-034/DEC-038). User tables are visible only to CURRENT active
members, so unpair removes visibility at once. The outbox is NOT exposed to the
user API surface: only the worker actor may read/update it; the app may only insert.

On SQLite (unit-test engine) the table DDL still applies; RLS/grants/backfill are
PostgreSQL-only, matching the Phase A/B RLS migration.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
_BODY_MAX = 4000
_CHAT_TABLES = ["chat_conversations", "chat_messages", "chat_read_states", "chat_outbox"]
_USER_TABLES = ["chat_conversations", "chat_messages", "chat_read_states"]


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # --- tables (portable DDL) --------------------------------------------- #
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("next_sequence", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="ck_status_enum"),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("couple_id", name="uq_chat_conversation_couple"),
    )
    op.create_index(
        op.f("ix_chat_conversations_couple_id"), "chat_conversations", ["couple_id"]
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=False),
        sa.Column("client_message_id", sa.String(length=64), nullable=False),
        sa.Column("server_sequence", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            f"length(body) <= {_BODY_MAX}", name="ck_chat_message_body_len"
        ),
        sa.CheckConstraint("server_sequence >= 1", name="ck_chat_message_seq_positive"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "sender_user_id",
            "client_message_id",
            name="uq_chat_message_idempotency",
        ),
        sa.UniqueConstraint(
            "conversation_id", "server_sequence", name="uq_chat_message_sequence"
        ),
    )
    op.create_index(
        op.f("ix_chat_messages_conversation_id"), "chat_messages", ["conversation_id"]
    )
    op.create_index(op.f("ix_chat_messages_couple_id"), "chat_messages", ["couple_id"])

    op.create_table(
        "chat_read_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_sequence", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("last_read_sequence >= 0", name="ck_chat_read_state_seq"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "user_id", name="uq_chat_read_state_member"
        ),
    )
    op.create_index(
        op.f("ix_chat_read_states_conversation_id"),
        "chat_read_states",
        ["conversation_id"],
    )
    op.create_index(
        op.f("ix_chat_read_states_couple_id"), "chat_read_states", ["couple_id"]
    )

    op.create_table(
        "chat_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("couple_id", sa.Uuid(), nullable=True),
        sa.Column("payload", _JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('CONVERSATION_CREATED', 'MESSAGE_CREATED', "
            "'MESSAGE_DELETED', 'READ_STATE_UPDATED', 'CONVERSATION_REVOKED')",
            name="ck_event_type_enum",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_outbox_conversation_id"), "chat_outbox", ["conversation_id"]
    )
    op.create_index(op.f("ix_chat_outbox_couple_id"), "chat_outbox", ["couple_id"])
    op.create_index(op.f("ix_chat_outbox_created_at"), "chat_outbox", ["created_at"])
    op.create_index(
        "ix_chat_outbox_unpublished", "chat_outbox", ["published_at", "created_at"]
    )

    if not _pg():
        return  # SQLite unit-test engine: RLS/grants/backfill are PostgreSQL-only.

    # --- backfill (before enabling FORCE RLS) ------------------------------ #
    # One ACTIVE conversation per ACTIVE couple that has none. Revoked couples get
    # no active conversation. gen_random_uuid() is built-in on PostgreSQL 13+.
    op.execute(
        """
        INSERT INTO chat_conversations
          (id, couple_id, status, next_sequence, version, created_at, updated_at)
        SELECT gen_random_uuid(), c.id, 'ACTIVE', 1, 1, now(), now()
        FROM couples c
        WHERE c.status = 'ACTIVE'
          AND NOT EXISTS (
            SELECT 1 FROM chat_conversations cc WHERE cc.couple_id = c.id
          )
        """
    )
    op.execute(
        """
        INSERT INTO chat_outbox
          (id, event_type, schema_version, conversation_id, couple_id, payload, created_at)
        SELECT gen_random_uuid(), 'CONVERSATION_CREATED', 1, cc.id, cc.couple_id,
               jsonb_build_object(
                 'conversation_id', cc.id::text,
                 'couple_id', cc.couple_id::text,
                 'reason', 'backfill'
               ),
               now()
        FROM chat_conversations cc
        """
    )

    # --- privilege grants (least privilege) -------------------------------- #
    for tbl in _USER_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {tbl} TO dilchat_app, dilchat_worker")
        op.execute(f"GRANT SELECT ON {tbl} TO dilchat_readonly")
    # Outbox: the app may only INSERT (write events in the same tx); the worker relay
    # may read + mark published. Never exposed to the read-only reporting role.
    op.execute("GRANT INSERT ON chat_outbox TO dilchat_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON chat_outbox TO dilchat_worker")

    # --- enable + FORCE RLS ------------------------------------------------ #
    for tbl in _CHAT_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

    # --- policies: user tables (current active members only) --------------- #
    op.execute(
        "CREATE POLICY chat_conv_member ON chat_conversations FOR ALL "
        "USING (app_is_active_member(couple_id)) WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY chat_msg_member ON chat_messages FOR ALL "
        "USING (app_is_active_member(couple_id)) "
        "WITH CHECK (app_is_active_member(couple_id) "
        "AND sender_user_id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY chat_read_member ON chat_read_states FOR ALL "
        "USING (app_is_active_member(couple_id)) "
        "WITH CHECK (app_is_active_member(couple_id) AND user_id = app_current_user())"
    )

    # --- policies: outbox (internal worker only; not on the user API surface) -- #
    op.execute(
        "CREATE POLICY chat_outbox_insert ON chat_outbox FOR INSERT WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY chat_outbox_worker_read ON chat_outbox FOR SELECT "
        "USING (app_actor_type() = 'worker')"
    )
    op.execute(
        "CREATE POLICY chat_outbox_worker_write ON chat_outbox FOR UPDATE "
        "USING (app_actor_type() = 'worker') WITH CHECK (app_actor_type() = 'worker')"
    )


def downgrade() -> None:
    if _pg():
        policies = {
            "chat_conversations": ["chat_conv_member"],
            "chat_messages": ["chat_msg_member"],
            "chat_read_states": ["chat_read_member"],
            "chat_outbox": [
                "chat_outbox_insert",
                "chat_outbox_worker_read",
                "chat_outbox_worker_write",
            ],
        }
        for tbl, names in policies.items():
            for name in names:
                op.execute(f"DROP POLICY IF EXISTS {name} ON {tbl}")
            op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY")
        for tbl in _CHAT_TABLES:
            op.execute(
                f"REVOKE ALL ON {tbl} FROM dilchat_app, dilchat_worker, dilchat_readonly"
            )

    op.drop_table("chat_outbox")
    op.drop_table("chat_read_states")
    op.drop_table("chat_messages")
    op.drop_table("chat_conversations")
