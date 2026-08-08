"""The compiled ``HiringWorkflowIR`` and its parts.

Mirrors the platform ``WorkflowIR`` (``workflow_ir.v1``): a canonical, typed,
versioned, content-addressed (SHA-256 over the canonical *semantic* body) and
signed artifact. The content digest excludes ``compiled_at`` and the signature,
so recompiling the same policy yields the same digest regardless of when it ran.

A :class:`~ugence_ai_hiring.hiring_policy.contract.HiringDecisionContract` is a
deployable projection of one IR digest. Matches
``docs/schemas/hiring_workflow_ir.schema.json``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .enums import GateStatus, HiringEvidenceClass, MandatoryGateType, RuntimeAssuranceCheck
from .signing import IRSignature

IR_VERSION = "hiring_workflow_ir.v1"
IR_KIND = "hiring_workflow_ir"

# Weight normalization tolerance.
_WEIGHT_TOLERANCE = 1e-6


class GatePredicate(DomainModel):
    """A typed predicate over admitted evidence (interpreted, never reads the OFI)."""

    expression: str
    evidence_types: tuple[HiringEvidenceClass, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "GatePredicate":
        if not self.expression.strip():
            raise DomainValidationError("gate predicate.expression is required")
        return self


class MandatoryGate(DomainModel):
    """A non-compensatory hard requirement. In a compiled IR this is a definition;
    ``status`` is the pre-evaluation fail-closed default ``INDETERMINATE``."""

    gate_id: str
    gate_type: MandatoryGateType
    predicate: GatePredicate
    status: GateStatus = GateStatus.INDETERMINATE
    deciding_evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "MandatoryGate":
        if not self.gate_id.strip():
            raise DomainValidationError("gate_id is required")
        return self


class CompilerProvenance(DomainModel):
    """Records the compiler run and its rejection-check results (all must be true)."""

    pwc_version: str
    compiled_at: datetime = Field(default_factory=utc_now)
    no_ofi_in_policy: bool
    gates_non_compensatory: bool
    weighted_dimensions_have_required_evidence: bool
    approval_chain_human_only: bool
    action_constraints_within_approver_authority: bool
    constrained_actions_have_assurance_checks: bool

    def all_passed(self) -> bool:
        return all(
            (
                self.no_ofi_in_policy,
                self.gates_non_compensatory,
                self.weighted_dimensions_have_required_evidence,
                self.approval_chain_human_only,
                self.action_constraints_within_approver_authority,
                self.constrained_actions_have_assurance_checks,
            )
        )


class Approver(DomainModel):
    """An approval-chain entry. ``actor_type`` is always HUMAN (enforced at compile)."""

    approver_role: str
    actor_type: str = "HUMAN"

    @model_validator(mode="after")
    def _validate(self) -> "Approver":
        if not self.approver_role.strip():
            raise DomainValidationError("approver_role is required")
        if self.actor_type != "HUMAN":
            raise DomainValidationError("approver actor_type must be HUMAN")
        return self


class IRActionConstraints(DomainModel):
    """Action bounds carried in the IR (mirror of the policy's constraints)."""

    salary_ceiling: float = Field(ge=0)
    salary_currency: str = "USD"
    approved_level: str
    approved_roles: tuple[str, ...] = ()
    allowed_locations: tuple[str, ...] = ()


class HiringWorkflowIR(DomainModel):
    """The canonical compiled artifact produced by the Hiring Policy Compiler."""

    ir_kind: str = IR_KIND
    ir_version: str = IR_VERSION
    source_policy_id: str
    content_digest: str
    signature: IRSignature
    dimensions: tuple[str, ...]
    # Weighted dimensions only (positive weight); sums to 1.0.
    dimension_weights: dict[str, float]
    mandatory_gates: tuple[MandatoryGate, ...] = ()
    evidence_requirements: dict[str, tuple[HiringEvidenceClass, ...]]
    confidence_thresholds: dict[str, float]
    action_constraints: IRActionConstraints
    runtime_assurance_checks: tuple[RuntimeAssuranceCheck, ...]
    approval_chain: tuple[Approver, ...]
    review_schedule_months: tuple[int, ...] = (1, 3, 6, 12)
    compiler: CompilerProvenance

    @model_validator(mode="after")
    def _validate(self) -> "HiringWorkflowIR":
        if self.ir_kind != IR_KIND:
            raise DomainValidationError(f"ir_kind must be {IR_KIND!r}")
        if self.ir_version != IR_VERSION:
            raise DomainValidationError(f"ir_version must be {IR_VERSION!r}")
        if not self.dimensions:
            raise DomainValidationError("IR must declare at least one dimension")
        if self.dimension_weights:
            total = sum(self.dimension_weights.values())
            if abs(total - 1.0) > _WEIGHT_TOLERANCE:
                raise DomainValidationError(
                    f"dimension_weights must sum to 1.0 (got {total:.6f})"
                )
        # weighted dimensions must be declared dimensions
        for dim in self.dimension_weights:
            if dim not in self.dimensions:
                raise DomainValidationError(f"weighted dimension {dim!r} not in dimensions")
        # content digest must match the canonical body, and the signature must
        # bind that digest.
        expected = compute_content_digest(self)
        if self.content_digest != expected:
            raise DomainValidationError("content_digest does not match canonical body")
        self.signature._validate_fields()
        return self

    def canonical_body(self) -> dict[str, Any]:
        """The digest-covered semantic body (excludes compiled_at, signature, digest)."""
        return _canonical_body(self)


def serialize_body(
    *,
    source_policy_id: str,
    dimensions: tuple[str, ...],
    dimension_weights: dict[str, float],
    mandatory_gates: tuple[MandatoryGate, ...],
    evidence_requirements: dict[str, tuple[HiringEvidenceClass, ...]],
    confidence_thresholds: dict[str, float],
    action_constraints: IRActionConstraints,
    runtime_assurance_checks: tuple[RuntimeAssuranceCheck, ...],
    approval_chain: tuple[Approver, ...],
    review_schedule_months: tuple[int, ...],
) -> dict[str, Any]:
    """Single canonical serializer of the digest-covered semantic body.

    Used both by the compiler (before the digest exists) and by the IR's own
    self-check, so the two can never drift.
    """
    return {
        "ir_kind": IR_KIND,
        "ir_version": IR_VERSION,
        "source_policy_id": source_policy_id,
        "dimensions": list(dimensions),
        "dimension_weights": {k: round(v, 9) for k, v in sorted(dimension_weights.items())},
        "mandatory_gates": [
            {
                "gate_id": g.gate_id,
                "gate_type": g.gate_type.value,
                "predicate": {
                    "expression": g.predicate.expression,
                    "evidence_types": [e.value for e in g.predicate.evidence_types],
                },
                "status": g.status.value,
                "deciding_evidence": list(g.deciding_evidence),
            }
            for g in mandatory_gates
        ],
        "evidence_requirements": {
            k: [e.value for e in v] for k, v in sorted(evidence_requirements.items())
        },
        "confidence_thresholds": {k: round(v, 9) for k, v in sorted(confidence_thresholds.items())},
        "action_constraints": {
            "salary_ceiling": action_constraints.salary_ceiling,
            "salary_currency": action_constraints.salary_currency,
            "approved_level": action_constraints.approved_level,
            "approved_roles": list(action_constraints.approved_roles),
            "allowed_locations": list(action_constraints.allowed_locations),
        },
        "runtime_assurance_checks": [c.value for c in runtime_assurance_checks],
        "approval_chain": [
            {"approver_role": a.approver_role, "actor_type": a.actor_type} for a in approval_chain
        ],
        "review_schedule_months": list(review_schedule_months),
    }


def _canonical_body(ir: HiringWorkflowIR) -> dict[str, Any]:
    """Deterministic dict of the digest-covered fields."""
    return serialize_body(
        source_policy_id=ir.source_policy_id,
        dimensions=ir.dimensions,
        dimension_weights=ir.dimension_weights,
        mandatory_gates=ir.mandatory_gates,
        evidence_requirements=ir.evidence_requirements,
        confidence_thresholds=ir.confidence_thresholds,
        action_constraints=ir.action_constraints,
        runtime_assurance_checks=ir.runtime_assurance_checks,
        approval_chain=ir.approval_chain,
        review_schedule_months=ir.review_schedule_months,
    )


def compute_content_digest(ir: HiringWorkflowIR) -> str:
    """SHA-256 over the canonical semantic body (excludes compiled_at + signature)."""
    return canonical_hash(_canonical_body(ir))


def compute_content_digest_from_parts(
    *,
    source_policy_id: str,
    dimensions: tuple[str, ...],
    dimension_weights: dict[str, float],
    mandatory_gates: tuple[MandatoryGate, ...],
    evidence_requirements: dict[str, tuple[HiringEvidenceClass, ...]],
    confidence_thresholds: dict[str, float],
    action_constraints: IRActionConstraints,
    runtime_assurance_checks: tuple[RuntimeAssuranceCheck, ...],
    approval_chain: tuple[Approver, ...],
    review_schedule_months: tuple[int, ...],
) -> str:
    """Digest over the canonical body, computed from raw parts (compiler use,
    before the IR object exists)."""
    return canonical_hash(
        serialize_body(
            source_policy_id=source_policy_id,
            dimensions=dimensions,
            dimension_weights=dimension_weights,
            mandatory_gates=mandatory_gates,
            evidence_requirements=evidence_requirements,
            confidence_thresholds=confidence_thresholds,
            action_constraints=action_constraints,
            runtime_assurance_checks=runtime_assurance_checks,
            approval_chain=approval_chain,
            review_schedule_months=review_schedule_months,
        )
    )
