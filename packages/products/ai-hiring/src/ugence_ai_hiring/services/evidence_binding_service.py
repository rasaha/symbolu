"""Evidence binding service — deterministic, criterion-specific, fail-closed.

Binds an evidence artifact to a specific criterion only after deterministic
eligibility and admissibility checks. It never infers semantic relevance (no text
similarity, embeddings, or LLMs); the evidence *type* is supplied by an authorized
source, and admissibility is computed by the Phase-3A `AdmissibilityPolicy`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..assessments.evidence_binding import EvidenceBinding, ExcludedEvidenceRecord
from ..assessments.status import BindingProvenance
from ..assessments.workspace import AssessmentWorkspace, CapabilityBinding
from ..errors import (
    CrossTenantAssessmentAccessError,
    EvidenceNotEligibleForAssessmentError,
    QuarantinedEvidenceBindingError,
)
from ..ontology.taxonomy import EvidenceType, ReasonCode
from ..rubrics.evidence_rules import (
    DEFAULT_ADMISSIBILITY_POLICY,
    AdmissibilityPolicy,
    EvidenceAdmissibility,
    EvidenceDescriptor,
)
from ..repositories.interfaces import EvidenceRepository
from .evidence_validation_service import EvidenceValidationService

_OUTCOME_REASON = {
    EvidenceAdmissibility.PROHIBITED: (ReasonCode.PROHIBITED_EVIDENCE,),
    EvidenceAdmissibility.STALE: (ReasonCode.STALE_EVIDENCE,),
    EvidenceAdmissibility.INSUFFICIENT: (ReasonCode.INSUFFICIENT_SAMPLE,),
    EvidenceAdmissibility.UNKNOWN: (),
}


@dataclass(frozen=True)
class BindingResult:
    admissible: bool
    binding: Optional[EvidenceBinding] = None
    exclusion: Optional[ExcludedEvidenceRecord] = None


class EvidenceBindingService:
    def __init__(
        self,
        evidence_repository: EvidenceRepository,
        evidence_validation_service: EvidenceValidationService,
        *,
        admissibility_policy: AdmissibilityPolicy = DEFAULT_ADMISSIBILITY_POLICY,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._evidence = evidence_repository
        self._eligibility = evidence_validation_service
        self._policy = admissibility_policy
        self._new_id = id_factory
        self._clock = clock

    def bind(
        self,
        workspace: AssessmentWorkspace,
        criterion: CapabilityBinding,
        *,
        evidence_id: str,
        evidence_type: EvidenceType,
        bound_by: str,
        provenance: BindingProvenance = BindingProvenance.MANUAL_AUTHORIZED,
    ) -> BindingResult:
        """Deterministically evaluate and produce a binding or an exclusion."""
        # existence (fail closed)
        if not self._evidence.exists(evidence_id):
            raise EvidenceNotEligibleForAssessmentError(
                f"evidence '{evidence_id}' does not exist")
        evidence = self._evidence.get(evidence_id)

        # tenant ownership
        if evidence.tenant_id != workspace.tenant_id:
            raise CrossTenantAssessmentAccessError(
                f"evidence '{evidence_id}' is outside tenant '{workspace.tenant_id}'")
        # subject relationship
        if evidence.candidate_id != workspace.subject_id:
            raise EvidenceNotEligibleForAssessmentError(
                f"evidence '{evidence_id}' does not belong to subject "
                f"'{workspace.subject_id}'")
        # quarantine / non-job-relevant is a hard boundary
        if not evidence.job_relevant:
            raise QuarantinedEvidenceBindingError(
                f"evidence '{evidence_id}' is quarantined / not job-relevant")
        # Phase-2.5 fail-closed eligibility
        elig = self._eligibility.evaluate_eligibility(
            evidence_id, tenant_id=workspace.tenant_id, authorized=True)
        if not elig.eligible:
            raise EvidenceNotEligibleForAssessmentError(
                f"evidence '{evidence_id}' failed eligibility: {elig.reason_codes}")

        # deterministic admissibility of the *declared* type against the criterion
        age_days = max(0, (self._clock() - evidence.created_at).days)
        outcome = self._policy.classify_item(
            criterion.evidence_rule, EvidenceDescriptor(evidence_type, age_days))

        if outcome is EvidenceAdmissibility.ADMISSIBLE:
            binding = EvidenceBinding(
                binding_id=self._new_id("bind"), workspace_id=workspace.workspace_id,
                criterion_id=criterion.criterion_id, capability_id=criterion.capability_id,
                capability_version=criterion.capability_version, evidence_id=evidence_id,
                evidence_version=evidence.version, evidence_type=evidence_type,
                admissibility_outcome=outcome, provenance=provenance, bound_by=bound_by,
                bound_at=self._clock(),
                policy_reference=f"admissibility:{criterion.capability_id}")
            return BindingResult(admissible=True, binding=binding)

        exclusion = ExcludedEvidenceRecord(
            record_id=self._new_id("excl"), workspace_id=workspace.workspace_id,
            criterion_id=criterion.criterion_id, capability_id=criterion.capability_id,
            capability_version=criterion.capability_version, evidence_id=evidence_id,
            evidence_type=evidence_type, admissibility_outcome=outcome,
            reason_codes=_OUTCOME_REASON.get(outcome, ()), excluded_at=self._clock())
        return BindingResult(admissible=False, exclusion=exclusion)
