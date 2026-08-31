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


class ConversationStatus(str, enum.Enum):
    """Lifecycle of a relationship-scoped secure chat conversation (Phase 3A)."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class OutboxEventType(str, enum.Enum):
    """Transactional-outbox event types for later real-time delivery (Phase 3A).

    Payloads carry stable internal IDs and minimal metadata ONLY — never message
    bodies, tokens, emails, or birth data.
    """

    CONVERSATION_CREATED = "CONVERSATION_CREATED"
    MESSAGE_CREATED = "MESSAGE_CREATED"
    MESSAGE_DELETED = "MESSAGE_DELETED"
    READ_STATE_UPDATED = "READ_STATE_UPDATED"
    CONVERSATION_REVOKED = "CONVERSATION_REVOKED"


class DevicePlatform(str, enum.Enum):
    """Client platform of a registered push device (Phase 3C)."""

    IOS = "IOS"
    ANDROID = "ANDROID"
    UNKNOWN = "UNKNOWN"


class DeviceStatus(str, enum.Enum):
    """Lifecycle of a push-device registration (Phase 3C).

    REVOKED covers user removal, logout(-all), token displacement by a new
    sign-in on the same device, and permanent provider rejection.
    """

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class BlockStatus(str, enum.Enum):
    """Lifecycle of a directional user block (Phase 3B safety)."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class SafetyBlockReason(str, enum.Enum):
    """Optional INTERNAL-only safety reason code attached to a block.

    Never required from the user and never disclosed through user APIs.
    """

    UNSPECIFIED = "UNSPECIFIED"
    HARASSMENT = "HARASSMENT"
    ABUSE = "ABUSE"
    SAFETY = "SAFETY"
    OTHER = "OTHER"


class ReportTargetType(str, enum.Enum):
    """Whether a report targets a single message or a whole conversation."""

    MESSAGE = "MESSAGE"
    CONVERSATION = "CONVERSATION"


class ReportReason(str, enum.Enum):
    """Reporter-selected reason code (Phase 3B). Never inferred automatically."""

    HARASSMENT = "HARASSMENT"
    THREAT = "THREAT"
    HATE_OR_ABUSE = "HATE_OR_ABUSE"
    SEXUAL_CONTENT = "SEXUAL_CONTENT"
    IMPERSONATION = "IMPERSONATION"
    SPAM = "SPAM"
    SELF_HARM_CONCERN = "SELF_HARM_CONCERN"
    OTHER = "OTHER"


class ReportStatus(str, enum.Enum):
    """Reporter-visible report status. Internal case state is NOT exposed here."""

    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"


class SafetyCaseState(str, enum.Enum):
    """Internal moderation-case lifecycle (never exposed to normal users)."""

    OPEN = "OPEN"
    TRIAGED = "TRIAGED"
    ACTIONED = "ACTIONED"
    DISMISSED = "DISMISSED"
    CLOSED = "CLOSED"


class SafetyCaseResolution(str, enum.Enum):
    """Internal recorded action on a safety case (never exposed to normal users)."""

    NO_ACTION = "NO_ACTION"
    BLOCK_CONFIRMED = "BLOCK_CONFIRMED"
    ACCOUNT_RESTRICTION_RECOMMENDED = "ACCOUNT_RESTRICTION_RECOMMENDED"
    CONTENT_PRESERVATION_REQUIRED = "CONTENT_PRESERVATION_REQUIRED"
    EXTERNAL_REVIEW_REQUIRED = "EXTERNAL_REVIEW_REQUIRED"


class SafetyCaseEventType(str, enum.Enum):
    """Immutable internal case-event types. Metadata is body-free (IDs/codes only)."""

    CASE_OPENED = "CASE_OPENED"
    REPORT_LINKED = "REPORT_LINKED"
    EVIDENCE_PRESERVED = "EVIDENCE_PRESERVED"
    EVIDENCE_ACCESSED = "EVIDENCE_ACCESSED"
    STATE_CHANGED = "STATE_CHANGED"
    ACTION_RECORDED = "ACTION_RECORDED"


class SafetyActorType(str, enum.Enum):
    """Actor that drove an internal safety-case event."""

    USER = "USER"
    SAFETY = "SAFETY"
    SYSTEM = "SYSTEM"
    WORKER = "WORKER"


class RetentionState(str, enum.Enum):
    """Explicit conversation retention state so a later purge worker is safe.

    Phase 3B implements the state transitions and a purge-candidate *seam* only;
    it performs no destructive production scheduled deletion.
    """

    ACTIVE = "ACTIVE"
    REVOKED_PENDING_POLICY = "REVOKED_PENDING_POLICY"
    PRESERVED_FOR_REPORT = "PRESERVED_FOR_REPORT"
    ELIGIBLE_FOR_PURGE = "ELIGIBLE_FOR_PURGE"
    PURGED = "PURGED"


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
    CONVERSATION_CREATED = "CONVERSATION_CREATED"
    CONVERSATION_REVOKED = "CONVERSATION_REVOKED"
    MESSAGE_DELETED = "MESSAGE_DELETED"
    # Phase 3B safety (all body-free; no reporter description ever stored here).
    DEVICE_REGISTERED = "DEVICE_REGISTERED"
    DEVICE_REVOKED = "DEVICE_REVOKED"
    USER_BLOCK_CREATED = "USER_BLOCK_CREATED"
    USER_BLOCK_REVOKED = "USER_BLOCK_REVOKED"
    CHAT_REPORT_CREATED = "CHAT_REPORT_CREATED"
    SAFETY_CASE_OPENED = "SAFETY_CASE_OPENED"
    SAFETY_CASE_STATE_CHANGED = "SAFETY_CASE_STATE_CHANGED"
    SAFETY_EVIDENCE_ACCESSED = "SAFETY_EVIDENCE_ACCESSED"
    ACCOUNT_DELETION_REQUESTED = "ACCOUNT_DELETION_REQUESTED"
    ACCOUNT_DELETED = "ACCOUNT_DELETED"
    CONSENT_CREATED = "CONSENT_CREATED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    SHARED_ARTIFACT_CREATED = "SHARED_ARTIFACT_CREATED"
    AUTHZ_DENIED = "AUTHZ_DENIED"
    JOB_WRITE_ABORTED_SCOPE = "JOB_WRITE_ABORTED_SCOPE"


class AuthzOutcome(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
