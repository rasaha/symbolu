"""The agent-value readiness determination envelope (ADR §6, §7, §14).

An **advisory, non-financial** readiness determination for one agent
(``subject_id``) against one requested target, under a governed
``AssessmentContext`` + ``ReadinessPolicy``. It carries the Intelligence,
Capability, and Adoption indicator results, the applicable and diagnostic gate
results, condition records, an optional advisory composite, and the recorded
classification.

Constructing this record proves **local structural consistency only**. It does
**not** compute the classification from the gate results — the ratified
FAIL/INDETERMINATE precedence calculus and tier selection belong to the GV-3R-b
evaluator. And it is **never** an authorization to deploy: it is consumed by a
separate human/deployment-governance process.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    PolicyFamily,
    PolicyReference,
    PolicyScope,
    ReadinessTarget,
)

from ._util import (
    canonical_digest,
    coerce_tuple,
    normalize_tokens,
    require_nonempty,
    require_tzaware,
    validate_digest,
)
from .composite import AdvisoryComposite
from .conditions import ConditionSet
from .enums import ReadinessClassification
from .errors import ReadinessContractError
from .gates import GateResult
from .indicators import (
    AdoptionReadinessResult,
    CapabilityReadinessResult,
    IntelligenceFitnessResult,
)

__all__ = ["AgentValueReadinessDetermination"]

_READY_CLASSES = (
    ReadinessClassification.PILOT_READY,
    ReadinessClassification.READY_WITH_CONDITIONS,
    ReadinessClassification.DEPLOYMENT_READY,
)


@dataclass(frozen=True)
class AgentValueReadinessDetermination:
    """An advisory agent-value readiness determination (contracts only)."""

    assessment_id: str
    tenant_id: str
    subject_id: str
    context: AssessmentContext
    readiness_policy_ref: PolicyReference
    requested_target: ReadinessTarget
    classification: ReadinessClassification
    created_at: datetime
    intelligence_results: tuple[IntelligenceFitnessResult, ...] = ()
    capability_results: tuple[CapabilityReadinessResult, ...] = ()
    adoption_results: tuple[AdoptionReadinessResult, ...] = ()
    gate_results: tuple[GateResult, ...] = ()
    conditions: tuple[ConditionSet, ...] = ()
    blocking_gate_ids: tuple[str, ...] = ()
    indeterminate_gate_ids: tuple[str, ...] = ()
    advisory_composite: Optional[AdvisoryComposite] = None
    reason_codes: tuple[str, ...] = ()
    evidence_digest: str = ""

    def __post_init__(self) -> None:
        require_nonempty(self.assessment_id, "AgentValueReadinessDetermination.assessment_id")
        require_nonempty(self.tenant_id, "AgentValueReadinessDetermination.tenant_id")
        require_nonempty(self.subject_id, "AgentValueReadinessDetermination.subject_id")

        # -- context + policy binding, tenant/subject consistency -----------
        if not isinstance(self.context, AssessmentContext):
            raise ReadinessContractError("determination.context must be an AssessmentContext")
        if self.context.tenant_id != self.tenant_id:
            raise ReadinessContractError(
                f"cross-tenant: context tenant {self.context.tenant_id!r} != {self.tenant_id!r}"
            )
        if self.context.subject_id != self.subject_id:
            raise ReadinessContractError(
                f"cross-subject: context subject {self.context.subject_id!r} != {self.subject_id!r}"
            )
        if not isinstance(self.readiness_policy_ref, PolicyReference):
            raise ReadinessContractError("determination.readiness_policy_ref must be a PolicyReference")
        if self.readiness_policy_ref.policy_family is not PolicyFamily.READINESS:
            raise ReadinessContractError("determination.readiness_policy_ref must reference a READINESS policy")
        if self.readiness_policy_ref.scope is PolicyScope.TENANT and self.readiness_policy_ref.tenant_id != self.tenant_id:
            raise ReadinessContractError("determination.readiness_policy_ref belongs to a different tenant")
        if not isinstance(self.requested_target, ReadinessTarget):
            raise ReadinessContractError("determination.requested_target must be a ReadinessTarget")
        if not isinstance(self.classification, ReadinessClassification):
            raise ReadinessContractError("determination.classification must be a ReadinessClassification")
        require_tzaware(self.created_at, "determination.created_at")
        if self.advisory_composite is not None and not isinstance(self.advisory_composite, AdvisoryComposite):
            raise ReadinessContractError("determination.advisory_composite must be an AdvisoryComposite")

        # -- normalize + type-check nested result sequences -----------------
        self._check_results("intelligence_results", IntelligenceFitnessResult)
        self._check_results("capability_results", CapabilityReadinessResult)
        self._check_results("adoption_results", AdoptionReadinessResult)
        self._check_gates()
        self._check_conditions()
        object.__setattr__(self, "reason_codes", normalize_tokens(self.reason_codes, "determination.reason_codes"))
        validate_digest(self.evidence_digest, "determination.evidence_digest", required=False)

        # -- blocking / indeterminate references point at real applicable gates
        gates_by_id = {g.gate_id: g for g in self.gate_results}
        object.__setattr__(self, "blocking_gate_ids", normalize_tokens(self.blocking_gate_ids, "determination.blocking_gate_ids"))
        object.__setattr__(self, "indeterminate_gate_ids", normalize_tokens(self.indeterminate_gate_ids, "determination.indeterminate_gate_ids"))
        for gid in self.blocking_gate_ids:
            g = gates_by_id.get(gid)
            if g is None:
                raise ReadinessContractError(f"blocking_gate_ids references unknown gate {gid!r}")
            if not g.is_blocking:
                raise ReadinessContractError(
                    f"blocking_gate_ids references gate {gid!r} that is not an applicable mandatory FAIL "
                    "(a diagnostic/non-applicable gate can never be a blocker)"
                )
        for gid in self.indeterminate_gate_ids:
            g = gates_by_id.get(gid)
            if g is None:
                raise ReadinessContractError(f"indeterminate_gate_ids references unknown gate {gid!r}")
            if not g.is_applicable_mandatory_indeterminate:
                raise ReadinessContractError(
                    f"indeterminate_gate_ids references gate {gid!r} that is not an applicable mandatory INDETERMINATE"
                )

        self._check_classification_consistency()

    # ------------------------------------------------------------------ #
    def _check_results(self, field: str, expected) -> None:
        coerced = coerce_tuple(getattr(self, field), f"determination.{field}")
        seen: set[str] = set()
        for r in coerced:
            if not isinstance(r, expected):
                raise ReadinessContractError(f"determination.{field} entries must be {expected.__name__}")
            if r.tenant_id != self.tenant_id or r.subject_id != self.subject_id:
                raise ReadinessContractError(f"determination.{field} contains a cross-tenant/subject result")
            if r.context_id != self.context.context_id:
                raise ReadinessContractError(f"determination.{field} result is bound to a different AssessmentContext")
            if r.result_id in seen:
                raise ReadinessContractError(f"determination.{field} duplicates result_id {r.result_id!r}")
            seen.add(r.result_id)
        object.__setattr__(self, field, coerced)

    def _check_gates(self) -> None:
        coerced = coerce_tuple(self.gate_results, "determination.gate_results")
        seen: set[str] = set()
        for g in coerced:
            if not isinstance(g, GateResult):
                raise ReadinessContractError("determination.gate_results entries must be GateResult")
            if g.requested_target is not self.requested_target:
                raise ReadinessContractError(
                    f"determination.gate_results gate {g.gate_id!r} was evaluated for "
                    f"{g.requested_target.value}, not the requested {self.requested_target.value}"
                )
            if g.gate_id in seen:
                raise ReadinessContractError(f"determination.gate_results duplicates gate_id {g.gate_id!r}")
            seen.add(g.gate_id)
        object.__setattr__(self, "gate_results", coerced)

    def _check_conditions(self) -> None:
        coerced = coerce_tuple(self.conditions, "determination.conditions")
        seen: set[str] = set()
        for c in coerced:
            if not isinstance(c, ConditionSet):
                raise ReadinessContractError("determination.conditions entries must be ConditionSet")
            if c.condition_id in seen:
                raise ReadinessContractError(f"determination.conditions duplicates condition_id {c.condition_id!r}")
            seen.add(c.condition_id)
        object.__setattr__(self, "conditions", coerced)

    def _check_classification_consistency(self) -> None:
        """Reject obviously-contradictory records (ADR §6, §7, §14).

        This is a *local* consistency guard, NOT the precedence selector: it does
        not compute the classification from the gates — it only refuses records
        that contradict themselves.
        """

        cls = self.classification
        tgt = self.requested_target

        if cls is ReadinessClassification.PILOT_READY and tgt is not ReadinessTarget.PILOT:
            raise ReadinessContractError("PILOT_READY requires requested_target=PILOT")
        if cls is ReadinessClassification.DEPLOYMENT_READY and tgt is not ReadinessTarget.PRODUCTION:
            raise ReadinessContractError("DEPLOYMENT_READY requires requested_target=PRODUCTION")
        if cls is ReadinessClassification.READY_WITH_CONDITIONS:
            if tgt is not ReadinessTarget.PRODUCTION:
                raise ReadinessContractError("READY_WITH_CONDITIONS requires requested_target=PRODUCTION")
            if not self.conditions:
                raise ReadinessContractError("READY_WITH_CONDITIONS requires at least one condition reference")

        # No ready classification may co-exist with an applicable mandatory
        # FAIL or INDETERMINATE.
        if cls in _READY_CLASSES:
            if self.blocking_gate_ids:
                raise ReadinessContractError(f"{cls.value} cannot carry blocking (applicable mandatory FAIL) gates")
            if self.indeterminate_gate_ids:
                raise ReadinessContractError(f"{cls.value} cannot carry applicable mandatory INDETERMINATE gates")

        if cls is ReadinessClassification.NOT_READY:
            if not (self.blocking_gate_ids or self.reason_codes):
                raise ReadinessContractError("NOT_READY requires a blocking gate reference or a reason code")
        if cls is ReadinessClassification.NOT_ASSESSABLE:
            if not (self.indeterminate_gate_ids or self.reason_codes):
                raise ReadinessContractError(
                    "NOT_ASSESSABLE requires an indeterminate gate reference or a context/evidence reason code"
                )

    # ------------------------------------------------------------------ #
    @property
    def is_advisory(self) -> bool:
        """Always advisory — this determination is never a deployment authorization."""

        return True

    @property
    def diagnostic_gate_ids(self) -> tuple[str, ...]:
        """Gate ids that were not applicable to the requested target (diagnostic only)."""

        return tuple(g.gate_id for g in self.gate_results if g.is_diagnostic)

    def canonical_digest(self) -> str:
        return canonical_digest(self)
