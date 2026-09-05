"""Individual reviewer principals + CASE_ACCESSED audit type (round PR-D, DEC-PR-4).

The ``dilchat_safety`` database role is an ENFORCEMENT posture, not a human
identity. This adds the identity layer the ratified decision requires:

- ``safety_reviewers`` — one row per individual internal reviewer, with an
  Argon2 credential hash (the key itself is shown once at provisioning and never
  stored, logged, or echoed) and a revocable ACTIVE/REVOKED lifecycle.
  Reachable ONLY by the safety posture: the application role — which serves
  every user-facing route — is granted nothing at all, so a user-facing API
  cannot authenticate a reviewer even by mistake, and ``dilchat_readonly``
  cannot see reviewers either.
- ``CASE_ACCESSED`` joins the case-event types, so a reviewer merely READING a
  case is recorded, attributed to that individual principal.

No adjudication surface is added: no state transition, resolution, or
enforcement path exists in this round.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EVENT_TYPES = (
    "CASE_OPENED",
    "REPORT_LINKED",
    "EVIDENCE_PRESERVED",
    "EVIDENCE_ACCESSED",
    "STATE_CHANGED",
    "ACTION_RECORDED",
    "CASE_ACCESSED",
)
_PREVIOUS_EVENT_TYPES = _EVENT_TYPES[:-1]


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _event_type_constraint(values: tuple[str, ...]) -> str:
    joined = ",".join(f"'{v}'" for v in values)
    return f"event_type IN ({joined})"


def upgrade() -> None:
    op.create_table(
        "safety_reviewers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("credential_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("label", name="uq_safety_reviewer_label"),
        sa.CheckConstraint("status IN ('ACTIVE','REVOKED')", name="ck_safety_reviewers_status"),
        sa.CheckConstraint("role IN ('READ_ONLY_REVIEWER')", name="ck_safety_reviewers_role"),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND revoked_at IS NULL) "
            "OR (status = 'REVOKED' AND revoked_at IS NOT NULL)",
            name="ck_safety_reviewer_revocation_complete",
        ),
    )

    # Widen the case-event type constraint to include CASE_ACCESSED.
    op.drop_constraint("ck_chat_case_event_type", "chat_safety_case_events")
    op.create_check_constraint(
        "ck_chat_case_event_type",
        "chat_safety_case_events",
        _event_type_constraint(_EVENT_TYPES),
    )

    if not _pg():
        return

    # Least privilege: ONLY the safety posture touches reviewers. The app role
    # (which serves every user-facing route) and dilchat_readonly get nothing —
    # a user-facing API therefore cannot authenticate a reviewer at all.
    op.execute("GRANT SELECT, INSERT, UPDATE ON safety_reviewers TO dilchat_safety")

    op.execute("ALTER TABLE safety_reviewers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE safety_reviewers FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY reviewer_safety ON safety_reviewers FOR ALL "
        "USING (app_actor_type() = 'safety') WITH CHECK (app_actor_type() = 'safety')"
    )


def downgrade() -> None:
    if _pg():
        op.execute("DROP POLICY IF EXISTS reviewer_safety ON safety_reviewers")
        op.execute("ALTER TABLE safety_reviewers NO FORCE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE safety_reviewers DISABLE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON safety_reviewers FROM dilchat_safety")

    # Any CASE_ACCESSED rows must go before the narrower constraint is restored.
    op.execute("DELETE FROM chat_safety_case_events WHERE event_type = 'CASE_ACCESSED'")
    op.drop_constraint("ck_chat_case_event_type", "chat_safety_case_events")
    op.create_check_constraint(
        "ck_chat_case_event_type",
        "chat_safety_case_events",
        _event_type_constraint(_PREVIOUS_EVENT_TYPES),
    )

    op.drop_table("safety_reviewers")
