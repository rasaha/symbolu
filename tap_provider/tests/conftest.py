"""Shared fixtures + kernel assessment/recommendation harness for TAP tests.

Drives the real DGM assessment → recommendation → decision-trace workflow with a
TAP assertion evaluation as the cited assessment. TAP integrates here — into
assessment/recommendation — and **never** into authorization or execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from governance_providers.api import (
    AssertionAssessment,
    AssertionAssessmentIntegration,
    AssertionCoverage,
    AssertionGovernanceRequest,
)

# TAP coverage → recommended outcome. UNSUPPORTED/INDETERMINATE can never become
# ADVANCE, so an unsupported/indeterminate assertion cannot be represented as
# supported in the recommendation.
_OUTCOME_BY_COVERAGE = {
    AssertionCoverage.SUPPORTED: "ADVANCE",
    AssertionCoverage.CONSTRAINED: "HOLD",
    AssertionCoverage.UNSUPPORTED: "REJECT",
    AssertionCoverage.INDETERMINATE: "REQUEST_ADDITIONAL_EVIDENCE",
}


@dataclass
class AssertionLifecycleResult:
    coverage: str
    finalized: bool
    blocked: bool
    evidence_coverage: float
    unsupported_elements: tuple[str, ...]
    constraints: tuple[str, ...]
    obligations: tuple[str, ...]
    omitted_qualifiers: tuple[str, ...]
    proposed_outcome: str
    recommendation_id: str
    cites_assessment: bool
    events: set
    assessment: AssertionAssessment


class _NeutralLinked:
    """A neutral finalized linked record so the case can link the assessment."""

    def get_record(self, *, tenant_id, record_type, record_id, version=None):
        from decision_governance.api.ports import FINALIZED_STATUS, LinkedRecordSnapshot
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id, version=version or 1,
            tenant_id="t", status=FINALIZED_STATUS, subject_ref="subject")


def run_tap_assessment_lifecycle(provider, request: AssertionGovernanceRequest
                                 ) -> AssertionLifecycleResult:
    """Assess an assertion with TAP, then cite it in a DGM recommendation.

    Never dispatches, authorizes, or executes — assertion governance feeds the
    assessment/recommendation workflow only.
    """
    from decision_governance.api.audit import AuditService, InMemoryAuditRepository
    from decision_governance.api.identity import StaticIdentityProvider
    from decision_governance.api.policy import (
        AccessGrant, EvidenceAccessPolicy, GrantStore, Permission)
    from decision_governance.api.repositories import InMemoryDecisionCaseRepository
    from decision_governance.api.services import (
        CaseRecommendationService, CaseValidationService, DecisionCaseService)
    from decision_governance.api.contracts import (
        GeneratorType, ProposedOutcome, VersionedRef)
    from decision_governance.api.vocabulary import ReasonCode

    t, actor, subject = "t", "gov", "subject"
    idp = StaticIdentityProvider(); idp.register_human(actor)
    grants = GrantStore(); grants.add(AccessGrant(actor, t, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants); audit = AuditService(InMemoryAuditRepository())
    cr = InMemoryDecisionCaseRepository()
    val = CaseValidationService(_NeutralLinked())
    cases = DecisionCaseService(cr, val, audit, idp, policy)
    rec_svc = CaseRecommendationService(cr, val, audit, idp, policy)

    # 1) TAP evaluates the assertion against evidence → AssertionAssessment.
    # A direct evaluate() captures the full structured result (constraints /
    # obligations / omitted qualifiers) that the neutral AssertionAssessment does
    # not carry directly; the integration path produces the cited assessment.
    result = provider.evaluate(request)
    integration = AssertionAssessmentIntegration(provider)
    assessment = integration.assess(request)
    assessment_id = "tap-" + assessment.fingerprint[:12]

    # 2) link the assessment into a decision case
    case = cases.create_case(tenant_id=t, decision_type="approve",
                             subject_ids=(subject,), created_by=actor)
    cases.link_assessment(case_id=case.decision_case_id, assessment_id=assessment_id,
                          version=1, actor=actor)

    # 3) submit a recommendation citing the TAP assessment
    proposed = ProposedOutcome[_OUTCOME_BY_COVERAGE[assessment.coverage]]
    rec = rec_svc.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="assertion_support",
        proposed_outcome=proposed, generated_by=actor,
        generator_type=GeneratorType.DETERMINISTIC_POLICY,
        assessment_refs=(VersionedRef(ref_id=assessment_id, version=1, kind="assessment"),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,))

    events = {e.event_type for e in audit._repo.all()}
    return AssertionLifecycleResult(
        coverage=assessment.coverage.value, finalized=assessment.finalized,
        blocked=assessment.blocked, evidence_coverage=assessment.evidence_coverage,
        unsupported_elements=assessment.unsupported_elements,
        constraints=result.constraints, obligations=result.obligations,
        omitted_qualifiers=result.omitted_qualifiers,
        proposed_outcome=proposed.value, recommendation_id=rec.recommendation_id,
        cites_assessment=assessment_id in {r.ref_id for r in rec.assessment_refs},
        events=events, assessment=assessment)
