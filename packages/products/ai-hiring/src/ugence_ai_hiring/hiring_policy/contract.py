"""The Hiring Decision Contract — a deployable projection of one IR digest.

The Decision Authority evaluates *this* (over dimension evidence + mandatory
gates + confidence), never a fit score. The contract carries its provenance
(``compiled_from``: the signed IR digest) so it is reproducible and
tamper-evident. Matches ``docs/schemas/hiring_decision_contract.schema.json``.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .enums import HiringEvidenceClass, LifecycleStatus, RuntimeAssuranceCheck
from .errors import ContractProjectionError
from .signing import IRSignature, Signer
from .workflow_ir import (
    Approver,
    HiringWorkflowIR,
    IRActionConstraints,
    MandatoryGate,
    compute_content_digest,
)


class CompiledFrom(DomainModel):
    """Provenance of a contract: the signed IR digest it projects."""

    source_policy_id: str
    ir_digest: str
    ir_version: str
    signature: IRSignature


class HiringDecisionContract(DomainModel):
    """The deployable policy object the Decision Authority evaluates."""

    contract_id: str
    version: int = 1
    status: LifecycleStatus = LifecycleStatus.PUBLISHED
    job_definition_id: str
    compiled_from: CompiledFrom
    mandatory_gates: tuple[MandatoryGate, ...] = ()
    dimension_weights_ref: str
    evidence_requirements: dict[str, tuple[HiringEvidenceClass, ...]]
    confidence_thresholds: dict[str, float]
    action_constraints: IRActionConstraints
    runtime_assurance_checks: tuple[RuntimeAssuranceCheck, ...]
    review_schedule_months: tuple[int, ...] = (1, 3, 6, 12)
    approval_chain: tuple[Approver, ...]
    compiled: bool = True

    @model_validator(mode="after")
    def _validate(self) -> "HiringDecisionContract":
        if not self.contract_id.strip():
            raise DomainValidationError("contract_id is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        if not self.job_definition_id.strip():
            raise DomainValidationError("job_definition_id is required")
        if not self.approval_chain:
            raise DomainValidationError("approval_chain must have at least one approver")
        return self


def project_contract(
    ir: HiringWorkflowIR,
    *,
    job_definition_id: str,
    contract_id: Optional[str] = None,
    version: int = 1,
    status: LifecycleStatus = LifecycleStatus.PUBLISHED,
    signer: Optional[Signer] = None,
) -> HiringDecisionContract:
    """Project a Hiring Decision Contract from a compiled, signed IR.

    Verifies the IR's content digest (and, when a ``signer`` is provided, its
    signature) before projecting, so a tampered IR can never yield a contract.
    """
    if compute_content_digest(ir) != ir.content_digest:
        raise ContractProjectionError("IR content_digest does not match its body; refusing to project")
    if signer is not None and not signer.verify(ir.content_digest, ir.signature):
        raise ContractProjectionError("IR signature failed verification; refusing to project")

    return HiringDecisionContract(
        contract_id=contract_id or f"hdc-{ir.source_policy_id}-v{version}",
        version=version,
        status=status,
        job_definition_id=job_definition_id,
        compiled_from=CompiledFrom(
            source_policy_id=ir.source_policy_id,
            ir_digest=ir.content_digest,
            ir_version=ir.ir_version,
            signature=ir.signature,
        ),
        mandatory_gates=ir.mandatory_gates,
        dimension_weights_ref=f"{ir.content_digest}#dimension_weights",
        evidence_requirements=ir.evidence_requirements,
        confidence_thresholds=ir.confidence_thresholds,
        action_constraints=ir.action_constraints,
        runtime_assurance_checks=ir.runtime_assurance_checks,
        review_schedule_months=ir.review_schedule_months,
        approval_chain=ir.approval_chain,
        compiled=ir.compiler.all_passed(),
    )
