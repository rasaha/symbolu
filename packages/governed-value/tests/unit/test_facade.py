from governed_value.api import GovernedValueApplication
from governed_value.domain.enums import (
    AssessmentStage,
    AuthorityStatus,
    EvidenceStatus,
)

from ..scenario import scorable_support_case


def test_facade_scores_and_emits_classified_event():
    app = GovernedValueApplication()
    result = app.score(scorable_support_case())
    assert result.reported_roi is not None

    log = app.events.log
    assert len(log) == 1
    ev = log[0]
    assert ev.event_type == "governed_value.scored"
    assert ev.agent_id == "support-manila-1"
    assert ev.stage is AssessmentStage.POST_DEPLOYMENT_VALUE
    assert ev.evidence_status is EvidenceStatus.REPORTED
    assert ev.authority_status is AuthorityStatus.UNVERIFIED
    assert ev.reported_net_governed_value_minor_units == 70_000
    assert ev.risk_adjusted_net_governed_value_minor_units == 69_800
