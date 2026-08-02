"""CaseRecommendationService — accepts advisory recommendations onto a case.

A recommendation *proposes* a course of action. This service validates provenance
and policy conformance and appends an immutable ``RecommendationRecord``; it never
converts a recommendation into a decision, never ranks candidates, and never binds
the case. Rejection marks the record REJECTED (a new immutable snapshot); it never
deletes it, so conflicting recommendations remain visible.
"""

from __future__ import annotations

from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..decisions.recommendation import RecommendationRecord
from ..decisions.status import (
    CaseStatus,
    GeneratorType,
    ProposedOutcome,
    RecommendationStatus,
)
from ..decisions.subject import VersionedRef
from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..errors import (
    CaseFinalizedError,
    RecommendationValidationError,
)
from ..vocabulary import ReasonCode
from ..identity import IdentityProvider
from ..policy import EvidenceAccessPolicy, Permission
from ..repositories.decision_case_repository import DecisionCaseRepository
from ..vocabulary import UncertaintyLevel
from ..decisions.status import TERMINAL_CASE_STATUSES
from ..audit import AuditService
from .case_validation_service import CaseValidationService
from ._case_authz import authorize_case_action


class CaseRecommendationService:
    def __init__(
        self,
        case_repository: DecisionCaseRepository,
        validation_service: CaseValidationService,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = case_repository
        self._validation = validation_service
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._new_id = id_factory
        self._clock = clock

    def _emit(self, event_type, entity_id, actor, actor_type, corr, payload):
        self._audit.record(
            event_type=event_type, entity_type="decision_case", entity_id=entity_id,
            actor_type=actor_type, actor_id=actor, correlation_id=corr, payload=payload)

    def submit_recommendation(
        self, *, case_id: str, recommendation_type: str,
        proposed_outcome: ProposedOutcome, generated_by: str,
        generator_type: GeneratorType,
        assessment_refs: tuple[VersionedRef, ...] = (),
        policy_refs: tuple[VersionedRef, ...] = (),
        reason_codes: tuple[ReasonCode, ...] = (),
        uncertainty: Optional[UncertaintyLevel] = None,
        model_provenance: Optional[str] = None,
        supersedes_recommendation_id: Optional[str] = None,
    ) -> RecommendationRecord:
        case = self._repo.get_case(case_id)
        if case.status in TERMINAL_CASE_STATUSES:
            raise CaseFinalizedError(
                f"case '{case_id}' is {case.status.value}; no recommendation may be added")
        actor_type = authorize_case_action(
            self._identity, self._policy, self._audit, actor=generated_by,
            permission=Permission.SUBMIT_RECOMMENDATION, tenant_id=case.tenant_id,
            subject_id=None, correlation_id=case.correlation_id, entity_id=case_id)

        result = self._validation.validate_recommendation(
            case, assessment_ref_ids=tuple(r.ref_id for r in assessment_refs),
            reason_codes=reason_codes, generator_type=generator_type,
            model_provenance=model_provenance)
        if not result.valid:
            raise RecommendationValidationError(
                f"recommendation rejected: {result.error_codes}")

        rec = RecommendationRecord(
            recommendation_id=self._new_id("rec"), decision_case_id=case_id,
            tenant_id=case.tenant_id, recommendation_type=recommendation_type,
            proposed_outcome=proposed_outcome, assessment_refs=assessment_refs,
            policy_refs=policy_refs, reason_codes=reason_codes, uncertainty=uncertainty,
            generated_by=generated_by, generator_type=generator_type,
            model_provenance=model_provenance, created_at=self._clock(),
            status=RecommendationStatus.PROPOSED,
            supersedes_recommendation_id=supersedes_recommendation_id)
        self._repo.add_recommendation(rec)

        ref = VersionedRef(ref_id=rec.recommendation_id, version=1, kind="recommendation")
        target = (CaseStatus.RECOMMENDATION_AVAILABLE
                  if case.status in (CaseStatus.READY_FOR_RECOMMENDATION,
                                     CaseStatus.RECOMMENDATION_AVAILABLE,
                                     CaseStatus.ASSESSMENT_IN_PROGRESS,
                                     CaseStatus.CREATED, CaseStatus.EVIDENCE_ASSEMBLY)
                  else case.status)
        self._repo.save_case_version(case.evolve(
            case_version_id=self._new_id("cv"), status=target,
            recommendation_refs=case.recommendation_refs + (ref,)))
        self._emit(AuditEventType.DECISION_CASE_RECOMMENDATION_ADDED, case_id,
                   generated_by, actor_type, case.correlation_id,
                   {"recommendation_id": rec.recommendation_id,
                    "generator_type": generator_type.value,
                    "proposed_outcome": proposed_outcome.value})
        return rec

    def reject_recommendation(self, *, case_id: str, recommendation_id: str,
                              actor: str,
                              reason_codes: tuple[ReasonCode, ...] = ()) -> RecommendationRecord:
        case = self._repo.get_case(case_id)
        actor_type = authorize_case_action(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.SUBMIT_RECOMMENDATION, tenant_id=case.tenant_id,
            subject_id=None, correlation_id=case.correlation_id, entity_id=case_id)
        original = self._repo.get_recommendation(recommendation_id)
        # Append a REJECTED snapshot; the original PROPOSED record remains visible.
        rejected = RecommendationRecord(
            recommendation_id=self._new_id("rec"), decision_case_id=case_id,
            tenant_id=case.tenant_id, recommendation_type=original.recommendation_type,
            proposed_outcome=original.proposed_outcome,
            assessment_refs=original.assessment_refs, policy_refs=original.policy_refs,
            reason_codes=reason_codes or original.reason_codes,
            uncertainty=original.uncertainty, generated_by=actor,
            generator_type=original.generator_type,
            model_provenance=original.model_provenance, created_at=self._clock(),
            status=RecommendationStatus.REJECTED,
            supersedes_recommendation_id=original.recommendation_id)
        self._repo.add_recommendation(rejected)
        self._emit(AuditEventType.DECISION_CASE_RECOMMENDATION_REJECTED, case_id, actor,
                   actor_type, case.correlation_id,
                   {"recommendation_id": recommendation_id,
                    "rejection_record_id": rejected.recommendation_id})
        return rejected

    def get_recommendation(self, recommendation_id: str) -> RecommendationRecord:
        return self._repo.get_recommendation(recommendation_id)

    def list_recommendations(self, case_id: str) -> tuple[RecommendationRecord, ...]:
        return self._repo.list_recommendations(case_id)
