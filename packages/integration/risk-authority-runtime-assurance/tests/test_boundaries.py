"""Structural boundary / invariant tests (spec §21; matrix 4–5, 29–39).

RA-7 cannot mint or mutate authority; production composition refuses reference
stand-ins; RA-4.5/RA-5/RA-6 and the Agent Runtime are untouched by importing RA-7.
"""

from __future__ import annotations

import pytest

from ugence_risk_authority_runtime_assurance import (
    ReferenceCompositionRejectedError,
    ReferenceTelemetryAuthenticator,
    ReferenceTrajectoryEvaluator,
    ReferenceTrajectoryPolicyReader,
    RuntimeAssuranceObserver,
    RuntimeAssuranceService,
    TrustedTelemetryIngress,
)

from ra7_scenario import build_reference_service


# -- matrix 39 / F-1: production composition refuses reference stand-ins ----
def test_production_service_refuses_reference_policy_reader():
    prod_ingress = TrustedTelemetryIngress(
        _RealAuth(), production_mode=True
    )
    evaluator = ReferenceTrajectoryEvaluator(ReferenceTrajectoryPolicyReader())
    with pytest.raises(ReferenceCompositionRejectedError):
        RuntimeAssuranceService(
            ingress=prod_ingress,
            observer=RuntimeAssuranceObserver(),
            evaluator=evaluator,
            production_mode=True,
        )


def test_production_service_refuses_non_production_ingress():
    # A reference (non-production) ingress cannot back a production service.
    ref_ingress = TrustedTelemetryIngress(ReferenceTelemetryAuthenticator())
    with pytest.raises(ReferenceCompositionRejectedError):
        RuntimeAssuranceService(
            ingress=ref_ingress,
            observer=RuntimeAssuranceObserver(),
            evaluator=ReferenceTrajectoryEvaluator(ReferenceTrajectoryPolicyReader()),
            production_mode=True,
        )


def test_reference_factory_is_not_production():
    service = build_reference_service()
    assert service._production_mode is False


# -- matrix 5: observer cannot mint authority (structural) -----------------
def test_service_exposes_no_authority_minting_method():
    service = build_reference_service()
    for attr in (
        "issue_envelope", "mint", "grant", "authorize", "sign",
        "advance_epoch", "revoke_envelope", "emergency_stop",
    ):
        assert not hasattr(service, attr)


# -- matrix 16 (privileged): RA-7 never emits TENANT_EMERGENCY_STOP ---------
def test_ra7_never_constructs_emergency_stop_signal():
    import ugence_risk_authority_runtime_assurance.handoff as handoff
    from risk_authority.domain.authority_signal import SignalChangeType

    src = (handoff.__file__)
    text = open(src, encoding="utf-8").read()
    assert "TENANT_EMERGENCY_STOP" not in text
    # The only change_type RA-7 constructs is RUNTIME_RISK_ESCALATED.
    assert "RUNTIME_RISK_ESCALATED" in text
    assert SignalChangeType.RUNTIME_RISK_ESCALATED.value == "RUNTIME_RISK_ESCALATED"


# -- matrix 29: RA-4.5 / RA-5 / RA-6 leaf unchanged by importing RA-7 -------
def test_importing_ra7_does_not_mutate_leaf_signal_enum():
    import ugence_risk_authority_runtime_assurance  # noqa: F401
    from risk_authority.domain.authority_signal import SignalChangeType

    # The leaf enum has exactly its ratified members — RA-7 added none.
    assert {m.value for m in SignalChangeType} == {
        "EVIDENCE_INVALIDATED",
        "CONTROL_CHANGED",
        "POLICY_SUPERSEDED",
        "WORKFLOW_SUPERSEDED",
        "MODEL_INVALIDATED",
        "RUNTIME_RISK_ESCALATED",
        "TENANT_EMERGENCY_STOP",
    }


class _RealAuth:
    is_reference_authenticator = False

    def authenticate(self, obs):
        return (True, ())
