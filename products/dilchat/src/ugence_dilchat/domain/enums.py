"""Domain enumerations. String-valued for portable storage + CHECK constraints."""

from __future__ import annotations

import enum


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DEACTIVATED = "DEACTIVATED"
    DELETION_PENDING = "DELETION_PENDING"
    DELETED = "DELETED"


class BirthTimePrecision(str, enum.Enum):
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"
    UNKNOWN = "UNKNOWN"


class AmbiguityResolution(str, enum.Enum):
    """Which occurrence of an ambiguous (DST fall-back) local time was intended."""

    EARLIER = "EARLIER"  # maps to fold=0
    LATER = "LATER"      # maps to fold=1


class FieldStatus(str, enum.Enum):
    """Certainty of a derived Moon classification over the birth-time interval."""

    EXACT = "EXACT"                # single exact instant (EXACT precision)
    STABLE = "STABLE"             # one value throughout an interval
    AMBIGUOUS = "AMBIGUOUS"       # multiple possible rashi/nakshatra values
    INDETERMINATE = "INDETERMINATE"  # multiple possible pada values
    UNAVAILABLE = "UNAVAILABLE"   # could not be evaluated


class GunaEligibility(str, enum.Enum):
    """Future-facing eligibility metadata for a classical Guna Milan calculation.

    This is metadata ONLY. No Guna engine exists or is implemented in this phase.
    """

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE_AMBIGUOUS_NAKSHATRA = "INELIGIBLE_AMBIGUOUS_NAKSHATRA"
    INELIGIBLE_AMBIGUOUS_REQUIRED_INPUT = "INELIGIBLE_AMBIGUOUS_REQUIRED_INPUT"
    INELIGIBLE_MISSING_TIME = "INELIGIBLE_MISSING_TIME"
    REQUIRES_USER_REVIEW = "REQUIRES_USER_REVIEW"


class ProviderKind(str, enum.Enum):
    """Whether a provider yields synthetic (non-astronomical) or real output."""

    SYNTHETIC = "SYNTHETIC"  # fake provider — test/local development only
    REAL = "REAL"            # a real ephemeris (Swiss dev adapter or licensed)


class Scope(str, enum.Enum):
    PRIVATE_A = "PRIVATE_A"
    PRIVATE_B = "PRIVATE_B"
    SHARED = "SHARED"


class ScopeSlot(str, enum.Enum):
    A = "A"
    B = "B"

    @property
    def private_scope(self) -> Scope:
        return Scope.PRIVATE_A if self is ScopeSlot.A else Scope.PRIVATE_B


class CoupleStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    UNPAIRED = "UNPAIRED"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class InvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ConsentState(str, enum.Enum):
    REQUESTED = "REQUESTED"
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ConsentEventType(str, enum.Enum):
    REQUEST = "REQUEST"
    GRANT = "GRANT"
    REVOKE = "REVOKE"
    EXPIRE = "EXPIRE"


class AuditAction(str, enum.Enum):
    USER_REGISTERED = "USER_REGISTERED"
    USER_LOGIN = "USER_LOGIN"
    SESSION_REFRESHED = "SESSION_REFRESHED"
    SESSION_REVOKED = "SESSION_REVOKED"
    SESSIONS_REVOKED_ALL = "SESSIONS_REVOKED_ALL"
    REFRESH_REUSE_DETECTED = "REFRESH_REUSE_DETECTED"
    BIRTH_PROFILE_CREATED = "BIRTH_PROFILE_CREATED"
    BIRTH_PROFILE_UPDATED = "BIRTH_PROFILE_UPDATED"
    NATAL_MOON_COMPUTED = "NATAL_MOON_COMPUTED"
    INVITATION_CREATED = "INVITATION_CREATED"
    INVITATION_ACCEPTED = "INVITATION_ACCEPTED"
    INVITATION_EXPIRED = "INVITATION_EXPIRED"
    INVITATION_CANCELLED = "INVITATION_CANCELLED"
    COUPLE_UNPAIRED = "COUPLE_UNPAIRED"
    CONSENT_CREATED = "CONSENT_CREATED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    SHARED_ARTIFACT_CREATED = "SHARED_ARTIFACT_CREATED"
    AUTHZ_DENIED = "AUTHZ_DENIED"
    JOB_WRITE_ABORTED_SCOPE = "JOB_WRITE_ABORTED_SCOPE"


class AuthzOutcome(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
