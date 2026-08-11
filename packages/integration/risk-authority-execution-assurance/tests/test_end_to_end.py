"""End-to-end assess→signal→reassess→revoke through the REAL DA + RA-6 stacks.

Nothing mocked in the consequence path: a real DA ``ReconciliationService`` under
RA-8's safe aggregation, then a real ``AuthorityReassessor`` + authenticated
``AuthorityLifecycleService`` + ``ReferenceAuthorityStore`` behind the leaf's
neutral intake port. Exercises the full ratified loop (spec §22, §35) and the
invariants that RA-8 observes/assesses while RA-6 owns the consequence.
"""

from __future__ import annotations

from ugence_decision_authority.execution.status import BusinessOutcome, Finality

from ugence_risk_authority_execution_assurance import (
    EffectAssuranceSignalEmitter,
    EffectReconciliationOutcome,
    HandoffOutcome,
)

from ra8_scenario import (
    ENVELOPE,
    assess,
    build_ra6_harness,
    build_reference_service,
    make_observation,
)


# -- MATCHED → no lifecycle mutation ---------------------------------------
def test_matched_effect_causes_no_revocation():
    harness = build_ra6_harness()
    svc = build_reference_service(harness=harness)
    out = assess(svc, [make_observation("o1", BusinessOutcome.SUCCEEDED)])
    assert out.outcome is EffectReconciliationOutcome.MATCHED
    assert out.handoff is None  # non-material → no signal
    assert not harness.is_envelope_revoked(ENVELOPE)
    assert harness.events == []


# -- mismatch → neutral signal → REAL targeted envelope revocation ---------
def test_mismatch_effect_revokes_envelope_via_ra6():
    harness = build_ra6_harness()
    svc = build_reference_service(harness=harness)
    assert not harness.is_envelope_revoked(ENVELOPE)
    out = assess(svc, [make_observation("o1", BusinessOutcome.FAILED)])
    assert out.outcome is EffectReconciliationOutcome.MISMATCH
    assert out.handoff is not None and out.handoff.submitted
    # The consequence was enacted by RA-6's writer — a TARGETED envelope revocation.
    # Any subsequent StatusAwareActionGate / pre-effect recheck reads this revoked
    # snapshot and DENIES the next consequential action (spec §22/§35).
    assert harness.is_envelope_revoked(ENVELOPE)


# -- M-1 through the whole stack: favorable-late cannot mask unfavorable ----
def test_m1_favorable_late_still_revokes():
    harness = build_ra6_harness()
    svc = build_reference_service(harness=harness)
    out = assess(
        svc,
        [
            make_observation("o1", BusinessOutcome.FAILED, external_effect_id="e-fail"),
            make_observation("o2", BusinessOutcome.SUCCEEDED, external_effect_id="e-ok"),
        ],
    )
    assert out.assessment.da_status.value == "RECONCILED"  # DA latest-wins would pass it
    assert out.outcome.is_material
    assert out.handoff.submitted
    assert harness.is_envelope_revoked(ENVELOPE)


# -- MATCHED cannot resurrect a revoked envelope (spec §24) -----------------
def test_matched_cannot_resurrect_revoked_envelope():
    harness = build_ra6_harness()
    svc = build_reference_service(harness=harness)
    assess(svc, [make_observation("o1", BusinessOutcome.FAILED)])
    assert harness.is_envelope_revoked(ENVELOPE)
    # A later, fully-favorable reconciliation on the SAME envelope: even MATCHED
    # emits no signal and can never un-revoke (RA-6 revocation is monotonic; RA-8
    # emits only mismatch signals, never a resurrection).
    later = assess(svc, [make_observation("o2", BusinessOutcome.SUCCEEDED)])
    assert later.outcome is EffectReconciliationOutcome.MATCHED
    assert later.handoff is None
    assert harness.is_envelope_revoked(ENVELOPE)  # still revoked


# -- RA-8 cannot revoke / mint directly (structural) -----------------------
def test_service_has_no_direct_lifecycle_mutation():
    svc = build_reference_service(harness=build_ra6_harness())
    for attr in ("revoke_envelope", "revoke_subject", "revoke_model", "advance_epoch",
                 "emergency_stop", "mint", "issue_envelope"):
        assert not hasattr(svc, attr)


# -- RA-6 signal sink unavailable → assessment stands, authority unchanged --
def test_ra6_sink_unavailable_leaves_authority_unchanged():
    class Broken:
        def submit(self, signal):
            raise RuntimeError("intake down")

    harness = build_ra6_harness()
    svc = build_reference_service(harness=harness)
    svc._emitter = EffectAssuranceSignalEmitter(Broken())
    out = assess(svc, [make_observation("o1", BusinessOutcome.FAILED)])
    assert out.outcome is EffectReconciliationOutcome.MISMATCH  # evidence stands
    assert out.handoff is not None and out.handoff.outcome is HandoffOutcome.SINK_UNAVAILABLE
    assert not harness.is_envelope_revoked(ENVELOPE)  # authority unchanged, not widened


# -- compensation recommendation is advisory, never self-executing ---------
def test_compensation_recommendation_is_not_authority():
    harness = build_ra6_harness()
    svc = build_reference_service(harness=harness)
    out = assess(svc, [make_observation("o1", BusinessOutcome.FAILED)])
    assert out.assessment.compensation_recommended is True
    # It is only a boolean advisory flag on an evidence object — there is no
    # compensation-execution method anywhere on the RA-8 surface; a compensating
    # action requires fresh governed authority (spec §21).
    assert not hasattr(out, "execute_compensation")
    assert not hasattr(svc, "execute_compensation")
    assert not hasattr(out.assessment, "compensation_authority")


def test_matched_does_not_recommend_compensation():
    harness = build_ra6_harness()
    svc = build_reference_service(harness=harness)
    out = assess(svc, [make_observation("o1", BusinessOutcome.SUCCEEDED)])
    assert out.assessment.compensation_recommended is False


# -- a second escalating signal on an already-revoked envelope is idempotent -
def test_repeated_mismatch_is_idempotent_no_widen():
    harness = build_ra6_harness()
    svc = build_reference_service(harness=harness)
    assess(svc, [make_observation("o1", BusinessOutcome.FAILED)])
    events_after_first = len(harness.events)
    # A fresh mismatch on the same envelope re-signals; RA-6 revocation is a set
    # union ⇒ still revoked, no error, no widening.
    out = assess(svc, [make_observation("o2", BusinessOutcome.REJECTED)])
    assert out.handoff.submitted
    assert harness.is_envelope_revoked(ENVELOPE)
    assert len(harness.events) >= events_after_first
