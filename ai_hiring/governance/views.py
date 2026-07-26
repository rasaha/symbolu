"""Governance views (H3): review workspace, dashboard, recommendation history.

Human-facing read models that combine the hiring recommendation/claims with the
bound DGM case, kernel recommendation, decision, and review tasks. No binding
decision is made here; these are read-only projections for reviewers and operators.
"""

from __future__ import annotations

from typing import Optional

from ..domain.base import DomainModel
from ..errors import CrossTenantHiringAccessError


class ReviewWorkspaceView(DomainModel):
    recommendation_id: str
    tenant_id: str
    application_id: str
    candidate_subject_ref: str
    recommendation_status: str
    recommendation_outcome: str
    advisory: bool = True
    decision_case_id: str = ""
    case_status: str = ""
    kernel_recommendation_id: str = ""
    proposed_outcome: str = ""
    binding_status: str = ""
    decision_outcome: str = ""
    material_claim_count: int = 0
    unsupported_claim_count: int = 0
    evidence_gaps: tuple[str, ...] = ()
    open_review_tasks: tuple[str, ...] = ()
    reviewer_actions: tuple[str, ...] = ()


class GovernanceCaseCard(DomainModel):
    recommendation_id: str
    application_id: str
    decision_case_id: str
    binding_status: str
    case_status: str
    decision_outcome: str = ""
    overridden: bool = False


class GovernanceDashboardView(DomainModel):
    tenant_id: str
    total: int
    open_count: int
    decided_count: int
    superseded_count: int
    cases: tuple[GovernanceCaseCard, ...] = ()


class RecommendationHistoryEntry(DomainModel):
    recommendation_id: str
    status: str
    outcome: str
    version: int
    decision_case_id: str = ""
    binding_status: str = ""
    decision_outcome: str = ""


class RecommendationHistoryView(DomainModel):
    application_id: str
    tenant_id: str
    entries: tuple[RecommendationHistoryEntry, ...] = ()


class GovernanceViewService:
    """Builds the H3 read models from hiring + kernel state."""

    def __init__(self, *, recommendations, claims, bindings, cases, case_decisions) -> None:
        self._recs = recommendations
        self._claims = claims
        self._bindings = bindings
        self._cases = cases
        self._case_decs = case_decisions

    def review_workspace(self, ctx, recommendation_id: str,
                         reviewer_actions: tuple[str, ...] = ()) -> ReviewWorkspaceView:
        rec = self._recs.get(recommendation_id)
        if rec.tenant_id != ctx.tenant_id:
            raise CrossTenantHiringAccessError(f"cross-tenant review workspace: {recommendation_id}")
        binding = self._bindings.for_recommendation(recommendation_id)
        claims = self._claims.claims_for(recommendation_id, 1)
        case_status = decision_outcome = kernel_rec_id = proposed = binding_status = case_id = ""
        open_tasks: tuple[str, ...] = ()
        if binding is not None:
            case_id = binding.decision_case_id
            binding_status = binding.status.value
            kernel_rec_id = binding.kernel_recommendation_id
            case = self._cases.get_case(case_id)
            case_status = case.status.value
            open_tasks = tuple(t.task_id for t in case.review_tasks if t.status.value == "PENDING")
            decisions = self._case_decs.list_decisions(case_id)
            if decisions:
                decision_outcome = decisions[-1].outcome.value
        return ReviewWorkspaceView(
            recommendation_id=recommendation_id, tenant_id=rec.tenant_id,
            application_id=rec.application_id, candidate_subject_ref=rec.candidate_subject_ref,
            recommendation_status=rec.status.value, recommendation_outcome=rec.outcome.value,
            advisory=rec.advisory, decision_case_id=case_id, case_status=case_status,
            kernel_recommendation_id=kernel_rec_id, proposed_outcome=proposed,
            binding_status=binding_status, decision_outcome=decision_outcome,
            material_claim_count=len([c for c in claims if c.material]),
            unsupported_claim_count=len(rec.unsupported_claim_ids), evidence_gaps=rec.evidence_gaps,
            open_review_tasks=open_tasks, reviewer_actions=reviewer_actions)

    def dashboard(self, ctx) -> GovernanceDashboardView:
        bindings = self._bindings.by_tenant(ctx.tenant_id)
        cards = []
        oc = dc = sc = 0
        for b in bindings:
            case = self._cases.get_case(b.decision_case_id)
            decisions = self._case_decs.list_decisions(b.decision_case_id)
            outcome = decisions[-1].outcome.value if decisions else ""
            overridden = bool(b.override_id)
            cards.append(GovernanceCaseCard(
                recommendation_id=b.hiring_recommendation_id, application_id=b.application_id,
                decision_case_id=b.decision_case_id, binding_status=b.status.value,
                case_status=case.status.value, decision_outcome=outcome, overridden=overridden))
            if b.status.value == "OPEN": oc += 1
            elif b.status.value == "DECIDED": dc += 1
            elif b.status.value == "SUPERSEDED": sc += 1
        return GovernanceDashboardView(
            tenant_id=ctx.tenant_id, total=len(bindings), open_count=oc, decided_count=dc,
            superseded_count=sc, cases=tuple(cards))

    def recommendation_history(self, ctx, application_id: str) -> RecommendationHistoryView:
        recs = self._recs.list_for_application(application_id)
        entries = []
        for r in recs:
            if r.tenant_id != ctx.tenant_id:
                continue
            b = self._bindings.for_recommendation(r.recommendation_id)
            case_id = b.decision_case_id if b else ""
            bstatus = b.status.value if b else ""
            doutcome = ""
            if b:
                decisions = self._case_decs.list_decisions(b.decision_case_id)
                doutcome = decisions[-1].outcome.value if decisions else ""
            entries.append(RecommendationHistoryEntry(
                recommendation_id=r.recommendation_id, status=r.status.value, outcome=r.outcome.value,
                version=r.version, decision_case_id=case_id, binding_status=bstatus,
                decision_outcome=doutcome))
        return RecommendationHistoryView(
            application_id=application_id, tenant_id=ctx.tenant_id, entries=tuple(entries))
