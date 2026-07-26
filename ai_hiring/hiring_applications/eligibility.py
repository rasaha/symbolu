"""Deterministic application eligibility rules (H1).

Purely structural gates evaluated when an application is submitted. No scoring,
ranking, or quality judgement — only whether the structural preconditions hold.
The result is an immutable, explainable record with the exact failing reasons.
"""

from __future__ import annotations

from typing import Optional

from ..candidates.candidate import Candidate, CandidateStatus
from ..domain.base import DomainModel
from ..requisitions.job_definition import JobDefinition
from ..requisitions.requisition import JobRequisition
from ..requisitions.status import RequisitionStatus


class EligibilityResult(DomainModel):
    eligible: bool
    reasons: tuple[str, ...] = ()  # empty iff eligible


def evaluate_eligibility(
    *,
    tenant_id: str,
    requisition: Optional[JobRequisition],
    job_definition: Optional[JobDefinition],
    candidate: Optional[Candidate],
    has_active_duplicate: bool,
) -> EligibilityResult:
    """Deterministically decide whether an application may be submitted.

    Rules (all must hold):
    * requisition exists, is in-tenant, and is OPEN;
    * a PUBLISHED job definition exists for that requisition, in-tenant;
    * candidate exists, is in-tenant, and is ACTIVE;
    * no active (non-terminal) application already exists for the pair.
    """
    reasons: list[str] = []

    if requisition is None:
        reasons.append("requisition_not_found")
    else:
        if requisition.tenant_id != tenant_id:
            reasons.append("requisition_tenant_mismatch")
        if requisition.status != RequisitionStatus.OPEN:
            reasons.append(f"requisition_not_open:{requisition.status.value}")

    if job_definition is None:
        reasons.append("job_definition_not_found")
    else:
        if job_definition.tenant_id != tenant_id:
            reasons.append("job_definition_tenant_mismatch")
        if not job_definition.is_published:
            reasons.append(f"job_definition_not_published:{job_definition.status.value}")
        if requisition is not None and job_definition.requisition_id != requisition.requisition_id:
            reasons.append("job_definition_requisition_mismatch")

    if candidate is None:
        reasons.append("candidate_not_found")
    else:
        if candidate.tenant_id != tenant_id:
            reasons.append("candidate_tenant_mismatch")
        if candidate.status != CandidateStatus.ACTIVE:
            reasons.append(f"candidate_not_active:{candidate.status.value}")

    if has_active_duplicate:
        reasons.append("duplicate_active_application")

    return EligibilityResult(eligible=not reasons, reasons=tuple(reasons))
