"""Retention hold columns (production-readiness round PR-B, DEC-PR-3).

The ratified purge-eligibility rule requires that no legal/operational hold and
no policy-specific retention exception applies before a revoked conversation may
ever become purge-eligible. The schema had no way to express a hold, so the
condition could only have been assumed true. This adds the minimal honest
representation:

- ``hold_reason``  — a short machine-style code (e.g. ``LEGAL_HOLD``,
  ``POLICY_EXCEPTION``); NULL means no hold. It is an operational marker, never
  free text about a user, and never message/report content.
- ``hold_placed_at`` — when the hold was placed (audit/provenance).

A held row is NEVER purge-eligible regardless of age or state. No destructive
purge exists in this round: ``retention_purge_enabled`` stays false and the only
executable path is the read-only report (``ugence_dilchat.scripts_retention_report``).

Grants and the ``retention_rw`` RLS policy on ``chat_conversation_retention``
already cover the table; new columns need neither.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_conversation_retention",
        sa.Column("hold_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "chat_conversation_retention",
        sa.Column("hold_placed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # A hold is either fully absent or fully recorded — never half-set.
    op.create_check_constraint(
        "ck_chat_retention_hold_complete",
        "chat_conversation_retention",
        "(hold_reason IS NULL AND hold_placed_at IS NULL) "
        "OR (hold_reason IS NOT NULL AND hold_placed_at IS NOT NULL)",
    )
    # Report/selection index: held rows are looked up as an exception set.
    op.create_index(
        "ix_chat_retention_hold",
        "chat_conversation_retention",
        ["hold_reason"],
        postgresql_where=sa.text("hold_reason IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_chat_retention_hold", table_name="chat_conversation_retention")
    op.drop_constraint(
        "ck_chat_retention_hold_complete", "chat_conversation_retention", type_="check"
    )
    op.drop_column("chat_conversation_retention", "hold_placed_at")
    op.drop_column("chat_conversation_retention", "hold_reason")
