"""app_conversation_context helper (Phase 3B services).

The post-revocation reporting window (``chat_report_after_revocation_days``)
requires a FORMER member to address their ended conversation, but RLS keys
``chat_conversations`` visibility on ACTIVE membership, so the runtime role can
no longer read the row. Following the ``app_block_exists`` pattern
(d4e5f6a7b8c9) and the hardened definer posture (b2c3d4e5f6a7), this adds one
bounded SECURITY DEFINER function that returns ONLY the conversation's
``couple_id``/``status``/``revoked_at`` — never a message, member list, or any
content — and only to a caller who has (or had) a membership row in that
couple; strangers get an empty result.

PostgreSQL-only; on SQLite (unit-test engine) the service uses equivalent
direct queries because there is no RLS to work around.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _pg():
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_conversation_context(p_conversation uuid)
        RETURNS TABLE(couple_id uuid, status text, revoked_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER AS $$
          SELECT c.couple_id, c.status::text, c.revoked_at
          FROM chat_conversations c
          WHERE c.id = p_conversation
            AND EXISTS (
              SELECT 1 FROM couple_memberships m
              WHERE m.couple_id = c.couple_id
                AND m.user_id = app_current_user()
            )
        $$;
        """
    )
    op.execute("ALTER FUNCTION app_conversation_context(uuid) OWNER TO dilchat_secfn_owner")
    op.execute(
        "ALTER FUNCTION app_conversation_context(uuid) SET search_path = pg_catalog, public"
    )
    op.execute("REVOKE ALL ON FUNCTION app_conversation_context(uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_conversation_context(uuid) "
        "TO dilchat_app, dilchat_worker, dilchat_safety"
    )
    # The definer's owner (BYPASSRLS) needs table privilege on the rows it reads;
    # it already holds SELECT on couple_memberships (b2c3d4e5f6a7).
    op.execute("GRANT SELECT ON chat_conversations TO dilchat_secfn_owner")


def downgrade() -> None:
    if not _pg():
        return
    op.execute("DROP FUNCTION IF EXISTS app_conversation_context(uuid)")
    op.execute("REVOKE SELECT ON chat_conversations FROM dilchat_secfn_owner")
