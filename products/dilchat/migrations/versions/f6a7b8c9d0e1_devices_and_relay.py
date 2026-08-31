"""Device registrations and outbox delivery columns (Phase 3C relay).

Ratified DILCHAT-D3C-1..4 + invariants I1..I8:

- ``chat_devices`` — a push endpoint is a DEVICE INSTALLATION belonging to the
  authenticated user (never a session credential). One user may hold multiple
  active devices; the token is revocable/replaceable; a token maps to at most
  one ACTIVE registration globally (partial unique index + the
  ``app_release_push_token`` definer, which lets a new sign-in on a handed-over
  device revoke the previous owner's registration that RLS would otherwise hide).
- ``chat_outbox`` gains at-least-once delivery bookkeeping: ``attempt_count``,
  ``next_attempt_at``, and a content-free ``last_error_code``. ``published_at``
  continues to mean "handed to the configured external transport according to
  its acknowledgement contract" — never "received/read by the user".
- The worker role gains DELETE on the outbox, but the RLS DELETE policy permits
  ONLY published rows (I8: unpublished work is never pruned) — the 30-day
  pruning bound lives in the relay; the published-only bound is DB-enforced.
- Devices RLS: owner-only for the app role; the worker role may SELECT (deliver
  to the recipient's devices) and UPDATE (deactivate on permanent provider
  rejection). On SQLite (unit-test engine) roles/RLS/definer are PostgreSQL-only.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _tz() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    # --- outbox delivery bookkeeping (portable DDL) ------------------------- #
    op.add_column(
        "chat_outbox",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("chat_outbox", sa.Column("next_attempt_at", _tz(), nullable=True))
    # Machine code only (e.g. TRANSPORT_UNAVAILABLE) — never a message body,
    # token, or free-text provider response (invariant I7).
    op.add_column(
        "chat_outbox", sa.Column("last_error_code", sa.String(length=64), nullable=True)
    )

    # --- device registrations ---------------------------------------------- #
    op.create_table(
        "chat_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        # Optional association only: the session that registered the device,
        # used so logout-of-this-device can revoke it. NOT an auth binding.
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        # SENSITIVE: the provider push token. Never logged, audited, or echoed.
        sa.Column("push_token", sa.Text(), nullable=False),
        sa.Column("provider_rejected_at", _tz(), nullable=True),
        sa.Column("revoked_at", _tz(), nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="ck_chat_device_status"),
        sa.CheckConstraint(
            "platform IN ('IOS', 'ANDROID', 'UNKNOWN')", name="ck_chat_device_platform"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["user_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_devices_user_id"), "chat_devices", ["user_id"])
    op.create_index(op.f("ix_chat_devices_session_id"), "chat_devices", ["session_id"])
    # A push token addresses one device installation: at most one ACTIVE
    # registration may hold it, whoever the owner is.
    op.create_index(
        "ux_chat_device_active_token",
        "chat_devices",
        ["push_token"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )

    if not _pg():
        return  # SQLite unit-test engine: roles/grants/RLS/definer are PostgreSQL-only.

    # --- grants -------------------------------------------------------------- #
    op.execute("GRANT SELECT, INSERT, UPDATE ON chat_devices TO dilchat_app")
    op.execute("GRANT SELECT, UPDATE ON chat_devices TO dilchat_worker")
    # dilchat_readonly and dilchat_safety get NOTHING (tokens stay off every
    # reporting/moderation surface).
    op.execute("GRANT DELETE ON chat_outbox TO dilchat_worker")

    # --- RLS ----------------------------------------------------------------- #
    op.execute("ALTER TABLE chat_devices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_devices FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY device_owner ON chat_devices FOR ALL "
        "USING (user_id = app_current_user()) WITH CHECK (user_id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY device_worker_read ON chat_devices FOR SELECT "
        "USING (app_actor_type() = 'worker')"
    )
    op.execute(
        "CREATE POLICY device_worker_update ON chat_devices FOR UPDATE "
        "USING (app_actor_type() = 'worker') WITH CHECK (app_actor_type() = 'worker')"
    )
    # Pruning may remove PUBLISHED rows only (I8) — DB-enforced, not just relay
    # discipline. The 30-day age bound lives in the relay.
    op.execute(
        "CREATE POLICY chat_outbox_worker_prune ON chat_outbox FOR DELETE "
        "USING (app_actor_type() = 'worker' AND published_at IS NOT NULL)"
    )

    # --- token-release definer ---------------------------------------------- #
    # A device handed to a NEW user carries the same provider token; the new
    # owner's registration must displace the old one, whose row the app role
    # cannot see under owner-only RLS. Bounded definer: revokes ACTIVE rows for
    # exactly this token, returns only the count.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_release_push_token(p_token text) RETURNS integer
        LANGUAGE sql VOLATILE SECURITY DEFINER AS $$
          WITH released AS (
            UPDATE chat_devices
            SET status = 'REVOKED', revoked_at = now(), updated_at = now()
            WHERE push_token = p_token AND status = 'ACTIVE'
            RETURNING 1
          )
          SELECT count(*)::integer FROM released
        $$;
        """
    )
    op.execute("ALTER FUNCTION app_release_push_token(text) OWNER TO dilchat_secfn_owner")
    op.execute("ALTER FUNCTION app_release_push_token(text) SET search_path = pg_catalog, public")
    op.execute("REVOKE ALL ON FUNCTION app_release_push_token(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_release_push_token(text) TO dilchat_app")
    op.execute("GRANT SELECT, UPDATE ON chat_devices TO dilchat_secfn_owner")


def downgrade() -> None:
    if _pg():
        op.execute("DROP FUNCTION IF EXISTS app_release_push_token(text)")
        op.execute("DROP POLICY IF EXISTS chat_outbox_worker_prune ON chat_outbox")
        for name in ("device_owner", "device_worker_read", "device_worker_update"):
            op.execute(f"DROP POLICY IF EXISTS {name} ON chat_devices")
        op.execute("ALTER TABLE chat_devices NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE chat_devices DISABLE ROW LEVEL SECURITY")
        op.execute(
            "REVOKE ALL ON chat_devices FROM dilchat_app, dilchat_worker, dilchat_secfn_owner"
        )
        op.execute("REVOKE DELETE ON chat_outbox FROM dilchat_worker")

    op.drop_index("ux_chat_device_active_token", table_name="chat_devices")
    op.drop_index(op.f("ix_chat_devices_session_id"), table_name="chat_devices")
    op.drop_index(op.f("ix_chat_devices_user_id"), table_name="chat_devices")
    op.drop_table("chat_devices")
    op.drop_column("chat_outbox", "last_error_code")
    op.drop_column("chat_outbox", "next_attempt_at")
    op.drop_column("chat_outbox", "attempt_count")
