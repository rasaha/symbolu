"""chat safety layer (Phase 3B): blocks, reports, evidence, cases, retention, rate limits

Adds the safety/moderation tables on top of the Phase 3A secure chat, with
least-privilege grants, an internal ``dilchat_safety`` role, ENABLE+FORCE RLS, and
policies that keep evidence/cases INTERNAL and a block invisible to the blocked
user. Reuses the existing transaction-local actor context
(``app.current_user_id`` / ``app.current_actor_type``) and the
``app_is_active_member`` / ``app_current_user`` / ``app_actor_type`` helpers, and
adds a SECURITY DEFINER ``app_block_exists`` helper for bidirectional block checks.

On SQLite (unit-test engine) the table DDL still applies; roles/grants/RLS/backfill
are PostgreSQL-only, matching the Phase A/B and 3A migrations.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

# User-facing safety tables (RLS keyed on the acting user).
_USER_TABLES = ["chat_user_blocks", "chat_reports"]
# Internal-only safety tables (app may INSERT where noted; only dilchat_safety reads).
_INTERNAL_TABLES = [
    "chat_report_evidence",
    "chat_safety_cases",
    "chat_safety_case_events",
]
_ALL_TABLES = _USER_TABLES + _INTERNAL_TABLES + [
    "chat_conversation_retention",
    "chat_rate_limits",
]


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _tz() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    # --- tables (portable DDL) --------------------------------------------- #
    op.create_table(
        "chat_user_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("blocker_user_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=True),
        sa.Column("revoked_at", _tz(), nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="ck_chat_block_status"),
        sa.CheckConstraint("blocker_user_id <> blocked_user_id", name="ck_chat_block_not_self"),
        sa.ForeignKeyConstraint(["blocker_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocked_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_chat_block_pair"),
    )
    op.create_index(
        op.f("ix_chat_user_blocks_blocker_user_id"), "chat_user_blocks", ["blocker_user_id"]
    )
    op.create_index(
        op.f("ix_chat_user_blocks_blocked_user_id"), "chat_user_blocks", ["blocked_user_id"]
    )
    op.create_index("ix_chat_block_blocked", "chat_user_blocks", ["blocked_user_id", "status"])

    op.create_table(
        "chat_safety_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("resolution", sa.String(length=40), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("couple_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.CheckConstraint(
            "state IN ('OPEN','TRIAGED','ACTIONED','DISMISSED','CLOSED')",
            name="ck_chat_case_state",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["chat_conversations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_safety_cases_conversation_id"), "chat_safety_cases", ["conversation_id"]
    )
    op.create_index(op.f("ix_chat_safety_cases_couple_id"), "chat_safety_cases", ["couple_id"])

    op.create_table(
        "chat_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_message_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("client_report_id", sa.String(length=64), nullable=False),
        sa.Column("resolved_at", _tz(), nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.CheckConstraint(
            "target_type IN ('MESSAGE','CONVERSATION')", name="ck_chat_report_target"
        ),
        sa.CheckConstraint(
            "reason IN ('HARASSMENT','THREAT','HATE_OR_ABUSE','SEXUAL_CONTENT',"
            "'IMPERSONATION','SPAM','SELF_HARM_CONCERN','OTHER')",
            name="ck_chat_report_reason",
        ),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','UNDER_REVIEW','RESOLVED')", name="ck_chat_report_status"
        ),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["case_id"], ["chat_safety_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reporter_user_id", "conversation_id", "client_report_id",
            name="uq_chat_report_idempotency",
        ),
    )
    op.create_index(op.f("ix_chat_reports_reporter_user_id"), "chat_reports", ["reporter_user_id"])
    op.create_index(op.f("ix_chat_reports_conversation_id"), "chat_reports", ["conversation_id"])
    op.create_index(op.f("ix_chat_reports_couple_id"), "chat_reports", ["couple_id"])
    op.create_index(op.f("ix_chat_reports_case_id"), "chat_reports", ["case_id"])

    op.create_table(
        "chat_report_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_sequence", sa.Integer(), nullable=False),
        sa.Column("source_conversation_id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("source_sender_id", sa.Uuid(), nullable=True),
        sa.Column("source_server_sequence", sa.BigInteger(), nullable=True),
        sa.Column("body_snapshot", sa.Text(), nullable=False),
        sa.Column("source_deleted_at", _tz(), nullable=True),
        sa.Column("source_created_at", _tz(), nullable=True),
        sa.Column("integrity_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["chat_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_sender_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "evidence_sequence", name="uq_chat_evidence_seq"),
    )
    op.create_index(
        op.f("ix_chat_report_evidence_report_id"), "chat_report_evidence", ["report_id"]
    )

    op.create_table(
        "chat_safety_case_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_internal_id", sa.Uuid(), nullable=True),
        sa.Column("meta", _JSON, nullable=True),
        sa.Column("created_at", _tz(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('CASE_OPENED','REPORT_LINKED','EVIDENCE_PRESERVED',"
            "'EVIDENCE_ACCESSED','STATE_CHANGED','ACTION_RECORDED')",
            name="ck_chat_case_event_type",
        ),
        sa.CheckConstraint(
            "actor_type IN ('USER','SAFETY','SYSTEM','WORKER')", name="ck_chat_case_actor_type"
        ),
        sa.ForeignKeyConstraint(["case_id"], ["chat_safety_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_safety_case_events_case_id"), "chat_safety_case_events", ["case_id"]
    )
    op.create_index(
        op.f("ix_chat_safety_case_events_created_at"),
        "chat_safety_case_events",
        ["created_at"],
    )

    op.create_table(
        "chat_conversation_retention",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
        sa.CheckConstraint(
            "state IN ('ACTIVE','REVOKED_PENDING_POLICY','PRESERVED_FOR_REPORT',"
            "'ELIGIBLE_FOR_PURGE','PURGED')",
            name="ck_chat_retention_state",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", name="uq_chat_retention_conversation"),
    )
    op.create_index(
        op.f("ix_chat_conversation_retention_couple_id"),
        "chat_conversation_retention",
        ["couple_id"],
    )
    op.create_index("ix_chat_retention_state", "chat_conversation_retention", ["state"])

    op.create_table(
        "chat_rate_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("action_key", sa.String(length=128), nullable=False),
        sa.Column("window_start", _tz(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("count", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("count >= 0", name="ck_chat_rate_limit_count"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_user_id", "action_key", "window_start", "window_seconds",
            name="uq_chat_rate_limit_window",
        ),
    )

    if not _pg():
        return  # SQLite unit-test engine: roles/grants/RLS/backfill are PostgreSQL-only.

    # --- deterministic retention backfill (no block/report fabricated) ----- #
    op.execute(
        """
        INSERT INTO chat_conversation_retention (id, conversation_id, couple_id, state, updated_at)
        SELECT gen_random_uuid(), c.id, c.couple_id,
               CASE WHEN c.status = 'ACTIVE' THEN 'ACTIVE' ELSE 'REVOKED_PENDING_POLICY' END,
               now()
        FROM chat_conversations c
        """
    )

    # --- internal safety role (least privilege) ---------------------------- #
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dilchat_safety') THEN
            CREATE ROLE dilchat_safety NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
          END IF;
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO dilchat_safety")
    # The safety role evaluates the invoker helpers used by RLS policies.
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_current_user(), app_actor_type(), "
        "app_is_active_member(uuid) TO dilchat_safety"
    )

    # --- bidirectional block-existence helper (SECURITY DEFINER) ----------- #
    # A user cannot see a block where they are the blocked party (blocker-only RLS),
    # so existence must be checked by a definer function owned by a BYPASSRLS role.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_block_exists(p_other uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER AS $$
          SELECT EXISTS (
            SELECT 1 FROM chat_user_blocks
            WHERE status = 'ACTIVE'
              AND ((blocker_user_id = app_current_user() AND blocked_user_id = p_other)
                OR (blocker_user_id = p_other AND blocked_user_id = app_current_user()))
          )
        $$;
        """
    )
    op.execute("ALTER FUNCTION app_block_exists(uuid) OWNER TO dilchat_secfn_owner")
    op.execute("ALTER FUNCTION app_block_exists(uuid) SET search_path = pg_catalog, public")
    op.execute("REVOKE ALL ON FUNCTION app_block_exists(uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_block_exists(uuid) "
        "TO dilchat_app, dilchat_worker, dilchat_safety"
    )
    # The definer's owner needs to read the block table it bypasses RLS on.
    op.execute("GRANT SELECT ON chat_user_blocks TO dilchat_secfn_owner")

    # --- privilege grants (least privilege) -------------------------------- #
    # Blocks: blocker (app) reads/creates/revokes own; safety reads. No DELETE.
    op.execute("GRANT SELECT, INSERT, UPDATE ON chat_user_blocks TO dilchat_app")
    op.execute("GRANT SELECT ON chat_user_blocks TO dilchat_safety")
    # Reports: reporter (app) reads own status + inserts; safety reads + transitions.
    op.execute("GRANT SELECT, INSERT ON chat_reports TO dilchat_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON chat_reports TO dilchat_safety")
    # Evidence: app may only INSERT (atomic with the report); safety reads. Immutable.
    op.execute("GRANT INSERT ON chat_report_evidence TO dilchat_app")
    op.execute("GRANT SELECT ON chat_report_evidence TO dilchat_safety")
    # Cases: app opens (INSERT); safety reads + transitions.
    op.execute("GRANT INSERT ON chat_safety_cases TO dilchat_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON chat_safety_cases TO dilchat_safety")
    # Case events: append-only; app + safety insert; safety reads. Immutable.
    op.execute("GRANT INSERT ON chat_safety_case_events TO dilchat_app")
    op.execute("GRANT SELECT, INSERT ON chat_safety_case_events TO dilchat_safety")
    # Retention: app transitions (while member), worker/safety manage. No DELETE.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON chat_conversation_retention "
        "TO dilchat_app, dilchat_worker, dilchat_safety"
    )
    # Rate limits: app upserts its own counters; worker/safety may read.
    op.execute("GRANT SELECT, INSERT, UPDATE ON chat_rate_limits TO dilchat_app")
    op.execute("GRANT SELECT ON chat_rate_limits TO dilchat_worker, dilchat_safety")
    # dilchat_readonly is granted NOTHING on any safety table (evidence/cases stay
    # off the reporting surface; INV: readonly cannot access evidence).

    # --- enable + FORCE RLS ------------------------------------------------ #
    for tbl in _ALL_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

    # --- policies: blocks (blocker-only; blocked user cannot see) ---------- #
    op.execute(
        "CREATE POLICY block_owner ON chat_user_blocks FOR ALL "
        "USING (blocker_user_id = app_current_user()) "
        "WITH CHECK (blocker_user_id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY block_safety_read ON chat_user_blocks FOR SELECT "
        "USING (app_actor_type() = 'safety')"
    )

    # --- policies: reports (reporter reads own + inserts; safety manages) --- #
    op.execute(
        "CREATE POLICY report_owner_read ON chat_reports FOR SELECT "
        "USING (reporter_user_id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY report_owner_insert ON chat_reports FOR INSERT "
        "WITH CHECK (reporter_user_id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY report_safety ON chat_reports FOR ALL "
        "USING (app_actor_type() = 'safety') WITH CHECK (app_actor_type() = 'safety')"
    )

    # --- policies: evidence (INTERNAL; app INSERT-only, safety read) ------- #
    op.execute(
        "CREATE POLICY evidence_insert ON chat_report_evidence FOR INSERT WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY evidence_safety_read ON chat_report_evidence FOR SELECT "
        "USING (app_actor_type() = 'safety')"
    )

    # --- policies: cases (INTERNAL) ---------------------------------------- #
    op.execute("CREATE POLICY case_insert ON chat_safety_cases FOR INSERT WITH CHECK (true)")
    op.execute(
        "CREATE POLICY case_safety ON chat_safety_cases FOR ALL "
        "USING (app_actor_type() = 'safety') WITH CHECK (app_actor_type() = 'safety')"
    )

    # --- policies: case events (INTERNAL; append-only) --------------------- #
    op.execute(
        "CREATE POLICY caseevt_insert ON chat_safety_case_events FOR INSERT WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY caseevt_safety_read ON chat_safety_case_events FOR SELECT "
        "USING (app_actor_type() = 'safety')"
    )

    # --- policies: retention (member while active; worker/safety anytime) -- #
    op.execute(
        "CREATE POLICY retention_rw ON chat_conversation_retention FOR ALL "
        "USING (app_is_active_member(couple_id) OR app_actor_type() IN ('worker','safety')) "
        "WITH CHECK (app_is_active_member(couple_id) OR app_actor_type() IN ('worker','safety'))"
    )

    # --- policies: rate limits (subject-only; worker/safety read) ---------- #
    op.execute(
        "CREATE POLICY rl_owner ON chat_rate_limits FOR ALL "
        "USING (subject_user_id = app_current_user()) "
        "WITH CHECK (subject_user_id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY rl_read ON chat_rate_limits FOR SELECT "
        "USING (app_actor_type() IN ('worker','safety'))"
    )


def downgrade() -> None:
    if _pg():
        policies = {
            "chat_user_blocks": ["block_owner", "block_safety_read"],
            "chat_reports": ["report_owner_read", "report_owner_insert", "report_safety"],
            "chat_report_evidence": ["evidence_insert", "evidence_safety_read"],
            "chat_safety_cases": ["case_insert", "case_safety"],
            "chat_safety_case_events": ["caseevt_insert", "caseevt_safety_read"],
            "chat_conversation_retention": ["retention_rw"],
            "chat_rate_limits": ["rl_owner", "rl_read"],
        }
        for tbl, names in policies.items():
            for name in names:
                op.execute(f"DROP POLICY IF EXISTS {name} ON {tbl}")
            op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY")
        for tbl in _ALL_TABLES:
            op.execute(
                f"REVOKE ALL ON {tbl} FROM dilchat_app, dilchat_worker, "
                f"dilchat_readonly, dilchat_safety"
            )
        op.execute("DROP FUNCTION IF EXISTS app_block_exists(uuid)")
        op.execute("REVOKE ALL ON FUNCTION app_current_user() FROM dilchat_safety")
        op.execute("REVOKE USAGE ON SCHEMA public FROM dilchat_safety")
        # dilchat_safety role left in place (cluster-global, like the other roles).

    op.drop_table("chat_rate_limits")
    op.drop_table("chat_conversation_retention")
    op.drop_table("chat_safety_case_events")
    op.drop_table("chat_report_evidence")
    op.drop_table("chat_reports")
    op.drop_table("chat_safety_cases")
    op.drop_table("chat_user_blocks")
