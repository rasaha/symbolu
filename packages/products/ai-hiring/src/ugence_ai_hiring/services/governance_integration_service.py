"""Governance integration service (H3).

Integrates the completed H1/H2 hiring domain with the frozen Decision Governance
kernel: it binds an advisory H2 hiring recommendation to a DGM ``DecisionCase``,
submits it as a kernel ``RecommendationRecord`` (AI-generated, advisory), manages
review tasks, and records a **human** ``DecisionRecord`` through the kernel — which
enforces human-only decision authority. It captures rationale and overrides, and
cross-links the hiring-owned audit to the DGM governance audit by correlation id.

Invariant preserved: **Recommendation → Human Decision → (H4) Authorized Action.**
This service records the governed human decision and stops there — it never creates
an action, calls ActionGate, or executes. Execution/authorization is exclusively H4.
"""

from __future__ import annotations

from typing import Callable, Optional

from ugence_decision_authority.api.common import new_id
from ugence_decision_authority.api.contracts import (
    AuthorityContext,
    AuthorityType,
    GeneratorType,
    ReviewTaskType,
    VersionedRef,
)
from ugence_decision_authority.api.identity import ActorType
from ugence_decision_authority.api.vocabulary import ReasonCode

from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..errors import (
    RecommendationGenerationError,
    RecommendationNotReadyError,
    ReviewerAuthorityError,
)
from ..governance.binding import GovernanceBindingStatus, GovernanceCaseBinding
from ..governance.outcomes import (
    HiringDecisionIntent,
    decision_outcome_for,
    is_override,
    proposed_outcome_for,
)
from ..recommendations.status import RecommendationStatus
from ._hiring_context import ActorContext, guard_tenant

_CASE_ELIGIBLE_REC_STATES = frozenset(
    {RecommendationStatus.READY_FOR_HUMAN_REVIEW, RecommendationStatus.ASSERTION_REVIEW_REQUIRED})
_DEFAULT_REASONS = (ReasonCode.NOT_APPLICABLE,)


class GovernanceIntegrationService:
    def __init__(
        self, *, recommendations, bindings, cases, case_recommendations, case_decisions,
        audit: HiringDomainAuditService, id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._recs = recommendations
        self._bindings = bindings
        self._cases = cases                    # kernel DecisionCaseService
        self._case_recs = case_recommendations  # kernel CaseRecommendationService
        self._case_decs = case_decisions        # kernel CaseDecisionService
        self._audit = audit
        self._new_id = id_factory

    # --- open a governance case for a recommendation -----------------------
    def open_case(self, ctx: ActorContext, *, recommendation_id: str,
                  correlation_id: str = "") -> GovernanceCaseBinding:
        rec = self._recs.get(recommendation_id)
        guard_tenant(ctx, record_tenant_id=rec.tenant_id, entity_type="recommendation",
                     entity_id=recommendation_id, audit=self._audit)
        if rec.status not in _CASE_ELIGIBLE_REC_STATES:
            raise RecommendationGenerationError(
                f"recommendation '{recommendation_id}' is not review-bound ({rec.status.value})")
        if self._bindings.for_recommendation(recommendation_id) is not None:
            raise RecommendationGenerationError(
                f"recommendation '{recommendation_id}' is already bound to a governance case")

        corr = correlation_id or rec.correlation_id or recommendation_id
        case = self._cases.create_case(
            tenant_id=rec.tenant_id, decision_type="hiring",
            subject_ids=(rec.candidate_subject_ref,), created_by=ctx.actor_id,
            policy_refs=tuple(VersionedRef(ref_id=p, version=1, kind="policy") for p in rec.policy_refs),
            require_recommendation=True, correlation_id=corr)
        self._cases.link_assessment(case_id=case.decision_case_id, assessment_id=recommendation_id,
                                    version=1, actor=ctx.actor_id)
        self._cases.mark_ready_for_recommendation(case_id=case.decision_case_id, actor=ctx.actor_id)
        krec = self._case_recs.submit_recommendation(
            case_id=case.decision_case_id, recommendation_type="hiring_recommendation",
            proposed_outcome=proposed_outcome_for(rec.outcome), generated_by=ctx.actor_id,
            generator_type=GeneratorType.AI_ASSISTED,
            assessment_refs=(VersionedRef(ref_id=recommendation_id, version=1, kind="assessment"),),
            policy_refs=tuple(VersionedRef(ref_id=p, version=1, kind="policy") for p in rec.policy_refs),
            model_provenance=f"{rec.generator_id}/{rec.provider_id}")

        binding = GovernanceCaseBinding(
            binding_id=self._new_id("gcb"), tenant_id=rec.tenant_id, application_id=rec.application_id,
            hiring_recommendation_id=recommendation_id, candidate_subject_ref=rec.candidate_subject_ref,
            decision_case_id=case.decision_case_id, kernel_recommendation_id=krec.recommendation_id,
            status=GovernanceBindingStatus.OPEN, correlation_id=corr)
        self._bindings.add(binding)
        self._audit.record(
            event_type=HiringDomainEventType.GOVERNANCE_CASE_OPENED, entity_type="recommendation",
            entity_id=recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=corr, causation_id=case.decision_case_id,
            payload={"decision_case_id": case.decision_case_id})
        self._audit.record(
            event_type=HiringDomainEventType.RECOMMENDATION_BOUND_TO_CASE, entity_type="recommendation",
            entity_id=recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=corr, causation_id=krec.recommendation_id,
            payload={"kernel_recommendation_id": krec.recommendation_id})
        return binding

    # --- review tasks ------------------------------------------------------
    def assign_review(self, ctx: ActorContext, *, recommendation_id: str, assigned_to: str,
                      task_type: ReviewTaskType = ReviewTaskType.RECOMMENDATION_REVIEW,
                      required_role: str = ""):
        binding = self._binding(ctx, recommendation_id)
        task = self._cases.assign_review(
            case_id=binding.decision_case_id, task_type=task_type, assigned_to=assigned_to,
            required_role=required_role, actor=ctx.actor_id)
        self._audit.record(
            event_type=HiringDomainEventType.GOVERNANCE_REVIEW_ASSIGNED, entity_type="recommendation",
            entity_id=recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=binding.correlation_id,
            causation_id=task.task_id, payload={"task_type": task_type.value})
        return task

    def complete_review(self, ctx: ActorContext, *, recommendation_id: str, task_id: str):
        binding = self._binding(ctx, recommendation_id)
        task = self._cases.complete_review(case_id=binding.decision_case_id, task_id=task_id,
                                           actor=ctx.actor_id)
        self._audit.record(
            event_type=HiringDomainEventType.GOVERNANCE_REVIEW_COMPLETED, entity_type="recommendation",
            entity_id=recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=binding.correlation_id, causation_id=task_id)
        return task

    # --- human decision (human-only) ---------------------------------------
    def record_human_decision(
        self, ctx: ActorContext, *, recommendation_id: str, intent: HiringDecisionIntent,
        reason_codes: tuple[ReasonCode, ...] = (), override_reason_codes: tuple[ReasonCode, ...] = (),
        override_notes: str = "",
    ):
        self._require_human(ctx, recommendation_id, f"decision:{intent.value}")
        rec = self._recs.get(recommendation_id)
        binding = self._binding(ctx, recommendation_id)

        readiness = self._cases.validate_decision_readiness(
            case_id=binding.decision_case_id, actor=ctx.actor_id)
        if not readiness.ready:
            raise RecommendationNotReadyError(
                f"decision not ready: blockers={list(readiness.blockers)}")

        proposed = proposed_outcome_for(rec.outcome)
        decision_outcome = decision_outcome_for(intent)
        override = is_override(proposed=proposed, decision=decision_outcome)
        reasons = reason_codes or _DEFAULT_REASONS
        ovr_reasons = (override_reason_codes or _DEFAULT_REASONS) if override else ()

        decision = self._case_decs.record_decision(
            case_id=binding.decision_case_id, outcome=decision_outcome,
            authority=AuthorityContext(authority_id=ctx.actor_id,
                                       authority_type=AuthorityType.HUMAN_APPROVER,
                                       decision_scope="hiring"),
            decided_by=ctx.actor_id, reason_codes=reasons,
            recommendation_refs=(VersionedRef(ref_id=binding.kernel_recommendation_id, version=1,
                                              kind="recommendation"),),
            override_reason_codes=ovr_reasons, override_notes=override_notes if override else "")

        updated = binding.with_updates(
            status=GovernanceBindingStatus.DECIDED, decision_id=decision.decision_id,
            override_id=decision.override_record_id or "")
        self._bindings.add(updated)
        self._audit.record(
            event_type=HiringDomainEventType.HUMAN_DECISION_RECORDED, entity_type="recommendation",
            entity_id=recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=binding.correlation_id,
            causation_id=decision.decision_id,
            payload={"outcome": decision_outcome.value, "override": str(override)})
        if override:
            self._audit.record(
                event_type=HiringDomainEventType.GOVERNANCE_DECISION_OVERRIDE_RECORDED, entity_type="recommendation",
                entity_id=recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
                actor_type=ctx.actor_type, correlation_id=binding.correlation_id,
                causation_id=decision.override_record_id or decision.decision_id,
                payload={"proposed": proposed.value, "decided": decision_outcome.value})
        return decision

    # --- reject the AI recommendation (human-only) -------------------------
    def reject_recommendation(self, ctx: ActorContext, *, recommendation_id: str,
                              reason_codes: tuple[ReasonCode, ...] = ()):
        self._require_human(ctx, recommendation_id, "reject_recommendation")
        binding = self._binding(ctx, recommendation_id)
        krec = self._case_recs.reject_recommendation(
            case_id=binding.decision_case_id, recommendation_id=binding.kernel_recommendation_id,
            actor=ctx.actor_id, reason_codes=reason_codes or _DEFAULT_REASONS)
        self._bindings.add(binding.with_updates(status=GovernanceBindingStatus.REJECTED))
        self._audit.record(
            event_type=HiringDomainEventType.GOVERNANCE_RECOMMENDATION_REJECTED,
            entity_type="recommendation", entity_id=recommendation_id, tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id, actor_type=ctx.actor_type, correlation_id=binding.correlation_id,
            causation_id=binding.kernel_recommendation_id)
        return krec

    # --- supersede ---------------------------------------------------------
    def supersede_case(self, ctx: ActorContext, *, recommendation_id: str) -> GovernanceCaseBinding:
        binding = self._binding(ctx, recommendation_id)
        case = self._cases.get_case(binding.decision_case_id)
        # The kernel reopens a DECIDED case for a superseding revision; an
        # undecided case is cancelled instead. Both leave the binding SUPERSEDED.
        if case.status.value == "DECIDED":
            self._cases.supersede_case(case_id=binding.decision_case_id, actor=ctx.actor_id)
        else:
            self._cases.cancel_case(case_id=binding.decision_case_id, actor=ctx.actor_id)
        updated = binding.with_updates(status=GovernanceBindingStatus.SUPERSEDED)
        self._bindings.add(updated)
        self._audit.record(
            event_type=HiringDomainEventType.GOVERNANCE_CASE_SUPERSEDED, entity_type="recommendation",
            entity_id=recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=binding.correlation_id,
            causation_id=binding.decision_case_id)
        return updated

    # --- helpers -----------------------------------------------------------
    def _binding(self, ctx: ActorContext, recommendation_id: str) -> GovernanceCaseBinding:
        binding = self._bindings.for_recommendation(recommendation_id)
        if binding is None:
            raise RecommendationGenerationError(
                f"no governance case bound to recommendation '{recommendation_id}'")
        guard_tenant(ctx, record_tenant_id=binding.tenant_id, entity_type="recommendation",
                     entity_id=recommendation_id, audit=self._audit)
        return binding

    def _require_human(self, ctx: ActorContext, recommendation_id: str, action: str) -> None:
        if ctx.actor_type is not ActorType.HUMAN:
            self._audit.record_denial(
                entity_type="recommendation", entity_id=recommendation_id, tenant_id=ctx.tenant_id,
                actor_id=ctx.actor_id, actor_type=ctx.actor_type,
                reason=f"non_human_governance_action:{action}")
            raise ReviewerAuthorityError(
                f"actor_type {ctx.actor_type.value} may not perform '{action}' — human authority required")
