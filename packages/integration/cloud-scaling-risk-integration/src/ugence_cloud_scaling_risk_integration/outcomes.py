"""The typed adapter outcome — the only thing Phase 4C ever returns.

Three statuses, and nothing else can be expressed:

``RISK_DECISION``
    The seam was reached and returned a non-executable
    :class:`~risk_authority.integrations.evaluation_contracts.SubjectRiskDecision`. That
    decision may itself be a risk pass, a denial, an escalation, or Risk Authority's own
    typed ``NOT_EVALUATED``. A risk pass is **not** authorization.

``PROJECTION_ABSTAINED_UPSTREAM``
    The controller abstained. No request was constructed, no subject digest was
    manufactured, and the seam was never called. The controller's typed reason and
    whatever input digests it had bound are carried through so the non-evaluation is
    auditable without overstating what was evaluated.

``PROJECTION_REJECTED``
    An adapter check failed closed before the seam. Nothing downstream was reached.

There is no field on this record — and no constructor argument anywhere in the package —
that can express an authorization, an envelope, a credential, an ActionGate result, an
actuation or an effect. Every such flag is fixed ``False`` and enforced at construction,
and a forged ``True`` on a returned decision is **rejected** rather than normalized.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Optional

from risk_authority.integrations import SubjectRiskDecision, SubjectRiskDisposition

from .errors import NonExecutableInvariantError
from .projection import CapacityRiskSubjectProjection

__all__ = [
    "ADAPTER_OUTCOME_SCHEMA_VERSION",
    "AdapterOutcomeStatus",
    "AdapterRejectionReason",
    "CloudScalingRiskOutcome",
]

ADAPTER_OUTCOME_SCHEMA_VERSION: Final[str] = "cloud-scaling-risk-adapter-outcome-1"


class AdapterOutcomeStatus(str, Enum):
    """What the adapter did — never what anyone may now do."""

    RISK_DECISION = "RISK_DECISION"
    PROJECTION_ABSTAINED_UPSTREAM = "PROJECTION_ABSTAINED_UPSTREAM"
    PROJECTION_REJECTED = "PROJECTION_REJECTED"


class AdapterRejectionReason(str, Enum):
    """Typed reasons an adapter check failed closed before the evaluation seam."""

    UNSUPPORTED_INPUT_TYPE = "unsupported_input_type"
    MALFORMED_RECOMMENDATION = "malformed_recommendation"
    MISSING_INDEPENDENT_RECOMMENDATION_DIGEST = "missing_independent_recommendation_digest"
    RECOMMENDATION_DIGEST_MISMATCH = "recommendation_digest_mismatch"
    RECOMMENDATION_EXPIRED = "recommendation_expired"
    RECOMMENDATION_NOT_YET_VALID = "recommendation_not_yet_valid"
    PROJECTION_FAILED = "projection_failed"
    UNTRUSTED_CLOCK = "untrusted_clock"


_AUTHORITY_FLAGS = (
    "authorization_performed",
    "envelope_issued",
    "actiongate_invoked",
    "credential_issued",
    "actuation_performed",
    "effect_verified",
    "executable",
)

# The decision-side flags Risk Authority fixes False on every SubjectRiskDecision. The
# adapter re-asserts them independently: a duck-typed or compromised seam that returned a
# look-alike carrying True must be refused here, not trusted because RA "would have"
# caught it.
_DECISION_FLAGS = (
    "authorization_performed",
    "envelope_issued",
    "actiongate_invoked",
    "actuation_performed",
    "effect_verified",
    "executable",
)


@dataclass(frozen=True)
class CloudScalingRiskOutcome:
    """The typed, non-executable result of one Phase 4C adapter invocation."""

    status: AdapterOutcomeStatus
    decision: Optional[SubjectRiskDecision] = None
    projection: Optional[CapacityRiskSubjectProjection] = None
    rejection_reason: Optional[AdapterRejectionReason] = None
    abstention_reason: Optional[str] = None
    detail: str = ""
    tenant_id: Optional[str] = None
    subject_id: Optional[str] = None
    recommendation_digest: Optional[str] = None
    evidence_references: tuple[str, ...] = ()
    schema_version: str = ADAPTER_OUTCOME_SCHEMA_VERSION
    # Fixed non-executable invariants — Phase 4C ends at a decision and grants nothing.
    authorization_performed: bool = False
    envelope_issued: bool = False
    actiongate_invoked: bool = False
    credential_issued: bool = False
    actuation_performed: bool = False
    effect_verified: bool = False
    executable: bool = False

    def __post_init__(self) -> None:
        for flag in _AUTHORITY_FLAGS:
            if getattr(self, flag) is not False:
                raise NonExecutableInvariantError(
                    f"{flag} must be False — Phase 4C introduces no execution or "
                    "authorization capability"
                )
        if not isinstance(self.status, AdapterOutcomeStatus):
            raise NonExecutableInvariantError("status must be an AdapterOutcomeStatus")
        if self.schema_version != ADAPTER_OUTCOME_SCHEMA_VERSION:
            raise NonExecutableInvariantError(
                f"schema_version must be {ADAPTER_OUTCOME_SCHEMA_VERSION!r}"
            )

        if self.status is AdapterOutcomeStatus.RISK_DECISION:
            if not isinstance(self.decision, SubjectRiskDecision):
                raise NonExecutableInvariantError(
                    "a RISK_DECISION outcome requires a canonical SubjectRiskDecision"
                )
            for flag in _DECISION_FLAGS:
                if getattr(self.decision, flag) is not False:
                    raise NonExecutableInvariantError(
                        f"the returned decision carries {flag}=True; a forged executable "
                        "flag is rejected, never normalized to False"
                    )
            if self.rejection_reason is not None or self.abstention_reason is not None:
                raise NonExecutableInvariantError(
                    "a RISK_DECISION outcome carries no rejection or abstention reason"
                )
        elif self.status is AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM:
            if self.decision is not None or self.projection is not None:
                raise NonExecutableInvariantError(
                    "an upstream abstention never reaches the seam and never manufactures "
                    "a subject projection or a risk decision"
                )
            if not isinstance(self.abstention_reason, str) or self.abstention_reason == "":
                raise NonExecutableInvariantError(
                    "an abstention outcome requires the controller's typed reason"
                )
            if self.rejection_reason is not None:
                raise NonExecutableInvariantError(
                    "an abstention is not an adapter rejection"
                )
        else:  # PROJECTION_REJECTED
            if self.decision is not None:
                raise NonExecutableInvariantError(
                    "a rejected projection never carries a risk decision"
                )
            if not isinstance(self.rejection_reason, AdapterRejectionReason):
                raise NonExecutableInvariantError(
                    "a rejected projection requires a typed AdapterRejectionReason"
                )
            if self.abstention_reason is not None:
                raise NonExecutableInvariantError(
                    "an adapter rejection is not an upstream abstention"
                )

    # ------------------------------------------------------------------ accessors
    @property
    def is_risk_decision(self) -> bool:
        """Whether Risk Authority produced a decision artifact for this invocation."""

        return self.status is AdapterOutcomeStatus.RISK_DECISION

    @property
    def disposition(self) -> Optional[SubjectRiskDisposition]:
        """The Risk Authority disposition, when one exists."""

        return self.decision.disposition if self.decision is not None else None

    @property
    def grants_authority(self) -> bool:
        """Always ``False``.

        Stated as an explicit, testable property rather than left implicit: a risk pass
        is not authorization, and no Phase 4C outcome of any status grants anything.
        """

        return False
