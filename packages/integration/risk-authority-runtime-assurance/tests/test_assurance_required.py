"""Assurance-required (D4) pre-effect gate tests (spec §7, §16, §20).

Default is additive (never blocks). The opt-in assurance-required gate fails
closed when current assurance is absent / stale / not-NORMAL — never widening
authority. The read seam grants no authority.
"""

from __future__ import annotations

from datetime import timedelta

from ugence_risk_authority_runtime_assurance import AssessmentOutcome, RuntimeRiskLevel

from ra7_scenario import (
    FIXED_NOW,
    TENANT,
    WORKFLOW,
    build_reference_service,
    make_observation,
)

NOW = FIXED_NOW


def _service_with_normal_state():
    service = build_reference_service()
    service.observe(
        make_observation(1, detail={"exposure": {"model_cost": 10.0}}), produced_at=NOW
    )
    return service


def test_not_required_always_continues():
    service = build_reference_service()  # no assurance state recorded at all
    dec = service.pre_effect_assurance_decision(
        tenant_id=TENANT, workflow_instance_id=WORKFLOW, assurance_required=False, now=NOW
    )
    assert dec.outcome is AssessmentOutcome.CONTINUE_UNDER_RA6
    assert dec.executable


def test_required_with_fresh_normal_continues():
    service = _service_with_normal_state()
    dec = service.pre_effect_assurance_decision(
        tenant_id=TENANT, workflow_instance_id=WORKFLOW, assurance_required=True, now=NOW,
        max_age=timedelta(minutes=5),
    )
    assert dec.outcome is AssessmentOutcome.CONTINUE_UNDER_RA6
    assert dec.state is not None and dec.state.risk_level is RuntimeRiskLevel.NORMAL


def test_required_with_no_state_fails_closed():
    service = build_reference_service()
    dec = service.pre_effect_assurance_decision(
        tenant_id=TENANT, workflow_instance_id=WORKFLOW, assurance_required=True, now=NOW
    )
    assert dec.outcome is AssessmentOutcome.ERROR_NON_EXECUTABLE
    assert not dec.executable


def test_required_with_stale_state_fails_closed():
    service = _service_with_normal_state()
    dec = service.pre_effect_assurance_decision(
        tenant_id=TENANT, workflow_instance_id=WORKFLOW, assurance_required=True,
        now=NOW + timedelta(hours=1), max_age=timedelta(minutes=5),
    )
    assert dec.outcome is AssessmentOutcome.ERROR_NON_EXECUTABLE


def test_required_with_escalated_state_fails_closed():
    service = build_reference_service()
    for i in range(1, 7):
        service.observe(
            make_observation(i, detail={"exposure": {"model_cost": 9000.0}}), produced_at=NOW
        )
    dec = service.pre_effect_assurance_decision(
        tenant_id=TENANT, workflow_instance_id=WORKFLOW, assurance_required=True, now=NOW
    )
    assert dec.outcome is AssessmentOutcome.ERROR_NON_EXECUTABLE
    assert dec.state is not None and dec.state.risk_level is RuntimeRiskLevel.ESCALATED


def test_deny_verdict_flag_uses_deny_outcome():
    service = build_reference_service()
    dec = service.pre_effect_assurance_decision(
        tenant_id=TENANT, workflow_instance_id=WORKFLOW, assurance_required=True, now=NOW,
        deny_verdict=True,
    )
    assert dec.outcome is AssessmentOutcome.DENY_IF_ASSURANCE_REQUIRED


def test_unknown_assessment_does_not_overwrite_known_state():
    # First establish NORMAL, then feed an unresolvable-policy observation (UNKNOWN).
    from ugence_risk_authority_runtime_assurance import TrajectoryPolicyRef

    service = _service_with_normal_state()
    service.observe(
        make_observation(2, policy_ref=TrajectoryPolicyRef("unknown", "1")), produced_at=NOW
    )
    state = service.assurance_state(TENANT, WORKFLOW)
    assert state is not None and state.risk_level is RuntimeRiskLevel.NORMAL


def test_assurance_state_absent_for_unseen_trajectory():
    service = build_reference_service()
    assert service.assurance_state("nope", "nope") is None
