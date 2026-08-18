"""A controller abstention is a typed non-evaluation — never a manufactured approval.

The properties pinned here are the six the ADR §11 forbids individually, each as its own
assertion rather than folded into one "it works" test: an abstention must not become a
recommendation, must not enter the seam, must not manufacture a subject digest, must not
produce PASS/ALLOW/authorization, must not trigger ActionGate or execution, and must
carry its reason and available provenance without overstating what was evaluated.
"""

from __future__ import annotations

import pytest

from conftest import build_abstention, fixed_clock
from ugence_cloud_scaling_controller.planning.recommendation import (
    RecommendationAbstention,
)

from ugence_cloud_scaling_risk_integration import (
    AdapterOutcomeStatus,
    AuthenticatedAbstention,
    CloudScalingRiskAdapter,
    ProjectionError,
    authenticate_controller_output,
    project_recommendation,
)


@pytest.fixture
def abstention() -> RecommendationAbstention:
    return build_abstention()


def test_an_abstention_produces_a_typed_non_evaluation(forbidden_seam, abstention):
    adapter = CloudScalingRiskAdapter(seam=forbidden_seam, clock=fixed_clock())
    outcome = adapter.evaluate(abstention.to_canonical_dict())
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM


def test_an_abstention_never_reaches_the_evaluation_seam(recording_seam, abstention):
    adapter = CloudScalingRiskAdapter(seam=recording_seam, clock=fixed_clock())
    adapter.evaluate(abstention.to_canonical_dict())
    assert not recording_seam.reached, "the seam observed an abstention"


def test_an_abstention_never_becomes_a_recommendation(abstention):
    result = authenticate_controller_output(abstention.to_canonical_dict())
    assert isinstance(result, AuthenticatedAbstention)
    with pytest.raises(ProjectionError, match="requires an AuthenticatedRecommendation"):
        project_recommendation(result)


def test_an_abstention_cannot_be_projected_through_the_adapter(forbidden_seam, abstention):
    adapter = CloudScalingRiskAdapter(seam=forbidden_seam, clock=fixed_clock())
    with pytest.raises(ProjectionError, match="abstention"):
        adapter.project(abstention.to_canonical_dict())


def test_an_abstention_manufactures_no_subject_digest(forbidden_seam, abstention):
    adapter = CloudScalingRiskAdapter(seam=forbidden_seam, clock=fixed_clock())
    outcome = adapter.evaluate(abstention.to_canonical_dict())
    assert outcome.projection is None
    assert outcome.recommendation_digest is None, (
        "an abstention is not a recommendation, so it has no recommendation digest to "
        "report — reporting its own digest under that name would overstate the record"
    )


def test_an_abstention_produces_no_pass_allow_or_authorization(forbidden_seam, abstention):
    adapter = CloudScalingRiskAdapter(seam=forbidden_seam, clock=fixed_clock())
    outcome = adapter.evaluate(abstention.to_canonical_dict())
    assert outcome.decision is None
    assert outcome.disposition is None
    assert outcome.is_risk_decision is False
    assert outcome.grants_authority is False


def test_an_abstention_triggers_no_actiongate_or_execution(forbidden_seam, abstention):
    adapter = CloudScalingRiskAdapter(seam=forbidden_seam, clock=fixed_clock())
    outcome = adapter.evaluate(abstention.to_canonical_dict())
    for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                 "credential_issued", "actuation_performed", "effect_verified",
                 "executable"):
        assert getattr(outcome, flag) is False


def test_an_abstention_preserves_its_reason_and_provenance(forbidden_seam, abstention):
    adapter = CloudScalingRiskAdapter(seam=forbidden_seam, clock=fixed_clock())
    outcome = adapter.evaluate(abstention.to_canonical_dict())

    assert outcome.abstention_reason == abstention.reason.value
    assert outcome.subject_id == abstention.subject.workload_id
    assert outcome.tenant_id == abstention.subject.tenant_id
    # Only the digests the controller actually had bound before abstaining are carried;
    # nothing is invented to fill the gaps.
    available = {
        value
        for value in (
            abstention.forecast_evidence_digest,
            abstention.canonical_state_digest,
            abstention.cost_evidence_digest,
        )
        if value is not None
    }
    assert set(outcome.evidence_references) == available
    assert outcome.evidence_references == tuple(sorted(outcome.evidence_references))


def test_an_expired_abstention_is_still_an_abstention_not_an_expiry(forbidden_seam, abstention):
    """No validity gate runs for an abstention: there is no window to be inside of."""

    from datetime import timedelta

    adapter = CloudScalingRiskAdapter(
        seam=forbidden_seam, clock=fixed_clock(abstention.recommendation_time + timedelta(days=7))
    )
    outcome = adapter.evaluate(abstention.to_canonical_dict())
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM
    assert outcome.rejection_reason is None


def test_a_live_abstention_object_is_accepted_without_an_expectation(forbidden_seam, abstention):
    """No digest expectation is demanded, because nothing will be projected from it."""

    adapter = CloudScalingRiskAdapter(seam=forbidden_seam, clock=fixed_clock())
    outcome = adapter.evaluate(abstention)
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM
