"""Telemetry trust-ingress tests (spec §10/D7, §20; matrix items 6–12, 41).

The ingress is the trust gate; rejection ⇒ IGNORE_EVENT and can never touch
another authority domain or mint/widen authority.
"""

from __future__ import annotations

import pytest

from ugence_risk_authority_runtime_assurance import (
    AssessmentOutcome,
    ExpectedBinding,
    IngressDisposition,
    ReferenceIngressRejectedError,
    ReferenceTelemetryAuthenticator,
    TrustedTelemetryIngress,
)

from ra7_scenario import ENVELOPE, TENANT, WORKFLOW, make_observation


def _ingress() -> TrustedTelemetryIngress:
    return TrustedTelemetryIngress(ReferenceTelemetryAuthenticator())


def test_wellformed_observation_admitted():
    dec = _ingress().admit(make_observation(1))
    assert dec.admitted
    assert dec.disposition is IngressDisposition.ADMITTED
    assert dec.observation is not None


def test_malformed_observation_ignored():
    obs = make_observation(1, event_id="")  # missing event_id
    dec = _ingress().admit(obs)
    assert not dec.admitted
    assert dec.outcome is AssessmentOutcome.IGNORE_EVENT


def test_non_observation_ignored():
    dec = _ingress().admit(object())  # type: ignore[arg-type]
    assert not dec.admitted
    assert dec.outcome is AssessmentOutcome.IGNORE_EVENT


def test_wrong_tenant_rejected():
    obs = make_observation(1, tenant_id="other_tenant")
    dec = _ingress().admit(
        obs, expected=ExpectedBinding(tenant_id=TENANT, workflow_instance_id=WORKFLOW, envelope_id=ENVELOPE)
    )
    assert not dec.admitted
    assert "wrong tenant" in dec.reasons


def test_wrong_workflow_rejected():
    obs = make_observation(1, workflow_instance_id="other_wf")
    dec = _ingress().admit(
        obs, expected=ExpectedBinding(tenant_id=TENANT, workflow_instance_id=WORKFLOW, envelope_id=ENVELOPE)
    )
    assert not dec.admitted
    assert "wrong workflow" in dec.reasons


def test_wrong_envelope_rejected():
    obs = make_observation(1, envelope_id="other_env")
    dec = _ingress().admit(
        obs, expected=ExpectedBinding(tenant_id=TENANT, workflow_instance_id=WORKFLOW, envelope_id=ENVELOPE)
    )
    assert not dec.admitted
    assert "wrong envelope" in dec.reasons


def test_untrusted_producer_rejected():
    class DenyAll:
        is_reference_authenticator = False

        def authenticate(self, obs):
            return (False, ("producer not on allowlist",))

    dec = TrustedTelemetryIngress(DenyAll()).admit(make_observation(1))
    assert not dec.admitted
    assert dec.outcome is AssessmentOutcome.IGNORE_EVENT
    assert "untrusted producer" in dec.reasons


def test_authenticator_exception_fails_closed():
    class Boom:
        is_reference_authenticator = False

        def authenticate(self, obs):
            raise RuntimeError("kaboom")

    dec = TrustedTelemetryIngress(Boom()).admit(make_observation(1))
    assert not dec.admitted
    assert dec.outcome is AssessmentOutcome.IGNORE_EVENT


def test_malformed_authenticator_truthy_return_cannot_admit():
    # A truthy-but-not-True return must NOT be treated as authenticated.
    class TruthyLiar:
        is_reference_authenticator = False

        def authenticate(self, obs):
            return ("yes", ())  # truthy string, not True

    dec = TrustedTelemetryIngress(TruthyLiar()).admit(make_observation(1))
    assert not dec.admitted, "only an exact True may admit"


def test_reference_authenticator_refused_in_production():
    with pytest.raises(ReferenceIngressRejectedError):
        TrustedTelemetryIngress(ReferenceTelemetryAuthenticator(), production_mode=True)


def test_production_ingress_with_real_authenticator_allowed():
    class RealAuth:
        is_reference_authenticator = False

        def authenticate(self, obs):
            return (True, ())

    ing = TrustedTelemetryIngress(RealAuth(), production_mode=True)
    assert ing.production_mode
    assert ing.admit(make_observation(1)).admitted


def test_missing_authenticator_rejected():
    with pytest.raises(ValueError):
        TrustedTelemetryIngress(None)  # type: ignore[arg-type]


def test_cross_tenant_cannot_pass_expected_of_other_tenant():
    # Telemetry for tenant B, evaluated against tenant A's expected binding.
    obs_b = make_observation(1, tenant_id="tenant_B", workflow_instance_id="wf_B", envelope_id="env_B")
    dec = _ingress().admit(
        obs_b,
        expected=ExpectedBinding(tenant_id="tenant_A", workflow_instance_id="wf_A", envelope_id="env_A"),
    )
    assert not dec.admitted
    for r in ("wrong tenant", "wrong workflow", "wrong envelope"):
        assert r in dec.reasons
