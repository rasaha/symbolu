"""Intelligence / Capability / Adoption readiness indicator results (ADR §10).

Three **distinct** non-financial leading-indicator result types. Each binds a
GV-2E-a :class:`MetricClaim` **by value** (preserving all five orthogonal
evidence axes), the assessed ``tenant_id``/``subject_id``, the
``AssessmentContext`` it was produced under, the intended task/outcome, the
governing requirement class and applicable targets, and a **recorded** gate
status (supplied by an upstream evaluator — never computed here).

None carries money, currency, cost, benefit, or ROI. A policy *requirement* for
evidence never manufactures evidence, and embedding a claim never elevates its
axes: whatever attestation/attribution/verification the claim carries is exactly
what it carried before.

M-3R.3 adds three **appended, optional** identity fields to each result:

* ``indicator_id`` — the stable id of the governed catalog definition this
  result claims to report against (see :mod:`~.catalogs`);
* ``system_binding_ref`` / ``system_binding_digest`` — the
  :class:`~.binding.AssessedSystemBinding` the result was produced against,
  co-required as a pair (both or neither).

All three default to absent, so every M-3R.1 / M-3R.2 construction remains valid
and the standalone evaluator is untouched. The orchestration boundary
**requires** them on its bound path: a result naming no catalog definition, or
carrying a different system binding, is either unrecognized vocabulary or a
replay from another system version or configuration, and is excluded there
rather than silently evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import BenchmarkReference, MetricClaim
from ugence_uvi_policy_contracts.api import ReadinessTarget, RequirementClass

from ._util import (
    canonical_digest,
    coerce_tuple,
    normalize_tokens,
    require_nonempty,
    require_tzaware,
    validate_digest,
)
from .enums import (
    AdoptionDimension,
    CapabilityDemonstration,
    CapabilityDimension,
    GateStatus,
    IntelligenceDimension,
    ReadinessIndicatorClass,
)
from .errors import ReadinessContractError

__all__ = [
    "IntelligenceFitnessResult",
    "CapabilityReadinessResult",
    "AdoptionReadinessResult",
]


def _normalize_targets(value, owner: str) -> tuple[ReadinessTarget, ...]:
    coerced = coerce_tuple(value, f"{owner}.applicable_targets")
    if not coerced:
        raise ReadinessContractError(f"{owner}.applicable_targets must name at least one target")
    seen: set[ReadinessTarget] = set()
    for t in coerced:
        if not isinstance(t, ReadinessTarget):
            raise ReadinessContractError(f"{owner}.applicable_targets entries must be ReadinessTarget")
        if t in seen:
            raise ReadinessContractError(f"{owner}.applicable_targets duplicates {t.value}")
        seen.add(t)
    return coerced


def _validate_common(self, owner: str) -> None:
    """Validate + normalize the fields common to every indicator result."""

    require_nonempty(self.result_id, f"{owner}.result_id")
    require_nonempty(self.tenant_id, f"{owner}.tenant_id")
    require_nonempty(self.subject_id, f"{owner}.subject_id")
    require_nonempty(self.context_id, f"{owner}.context_id")
    require_nonempty(self.task_or_outcome_ref, f"{owner}.task_or_outcome_ref")

    if not isinstance(self.claim, MetricClaim):
        raise ReadinessContractError(f"{owner}.claim must be a governance-contracts MetricClaim")
    # Cross-tenant / cross-subject binding: the evidence claim must belong to the
    # same subject and tenant this readiness result is about.
    if self.claim.tenant_id != self.tenant_id:
        raise ReadinessContractError(
            f"{owner} cross-tenant binding: claim tenant {self.claim.tenant_id!r} != {self.tenant_id!r}"
        )
    if self.claim.subject_id != self.subject_id:
        raise ReadinessContractError(
            f"{owner} cross-subject binding: claim subject {self.claim.subject_id!r} != {self.subject_id!r}"
        )
    if not isinstance(self.requirement_class, RequirementClass):
        raise ReadinessContractError(f"{owner}.requirement_class must be a RequirementClass")
    if self.benchmark_ref is not None and not isinstance(self.benchmark_ref, BenchmarkReference):
        raise ReadinessContractError(f"{owner}.benchmark_ref must be a BenchmarkReference")
    if self.threshold_ref and self.benchmark_ref is not None:
        raise ReadinessContractError(
            f"{owner} may reference a threshold literal or a benchmark, not both"
        )
    object.__setattr__(self, "applicable_targets", _normalize_targets(self.applicable_targets, owner))
    object.__setattr__(self, "evidence_refs", normalize_tokens(self.evidence_refs, f"{owner}.evidence_refs"))
    object.__setattr__(self, "reason_codes", normalize_tokens(self.reason_codes, f"{owner}.reason_codes"))
    if self.evaluated_at is not None:
        require_tzaware(self.evaluated_at, f"{owner}.evaluated_at")
    _validate_system_binding(self, owner)


def _validate_system_binding(self, owner: str) -> None:
    """Normalize the optional assessed-system binding identity (M-3R.3).

    The pair is co-required: a binding reference without its canonical digest
    could be pointed at any system, and a digest without a reference names
    nothing. Absent means "this result declares no system binding" — which the
    orchestration boundary refuses on its bound path.
    """

    indicator_id = getattr(self, "indicator_id")
    if not isinstance(indicator_id, str):
        raise ReadinessContractError(f"{owner}.indicator_id must be a string")
    object.__setattr__(self, "indicator_id", indicator_id.strip())

    for name in ("system_binding_ref", "system_binding_digest"):
        value = getattr(self, name)
        if not isinstance(value, str):
            raise ReadinessContractError(f"{owner}.{name} must be a string")
        object.__setattr__(self, name, value.strip())
    validate_digest(self.system_binding_digest, f"{owner}.system_binding_digest", required=False)
    if bool(self.system_binding_ref) != bool(self.system_binding_digest):
        raise ReadinessContractError(
            f"{owner}.system_binding_ref and .system_binding_digest are co-required: a result "
            "either declares the exact assessed system it was produced against, or declares none"
        )


@dataclass(frozen=True)
class IntelligenceFitnessResult:
    """A task/outcome-specific Intelligence-fitness indicator result (ADR §10)."""

    result_id: str
    tenant_id: str
    subject_id: str
    context_id: str
    task_or_outcome_ref: str
    dimension: IntelligenceDimension
    claim: MetricClaim
    requirement_class: RequirementClass
    applicable_targets: tuple[ReadinessTarget, ...]
    status: GateStatus
    threshold_ref: str = ""
    benchmark_ref: Optional[BenchmarkReference] = None
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    evaluated_at: Optional[datetime] = None
    indicator_id: str = ""
    system_binding_ref: str = ""
    system_binding_digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, IntelligenceDimension):
            raise ReadinessContractError("IntelligenceFitnessResult.dimension must be an IntelligenceDimension")
        _validate_status(self.status, "IntelligenceFitnessResult")
        _validate_common(self, "IntelligenceFitnessResult")

    @property
    def indicator_class(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.INTELLIGENCE

    @property
    def system_bound(self) -> bool:
        """Whether this result names the exact assessed system it describes."""

        return bool(self.system_binding_ref and self.system_binding_digest)

    @property
    def catalog_bound(self) -> bool:
        """Whether this result names the governed indicator definition it claims."""

        return bool(self.indicator_id)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class CapabilityReadinessResult:
    """A Capability-readiness indicator result (ADR §9, §10).

    Distinguishes *exists* / *tested* / *met the policy threshold*
    (``demonstration``), whether the evidence was sufficient
    (``evidence_sufficient``), and whether the capability is mandatory for the
    requested target (``requirement_class`` + ``applicable_targets``). A missing
    critical capability is representable as ``requirement_class=MANDATORY`` with
    ``demonstration=NOT_PRESENT`` / ``status=FAIL`` — a mandatory blocking
    failure that no strength elsewhere can average away.
    """

    result_id: str
    tenant_id: str
    subject_id: str
    context_id: str
    task_or_outcome_ref: str
    dimension: CapabilityDimension
    claim: MetricClaim
    requirement_class: RequirementClass
    applicable_targets: tuple[ReadinessTarget, ...]
    status: GateStatus
    demonstration: CapabilityDemonstration
    evidence_sufficient: bool
    threshold_ref: str = ""
    benchmark_ref: Optional[BenchmarkReference] = None
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    evaluated_at: Optional[datetime] = None
    indicator_id: str = ""
    system_binding_ref: str = ""
    system_binding_digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, CapabilityDimension):
            raise ReadinessContractError("CapabilityReadinessResult.dimension must be a CapabilityDimension")
        if not isinstance(self.demonstration, CapabilityDemonstration):
            raise ReadinessContractError("CapabilityReadinessResult.demonstration must be a CapabilityDemonstration")
        if not isinstance(self.evidence_sufficient, bool):
            raise ReadinessContractError("CapabilityReadinessResult.evidence_sufficient must be a bool")
        _validate_status(self.status, "CapabilityReadinessResult")
        _validate_common(self, "CapabilityReadinessResult")

    @property
    def indicator_class(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.CAPABILITY

    @property
    def system_bound(self) -> bool:
        """Whether this result names the exact assessed system it describes."""

        return bool(self.system_binding_ref and self.system_binding_digest)

    @property
    def catalog_bound(self) -> bool:
        """Whether this result names the governed indicator definition it claims."""

        return bool(self.indicator_id)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class AdoptionReadinessResult:
    """A **pre-deployment** Adoption-readiness indicator result (ADR §10).

    ``pre_deployment`` is structurally locked to ``True``: this type represents
    *predicted* adoption readiness and can never be relabelled as post-deployment
    ``ObservedAdoption`` (a distinct GV-3+ evidence class not defined here). The
    underlying claim may draw on surveys, pilots, historical analogues, synthetic
    evaluations, or modeled values under GV-2E-a's restrictions, but this result
    is never observed realized adoption and never monetary benefit.
    """

    result_id: str
    tenant_id: str
    subject_id: str
    context_id: str
    task_or_outcome_ref: str
    dimension: AdoptionDimension
    claim: MetricClaim
    requirement_class: RequirementClass
    applicable_targets: tuple[ReadinessTarget, ...]
    status: GateStatus
    pre_deployment: bool = True
    threshold_ref: str = ""
    benchmark_ref: Optional[BenchmarkReference] = None
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    evaluated_at: Optional[datetime] = None
    indicator_id: str = ""
    system_binding_ref: str = ""
    system_binding_digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, AdoptionDimension):
            raise ReadinessContractError("AdoptionReadinessResult.dimension must be an AdoptionDimension")
        if self.pre_deployment is not True:
            raise ReadinessContractError(
                "AdoptionReadinessResult.pre_deployment must be True — adoption readiness is a "
                "pre-deployment prediction, never post-deployment ObservedAdoption"
            )
        _validate_status(self.status, "AdoptionReadinessResult")
        _validate_common(self, "AdoptionReadinessResult")

    @property
    def indicator_class(self) -> ReadinessIndicatorClass:
        return ReadinessIndicatorClass.ADOPTION

    @property
    def system_bound(self) -> bool:
        """Whether this result names the exact assessed system it describes."""

        return bool(self.system_binding_ref and self.system_binding_digest)

    @property
    def catalog_bound(self) -> bool:
        """Whether this result names the governed indicator definition it claims."""

        return bool(self.indicator_id)

    def canonical_digest(self) -> str:
        return canonical_digest(self)


def _validate_status(status, owner: str) -> None:
    if not isinstance(status, GateStatus):
        raise ReadinessContractError(f"{owner}.status must be a GateStatus")
