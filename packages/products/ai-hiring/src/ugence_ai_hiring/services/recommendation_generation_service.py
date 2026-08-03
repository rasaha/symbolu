"""Recommendation generation & review orchestration (H2).

Distinct from the legacy ``RecommendationService`` (which creates a simple
advisory record tied to an evaluation). This H2 service generates an advisory,
evidence-grounded recommendation *package* for human review:

1. checks the application is in an H2-eligible lifecycle state (ASSESSMENT/IN_REVIEW);
2. runs the injected recommendation-generator **port** (fail-safe on error/malformed);
3. materializes structured claims and evaluates each through the **Assertion
   Governance Provider** (TAP) via the injected evaluator;
4. applies the H2 readiness gate — READY_FOR_HUMAN_REVIEW requires complete
   evidence, required claims passing the assertion policy, no unresolved conflict
   or provider error, and reconstructable provenance;
5. records hiring-owned domain audit events throughout.

Human authority is preserved: reviewer actions are human-only, and no method makes
or executes a binding hiring decision.
"""

from __future__ import annotations

from typing import Callable, Optional

from ugence_decision_authority.api.common import new_id
from ugence_decision_authority.api.identity import ActorType

from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..errors import (
    RecommendationGenerationError,
    ReviewerAuthorityError,
)
from ..hiring_applications.status import ApplicationStatus
from ..recommendations.claim import ASSERTION_POLICY_PASS, HiringClaim
from ..recommendations.generator import GenerationContext, validate_generator_output
from ..recommendations.recommendation import HiringRecommendation, RecommendationOutcome
from ..recommendations.review import (
    RecommendationReviewPackage,
    ReviewerAction,
    ReviewerDisposition,
)
from ..recommendations.status import RecommendationStatus
from ..synthesis.package import EvidencePackage
from ._hiring_context import ActorContext, guard_tenant

H2_ELIGIBLE_APPLICATION_STATES = frozenset(
    {ApplicationStatus.ASSESSMENT, ApplicationStatus.IN_REVIEW})

_ACTION_EVENT = {
    ReviewerAction.REJECT_RECOMMENDATION: HiringDomainEventType.RECOMMENDATION_REJECTED_BY_REVIEWER,
    ReviewerAction.ACCEPT_FOR_CONSIDERATION: HiringDomainEventType.RECOMMENDATION_ACCEPTED_FOR_CONSIDERATION,
    ReviewerAction.REQUEST_ADDITIONAL_EVIDENCE: HiringDomainEventType.ADDITIONAL_EVIDENCE_REQUESTED,
    ReviewerAction.RETURN_FOR_REVISION: HiringDomainEventType.RECOMMENDATION_RETURNED_FOR_REVISION,
    ReviewerAction.RECORD_COMMENT: HiringDomainEventType.RECOMMENDATION_SUBMITTED_FOR_REVIEW,
}


class RecommendationGenerationService:
    def __init__(
        self, *,
        applications,
        recommendations,
        claims,
        bindings,
        dispositions,
        audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._apps = applications
        self._recs = recommendations
        self._claims = claims
        self._bindings = bindings
        self._dispositions = dispositions
        self._audit = audit
        self._new_id = id_factory

    # --- generation --------------------------------------------------------
    def generate(
        self, ctx: ActorContext, *, application_id: str, package: EvidencePackage,
        generator, evaluator, policy_refs: tuple[str, ...] = (),
        supersede_existing: bool = False, recommendation_id: Optional[str] = None,
        correlation_id: str = "",
    ) -> HiringRecommendation:
        app = self._apps.get(application_id)
        guard_tenant(ctx, record_tenant_id=app.tenant_id, entity_type="application",
                     entity_id=application_id, audit=self._audit)
        if package.tenant_id != ctx.tenant_id or package.application_id != application_id:
            raise RecommendationGenerationError("evidence package does not match application/tenant")
        if app.status not in H2_ELIGIBLE_APPLICATION_STATES:
            raise RecommendationGenerationError(
                f"application '{application_id}' is not in an H2-eligible state ({app.status.value})")

        actives = self._recs.active_for_application(application_id)
        if actives and not supersede_existing:
            raise RecommendationGenerationError(
                f"an active recommendation already exists for application '{application_id}'")

        rec_id = recommendation_id or self._new_id("rec")
        corr = correlation_id or rec_id

        required_types = tuple(sorted(
            set(package.missing_evidence_types) | package.covered_evidence_types()))
        context = GenerationContext(
            package=package, required_capability_ids=(), required_evidence_types=required_types)

        # 1) generate (fail-safe)
        try:
            output = validate_generator_output(generator.generate(context))
        except RecommendationGenerationError as exc:
            self._audit.record(
                event_type=HiringDomainEventType.RECOMMENDATION_GENERATION_FAILED,
                entity_type="recommendation", entity_id=rec_id, tenant_id=ctx.tenant_id,
                actor_id=ctx.actor_id, actor_type=ctx.actor_type, correlation_id=corr,
                payload={"error": f"{type(exc).__name__}: {exc}"})
            raise

        # 2) materialize + evaluate claims
        material_claims: list[HiringClaim] = []
        provider_error = False
        for draft in output.claims:
            claim = HiringClaim(
                claim_id=self._new_id("clm"), tenant_id=ctx.tenant_id, recommendation_id=rec_id,
                recommendation_version=1, application_id=application_id,
                candidate_subject_ref=app.candidate_id, claim_type=draft.claim_type,
                proposition=draft.proposition, competency_id=draft.competency_id,
                criterion_id=draft.criterion_id, material=draft.material,
                supporting_evidence_refs=draft.supporting_evidence_refs,
                contradicting_evidence_refs=draft.contradicting_evidence_refs,
                evidence_sufficiency=draft.evidence_sufficiency, confidence=draft.confidence,
                generator_id=output.generator_id, correlation_id=corr)
            self._audit.record(
                event_type=HiringDomainEventType.CLAIM_CREATED, entity_type="claim",
                entity_id=claim.claim_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
                actor_type=ctx.actor_type, correlation_id=corr,
                payload={"recommendation_id": rec_id, "claim_type": draft.claim_type.value})

            if claim.material:
                claim, binding = evaluator.evaluate(
                    claim, policy_refs=policy_refs, correlation_id=corr, causation_id=rec_id)
                self._bindings.add(binding)
                if not binding.evaluated:
                    provider_error = True
                self._audit.record(
                    event_type=HiringDomainEventType.CLAIM_EVALUATED, entity_type="claim",
                    entity_id=claim.claim_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
                    actor_type=ctx.actor_type, correlation_id=corr, causation_id=rec_id,
                    payload={"outcome": claim.assertion_outcome.value,
                             "trace": binding.provider_trace_id, "evaluated": str(binding.evaluated)})
            self._claims.add(claim)
            material_claims.append(claim)

        # 3) readiness gate
        material = [c for c in material_claims if c.material]
        failing = [c for c in material if c.assertion_outcome not in ASSERTION_POLICY_PASS]
        missing = tuple(package.missing_evidence_types)
        status, outcome = self._decide_status(output.outcome, missing, failing, provider_error)

        unsupported_ids = tuple(c.claim_id for c in failing)
        evidence_gaps = tuple(sorted(set(missing) | {c.criterion_id for c in failing if c.criterion_id}))

        rec = HiringRecommendation(
            recommendation_id=rec_id, tenant_id=ctx.tenant_id, application_id=application_id,
            candidate_subject_ref=app.candidate_id, requisition_id=app.requisition_id,
            job_definition_id=app.job_definition_id,
            job_definition_version=app.job_definition_version, rubric_id=package.rubric_id,
            rubric_version=package.rubric_version, outcome=outcome, confidence=output.confidence,
            uncertainty_note=output.uncertainty_note, rationale=output.rationale,
            material_claim_ids=tuple(c.claim_id for c in material),
            unsupported_claim_ids=unsupported_ids, evidence_gaps=evidence_gaps,
            evidence_package_ref=package.synthesis_package_id, evidence_refs=package.evidence_refs,
            generator_id=output.generator_id, provider_id=getattr(evaluator, "_provider_id", ""),
            policy_refs=policy_refs, provenance_id=package.fingerprint, correlation_id=corr,
            status=status, version=1)
        self._recs.add(rec)

        if missing:
            self._audit.record(
                event_type=HiringDomainEventType.EVIDENCE_INSUFFICIENCY_DETECTED,
                entity_type="recommendation", entity_id=rec_id, tenant_id=ctx.tenant_id,
                actor_id=ctx.actor_id, actor_type=ctx.actor_type, correlation_id=corr,
                payload={"missing": ",".join(missing)})
        self._audit.record(
            event_type=HiringDomainEventType.RECOMMENDATION_GENERATED, entity_type="recommendation",
            entity_id=rec_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, new_state=status.value, entity_version=rec.version,
            correlation_id=corr,
            payload={"outcome": outcome.value, "package": package.synthesis_package_id,
                     "provider_error": str(provider_error)})

        if actives and supersede_existing:
            for prior in actives:
                self._supersede(ctx, prior, rec_id, corr)
        return rec

    def _decide_status(self, gen_outcome, missing, failing, provider_error):
        if missing:
            return RecommendationStatus.EVIDENCE_INCOMPLETE, RecommendationOutcome.INSUFFICIENT_EVIDENCE
        if provider_error or failing:
            return RecommendationStatus.ASSERTION_REVIEW_REQUIRED, gen_outcome
        return RecommendationStatus.READY_FOR_HUMAN_REVIEW, gen_outcome

    def _supersede(self, ctx, prior: HiringRecommendation, new_id_: str, corr: str) -> None:
        superseded = prior.superseded(by_recommendation_id=new_id_)
        self._recs.add(superseded)
        self._audit.record(
            event_type=HiringDomainEventType.RECOMMENDATION_SUPERSEDED, entity_type="recommendation",
            entity_id=prior.recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, previous_state=prior.status.value,
            new_state=superseded.status.value, entity_version=superseded.version, correlation_id=corr,
            payload={"superseded_by": new_id_})

    # --- review ------------------------------------------------------------
    def submit_for_review(self, ctx: ActorContext, recommendation_id: str) -> HiringRecommendation:
        rec = self._get_in_tenant(ctx, recommendation_id)
        if rec.status is not RecommendationStatus.READY_FOR_HUMAN_REVIEW:
            raise RecommendationGenerationError(
                f"recommendation '{recommendation_id}' is not READY_FOR_HUMAN_REVIEW")
        self._audit.record(
            event_type=HiringDomainEventType.RECOMMENDATION_SUBMITTED_FOR_REVIEW,
            entity_type="recommendation", entity_id=recommendation_id, tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id, actor_type=ctx.actor_type, new_state=rec.status.value,
            entity_version=rec.version, correlation_id=rec.correlation_id)
        return rec

    def record_disposition(
        self, ctx: ActorContext, *, recommendation_id: str, action: ReviewerAction,
        comment: str = "", requested_evidence_types: tuple[str, ...] = (),
    ) -> ReviewerDisposition:
        # Human-only: AI/system may never dispose of (accept/reject) a recommendation.
        if ctx.actor_type is not ActorType.HUMAN:
            self._audit.record_denial(
                entity_type="recommendation", entity_id=recommendation_id, tenant_id=ctx.tenant_id,
                actor_id=ctx.actor_id, actor_type=ctx.actor_type,
                reason=f"non_human_review_action:{action.value}")
            raise ReviewerAuthorityError(
                f"actor_type {ctx.actor_type.value} may not perform reviewer action {action.value}")
        rec = self._get_in_tenant(ctx, recommendation_id)

        if action is ReviewerAction.REJECT_RECOMMENDATION:
            rejected = rec.with_status(RecommendationStatus.REJECTED_BY_REVIEW)
            self._recs.add(rejected)
            rec = rejected

        disposition = ReviewerDisposition(
            disposition_id=self._new_id("disp"), tenant_id=ctx.tenant_id,
            recommendation_id=recommendation_id, recommendation_version=rec.version, action=action,
            reviewer_id=ctx.actor_id, comment=comment,
            requested_evidence_types=tuple(requested_evidence_types), correlation_id=rec.correlation_id)
        self._dispositions.add(disposition)
        self._audit.record(
            event_type=_ACTION_EVENT[action], entity_type="recommendation",
            entity_id=recommendation_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, new_state=rec.status.value, entity_version=rec.version,
            correlation_id=rec.correlation_id, payload={"action": action.value})
        return disposition

    def build_review_package(self, ctx: ActorContext, recommendation_id: str) -> RecommendationReviewPackage:
        rec = self._get_in_tenant(ctx, recommendation_id)
        claims = self._claims.claims_for(recommendation_id, 1)
        history = tuple(r.version for r in self._recs.history(recommendation_id))
        available = self._available_actions(rec.status)
        return RecommendationReviewPackage.build(
            recommendation=rec, claims=claims, version_history=history, available_actions=available)

    def _available_actions(self, status: RecommendationStatus) -> tuple[str, ...]:
        if status in (RecommendationStatus.REJECTED_BY_REVIEW, RecommendationStatus.SUPERSEDED):
            return (ReviewerAction.RECORD_COMMENT.value,)
        return tuple(a.value for a in ReviewerAction)

    def _get_in_tenant(self, ctx: ActorContext, recommendation_id: str) -> HiringRecommendation:
        rec = self._recs.get(recommendation_id)
        guard_tenant(ctx, record_tenant_id=rec.tenant_id, entity_type="recommendation",
                     entity_id=recommendation_id, audit=self._audit)
        return rec
