"""birth-time uncertainty + provider safety (Area A/B/C hardening)

Adds the birth-time uncertainty interval, per-field classification statuses,
future Guna eligibility metadata, and provider-safety columns
(synthetic/test_only/authoritative/provider_kind). Existing single-value natal
columns become nullable (populated only when a field is EXACT/STABLE).

Existing "noon-assumption" natal snapshots (Phase A/B, produced before the
uncertainty model) are NOT silently reinterpreted: they are marked
``requires_recalculation = true`` and ``guna_eligibility = REQUIRES_USER_REVIEW``.
Synthetic (fake) rows are marked ``synthetic/test_only`` and ``authoritative=false``
so the new invariant NOT(synthetic AND authoritative) holds.

Revision ID: 9c2b82ab02d2
Revises: dfd7ee81e09c
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ugence_dilchat.base import UTCDateTime

revision: str = "9c2b82ab02d2"
down_revision: str | None = "dfd7ee81e09c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
_NOON = "ASSUMED_NOON_UTC_UNKNOWN_PRECISION"


def upgrade() -> None:
    # --- birth_profiles: uncertainty interval --------------------------------
    op.add_column("birth_profiles", sa.Column("uncertainty_minutes", sa.Integer(), nullable=True))
    op.add_column("birth_profiles", sa.Column("utc_interval_start", UTCDateTime(), nullable=True))
    op.add_column("birth_profiles", sa.Column("utc_interval_end", UTCDateTime(), nullable=True))
    # Backfill existing EXACT rows: the single instant is both interval ends.
    op.execute(
        "UPDATE birth_profiles SET utc_interval_start = utc_birth_instant, "
        "utc_interval_end = utc_birth_instant WHERE utc_birth_instant IS NOT NULL"
    )
    op.create_check_constraint(
        "ck_bp_uncertainty",
        "birth_profiles",
        "uncertainty_minutes IS NULL OR (uncertainty_minutes > 0 AND uncertainty_minutes <= 720)",
    )

    # --- natal_chart_snapshots: interval + statuses + provider safety ---------
    op.add_column("natal_chart_snapshots", sa.Column("longitude_end", sa.Float(), nullable=True))
    op.add_column("natal_chart_snapshots", sa.Column("utc_interval_start", UTCDateTime(), nullable=True))
    op.add_column("natal_chart_snapshots", sa.Column("utc_interval_end", UTCDateTime(), nullable=True))
    op.add_column("natal_chart_snapshots", sa.Column("rashi_possible", _JSON, nullable=True))
    op.add_column("natal_chart_snapshots", sa.Column("nakshatra_possible", _JSON, nullable=True))
    op.add_column("natal_chart_snapshots", sa.Column("pada_possible", _JSON, nullable=True))

    # NOT NULL columns added with a server_default for a safe backfill; the default
    # is dropped afterwards so the ORM (python-side default) remains the source.
    op.add_column(
        "natal_chart_snapshots",
        sa.Column("rashi_status", sa.String(16), nullable=False, server_default="STABLE"),
    )
    op.add_column(
        "natal_chart_snapshots",
        sa.Column("nakshatra_status", sa.String(16), nullable=False, server_default="STABLE"),
    )
    op.add_column(
        "natal_chart_snapshots",
        sa.Column("pada_status", sa.String(16), nullable=False, server_default="STABLE"),
    )
    op.add_column(
        "natal_chart_snapshots",
        sa.Column(
            "guna_eligibility", sa.String(48), nullable=False,
            server_default="REQUIRES_USER_REVIEW",
        ),
    )
    op.add_column(
        "natal_chart_snapshots",
        sa.Column("provider_kind", sa.String(16), nullable=False, server_default="REAL"),
    )
    op.add_column(
        "natal_chart_snapshots",
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "natal_chart_snapshots",
        sa.Column("test_only", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "natal_chart_snapshots",
        sa.Column("authoritative", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "natal_chart_snapshots",
        sa.Column(
            "requires_recalculation", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    # Single-value columns become nullable (populated only when EXACT/STABLE).
    for col, typ in [
        ("rashi_index", sa.INTEGER()),
        ("rashi_name", sa.VARCHAR(length=24)),
        ("nakshatra_index", sa.INTEGER()),
        ("nakshatra_name", sa.VARCHAR(length=32)),
        ("pada", sa.INTEGER()),
    ]:
        op.alter_column("natal_chart_snapshots", col, existing_type=typ, nullable=True)

    # Backfill: synthetic (fake) rows -> synthetic/test_only, not authoritative.
    op.execute(
        "UPDATE natal_chart_snapshots SET provider_kind='SYNTHETIC', synthetic=true, "
        "test_only=true, authoritative=false "
        "WHERE provider_id='fake' OR ephemeris_mode='synthetic'"
    )
    # Backfill: legacy noon-assumption rows require recalculation (not reinterpreted).
    op.execute(
        "UPDATE natal_chart_snapshots SET requires_recalculation=true, "
        "guna_eligibility='REQUIRES_USER_REVIEW' WHERE time_assumption = '" + _NOON + "'"
    )

    op.create_check_constraint(
        "ck_natal_no_synthetic_authoritative",
        "natal_chart_snapshots",
        "NOT (synthetic AND authoritative)",
    )

    # Drop the temporary server defaults so the ORM defaults are authoritative.
    for col in [
        "rashi_status", "nakshatra_status", "pada_status", "guna_eligibility",
        "provider_kind", "synthetic", "test_only", "authoritative", "requires_recalculation",
    ]:
        op.alter_column("natal_chart_snapshots", col, server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_natal_no_synthetic_authoritative", "natal_chart_snapshots")
    for col, typ in [
        ("pada", sa.INTEGER()),
        ("nakshatra_name", sa.VARCHAR(length=32)),
        ("nakshatra_index", sa.INTEGER()),
        ("rashi_name", sa.VARCHAR(length=24)),
        ("rashi_index", sa.INTEGER()),
    ]:
        # Restore NOT NULL; safe because pre-0002 rows always had these populated.
        op.alter_column("natal_chart_snapshots", col, existing_type=typ, nullable=False)
    for col in [
        "requires_recalculation", "authoritative", "test_only", "synthetic", "provider_kind",
        "guna_eligibility", "pada_possible", "nakshatra_possible", "rashi_possible",
        "pada_status", "nakshatra_status", "rashi_status", "utc_interval_end",
        "utc_interval_start", "longitude_end",
    ]:
        op.drop_column("natal_chart_snapshots", col)
    op.drop_constraint("ck_bp_uncertainty", "birth_profiles")
    op.drop_column("birth_profiles", "utc_interval_end")
    op.drop_column("birth_profiles", "utc_interval_start")
    op.drop_column("birth_profiles", "uncertainty_minutes")
