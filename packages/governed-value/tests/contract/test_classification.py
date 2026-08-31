"""GV-0: classification is three orthogonal axes and never over-claims.

This kernel has no evidence, attribution or authority binding, so every result —
scorable or not — must be POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED. Naming an
input "realized" (or anything else) can never lift it to OBSERVED / ATTRIBUTED /
VERIFIED.
"""

from decimal import Decimal

from governed_value.domain.attribution import AttributionEvidence
from governed_value.domain.enums import (
    AssessmentStage,
    AuthorityStatus,
    EvidenceStatus,
    OutcomeClass,
    Scorability,
)
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def _forbidden_evidence():
    return {EvidenceStatus.OBSERVED, EvidenceStatus.ATTRIBUTED, EvidenceStatus.VERIFIED}


def test_scorable_result_is_reported_unverified():
    r = score_case(scorable_support_case())
    assert r.stage is AssessmentStage.POST_DEPLOYMENT_VALUE
    assert r.evidence_status is EvidenceStatus.REPORTED
    assert r.authority_status is AuthorityStatus.UNVERIFIED
    assert r.evidence_status not in _forbidden_evidence()


def test_not_scorable_result_keeps_same_honest_classification():
    # A fatal guard suppresses the headline but must not change the classification.
    r = score_case(
        scorable_support_case(attribution=AttributionEvidence(baseline_captured=False))
    )
    assert r.scorability is Scorability.NOT_SCORABLE
    assert r.reported_roi is None and r.risk_adjusted_roi is None
    assert r.stage is AssessmentStage.POST_DEPLOYMENT_VALUE
    assert r.evidence_status is EvidenceStatus.REPORTED
    assert r.authority_status is AuthorityStatus.UNVERIFIED


def test_evidence_status_is_orthogonal_to_scorability():
    # Both a clean and a caveated result carry REPORTED — evidence != verdict.
    clean = score_case(scorable_support_case())
    from ..scenario import money
    from governed_value.domain.cost import CostToServe

    thin = CostToServe(currency="USD", inference=money(200_00))
    degraded = score_case(scorable_support_case(cost=thin))
    assert degraded.scorability is Scorability.DEGRADED
    assert clean.evidence_status is degraded.evidence_status is EvidenceStatus.REPORTED


def test_reported_confidence_is_caller_supplied_and_non_evidential():
    from governed_value.domain.enums import ConfidenceClass

    # Caller asserts HIGH confidence; it is echoed but does NOT change the money,
    # the evidence status, or the scorability — it is not an evidence signal.
    base = score_case(scorable_support_case())
    hi = score_case(scorable_support_case(reported_confidence=ConfidenceClass.HIGH))
    assert hi.reported_confidence is ConfidenceClass.HIGH
    assert hi.evidence_status is EvidenceStatus.REPORTED  # unchanged by confidence
    assert hi.reported_net_governed_value == base.reported_net_governed_value
    assert hi.reported_roi == base.reported_roi
