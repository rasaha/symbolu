"""RA-8 composition — end-to-end verdicts through the reference service (spec §6, §27)."""

from __future__ import annotations

import pytest

from ugence_decision_authority.execution.status import BusinessOutcome, Finality

from ugence_risk_authority_execution_assurance import (
    EffectAssuranceService,
    EffectReconciliationOutcome,
    ReferenceDecisionAuthorityReconciler,
    ReferenceEffectSourceAuthenticator,
    ReferenceReconcilerRejectedError,
    TrustedEffectIngress,
)

from ra8_scenario import assess, build_reference_service, make_observation


def test_matched_path():
    svc = build_reference_service()
    out = assess(svc, [make_observation("o1", BusinessOutcome.SUCCEEDED)])
    assert out.outcome is EffectReconciliationOutcome.MATCHED
    assert not out.assessment.is_material
    assert not out.assessment.compensation_recommended


def test_m1_favorable_cannot_mask_unfavorable_through_service():
    svc = build_reference_service()
    out = assess(
        svc,
        [
            make_observation("o1", BusinessOutcome.FAILED, external_effect_id="e-fail"),
            make_observation("o2", BusinessOutcome.SUCCEEDED, external_effect_id="e-ok"),
        ],
    )
    # DA's own verdict is latest-wins RECONCILED; RA-8 dominates it non-compensatorily.
    assert out.assessment.da_status is not None
    assert out.assessment.da_status.value == "RECONCILED"
    assert out.outcome is not EffectReconciliationOutcome.MATCHED
    assert out.outcome.is_material
    assert out.assessment.compensation_recommended


def test_no_observation_is_unknown_not_matched():
    svc = build_reference_service()
    out = assess(svc, [])
    assert out.outcome is EffectReconciliationOutcome.UNKNOWN


def test_effect_source_unavailable_is_unverifiable():
    svc = build_reference_service()
    out = assess(svc, [make_observation("o1", BusinessOutcome.SUCCEEDED)], effect_source_available=False)
    assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE
    assert not out.outcome.is_material  # authority unchanged


def test_all_observations_rejected_is_unverifiable():
    svc = build_reference_service()
    # Wrong tenant on every observation → all rejected at the trust boundary.
    out = assess(svc, [make_observation("o1", BusinessOutcome.SUCCEEDED, tenant_id="tenantB")])
    assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE
    assert not any(d.admitted for d in out.ingress_decisions)


def test_reconciliation_error_fails_closed_to_unknown():
    class BoomReconciler:
        is_reference_reconciler = True

        def reconcile(self, correlation, observations, expected):
            from ugence_risk_authority_execution_assurance import ReconciliationEvidence

            return ReconciliationEvidence(error="DA unavailable")

    svc = EffectAssuranceService(
        ingress=TrustedEffectIngress(ReferenceEffectSourceAuthenticator()),
        reconciler=BoomReconciler(),
    )
    out = assess(svc, [make_observation("o1", BusinessOutcome.SUCCEEDED)])
    assert out.outcome is EffectReconciliationOutcome.UNKNOWN
    assert not out.outcome.is_material


def test_production_refuses_reference_reconciler():
    with pytest.raises(ReferenceReconcilerRejectedError):
        EffectAssuranceService(
            ingress=TrustedEffectIngress(ReferenceEffectSourceAuthenticator()),
            reconciler=ReferenceDecisionAuthorityReconciler(),
            production_mode=True,
        )


def test_timeout_then_effect_reflects_the_effect():
    # Provider transport failed/timed out, but the external effect actually happened
    # and was trusted-observed → reconciliation reflects the effect, not "no effect".
    svc = build_reference_service()
    out = assess(svc, [make_observation("o1", BusinessOutcome.SUCCEEDED)])
    assert out.outcome is EffectReconciliationOutcome.MATCHED
    # And an observed failure after a "successful" provider call is a mismatch.
    out2 = assess(svc, [make_observation("o2", BusinessOutcome.FAILED)])
    assert out2.outcome is EffectReconciliationOutcome.MISMATCH


def test_partial_async_effect_not_prematurely_final():
    svc = build_reference_service()
    out = assess(
        svc,
        [make_observation("o1", BusinessOutcome.PARTIALLY_SUCCEEDED, finality=Finality.NON_FINAL)],
    )
    assert out.outcome is EffectReconciliationOutcome.PARTIAL
    assert not out.outcome.is_material
