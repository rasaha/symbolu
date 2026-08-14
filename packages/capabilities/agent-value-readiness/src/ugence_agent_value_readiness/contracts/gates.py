"""Gate evaluation records (ADR §6, §7).

A :class:`GateResult` **references** an existing ``PolicyGate`` (by ``gate_id``
inside a signed ``ReadinessPolicy`` :class:`PolicyReference`) and records the
outcome an upstream evaluator produced. It does **not** redefine a gate and does
**not** compute the outcome. It preserves the requested target, whether the gate
was applicable to that target, and (crucially) that a **non-applicable gate is
diagnostic only** — a diagnostic production-gate FAIL never blocks a PILOT
target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import BenchmarkReference
from ugence_uvi_policy_contracts.api import (
    PolicyFamily,
    PolicyReference,
    ReadinessTarget,
    RequirementClass,
)

from ._util import canonical_digest, normalize_tokens, require_nonempty, require_tzaware
from .enums import GateStatus
from .errors import ReadinessContractError

__all__ = ["GateResult"]


@dataclass(frozen=True)
class GateResult:
    """A recorded evaluation of one policy gate against a requested target."""

    gate_id: str
    readiness_policy_ref: PolicyReference
    gate_kind: RequirementClass
    requested_target: ReadinessTarget
    applicable: bool
    status: GateStatus
    observed_claim_refs: tuple[str, ...] = ()
    threshold_ref: str = ""
    benchmark_ref: Optional[BenchmarkReference] = None
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    window_ref: str = ""
    evaluated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        require_nonempty(self.gate_id, "GateResult.gate_id")
        if not isinstance(self.readiness_policy_ref, PolicyReference):
            raise ReadinessContractError("GateResult.readiness_policy_ref must be a PolicyReference")
        if self.readiness_policy_ref.policy_family is not PolicyFamily.READINESS:
            raise ReadinessContractError(
                "GateResult.readiness_policy_ref must reference a READINESS policy "
                f"(got {self.readiness_policy_ref.policy_family.value})"
            )
        if not isinstance(self.gate_kind, RequirementClass):
            raise ReadinessContractError("GateResult.gate_kind must be a RequirementClass")
        if not isinstance(self.requested_target, ReadinessTarget):
            raise ReadinessContractError("GateResult.requested_target must be a ReadinessTarget")
        if not isinstance(self.applicable, bool):
            raise ReadinessContractError("GateResult.applicable must be a bool")
        if not isinstance(self.status, GateStatus):
            raise ReadinessContractError("GateResult.status must be a GateStatus")
        if self.benchmark_ref is not None and not isinstance(self.benchmark_ref, BenchmarkReference):
            raise ReadinessContractError("GateResult.benchmark_ref must be a BenchmarkReference")
        if self.threshold_ref and self.benchmark_ref is not None:
            raise ReadinessContractError("GateResult may reference a threshold literal or a benchmark, not both")
        object.__setattr__(self, "observed_claim_refs", normalize_tokens(self.observed_claim_refs, "GateResult.observed_claim_refs"))
        object.__setattr__(self, "evidence_refs", normalize_tokens(self.evidence_refs, "GateResult.evidence_refs"))
        object.__setattr__(self, "reason_codes", normalize_tokens(self.reason_codes, "GateResult.reason_codes"))
        if self.evaluated_at is not None:
            require_tzaware(self.evaluated_at, "GateResult.evaluated_at")

    @property
    def is_diagnostic(self) -> bool:
        """A gate not applicable to the requested target is diagnostic only."""

        return not self.applicable

    @property
    def is_blocking(self) -> bool:
        """A blocking gate: applicable, mandatory, and failed.

        A diagnostic (non-applicable) gate is **never** blocking, even on FAIL —
        so a production-only gate cannot block a PILOT target. This is a recorded
        structural property, not the precedence decision (which is GV-3R-b).
        """

        return (
            self.applicable
            and self.gate_kind is RequirementClass.MANDATORY
            and self.status is GateStatus.FAIL
        )

    @property
    def is_applicable_mandatory_indeterminate(self) -> bool:
        return (
            self.applicable
            and self.gate_kind is RequirementClass.MANDATORY
            and self.status is GateStatus.INDETERMINATE
        )

    def canonical_digest(self) -> str:
        return canonical_digest(self)
