"""The orchestration provenance trace and the assessment outcome envelope.

The trace is **explanatory only**. It is not evidence, not an attestation, not a
signed record and not a durable event: no signing, event bus or persistence is
introduced in this phase, and the outcome is deliberately **not signed** — a
signed readiness determination needs a separately ratified authority owner.

Constructing a :class:`ReadinessAssessmentOutcome` by hand is possible (it is a
public dataclass) and proves **nothing**: it carries no authority provenance and
no claim that any boundary was consulted. Only
:func:`~ugence_agent_value_readiness.orchestration.service.assess_readiness`
performs orchestration, exactly as a hand-assembled ``PolicyResolution`` proves
nothing about the shared Policy Authority.

Every collection is canonically ordered — by gate id, condition id, or code
declaration order — never by the order the caller supplied its inputs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_policy_authority.api import PolicyResolutionReason, PolicyResolutionStatus
from ugence_uvi_policy_contracts.api import PolicyReference, ReadinessTarget

from ..contracts.enums import ConditionStatus, GateStatus, ReadinessClassification
from ..evaluation.codes import EVALUATOR_FORMULA_VERSION
from ..evaluation.trace import ReadinessEvaluationResult
from .codes import (
    ORCHESTRATOR_ID,
    READINESS_ORCHESTRATOR_VERSION,
    ReadinessAssessmentStatus,
    ReadinessInputVerificationStatus,
    ReadinessTrustAdvisoryState,
)
from ._util import (
    digest_payload as _digest,
    require_digest_token as _require_digest_token,
    require_nonempty_str as _nonempty,
    require_str as _require_str,
)
from .errors import ReadinessAssessmentError

__all__ = [
    "GateVerificationSummary",
    "ConditionVerificationSummary",
    "ReadinessAssessmentDisposition",
    "ReadinessAssessmentTrace",
    "ReadinessAssessmentOutcome",
]


def _tuple_of(value, expected, name):
    if not isinstance(value, tuple) or any(not isinstance(v, expected) for v in value):
        raise ReadinessAssessmentError(f"{name} must be a tuple of {expected.__name__}")
    return value


def _tuple_of_str(value, name) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(v, str) for v in value):
        raise ReadinessAssessmentError(f"{name} must be a tuple of strings")
    return value


# --------------------------------------------------------------------------- #
# Per-input sanitization summaries
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GateVerificationSummary:
    """What happened to one supplied gate result, and why.

    ``admitted`` records only that the result passed **every** stage: structural
    binding to the resolved policy, a ``VERIFIED`` verifier answer, and the
    orchestrator's independent recheck of every returned coordinate. It never
    asserts that the underlying metric is true — it asserts that the configured
    verifier attested it under this exact binding.

    ``verification_status`` is the verifier's own answer, or
    ``REFERENCE_MISMATCH`` when the result never reached a verifier because its
    binding to the resolved policy was refused first. ``trust_gap_codes`` always
    names the precise reason.
    """

    gate_id: str
    claimed_status: GateStatus
    verification_status: ReadinessInputVerificationStatus
    admitted: bool
    verifier_id: str = ""
    gate_digest: str = ""
    trust_gap_codes: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        _nonempty(self.gate_id, "GateVerificationSummary.gate_id")
        if not isinstance(self.claimed_status, GateStatus):
            raise ReadinessAssessmentError(
                "GateVerificationSummary.claimed_status must be a GateStatus"
            )
        if not isinstance(self.verification_status, ReadinessInputVerificationStatus):
            raise ReadinessAssessmentError(
                "GateVerificationSummary.verification_status must be a "
                "ReadinessInputVerificationStatus"
            )
        if not isinstance(self.admitted, bool):
            raise ReadinessAssessmentError("GateVerificationSummary.admitted must be a bool")
        _require_str(self.verifier_id, "GateVerificationSummary.verifier_id")
        _require_str(self.gate_digest, "GateVerificationSummary.gate_digest")
        _tuple_of_str(self.trust_gap_codes, "GateVerificationSummary.trust_gap_codes")
        _require_str(self.detail, "GateVerificationSummary.detail")
        # An admitted result cannot simultaneously carry a trust gap or a
        # non-VERIFIED status: "admitted but untrusted" is unrepresentable.
        if self.admitted:
            if self.verification_status is not ReadinessInputVerificationStatus.VERIFIED:
                raise ReadinessAssessmentError(
                    "an admitted GateVerificationSummary must carry VERIFIED"
                )
            if self.trust_gap_codes:
                raise ReadinessAssessmentError(
                    "an admitted GateVerificationSummary must carry no trust gap"
                )
        elif not self.trust_gap_codes:
            raise ReadinessAssessmentError(
                "a rejected GateVerificationSummary must name at least one trust gap"
            )

    def canonical_payload(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "claimed_status": self.claimed_status.value,
            "verification_status": self.verification_status.value,
            "admitted": self.admitted,
            "verifier_id": self.verifier_id,
            "gate_digest": self.gate_digest,
            "trust_gap_codes": list(self.trust_gap_codes),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ConditionVerificationSummary:
    """What happened to one supplied compensating control, and why.

    A control that is not admitted stays fully visible here with its stable
    rejection reason — an unadmitted condition is never silently dropped from
    the record. ``verification_status`` is the verifier's own answer, or
    ``REFERENCE_MISMATCH`` when the control never reached a verifier because its
    concern was ineligible or it was inactive at the evaluation instant.
    """

    condition_id: str
    source_gate_or_finding_ref: str
    claimed_status: ConditionStatus
    verification_status: ReadinessInputVerificationStatus
    admitted: bool
    verifier_id: str = ""
    condition_digest: str = ""
    trust_gap_codes: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        _nonempty(self.condition_id, "ConditionVerificationSummary.condition_id")
        _nonempty(
            self.source_gate_or_finding_ref,
            "ConditionVerificationSummary.source_gate_or_finding_ref",
        )
        if not isinstance(self.claimed_status, ConditionStatus):
            raise ReadinessAssessmentError(
                "ConditionVerificationSummary.claimed_status must be a ConditionStatus"
            )
        if not isinstance(self.verification_status, ReadinessInputVerificationStatus):
            raise ReadinessAssessmentError(
                "ConditionVerificationSummary.verification_status must be a "
                "ReadinessInputVerificationStatus"
            )
        if not isinstance(self.admitted, bool):
            raise ReadinessAssessmentError("ConditionVerificationSummary.admitted must be a bool")
        _require_str(self.verifier_id, "ConditionVerificationSummary.verifier_id")
        _require_str(self.condition_digest, "ConditionVerificationSummary.condition_digest")
        _tuple_of_str(self.trust_gap_codes, "ConditionVerificationSummary.trust_gap_codes")
        _require_str(self.detail, "ConditionVerificationSummary.detail")
        if self.admitted:
            if self.verification_status is not ReadinessInputVerificationStatus.VERIFIED:
                raise ReadinessAssessmentError(
                    "an admitted ConditionVerificationSummary must carry VERIFIED"
                )
            if self.trust_gap_codes:
                raise ReadinessAssessmentError(
                    "an admitted ConditionVerificationSummary must carry no trust gap"
                )
        elif not self.trust_gap_codes:
            raise ReadinessAssessmentError(
                "a rejected ConditionVerificationSummary must name at least one trust gap"
            )

    def canonical_payload(self) -> dict:
        return {
            "condition_id": self.condition_id,
            "source_gate_or_finding_ref": self.source_gate_or_finding_ref,
            "claimed_status": self.claimed_status.value,
            "verification_status": self.verification_status.value,
            "admitted": self.admitted,
            "verifier_id": self.verifier_id,
            "condition_digest": self.condition_digest,
            "trust_gap_codes": list(self.trust_gap_codes),
            "detail": self.detail,
        }


# --------------------------------------------------------------------------- #
# Trust-advisory reconciliation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReadinessAssessmentDisposition:
    """What GV-3R-c did about one standing GV-3R-b honesty advisory.

    The standalone evaluator is right to emit its advisories: it genuinely
    cannot verify an external trust boundary. Orchestration therefore never
    deletes or contradicts one — it states, per advisory, which configured
    boundary closed it, or that it stays open.

    An advisory is **never** marked resolved because a caller supplied a boolean
    or a structurally complete record.
    """

    advisory_code: str
    state: ReadinessTrustAdvisoryState
    detail: str = ""

    def __post_init__(self) -> None:
        _nonempty(self.advisory_code, "ReadinessAssessmentDisposition.advisory_code")
        if not isinstance(self.state, ReadinessTrustAdvisoryState):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentDisposition.state must be a ReadinessTrustAdvisoryState"
            )
        _require_str(self.detail, "ReadinessAssessmentDisposition.detail")

    def canonical_payload(self) -> dict:
        return {
            "advisory_code": self.advisory_code,
            "state": self.state.value,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------- #
# The orchestration trace
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReadinessAssessmentTrace:
    """A deterministic explanation of one orchestrated readiness assessment.

    It deliberately carries **no** ``ReadinessClassification`` field. The
    readiness headline exists in exactly one place — the GV-3R-b
    ``ReadinessEvaluationResult`` on the outcome — so a trace that disagrees
    with the evaluation about the classification is not merely rejected, it is
    unrepresentable.

    ``policy_resolution_status`` / ``policy_resolution_reason`` report what the
    **authority** answered, verbatim. ``policy_resolution_accepted`` reports
    whether the **orchestrator** then accepted that answer after independently
    rechecking every coordinate — the two are deliberately separate, because an
    authority can legitimately resolve a policy that this assessment must still
    refuse (a context that binds a different policy, a target the policy does
    not govern, an ``as_of`` that is not the evaluation instant).

    ``issuance_record_ref`` is the stable identifier of the issuance record the
    shared authority resolved. Unless the resolution was accepted it is empty,
    alongside every other policy field except the requested reference the caller
    already holds: a refusal exposes **no usable policy material**.
    """

    assessment_id: str
    tenant_id: str
    subject_id: str
    context_digest: str
    readiness_policy_ref: PolicyReference
    requested_target: ReadinessTarget
    evaluation_time: datetime
    request_digest: str
    policy_resolution_status: PolicyResolutionStatus
    policy_resolution_reason: PolicyResolutionReason
    policy_resolution_accepted: bool = False
    issuance_record_ref: str = ""
    resolved_policy_digest: str = ""
    gate_verifications: tuple[GateVerificationSummary, ...] = ()
    condition_verifications: tuple[ConditionVerificationSummary, ...] = ()
    admitted_gate_ids: tuple[str, ...] = ()
    rejected_gate_ids: tuple[str, ...] = ()
    admitted_condition_ids: tuple[str, ...] = ()
    rejected_condition_ids: tuple[str, ...] = ()
    trust_gap_codes: tuple[str, ...] = ()
    dispositions: tuple[ReadinessAssessmentDisposition, ...] = ()
    orchestrator_id: str = ORCHESTRATOR_ID
    orchestrator_version: str = READINESS_ORCHESTRATOR_VERSION
    evaluator_formula_version: str = EVALUATOR_FORMULA_VERSION

    def __post_init__(self) -> None:
        _nonempty(self.assessment_id, "ReadinessAssessmentTrace.assessment_id")
        _nonempty(self.tenant_id, "ReadinessAssessmentTrace.tenant_id")
        _nonempty(self.subject_id, "ReadinessAssessmentTrace.subject_id")
        _require_digest_token(self.context_digest, "ReadinessAssessmentTrace.context_digest")
        if not isinstance(self.readiness_policy_ref, PolicyReference):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentTrace.readiness_policy_ref must be a PolicyReference"
            )
        if not isinstance(self.requested_target, ReadinessTarget):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentTrace.requested_target must be a ReadinessTarget"
            )
        if not isinstance(self.evaluation_time, datetime) or (
            self.evaluation_time.tzinfo is None
            or self.evaluation_time.tzinfo.utcoffset(self.evaluation_time) is None
        ):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentTrace.evaluation_time must be a timezone-aware datetime"
            )
        _require_digest_token(self.request_digest, "ReadinessAssessmentTrace.request_digest")
        if not isinstance(self.policy_resolution_status, PolicyResolutionStatus):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentTrace.policy_resolution_status must be a "
                "PolicyResolutionStatus"
            )
        if not isinstance(self.policy_resolution_reason, PolicyResolutionReason):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentTrace.policy_resolution_reason must be a "
                "PolicyResolutionReason"
            )
        if not isinstance(self.policy_resolution_accepted, bool):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentTrace.policy_resolution_accepted must be a bool"
            )
        _require_str(self.issuance_record_ref, "ReadinessAssessmentTrace.issuance_record_ref")
        _require_str(self.resolved_policy_digest, "ReadinessAssessmentTrace.resolved_policy_digest")
        _tuple_of(
            self.gate_verifications,
            GateVerificationSummary,
            "ReadinessAssessmentTrace.gate_verifications",
        )
        _tuple_of(
            self.condition_verifications,
            ConditionVerificationSummary,
            "ReadinessAssessmentTrace.condition_verifications",
        )
        for name in (
            "admitted_gate_ids",
            "rejected_gate_ids",
            "admitted_condition_ids",
            "rejected_condition_ids",
            "trust_gap_codes",
        ):
            _tuple_of_str(getattr(self, name), f"ReadinessAssessmentTrace.{name}")
        _tuple_of(
            self.dispositions,
            ReadinessAssessmentDisposition,
            "ReadinessAssessmentTrace.dispositions",
        )
        _nonempty(self.orchestrator_id, "ReadinessAssessmentTrace.orchestrator_id")
        _nonempty(self.orchestrator_version, "ReadinessAssessmentTrace.orchestrator_version")
        _nonempty(
            self.evaluator_formula_version, "ReadinessAssessmentTrace.evaluator_formula_version"
        )
        # Acceptance and policy material are the same fact stated twice, so
        # "accepted with nothing to show" and "material without acceptance" are
        # both unrepresentable.
        if self.policy_resolution_accepted:
            if self.policy_resolution_status is not PolicyResolutionStatus.RESOLVED:
                raise ReadinessAssessmentError(
                    "a ReadinessAssessmentTrace cannot accept a resolution the authority did "
                    "not resolve"
                )
            if not (self.issuance_record_ref and self.resolved_policy_digest):
                raise ReadinessAssessmentError(
                    "an accepted ReadinessAssessmentTrace must carry the resolved issuance "
                    "record reference and policy digest"
                )
        elif self.issuance_record_ref or self.resolved_policy_digest:
            raise ReadinessAssessmentError(
                "a ReadinessAssessmentTrace that did not accept its resolution must not carry "
                "an issuance record reference or a resolved policy digest"
            )

    @property
    def is_explanatory_only(self) -> bool:
        """Always ``True`` — the trace explains, it never authorizes or attests."""

        return True

    def canonical_digest(self) -> str:
        payload = {
            "assessment_id": self.assessment_id,
            "tenant_id": self.tenant_id,
            "subject_id": self.subject_id,
            "context_digest": self.context_digest,
            "readiness_policy_ref": self.readiness_policy_ref.canonical_digest(),
            "requested_target": self.requested_target.value,
            "evaluation_time": self.evaluation_time.isoformat(),
            "request_digest": self.request_digest,
            "policy_resolution_status": self.policy_resolution_status.value,
            "policy_resolution_reason": self.policy_resolution_reason.value,
            "policy_resolution_accepted": self.policy_resolution_accepted,
            "issuance_record_ref": self.issuance_record_ref,
            "resolved_policy_digest": self.resolved_policy_digest,
            "gate_verifications": [s.canonical_payload() for s in self.gate_verifications],
            "condition_verifications": [
                s.canonical_payload() for s in self.condition_verifications
            ],
            "admitted_gate_ids": list(self.admitted_gate_ids),
            "rejected_gate_ids": list(self.rejected_gate_ids),
            "admitted_condition_ids": list(self.admitted_condition_ids),
            "rejected_condition_ids": list(self.rejected_condition_ids),
            "trust_gap_codes": list(self.trust_gap_codes),
            "dispositions": [d.canonical_payload() for d in self.dispositions],
            "orchestrator_id": self.orchestrator_id,
            "orchestrator_version": self.orchestrator_version,
            "evaluator_formula_version": self.evaluator_formula_version,
        }
        return _digest(payload)


# --------------------------------------------------------------------------- #
# The outcome envelope
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReadinessAssessmentOutcome:
    """The result of one orchestrated readiness assessment.

    Exactly two shapes are representable:

    * ``NOT_EVALUATED`` — a trust boundary refused. There is **no** readiness
      headline: no classification, no determination, no evaluation result. The
      constructor rejects any attempt to carry one.
    * ``EVALUATED`` — the deterministic GV-3R-b evaluator ran exactly once over
      sanitized input, and the outcome carries exactly one
      ``ReadinessEvaluationResult`` whose context, target, policy reference and
      instant agree with the trace.

    The outcome is **advisory** and authorizes nothing. It is not signed: a
    signed readiness determination requires a separately ratified authority
    owner, which this phase does not create.
    """

    status: ReadinessAssessmentStatus
    trace: ReadinessAssessmentTrace
    evaluation: Optional[ReadinessEvaluationResult] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReadinessAssessmentStatus):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentOutcome.status must be a ReadinessAssessmentStatus"
            )
        if not isinstance(self.trace, ReadinessAssessmentTrace):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentOutcome.trace must be a ReadinessAssessmentTrace"
            )

        if self.status is ReadinessAssessmentStatus.NOT_EVALUATED:
            if self.evaluation is not None:
                raise ReadinessAssessmentError(
                    "a NOT_EVALUATED ReadinessAssessmentOutcome cannot carry an evaluation "
                    "result or a readiness classification — no headline exists"
                )
            if not self.trace.trust_gap_codes:
                raise ReadinessAssessmentError(
                    "a NOT_EVALUATED ReadinessAssessmentOutcome must name at least one trust gap"
                )
            return

        if not isinstance(self.evaluation, ReadinessEvaluationResult):
            raise ReadinessAssessmentError(
                "an EVALUATED ReadinessAssessmentOutcome must carry exactly one "
                "ReadinessEvaluationResult"
            )
        determination = self.evaluation.determination
        if determination.assessment_id != self.trace.assessment_id:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation disagree about the assessment identity"
            )
        if determination.tenant_id != self.trace.tenant_id:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation disagree about the tenant"
            )
        if determination.subject_id != self.trace.subject_id:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation disagree about the subject"
            )
        if determination.context.canonical_digest() != self.trace.context_digest:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation disagree about the AssessmentContext"
            )
        if determination.readiness_policy_ref != self.trace.readiness_policy_ref:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation disagree about the readiness policy reference"
            )
        if determination.requested_target is not self.trace.requested_target:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation disagree about the requested target"
            )
        if determination.created_at != self.trace.evaluation_time:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation disagree about the evaluation instant"
            )
        if self.evaluation.trace.evaluation_time != self.trace.evaluation_time:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation trace disagree about the evaluation instant"
            )
        if self.evaluation.trace.formula_version != self.trace.evaluator_formula_version:
            raise ReadinessAssessmentError(
                "outcome trace and evaluation trace disagree about the evaluator formula version"
            )
        if not self.trace.policy_resolution_accepted:
            raise ReadinessAssessmentError(
                "an EVALUATED ReadinessAssessmentOutcome requires a readiness policy that both "
                "resolved through the authority and passed every independent recheck — "
                "policy-resolution failure dominates every gate result"
            )

    # ------------------------------------------------------------------ #
    # Derived views. None is a settable field, so no caller can state a
    # summary that disagrees with the trace it was derived from.
    # ------------------------------------------------------------------ #
    @property
    def assessment_id(self) -> str:
        return self.trace.assessment_id

    @property
    def evaluated(self) -> bool:
        return self.status is ReadinessAssessmentStatus.EVALUATED

    @property
    def classification(self) -> Optional[ReadinessClassification]:
        """The readiness headline, or ``None`` when none was ever asserted."""

        return self.evaluation.classification if self.evaluation is not None else None

    @property
    def gate_verifications(self) -> tuple[GateVerificationSummary, ...]:
        return self.trace.gate_verifications

    @property
    def condition_verifications(self) -> tuple[ConditionVerificationSummary, ...]:
        return self.trace.condition_verifications

    @property
    def trust_gap_codes(self) -> tuple[str, ...]:
        return self.trace.trust_gap_codes

    @property
    def dispositions(self) -> tuple[ReadinessAssessmentDisposition, ...]:
        return self.trace.dispositions

    @property
    def is_advisory(self) -> bool:
        """Always ``True``. This outcome never authorizes a deployment."""

        return True

    @property
    def authorizes_deployment(self) -> bool:
        """Always ``False`` — deployment governance is a separate process.

        A read-only property, not a field: there is no assignment, constructor
        argument or subclass hook that can make it ``True``.
        """

        return False

    def canonical_digest(self) -> str:
        """Stable digest over the status, the trace and the evaluation (if any)."""

        joined = ":".join(
            (
                self.status.value,
                self.trace.canonical_digest(),
                self.evaluation.canonical_digest() if self.evaluation is not None else "",
            )
        )
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()
