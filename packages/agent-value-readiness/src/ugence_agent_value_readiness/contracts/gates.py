"""Gate evaluation records (ADR §6, §7).

A :class:`GateResult` records the outcome an upstream evaluator produced for one
policy gate. To make the policy-owned facts **non-forgeable**, it embeds the
actual immutable :class:`PolicyGate` **by value** and *derives*
``gate_id`` / gate kind / target applicability / diagnostic-vs-blocking / owned
threshold from it. The caller supplies only the recorded ``status`` (and
evidence/observation references) — it cannot independently relabel a mandatory
gate as advisory, mark an applicable gate diagnostic, or swap the gate's
threshold.

This binds the gate metadata *internally*; it does **not** prove the embedded
``PolicyGate`` is itself authentic or authority-approved — that is
Policy-Authority / GV-3R-b work, out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import (
    GovernedThreshold,
    PolicyFamily,
    PolicyGate,
    PolicyReference,
    ReadinessTarget,
    RequirementClass,
)

from ._util import canonical_digest, normalize_tokens, require_tzaware
from .enums import GateStatus
from .errors import ReadinessContractError

__all__ = ["GateResult"]


@dataclass(frozen=True)
class GateResult:
    """A recorded evaluation of one policy gate against a requested target.

    ``policy_gate`` is the authoritative source of the gate's identity, kind, and
    applicability — those are **not** separate caller-settable fields, so they
    cannot be forged. ``requested_target`` and ``status`` are the recorded
    evaluation inputs.
    """

    policy_gate: PolicyGate
    readiness_policy_ref: PolicyReference
    requested_target: ReadinessTarget
    status: GateStatus
    observed_claim_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    window_ref: str = ""
    evaluated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.policy_gate, PolicyGate):
            raise ReadinessContractError("GateResult.policy_gate must be a PolicyGate")
        if not isinstance(self.readiness_policy_ref, PolicyReference):
            raise ReadinessContractError("GateResult.readiness_policy_ref must be a PolicyReference")
        if self.readiness_policy_ref.policy_family is not PolicyFamily.READINESS:
            raise ReadinessContractError(
                "GateResult.readiness_policy_ref must reference a READINESS policy "
                f"(got {self.readiness_policy_ref.policy_family.value})"
            )
        if not isinstance(self.requested_target, ReadinessTarget):
            raise ReadinessContractError("GateResult.requested_target must be a ReadinessTarget")
        if not isinstance(self.status, GateStatus):
            raise ReadinessContractError("GateResult.status must be a GateStatus")
        object.__setattr__(self, "observed_claim_refs", normalize_tokens(self.observed_claim_refs, "GateResult.observed_claim_refs"))
        object.__setattr__(self, "evidence_refs", normalize_tokens(self.evidence_refs, "GateResult.evidence_refs"))
        object.__setattr__(self, "reason_codes", normalize_tokens(self.reason_codes, "GateResult.reason_codes"))
        if self.evaluated_at is not None:
            require_tzaware(self.evaluated_at, "GateResult.evaluated_at")

    # ---- policy-owned facts, DERIVED (never caller-settable) ----------- #
    @property
    def gate_id(self) -> str:
        return self.policy_gate.gate_id

    @property
    def gate_kind(self) -> RequirementClass:
        return self.policy_gate.requirement_class

    @property
    def threshold(self) -> Optional[GovernedThreshold]:
        return self.policy_gate.threshold

    @property
    def applicable(self) -> bool:
        """Applicability derived from the gate's own ``applicability`` set."""

        return self.requested_target in self.policy_gate.applicability

    @property
    def is_diagnostic(self) -> bool:
        """A gate not applicable to the requested target is diagnostic only."""

        return not self.applicable

    @property
    def is_blocking(self) -> bool:
        """Applicable + mandatory + FAIL. A diagnostic gate is never blocking."""

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

    @property
    def is_applicable_conditional_unresolved(self) -> bool:
        """Applicable CONDITIONAL gate whose status is FAIL or INDETERMINATE.

        An unresolved conditional concern — the kind that a ``ConditionSet`` may
        (only) compensate for.
        """

        return (
            self.applicable
            and self.gate_kind is RequirementClass.CONDITIONAL
            and self.status in (GateStatus.FAIL, GateStatus.INDETERMINATE)
        )

    @staticmethod
    def from_policy_gate(
        *,
        policy_gate: PolicyGate,
        readiness_policy_ref: PolicyReference,
        requested_target: ReadinessTarget,
        status: GateStatus,
        observed_claim_refs: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
        reason_codes: tuple[str, ...] = (),
        window_ref: str = "",
        evaluated_at: Optional[datetime] = None,
    ) -> "GateResult":
        """Ergonomic factory. Identical safety to the direct constructor — the
        direct constructor is already non-forgeable (it embeds the PolicyGate).
        """

        return GateResult(
            policy_gate=policy_gate,
            readiness_policy_ref=readiness_policy_ref,
            requested_target=requested_target,
            status=status,
            observed_claim_refs=observed_claim_refs,
            evidence_refs=evidence_refs,
            reason_codes=reason_codes,
            window_ref=window_ref,
            evaluated_at=evaluated_at,
        )

    def canonical_digest(self) -> str:
        return canonical_digest(self)
