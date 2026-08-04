"""SQLAlchemy ORM models — the 10 authorized Phase A/B tables.

Ownership, scope classification, and immutability are expressed here. Immutable
tables (``natal_chart_snapshots``, ``shared_artifacts``, ``audit_events``) are
insert-only by repository contract; there is no UPDATE path. Columns holding
sensitive PII carry ``info={"classification": ...}`` metadata
(PUBLIC/INTERNAL/SENSITIVE) as the design-level encryption classification and are
never written to logs.
"""

from __future__ import annotations

import datetime as dt
import enum
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, JSONVariant, TimestampMixin, UTCDateTime, uuid_pk
from ..domain import enums

SENSITIVE = {"classification": "SENSITIVE"}
INTERNAL = {"classification": "INTERNAL"}
PUBLIC = {"classification": "PUBLIC"}


def _enum_check(column: str, e: type[enum.Enum]) -> sa.CheckConstraint:
    values = ", ".join(f"'{m.value}'" for m in e)
    return sa.CheckConstraint(f"{column} IN ({values})", name=f"ck_{column}_enum")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(sa.String(320), nullable=False, info=INTERNAL)
    credential_hash: Mapped[str | None] = mapped_column(
        sa.String(255), nullable=True, info=SENSITIVE
    )
    status: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default=enums.AccountStatus.ACTIVE.value, info=PUBLIC
    )
    deleted_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user")

    __table_args__ = (
        sa.UniqueConstraint("email", name="uq_users_email"),
        _enum_check("status", enums.AccountStatus),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 hash of the opaque refresh token (never the token itself).
    refresh_token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, info=SENSITIVE)
    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("user_sessions.id", ondelete="SET NULL")
    )
    issued_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: dt.datetime.now(dt.UTC)
    )
    expires_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False)
    rotated_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    user_agent: Mapped[str | None] = mapped_column(sa.String(256), info=INTERNAL)

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (
        sa.UniqueConstraint("refresh_token_hash", name="uq_sessions_refresh_hash"),
        sa.Index("ix_sessions_user_active", "user_id", "revoked_at"),
    )

    @property
    def is_active(self) -> bool:
        now = dt.datetime.now(dt.UTC)
        return self.revoked_at is None and self.rotated_at is None and self.expires_at > now


class BirthProfile(Base, TimestampMixin):
    __tablename__ = "birth_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("birth_profiles.id", ondelete="SET NULL")
    )

    preferred_name: Mapped[str] = mapped_column(sa.String(120), nullable=False, info=INTERNAL)
    birth_date: Mapped[dt.date] = mapped_column(sa.Date, nullable=False, info=SENSITIVE)
    # Local wall-clock time as originally entered (preserved verbatim). Null iff UNKNOWN.
    birth_time_local: Mapped[dt.time | None] = mapped_column(sa.Time, info=SENSITIVE)
    birth_time_precision: Mapped[str] = mapped_column(sa.String(16), nullable=False, info=PUBLIC)
    ambiguity_resolution: Mapped[str | None] = mapped_column(sa.String(8), info=INTERNAL)

    birthplace_label: Mapped[str] = mapped_column(sa.String(256), nullable=False, info=INTERNAL)
    latitude: Mapped[float] = mapped_column(sa.Float, nullable=False, info=SENSITIVE)
    longitude: Mapped[float] = mapped_column(sa.Float, nullable=False, info=SENSITIVE)
    iana_timezone: Mapped[str] = mapped_column(sa.String(64), nullable=False, info=INTERNAL)

    # Derived UTC birth instant; NULL when precision UNKNOWN (never fabricated).
    # Retained for EXACT inputs (== utc_interval_start == utc_interval_end).
    utc_birth_instant: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    input_confidence: Mapped[float] = mapped_column(sa.Float, nullable=False, info=PUBLIC)

    # Birth-time uncertainty interval (Area B). Present for all precisions.
    uncertainty_minutes: Mapped[int | None] = mapped_column(sa.Integer)  # APPROXIMATE
    utc_interval_start: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    utc_interval_end: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        sa.UniqueConstraint("user_id", "version", name="uq_birth_profile_user_version"),
        _enum_check("birth_time_precision", enums.BirthTimePrecision),
        sa.CheckConstraint("input_confidence >= 0 AND input_confidence <= 1", name="ck_bp_conf"),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_bp_lat"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_bp_lon"),
        sa.CheckConstraint(
            "uncertainty_minutes IS NULL OR "
            "(uncertainty_minutes > 0 AND uncertainty_minutes <= 720)",
            name="ck_bp_uncertainty",
        ),
    )


class NatalChartSnapshot(Base):
    """Immutable natal-Moon derivation for a (birth profile version, provider tuple)."""

    __tablename__ = "natal_chart_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    birth_profile_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("birth_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    birth_profile_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    provider_id: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    provider_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    ephemeris_mode: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    ayanamsa: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    julian_day: Mapped[float] = mapped_column(sa.Float, nullable=False)
    # Representative interval-start longitude (data, not the user-facing answer).
    moon_longitude: Mapped[float] = mapped_column(sa.Float, nullable=False)
    longitude_end: Mapped[float | None] = mapped_column(sa.Float)

    # Definitive single values — populated ONLY when the field is EXACT/STABLE.
    rashi_index: Mapped[int | None] = mapped_column(sa.Integer)
    rashi_name: Mapped[str | None] = mapped_column(sa.String(24))
    nakshatra_index: Mapped[int | None] = mapped_column(sa.Integer)
    nakshatra_name: Mapped[str | None] = mapped_column(sa.String(32))
    pada: Mapped[int | None] = mapped_column(sa.Integer)

    # Interval + per-field uncertainty (Area B).
    utc_interval_start: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    utc_interval_end: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    rashi_status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    nakshatra_status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    pada_status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    rashi_possible: Mapped[list | None] = mapped_column(JSONVariant)
    nakshatra_possible: Mapped[list | None] = mapped_column(JSONVariant)
    pada_possible: Mapped[list | None] = mapped_column(JSONVariant)
    guna_eligibility: Mapped[str] = mapped_column(sa.String(48), nullable=False)

    # Provider safety (Area A).
    provider_kind: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.ProviderKind.REAL.value
    )
    synthetic: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    test_only: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    authoritative: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    requires_recalculation: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False
    )

    numerical_precision_class: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    fallback_used: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(sa.String(128))
    input_confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    time_assumption: Mapped[str | None] = mapped_column(sa.String(48))
    calculation_timestamp: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: dt.datetime.now(dt.UTC)
    )
    trace: Mapped[dict] = mapped_column(JSONVariant, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint(
            "birth_profile_id",
            "birth_profile_version",
            "provider_id",
            "provider_version",
            "ephemeris_mode",
            "ayanamsa",
            name="uq_natal_version_tuple",
        ),
        sa.CheckConstraint(
            "rashi_index IS NULL OR (rashi_index >= 0 AND rashi_index <= 11)",
            name="ck_natal_rashi",
        ),
        sa.CheckConstraint(
            "nakshatra_index IS NULL OR (nakshatra_index >= 0 AND nakshatra_index <= 26)",
            name="ck_natal_nak",
        ),
        sa.CheckConstraint("pada IS NULL OR (pada >= 1 AND pada <= 4)", name="ck_natal_pada"),
        sa.CheckConstraint(
            "moon_longitude >= 0 AND moon_longitude < 360", name="ck_natal_lon"
        ),
        # A synthetic (fake) result may never be persisted as authoritative (Area A).
        sa.CheckConstraint(
            "NOT (synthetic AND authoritative)", name="ck_natal_no_synthetic_authoritative"
        ),
    )


class Couple(Base, TimestampMixin):
    __tablename__ = "couples"

    id: Mapped[uuid.UUID] = uuid_pk()
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.CoupleStatus.ACTIVE.value
    )
    unpaired_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    memberships: Mapped[list[CoupleMembership]] = relationship(back_populates="couple")

    __table_args__ = (_enum_check("status", enums.CoupleStatus),)


class CoupleMembership(Base):
    __tablename__ = "couple_memberships"

    id: Mapped[uuid.UUID] = uuid_pk()
    couple_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope_slot: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.MembershipStatus.ACTIVE.value
    )
    joined_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: dt.datetime.now(dt.UTC)
    )
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    couple: Mapped[Couple] = relationship(back_populates="memberships")

    __table_args__ = (
        sa.UniqueConstraint("couple_id", "scope_slot", name="uq_membership_couple_slot"),
        sa.UniqueConstraint("couple_id", "user_id", name="uq_membership_couple_user"),
        _enum_check("scope_slot", enums.ScopeSlot),
        _enum_check("status", enums.MembershipStatus),
    )


class CoupleInvitation(Base, TimestampMixin):
    __tablename__ = "couple_invitations"

    id: Mapped[uuid.UUID] = uuid_pk()
    inviter_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    couple_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="SET NULL")
    )
    token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, info=SENSITIVE)
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.InvitationStatus.PENDING.value
    )
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    expires_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False)
    accepted_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        sa.UniqueConstraint("token_hash", name="uq_invitation_token"),
        _enum_check("status", enums.InvitationStatus),
    )


class ConsentEvent(Base):
    """A consent action that authorizes a bounded private->shared projection."""

    __tablename__ = "consent_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    couple_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    granter_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    source_scope: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    artifact_type: Mapped[str] = mapped_column(sa.String(48), nullable=False)
    # A bounded, human-meaningful description of exactly what is shared. Never the
    # raw private stream.
    bounded_summary: Mapped[str] = mapped_column(sa.String(2000), nullable=False, info=INTERNAL)
    purpose: Mapped[str | None] = mapped_column(sa.String(256))
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: dt.datetime.now(dt.UTC)
    )
    expires_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        _enum_check("event_type", enums.ConsentEventType),
        _enum_check("state", enums.ConsentState),
        _enum_check("source_scope", enums.Scope),
    )


class SharedArtifact(Base):
    """Immutable snapshot of consented, bounded content (DEC-028).

    ``payload_snapshot`` is an inline immutable copy taken at consent time. There
    is deliberately NO foreign key to any private-scope row: deleting the private
    source can never break or re-expose a shared artifact.
    """

    __tablename__ = "shared_artifacts"

    id: Mapped[uuid.UUID] = uuid_pk()
    couple_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consent_event_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("consent_events.id", ondelete="RESTRICT"), nullable=False
    )
    source_scope: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    artifact_type: Mapped[str] = mapped_column(sa.String(48), nullable=False)
    # Immutable snapshot of the bounded projection (would be couple-DEK-encrypted in
    # production; classified SENSITIVE). No live pointer to the private source.
    payload_snapshot: Mapped[str] = mapped_column(sa.Text, nullable=False, info=SENSITIVE)
    provenance: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: dt.datetime.now(dt.UTC)
    )
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (_enum_check("source_scope", enums.Scope),)


class AuditEvent(Base):
    """Append-only audit record. Never contains secrets or raw sensitive payloads."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(sa.String(48), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(sa.String(48))
    resource_id: Mapped[str | None] = mapped_column(sa.String(64))
    scope: Mapped[str | None] = mapped_column(sa.String(16))
    couple_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("couples.id", ondelete="SET NULL"), index=True
    )
    outcome: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    denial_reason_code: Mapped[str | None] = mapped_column(sa.String(48))
    consent_event_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid())
    correlation_id: Mapped[str | None] = mapped_column(sa.String(64))
    provenance: Mapped[dict | None] = mapped_column(JSONVariant)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: dt.datetime.now(dt.UTC), index=True
    )

    __table_args__ = (_enum_check("outcome", enums.AuthzOutcome),)
