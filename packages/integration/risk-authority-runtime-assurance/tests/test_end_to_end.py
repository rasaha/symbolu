"""End-to-end observe→signal→reassess→revoke through the REAL RA-6 stack.

Nothing mocked: a real ``AuthorityReassessor`` + authenticated
``AuthorityLifecycleService`` + ``ReferenceAuthorityStore`` sit behind the leaf's
neutral intake port. This exercises the full ratified loop and the invariants that
RA-7 observes/assesses while RA-6 owns the consequence (spec §18; matrix 3–5,
25–28).
"""

from __future__ import annotations

from datetime import timedelta

from ugence_risk_authority_runtime_assurance import AssessmentOutcome, RuntimeRiskLevel

from ra7_scenario import (
    ENVELOPE,
    FIXED_NOW,
    TENANT,
    WORKFLOW,
    build_ra6_harness,
    build_reference_service,
    make_observation,
)

NOW = FIXED_NOW


def _drive(service, harness, n, amount=9000.0):
    last = None
    for i in range(1, n + 1):
        last = service.observe(
            make_observation(i, detail={"exposure": {"model_cost": amount}}),
            produced_at=NOW,
        )
    return last


# -- matrix 1: normal → no revocation --------------------------------------
def test_normal_trajectory_causes_no_revocation():
    harness = build_ra6_harness()
    service = build_reference_service(harness=harness)
    out = _drive(service, harness, 3, amount=100.0)
    assert out.assessment.risk_level is RuntimeRiskLevel.NORMAL
    assert out.handoff is None
    assert not harness.is_envelope_revoked(ENVELOPE)


# -- matrix 3–5, 16: escalation → signal → REAL targeted revocation --------
def test_cumulative_escalation_revokes_envelope_via_ra6():
    harness = build_ra6_harness()
    service = build_reference_service(harness=harness)
    assert not harness.is_envelope_revoked(ENVELOPE)
    out = _drive(service, harness, 6)  # 6×9000 = 54000 > 50000
    assert out.outcome is AssessmentOutcome.SIGNAL_REASSESS
    assert out.handoff is not None and out.handoff.submitted
    # The consequence was enacted by RA-6's writer — a TARGETED envelope revocation.
    assert harness.is_envelope_revoked(ENVELOPE)


# -- matrix 27, 8: replayed signal is idempotent (grow-only) ---------------
def test_replayed_observation_is_idempotent_no_double_effect():
    harness = build_ra6_harness()
    service = build_reference_service(harness=harness)
    _drive(service, harness, 6)
    revoked_events = [e for e in harness.events]
    # Re-submit the very same observations: dedup at observer ⇒ no new assessment.
    for i in range(1, 7):
        again = service.observe(
            make_observation(i, detail={"exposure": {"model_cost": 9000.0}}),
            produced_at=NOW,
        )
        assert again.outcome is AssessmentOutcome.IGNORE_EVENT
    # No additional lifecycle events beyond the first revocation burst.
    assert len(harness.events) == len(revoked_events)


# -- matrix 25, 26: recovery to NORMAL does not resurrect the envelope ------
def test_recovery_to_normal_does_not_resurrect_revoked_envelope():
    harness = build_ra6_harness()
    service = build_reference_service(harness=harness)
    _drive(service, harness, 6)
    assert harness.is_envelope_revoked(ENVELOPE)
    # A later, individually-benign observation on the same envelope: even a NORMAL
    # assessment cannot un-revoke (grow-only revocation is RA-6's; RA-7 emits only
    # escalation signals, never a resurrection).
    out = service.observe(
        make_observation(99, workflow_instance_id="wf_fresh", detail={"exposure": {"model_cost": 1.0}}),
        produced_at=NOW,
    )
    assert out.assessment.risk_level is RuntimeRiskLevel.NORMAL
    assert harness.is_envelope_revoked(ENVELOPE)  # still revoked


# -- matrix 28: signal after envelope already revoked → idempotent no-op ----
def test_signal_after_already_revoked_is_idempotent():
    harness = build_ra6_harness()
    service = build_reference_service(harness=harness)
    _drive(service, harness, 6)
    assert harness.is_envelope_revoked(ENVELOPE)
    # A brand-new escalating trajectory on the SAME envelope re-signals; RA-6
    # revocation is a set union ⇒ still revoked, no error, no widening.
    out = None
    for i in range(1, 7):
        out = service.observe(
            make_observation(i, workflow_instance_id="wf_second", detail={"exposure": {"model_cost": 9000.0}}),
            produced_at=NOW,
        )
    assert out.handoff is not None and out.handoff.submitted
    assert harness.is_envelope_revoked(ENVELOPE)


# -- matrix 4: observer cannot revoke directly (structural) -----------------
def test_service_has_no_direct_lifecycle_mutation():
    service = build_reference_service(harness=build_ra6_harness())
    for attr in ("revoke_envelope", "revoke_subject", "revoke_model", "advance_epoch", "emergency_stop"):
        assert not hasattr(service, attr)


# -- matrix 24: RA-6 signal sink unavailable → no widen ---------------------
def test_ra6_sink_unavailable_leaves_authority_unchanged():
    from ugence_risk_authority_runtime_assurance import AuthorityReassessmentSignalEmitter

    class Broken:
        def submit(self, signal):
            raise RuntimeError("intake down")

    harness = build_ra6_harness()
    service = build_reference_service()
    # Rewire the service's emitter to a broken sink.
    service._emitter = AuthorityReassessmentSignalEmitter(Broken())
    out = _drive(service, harness, 6)
    assert out.assessment.risk_level is RuntimeRiskLevel.ESCALATED
    assert out.handoff is not None and not out.handoff.submitted
    assert not harness.is_envelope_revoked(ENVELOPE)  # authority unchanged


# -- material escalation without an emitter still assesses (additive) -------
def test_no_emitter_still_produces_assessment():
    harness = build_ra6_harness()
    service = build_reference_service()  # no emitter wired
    out = _drive(service, harness, 6)
    assert out.assessment.risk_level is RuntimeRiskLevel.ESCALATED
    assert out.handoff is None
    assert not harness.is_envelope_revoked(ENVELOPE)
