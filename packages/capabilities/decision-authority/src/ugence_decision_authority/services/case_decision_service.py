"""CaseDecisionService — validates authority and records binding decisions.

This service validates that an authorized actor (or a bounded, published delegated
policy) may decide, records an immutable ``DecisionRecord``, and — when the outcome
departs materially from a recommendation or default — an ``OverrideRecord`` that
preserves the original. It never executes an action, never constructs a CER, and
never invokes the ActionGate. A changed decision supersedes the prior record.
"""

from __future__ import annotations

from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..decisions.authority import AuthorityContext
from ..decisions.case import DecisionCase
from ..decisions.decision import DecisionRecord
from ..decisions.lifecycle import is_legal_transition
from ..decisions.override import OverrideRecord
from ..decisions.status import (
    CaseStatus,
    DecisionOutcome,
    EffectiveStatus,
    ProposedOutcome,
    TERMINAL_CASE_STATUSES,
)
from ..decisions.subject import VersionedRef
from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..errors import (
    AIDecisionAuthorityError,
    CaseFinalizedError,
    DecisionAuthorityError,
    DecisionReadinessError,
    InvalidCaseTransitionError,
    SegregationOfDutiesError,
    UnauthorizedOverrideError,
)
from ..vocabulary import ReasonCode
from ..identity import IdentityProvider
from ..policy import EvidenceAccessPolicy, Permission
from ..repositories.decision_case_repository import DecisionCaseRepository
from ..audit import AuditService
from .case_validation_service import CaseValidationService
from ._case_authz import authorize_case_action

#: Validation codes that indicate an AI principal attempted to decide.
_AI_CODES = frozenset({"AI_CANNOT_DECIDE", "DELEGATED_POLICY_NOT_AI"})
_SOD_CODES = frozenset({"SEGREGATION_OF_DUTIES"})


class CaseDecisionService:
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

    def record_decision(
        self, *, case_id: str, outcome: DecisionOutcome,
        authority: AuthorityContext, decided_by: str,
        reason_codes: tuple[ReasonCode, ...],
        recommendation_refs: tuple[VersionedRef, ...] = (),
        assessment_refs: tuple[VersionedRef, ...] = (),
        policy_refs: tuple[VersionedRef, ...] = (),
        override_reason_codes: tuple[ReasonCode, ...] = (),
        override_notes: str = "",
        policy_default_outcome: Optional[DecisionOutcome] = None,
    ) -> DecisionRecord:
        case = self._repo.get_case(case_id)
        if case.status in TERMINAL_CASE_STATUSES:
            raise CaseFinalizedError(
                f"case '{case_id}' is {case.status.value}; no decision may be recorded")
        actor_type = authorize_case_action(
            self._identity, self._policy, self._audit, actor=decided_by,
            permission=Permission.MAKE_DECISION, tenant_id=case.tenant_id,
            subject_id=None, correlation_id=case.correlation_id, entity_id=case_id)

        # Structural readiness (required reviews complete, no blocking assessment).
        readiness = self._validation.evaluate_decision_readiness(
            case, review_tasks=self._repo.list_review_tasks(case_id))
        if not readiness.ready:
            raise DecisionReadinessError(
                f"case not ready for decision: {readiness.blocker_codes}")

        # DECIDED is only reachable via READY_FOR_DECISION. Advance the case there
        # first when the transition is legal; otherwise the transition is refused.
        if case.status is not CaseStatus.READY_FOR_DECISION:
            if not is_legal_transition(case.status, CaseStatus.READY_FOR_DECISION):
                raise InvalidCaseTransitionError(
                    f"cannot decide from status {case.status.value}")
            case = self._repo.save_case_version(case.evolve(
                case_version_id=self._new_id("cv"), status=CaseStatus.READY_FOR_DECISION))

        # Authority validation (AI cannot decide, delegated-policy bounds, SoD).
        rec_authors = frozenset(
            r.generated_by for r in self._repo.list_recommendations(case_id))
        auth_result = self._validation.validate_authority(
            case, authority, actor_type=actor_type, decided_by=decided_by,
            recommendation_authors=rec_authors)
        if not auth_result.valid:
            codes = set(auth_result.error_codes)
            if codes & _AI_CODES:
                raise AIDecisionAuthorityError(
                    f"AI principal may not decide: {auth_result.error_codes}")
            if codes & _SOD_CODES:
                raise SegregationOfDutiesError(
                    f"segregation of duties violated: {auth_result.error_codes}")
            raise DecisionAuthorityError(
                f"invalid decision authority: {auth_result.error_codes}")

        # Determine whether this decision departs from advice/default → override.
        override = self._maybe_build_override(
            case, outcome=outcome, recommendation_refs=recommendation_refs,
            override_reason_codes=override_reason_codes or reason_codes,
            override_notes=override_notes,
            policy_default_outcome=policy_default_outcome, authority=authority,
            decided_by=decided_by)

        decision = DecisionRecord(
            decision_id=self._new_id("dec"), decision_case_id=case_id,
            tenant_id=case.tenant_id, decision_type=case.decision_type, outcome=outcome,
            authority_type=authority.authority_type, decided_by=decided_by,
            decided_at=self._clock(), recommendation_refs=recommendation_refs,
            assessment_refs=assessment_refs, policy_refs=policy_refs,
            reason_codes=reason_codes,
            override_record_id=override.override_id if override else None,
            effective_status=EffectiveStatus.EFFECTIVE,
            supersedes_decision_id=self._latest_decision_id(case_id))
        self._repo.record_decision(decision)

        ref = VersionedRef(ref_id=decision.decision_id, version=1, kind="decision")
        self._repo.save_case_version(case.evolve(
            case_version_id=self._new_id("cv"), status=CaseStatus.DECIDED,
            decision_refs=case.decision_refs + (ref,)))
        self._emit(AuditEventType.DECISION_RECORDED, case_id, decided_by, actor_type,
                   case.correlation_id,
                   {"decision_id": decision.decision_id, "outcome": outcome.value,
                    "authority_type": authority.authority_type.value,
                    "override_record_id": decision.override_record_id})
        if override is not None:
            self._emit(AuditEventType.DECISION_OVERRIDE_RECORDED, case_id, decided_by,
                       actor_type, case.correlation_id,
                       {"override_id": override.override_id,
                        "decision_id": decision.decision_id})
        return decision

    def _maybe_build_override(
        self, case: DecisionCase, *, outcome: DecisionOutcome,
        recommendation_refs: tuple[VersionedRef, ...],
        override_reason_codes: tuple[ReasonCode, ...], override_notes: str,
        policy_default_outcome: Optional[DecisionOutcome],
        authority: AuthorityContext, decided_by: str,
    ) -> Optional[OverrideRecord]:
        original_rec = None
        original_proposed: Optional[ProposedOutcome] = None
        if recommendation_refs:
            original_rec = self._repo.get_recommendation(recommendation_refs[-1].ref_id)
            original_proposed = original_rec.proposed_outcome
        departs = False
        if original_proposed is not None:
            departs = outcome.value != original_proposed.value
        elif policy_default_outcome is not None:
            departs = outcome != policy_default_outcome
        if not departs:
            return None
        if not override_reason_codes:
            raise UnauthorizedOverrideError(
                "an override requires explicit reason codes")
        override = OverrideRecord(
            override_id=self._new_id("ovr"), decision_case_id=case.decision_case_id,
            tenant_id=case.tenant_id, final_outcome=outcome, authorized_by=decided_by,
            reason_codes=override_reason_codes,
            original_recommendation_id=(original_rec.recommendation_id
                                        if original_rec else None),
            original_proposed_outcome=original_proposed,
            policy_default_outcome=policy_default_outcome,
            permitting_policy_ref=authority.granting_policy_ref, notes=override_notes,
            created_at=self._clock())
        self._repo.record_override(override)
        return override

    def _latest_decision_id(self, case_id: str) -> Optional[str]:
        decisions = self._repo.list_decisions(case_id)
        return decisions[-1].decision_id if decisions else None

    # --- reads ------------------------------------------------------------
    def get_decision(self, decision_id: str) -> DecisionRecord:
        return self._repo.get_decision(decision_id)

    def list_decisions(self, case_id: str) -> tuple[DecisionRecord, ...]:
        return self._repo.list_decisions(case_id)

    def list_overrides(self, case_id: str) -> tuple[OverrideRecord, ...]:
        return self._repo.list_overrides(case_id)
