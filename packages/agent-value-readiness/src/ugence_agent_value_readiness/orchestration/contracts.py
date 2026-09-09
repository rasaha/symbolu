"""The additive trusted-orchestration contracts.

Four shapes, all frozen, tuple-normalized, timezone-safe and canonically
digestible:

* :class:`ReadinessAssessmentRequest` — everything an assessment is orchestrated
  *from*, and deliberately nothing more. It carries **no** classification, no
  caller-supplied "trusted" boolean, no policy lifecycle conclusion, no
  deployment authorization, no financial field, no system-clock default, and
  **no policy body** — the governing ``ReadinessPolicy`` can only arrive through
  the policy-resolution boundary, so a caller cannot hand the evaluator a second
  policy that disagrees with the resolved one.
* :class:`GateVerificationRequest` / :class:`ConditionVerificationRequest` — the
  complete binding handed to a configured verifier. The verifier is told the
  exact tenant, subject, context digest, target, policy reference, gate (or
  condition) identity and evaluation instant it must attest against; it is never
  asked "is this fine?" in the abstract.
* :class:`GateResultVerification` / :class:`ConditionSetVerification` — the
  verifier's answer. Every coordinate is echoed back so the orchestrator can
  recheck it independently; a status other than ``VERIFIED`` structurally cannot
  carry a verified status or a satisfied supporting-verification flag.

Constructing any of these proves nothing. Only
:func:`~ugence_agent_value_readiness.orchestration.service.assess_readiness`
performs orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import AssessedSystemBinding
from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    PolicyFamily,
    PolicyGate,
    PolicyReference,
    ReadinessTarget,
)

from ..contracts._util import coerce_tuple, normalize_tokens, require_nonempty, require_tzaware
from ..contracts.catalogs import ReadinessIndicatorCatalogSet
from ..contracts.composite import AdvisoryComposite
from ..contracts.conditions import ConditionSet
from ..contracts.enums import ConditionStatus, GateStatus
from ..contracts.gates import GateResult
from ..contracts.indicators import (
    AdoptionReadinessResult,
    CapabilityReadinessResult,
    IntelligenceFitnessResult,
)
from ._util import (
    as_assessment_error as _raise_as_assessment_error,
    digest_payload as _digest,
    iso_or_none as _iso,
    require_bool as _require_bool,
    require_digest_token as _require_digest_token,
    require_str as _require_str,
)
from .codes import ReadinessInputVerificationStatus
from .errors import ReadinessAssessmentError

__all__ = [
    "ReadinessAssessmentRequest",
    "GateVerificationRequest",
    "GateResultVerification",
    "ConditionVerificationRequest",
    "ConditionSetVerification",
]


def _require_readiness_ref(ref: object, name: str) -> None:
    if not isinstance(ref, PolicyReference):
        raise ReadinessAssessmentError(f"{name} must be a PolicyReference")
    if ref.policy_family is not PolicyFamily.READINESS:
        raise ReadinessAssessmentError(
            f"{name} must reference a READINESS policy (got {ref.policy_family.value})"
        )


def _require_target(value: object, name: str) -> None:
    if not isinstance(value, ReadinessTarget):
        raise ReadinessAssessmentError(f"{name} must be a ReadinessTarget")


# --------------------------------------------------------------------------- #
# The assessment request
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReadinessAssessmentRequest:
    """The complete, immutable input to one orchestrated readiness assessment.

    What it deliberately **cannot** express:

    * a :class:`~ugence_agent_value_readiness.contracts.enums.ReadinessClassification`
      — there is no field for one, so a caller cannot propose, hint or default a
      readiness headline;
    * a "resolved" / "trusted" / "verified" boolean — trust is an outcome of the
      configured boundaries, never a caller assertion;
    * a policy lifecycle conclusion — the resolved artifact's own metadata is
      read at the resolution stage;
    * a deployment authorization, or any monetary, cost, benefit, return or
      forecast quantity;
    * a second ``ReadinessPolicy`` body — only the resolution boundary supplies
      one, so there is nothing that can disagree with it;
    * an implicit instant — ``evaluation_time`` is mandatory and timezone-aware,
      and the system clock is never read.

    Every sequence is normalized to a real tuple at construction, so mutating a
    caller-owned list afterwards can never reach the frozen request or change
    its :meth:`canonical_digest`.

    M-3R.3 adds two shapes, both **optional on the dataclass and required by the
    boundary**:

    * ``system_binding`` — the exact governance-contracts ``AssessedSystemBinding``
      this assessment is about. ``None`` is representable so that "no binding was
      supplied" is a typed ``NOT_EVALUATED`` outcome rather than a constructor
      exception; there is no second, unbound orchestration path.
    * ``indicator_catalogs`` — the governed
      :class:`~..contracts.catalogs.ReadinessIndicatorCatalogSet` an indicator
      result must be recognized by. Binding a catalog for a family makes **no**
      family required: requirements come from the resolved policy's gates.

    Both participate in :meth:`canonical_digest` by canonical digest, so an
    assessment of one system configuration can never share a request fingerprint
    with an assessment of another.
    """

    assessment_id: str
    tenant_id: str
    subject_id: str
    context: AssessmentContext
    readiness_policy_ref: PolicyReference
    requested_target: ReadinessTarget
    evaluation_time: datetime
    gate_results: tuple[GateResult, ...] = ()
    conditions: tuple[ConditionSet, ...] = ()
    intelligence_results: tuple[IntelligenceFitnessResult, ...] = ()
    capability_results: tuple[CapabilityReadinessResult, ...] = ()
    adoption_results: tuple[AdoptionReadinessResult, ...] = ()
    advisory_composite: Optional[AdvisoryComposite] = None
    evidence_refs: tuple[str, ...] = ()
    assessment_window_ref: str = ""
    system_binding: Optional[AssessedSystemBinding] = None
    indicator_catalogs: Optional[ReadinessIndicatorCatalogSet] = None

    def __post_init__(self) -> None:
        _raise_as_assessment_error(
            require_nonempty, self.assessment_id, "ReadinessAssessmentRequest.assessment_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.tenant_id, "ReadinessAssessmentRequest.tenant_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.subject_id, "ReadinessAssessmentRequest.subject_id"
        )

        if not isinstance(self.context, AssessmentContext):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentRequest.context must be an AssessmentContext"
            )
        if self.context.tenant_id != self.tenant_id:
            raise ReadinessAssessmentError(
                f"cross-tenant request: context tenant {self.context.tenant_id!r} != "
                f"{self.tenant_id!r}"
            )
        if self.context.subject_id != self.subject_id:
            raise ReadinessAssessmentError(
                f"cross-subject request: context subject {self.context.subject_id!r} != "
                f"{self.subject_id!r}"
            )

        _require_readiness_ref(
            self.readiness_policy_ref, "ReadinessAssessmentRequest.readiness_policy_ref"
        )
        _require_target(self.requested_target, "ReadinessAssessmentRequest.requested_target")
        # Mandatory and timezone-aware. There is no default and no fallback: an
        # assessment instant is an input, never something this package invents.
        _raise_as_assessment_error(
            require_tzaware, self.evaluation_time, "ReadinessAssessmentRequest.evaluation_time"
        )

        self._normalize_sequence("gate_results", GateResult)
        self._normalize_sequence("conditions", ConditionSet)
        for field, expected in (
            ("intelligence_results", IntelligenceFitnessResult),
            ("capability_results", CapabilityReadinessResult),
            ("adoption_results", AdoptionReadinessResult),
        ):
            self._normalize_sequence(field, expected)
            self._check_indicator_binding(field)

        if self.advisory_composite is not None and not isinstance(
            self.advisory_composite, AdvisoryComposite
        ):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentRequest.advisory_composite must be an AdvisoryComposite"
            )
        object.__setattr__(
            self,
            "evidence_refs",
            _raise_as_assessment_error(
                normalize_tokens, self.evidence_refs, "ReadinessAssessmentRequest.evidence_refs"
            ),
        )
        _require_str(
            self.assessment_window_ref, "ReadinessAssessmentRequest.assessment_window_ref"
        )
        # M-3R.3 shapes are type-checked here and *semantically* checked by the
        # orchestrator, which emits stable typed gap codes for every mismatch
        # rather than raising — a caller must not be able to distinguish a
        # rejected binding from a rejected catalog by exception type.
        if self.system_binding is not None and not isinstance(
            self.system_binding, AssessedSystemBinding
        ):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentRequest.system_binding must be an AssessedSystemBinding"
            )
        if self.indicator_catalogs is not None and not isinstance(
            self.indicator_catalogs, ReadinessIndicatorCatalogSet
        ):
            raise ReadinessAssessmentError(
                "ReadinessAssessmentRequest.indicator_catalogs must be a "
                "ReadinessIndicatorCatalogSet"
            )

    # ------------------------------------------------------------------ #
    def _normalize_sequence(self, field: str, expected: type) -> None:
        coerced = _raise_as_assessment_error(
            coerce_tuple, getattr(self, field), f"ReadinessAssessmentRequest.{field}"
        )
        for item in coerced:
            if not isinstance(item, expected):
                raise ReadinessAssessmentError(
                    f"ReadinessAssessmentRequest.{field} entries must be {expected.__name__}"
                )
        object.__setattr__(self, field, coerced)

    def _check_indicator_binding(self, field: str) -> None:
        """Indicators keep their exact tenant / subject / context binding.

        Duplicate ``result_id``s are rejected too: two contradictory records for
        one indicator result are a self-contradiction, not an untrusted input.
        """

        seen: set[str] = set()
        for r in getattr(self, field):
            if r.tenant_id != self.tenant_id or r.subject_id != self.subject_id:
                raise ReadinessAssessmentError(
                    f"ReadinessAssessmentRequest.{field} contains a cross-tenant/subject result"
                )
            if r.context_id != self.context.context_id:
                raise ReadinessAssessmentError(
                    f"ReadinessAssessmentRequest.{field} result {r.result_id!r} is bound to a "
                    "different AssessmentContext"
                )
            if r.result_id in seen:
                raise ReadinessAssessmentError(
                    f"ReadinessAssessmentRequest.{field} duplicates result_id {r.result_id!r}"
                )
            seen.add(r.result_id)

    # ------------------------------------------------------------------ #
    @property
    def context_digest(self) -> str:
        """The bound context's canonical digest — the context binding token."""

        return self.context.canonical_digest()

    def canonical_digest(self) -> str:
        """A deterministic, **order-independent** sha-256 over the request.

        Component digests are sorted, so two requests that differ only in the
        order their gate results, conditions or indicator results were supplied
        produce the same digest. An input fingerprint — not evidence, not a
        signature, not an authenticity proof.
        """

        return _digest(
            {
                "assessment_id": self.assessment_id,
                "tenant_id": self.tenant_id,
                "subject_id": self.subject_id,
                "context": self.context.canonical_digest(),
                "readiness_policy_ref": self.readiness_policy_ref.canonical_digest(),
                "requested_target": self.requested_target.value,
                "evaluation_time": self.evaluation_time.isoformat(),
                "gate_results": sorted(g.canonical_digest() for g in self.gate_results),
                "conditions": sorted(c.canonical_digest() for c in self.conditions),
                "intelligence_results": sorted(
                    r.canonical_digest() for r in self.intelligence_results
                ),
                "capability_results": sorted(
                    r.canonical_digest() for r in self.capability_results
                ),
                "adoption_results": sorted(r.canonical_digest() for r in self.adoption_results),
                "advisory_composite": (
                    self.advisory_composite.canonical_digest()
                    if self.advisory_composite is not None
                    else None
                ),
                "evidence_refs": sorted(self.evidence_refs),
                "assessment_window_ref": self.assessment_window_ref,
                "system_binding": (
                    self.system_binding.canonical_digest()
                    if self.system_binding is not None
                    else None
                ),
                "indicator_catalogs": (
                    self.indicator_catalogs.canonical_digest()
                    if self.indicator_catalogs is not None
                    else None
                ),
            }
        )


# --------------------------------------------------------------------------- #
# Gate-result verification
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GateVerificationRequest:
    """The complete binding a gate-result verifier must attest against.

    ``policy_gate`` is the gate **as resolved through the Policy Authority
    boundary**, not the one the caller embedded — the orchestrator has already
    proven those are canonically identical before this request is built.
    """

    assessment_id: str
    tenant_id: str
    subject_id: str
    context_digest: str
    readiness_policy_ref: PolicyReference
    requested_target: ReadinessTarget
    evaluation_time: datetime
    policy_gate: PolicyGate
    gate_digest: str
    claimed_status: GateStatus
    gate_result_digest: str
    observed_claim_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    window_ref: str = ""

    def __post_init__(self) -> None:
        _raise_as_assessment_error(
            require_nonempty, self.assessment_id, "GateVerificationRequest.assessment_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.tenant_id, "GateVerificationRequest.tenant_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.subject_id, "GateVerificationRequest.subject_id"
        )
        _require_digest_token(self.context_digest, "GateVerificationRequest.context_digest")
        _require_readiness_ref(
            self.readiness_policy_ref, "GateVerificationRequest.readiness_policy_ref"
        )
        _require_target(self.requested_target, "GateVerificationRequest.requested_target")
        _raise_as_assessment_error(
            require_tzaware, self.evaluation_time, "GateVerificationRequest.evaluation_time"
        )
        if not isinstance(self.policy_gate, PolicyGate):
            raise ReadinessAssessmentError(
                "GateVerificationRequest.policy_gate must be a PolicyGate"
            )
        _require_digest_token(self.gate_digest, "GateVerificationRequest.gate_digest")
        if not isinstance(self.claimed_status, GateStatus):
            raise ReadinessAssessmentError(
                "GateVerificationRequest.claimed_status must be a GateStatus"
            )
        _require_digest_token(
            self.gate_result_digest, "GateVerificationRequest.gate_result_digest"
        )
        for name in ("observed_claim_refs", "evidence_refs", "reason_codes"):
            object.__setattr__(
                self,
                name,
                _raise_as_assessment_error(
                    normalize_tokens, getattr(self, name), f"GateVerificationRequest.{name}"
                ),
            )
        _require_str(self.window_ref, "GateVerificationRequest.window_ref")

    @property
    def gate_id(self) -> str:
        return self.policy_gate.gate_id

    def canonical_digest(self) -> str:
        return _digest(
            {
                "assessment_id": self.assessment_id,
                "tenant_id": self.tenant_id,
                "subject_id": self.subject_id,
                "context_digest": self.context_digest,
                "readiness_policy_ref": self.readiness_policy_ref.canonical_digest(),
                "requested_target": self.requested_target.value,
                "evaluation_time": self.evaluation_time.isoformat(),
                "gate_digest": self.gate_digest,
                "claimed_status": self.claimed_status.value,
                "gate_result_digest": self.gate_result_digest,
                "observed_claim_refs": sorted(self.observed_claim_refs),
                "evidence_refs": sorted(self.evidence_refs),
                "reason_codes": sorted(self.reason_codes),
                "window_ref": self.window_ref,
            }
        )


@dataclass(frozen=True)
class GateResultVerification:
    """A configured verifier's answer about one supplied ``GateResult``.

    The shape makes a dishonest answer harder to state than an honest one: a
    status other than
    :attr:`~ugence_agent_value_readiness.orchestration.codes.ReadinessInputVerificationStatus.VERIFIED`
    **cannot** carry a ``verified_status`` or any satisfied supporting-verification
    flag, and ``VERIFIED`` **must** carry the status it verified.

    Constructing one is not an attestation of anything: the orchestrator
    independently rechecks every coordinate below against what it asked for, and
    a mismatch rejects the gate result.
    """

    status: ReadinessInputVerificationStatus
    verifier_id: str
    gate_id: str
    gate_digest: str
    readiness_policy_ref: PolicyReference
    tenant_id: str
    subject_id: str
    context_digest: str
    requested_target: ReadinessTarget
    verified_at: datetime
    verified_status: Optional[GateStatus] = None
    evidence_verified: bool = False
    benchmark_resolved: bool = False
    threshold_evaluation_verified: bool = False
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReadinessInputVerificationStatus):
            raise ReadinessAssessmentError(
                "GateResultVerification.status must be a ReadinessInputVerificationStatus"
            )
        _raise_as_assessment_error(
            require_nonempty, self.verifier_id, "GateResultVerification.verifier_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.gate_id, "GateResultVerification.gate_id"
        )
        _require_digest_token(self.gate_digest, "GateResultVerification.gate_digest")
        _require_readiness_ref(
            self.readiness_policy_ref, "GateResultVerification.readiness_policy_ref"
        )
        _raise_as_assessment_error(
            require_nonempty, self.tenant_id, "GateResultVerification.tenant_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.subject_id, "GateResultVerification.subject_id"
        )
        _require_digest_token(self.context_digest, "GateResultVerification.context_digest")
        _require_target(self.requested_target, "GateResultVerification.requested_target")
        _raise_as_assessment_error(
            require_tzaware, self.verified_at, "GateResultVerification.verified_at"
        )
        if self.verified_status is not None and not isinstance(self.verified_status, GateStatus):
            raise ReadinessAssessmentError(
                "GateResultVerification.verified_status must be a GateStatus or None"
            )
        for name in ("evidence_verified", "benchmark_resolved", "threshold_evaluation_verified"):
            _require_bool(getattr(self, name), f"GateResultVerification.{name}")
        _require_str(self.detail, "GateResultVerification.detail")

        if self.status is ReadinessInputVerificationStatus.VERIFIED:
            if self.verified_status is None:
                raise ReadinessAssessmentError(
                    "a VERIFIED GateResultVerification must name the GateStatus it verified"
                )
        else:
            if self.verified_status is not None:
                raise ReadinessAssessmentError(
                    "a non-VERIFIED GateResultVerification must not carry a verified_status"
                )
            if (
                self.evidence_verified
                or self.benchmark_resolved
                or self.threshold_evaluation_verified
            ):
                raise ReadinessAssessmentError(
                    "a non-VERIFIED GateResultVerification must not claim any supporting "
                    "verification"
                )

    @property
    def is_verified(self) -> bool:
        return self.status is ReadinessInputVerificationStatus.VERIFIED

    def canonical_digest(self) -> str:
        return _digest(
            {
                "status": self.status.value,
                "verifier_id": self.verifier_id,
                "gate_id": self.gate_id,
                "gate_digest": self.gate_digest,
                "readiness_policy_ref": self.readiness_policy_ref.canonical_digest(),
                "tenant_id": self.tenant_id,
                "subject_id": self.subject_id,
                "context_digest": self.context_digest,
                "requested_target": self.requested_target.value,
                "verified_at": self.verified_at.isoformat(),
                "verified_status": (
                    self.verified_status.value if self.verified_status is not None else None
                ),
                "evidence_verified": self.evidence_verified,
                "benchmark_resolved": self.benchmark_resolved,
                "threshold_evaluation_verified": self.threshold_evaluation_verified,
                "detail": self.detail,
            }
        )


# --------------------------------------------------------------------------- #
# Condition verification
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ConditionVerificationRequest:
    """The complete binding a condition verifier must attest against.

    ``policy_gate`` is the exact conditional gate — resolved through the Policy
    Authority boundary — that this condition claims to compensate for. The
    verifier is therefore never asked whether a condition is "valid" in the
    abstract, only whether *this* control covers *this* concern for *this*
    tenant, subject and context at *this* instant.
    """

    assessment_id: str
    tenant_id: str
    subject_id: str
    context_digest: str
    readiness_policy_ref: PolicyReference
    requested_target: ReadinessTarget
    evaluation_time: datetime
    condition_id: str
    condition_digest: str
    source_gate_or_finding_ref: str
    policy_gate: PolicyGate
    gate_digest: str
    claimed_status: ConditionStatus
    approving_authority_ref: str = ""
    approved_mitigation_ref: str = ""
    accountable_owner: str = ""
    scope_exposure_limit: str = ""
    monitoring_requirement: str = ""
    revocation_trigger: str = ""
    evidence_refs: tuple[str, ...] = ()
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    expiry: Optional[datetime] = None

    def __post_init__(self) -> None:
        _raise_as_assessment_error(
            require_nonempty, self.assessment_id, "ConditionVerificationRequest.assessment_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.tenant_id, "ConditionVerificationRequest.tenant_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.subject_id, "ConditionVerificationRequest.subject_id"
        )
        _require_digest_token(self.context_digest, "ConditionVerificationRequest.context_digest")
        _require_readiness_ref(
            self.readiness_policy_ref, "ConditionVerificationRequest.readiness_policy_ref"
        )
        _require_target(self.requested_target, "ConditionVerificationRequest.requested_target")
        _raise_as_assessment_error(
            require_tzaware, self.evaluation_time, "ConditionVerificationRequest.evaluation_time"
        )
        _raise_as_assessment_error(
            require_nonempty, self.condition_id, "ConditionVerificationRequest.condition_id"
        )
        _require_digest_token(
            self.condition_digest, "ConditionVerificationRequest.condition_digest"
        )
        _raise_as_assessment_error(
            require_nonempty,
            self.source_gate_or_finding_ref,
            "ConditionVerificationRequest.source_gate_or_finding_ref",
        )
        if not isinstance(self.policy_gate, PolicyGate):
            raise ReadinessAssessmentError(
                "ConditionVerificationRequest.policy_gate must be a PolicyGate"
            )
        _require_digest_token(self.gate_digest, "ConditionVerificationRequest.gate_digest")
        if not isinstance(self.claimed_status, ConditionStatus):
            raise ReadinessAssessmentError(
                "ConditionVerificationRequest.claimed_status must be a ConditionStatus"
            )
        for name in (
            "approving_authority_ref",
            "approved_mitigation_ref",
            "accountable_owner",
            "scope_exposure_limit",
            "monitoring_requirement",
            "revocation_trigger",
        ):
            _require_str(getattr(self, name), f"ConditionVerificationRequest.{name}")
        object.__setattr__(
            self,
            "evidence_refs",
            _raise_as_assessment_error(
                normalize_tokens,
                self.evidence_refs,
                "ConditionVerificationRequest.evidence_refs",
            ),
        )
        for name in ("effective_from", "effective_to", "expiry"):
            value = getattr(self, name)
            if value is not None:
                _raise_as_assessment_error(
                    require_tzaware, value, f"ConditionVerificationRequest.{name}"
                )

    @property
    def covered_gate_id(self) -> str:
        return self.policy_gate.gate_id

    def canonical_digest(self) -> str:
        return _digest(
            {
                "assessment_id": self.assessment_id,
                "tenant_id": self.tenant_id,
                "subject_id": self.subject_id,
                "context_digest": self.context_digest,
                "readiness_policy_ref": self.readiness_policy_ref.canonical_digest(),
                "requested_target": self.requested_target.value,
                "evaluation_time": self.evaluation_time.isoformat(),
                "condition_id": self.condition_id,
                "condition_digest": self.condition_digest,
                "source_gate_or_finding_ref": self.source_gate_or_finding_ref,
                "gate_digest": self.gate_digest,
                "claimed_status": self.claimed_status.value,
                "evidence_refs": sorted(self.evidence_refs),
                "effective_from": _iso(self.effective_from),
                "effective_to": _iso(self.effective_to),
                "expiry": _iso(self.expiry),
            }
        )


@dataclass(frozen=True)
class ConditionSetVerification:
    """A configured verifier's answer about one supplied ``ConditionSet``.

    ``verified_status`` is the lifecycle status the verifier **independently**
    established — it is not the caller's label echoed back, and the orchestrator
    rejects the condition when the two disagree. The attested window
    (``effective_from`` / ``effective_to`` / ``expiry``) is likewise rechecked
    against the supplied record and re-evaluated at the evaluation instant under
    the merged half-open convention.

    A verified condition is still only *coverage* when its verified status is
    ``APPROVED_ACTIVE`` and it is active at that instant: verification and
    coverage are deliberately different questions.
    """

    status: ReadinessInputVerificationStatus
    verifier_id: str
    condition_id: str
    condition_digest: str
    source_gate_or_finding_ref: str
    covered_gate_id: str
    gate_digest: str
    readiness_policy_ref: PolicyReference
    tenant_id: str
    subject_id: str
    context_digest: str
    requested_target: ReadinessTarget
    verified_at: datetime
    verified_status: Optional[ConditionStatus] = None
    approval_authority_verified: bool = False
    approval_evidence_verified: bool = False
    owner_and_monitoring_verified: bool = False
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    expiry: Optional[datetime] = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReadinessInputVerificationStatus):
            raise ReadinessAssessmentError(
                "ConditionSetVerification.status must be a ReadinessInputVerificationStatus"
            )
        _raise_as_assessment_error(
            require_nonempty, self.verifier_id, "ConditionSetVerification.verifier_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.condition_id, "ConditionSetVerification.condition_id"
        )
        _require_digest_token(self.condition_digest, "ConditionSetVerification.condition_digest")
        _raise_as_assessment_error(
            require_nonempty,
            self.source_gate_or_finding_ref,
            "ConditionSetVerification.source_gate_or_finding_ref",
        )
        _raise_as_assessment_error(
            require_nonempty, self.covered_gate_id, "ConditionSetVerification.covered_gate_id"
        )
        _require_digest_token(self.gate_digest, "ConditionSetVerification.gate_digest")
        _require_readiness_ref(
            self.readiness_policy_ref, "ConditionSetVerification.readiness_policy_ref"
        )
        _raise_as_assessment_error(
            require_nonempty, self.tenant_id, "ConditionSetVerification.tenant_id"
        )
        _raise_as_assessment_error(
            require_nonempty, self.subject_id, "ConditionSetVerification.subject_id"
        )
        _require_digest_token(self.context_digest, "ConditionSetVerification.context_digest")
        _require_target(self.requested_target, "ConditionSetVerification.requested_target")
        _raise_as_assessment_error(
            require_tzaware, self.verified_at, "ConditionSetVerification.verified_at"
        )
        if self.verified_status is not None and not isinstance(
            self.verified_status, ConditionStatus
        ):
            raise ReadinessAssessmentError(
                "ConditionSetVerification.verified_status must be a ConditionStatus or None"
            )
        for name in (
            "approval_authority_verified",
            "approval_evidence_verified",
            "owner_and_monitoring_verified",
        ):
            _require_bool(getattr(self, name), f"ConditionSetVerification.{name}")
        for name in ("effective_from", "effective_to", "expiry"):
            value = getattr(self, name)
            if value is not None:
                _raise_as_assessment_error(
                    require_tzaware, value, f"ConditionSetVerification.{name}"
                )
        _require_str(self.detail, "ConditionSetVerification.detail")

        if self.status is ReadinessInputVerificationStatus.VERIFIED:
            if self.verified_status is None:
                raise ReadinessAssessmentError(
                    "a VERIFIED ConditionSetVerification must name the ConditionStatus it verified"
                )
        else:
            if self.verified_status is not None:
                raise ReadinessAssessmentError(
                    "a non-VERIFIED ConditionSetVerification must not carry a verified_status"
                )
            if (
                self.approval_authority_verified
                or self.approval_evidence_verified
                or self.owner_and_monitoring_verified
            ):
                raise ReadinessAssessmentError(
                    "a non-VERIFIED ConditionSetVerification must not claim any approval or "
                    "monitoring verification"
                )

    @property
    def is_verified(self) -> bool:
        return self.status is ReadinessInputVerificationStatus.VERIFIED

    def canonical_digest(self) -> str:
        return _digest(
            {
                "status": self.status.value,
                "verifier_id": self.verifier_id,
                "condition_id": self.condition_id,
                "condition_digest": self.condition_digest,
                "source_gate_or_finding_ref": self.source_gate_or_finding_ref,
                "covered_gate_id": self.covered_gate_id,
                "gate_digest": self.gate_digest,
                "readiness_policy_ref": self.readiness_policy_ref.canonical_digest(),
                "tenant_id": self.tenant_id,
                "subject_id": self.subject_id,
                "context_digest": self.context_digest,
                "requested_target": self.requested_target.value,
                "verified_at": self.verified_at.isoformat(),
                "verified_status": (
                    self.verified_status.value if self.verified_status is not None else None
                ),
                "approval_authority_verified": self.approval_authority_verified,
                "approval_evidence_verified": self.approval_evidence_verified,
                "owner_and_monitoring_verified": self.owner_and_monitoring_verified,
                "effective_from": _iso(self.effective_from),
                "effective_to": _iso(self.effective_to),
                "expiry": _iso(self.expiry),
                "detail": self.detail,
            }
        )
