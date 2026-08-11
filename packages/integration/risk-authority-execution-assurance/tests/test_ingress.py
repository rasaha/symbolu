"""Trusted effect ingress — trust boundary + F-1 + malformed hardening (spec §4/D-A, §19, §29)."""

from __future__ import annotations

import pytest

from ugence_decision_authority.execution.status import BusinessOutcome, Finality
from ugence_governance_contracts.contracts.execution import (
    ExecutionBusinessOutcome,
    ExecutionObservation,
)

from ugence_risk_authority_execution_assurance import (
    ReferenceEffectIngressRejectedError,
    ReferenceEffectSourceAuthenticator,
    TrustedEffectIngress,
    normalize_execution_observation,
)

from ra8_scenario import ATTEMPT_ID, EXTERNAL_REQUEST, default_context, make_observation
from ugence_risk_authority_execution_assurance import ExecutionCorrelator


def _corr():
    return ExecutionCorrelator().mint(
        default_context(), attempt_id=ATTEMPT_ID, external_request_id=EXTERNAL_REQUEST,
        provider="cloud", idempotency_key="idem-1",
    )


# ---------------------------------------------------------------- F-1 refusal ----
def test_reference_authenticator_refused_in_production():
    with pytest.raises(ReferenceEffectIngressRejectedError):
        TrustedEffectIngress(ReferenceEffectSourceAuthenticator(), production_mode=True)


def test_reference_authenticator_allowed_at_reference_grade():
    ing = TrustedEffectIngress(ReferenceEffectSourceAuthenticator())
    assert ing.production_mode is False


def test_ingress_requires_authenticator():
    with pytest.raises(ValueError):
        TrustedEffectIngress(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------- admission ----
def test_well_formed_bound_observation_admitted():
    ing = TrustedEffectIngress(ReferenceEffectSourceAuthenticator())
    decision = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED), correlation=_corr())
    assert decision.admitted


def test_wrong_tenant_observation_rejected():
    ing = TrustedEffectIngress(ReferenceEffectSourceAuthenticator())
    obs = make_observation("o1", BusinessOutcome.SUCCEEDED, tenant_id="tenantB")
    decision = ing.admit(obs, correlation=_corr())
    assert not decision.admitted
    assert "wrong tenant" in decision.reasons


def test_missing_source_is_untrusted():
    ing = TrustedEffectIngress(ReferenceEffectSourceAuthenticator())
    obs = make_observation("o1", BusinessOutcome.SUCCEEDED, source="")
    decision = ing.admit(obs, correlation=_corr())
    assert not decision.admitted
    assert "untrusted producer" in decision.reasons


def test_non_observation_rejected():
    ing = TrustedEffectIngress(ReferenceEffectSourceAuthenticator())
    decision = ing.admit(object(), correlation=_corr())  # type: ignore[arg-type]
    assert not decision.admitted


# ------------------------------------------------- malformed authenticator (§29) ----
@pytest.mark.parametrize("truthy", [None, 1, "true", "MATCHED", (), [], {}, object()])
def test_malformed_authenticator_return_never_admits(truthy):
    class BadAuth:
        is_reference_authenticator = True

        def authenticate(self, obs):
            return (truthy, ())  # not exactly True

    ing = TrustedEffectIngress(BadAuth())
    decision = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED), correlation=_corr())
    assert not decision.admitted
    assert "untrusted producer" in decision.reasons


def test_exception_throwing_authenticator_fails_closed():
    class Boom:
        is_reference_authenticator = True

        def authenticate(self, obs):
            raise RuntimeError("auth down")

    ing = TrustedEffectIngress(Boom())
    decision = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED), correlation=_corr())
    assert not decision.admitted
    assert "authenticator error" in decision.reasons


# --------------------------------------------- governance-contracts normalization ----
def test_normalize_execution_observation_reuses_governance_seam():
    corr = _corr()
    gov = ExecutionObservation(
        business_outcome=ExecutionBusinessOutcome.SUCCEEDED,
        observed_parameters={"target": "i-123"}, final=True, provider_trace_id="prov-9",
    )
    obs = normalize_execution_observation(gov, corr, observation_id="o1", source="src", source_version="1")
    assert obs.business_outcome is BusinessOutcome.SUCCEEDED
    assert obs.finality is Finality.FINAL
    assert obs.tenant_id == corr.tenant_id  # binding from correlation, not producer
    assert obs.external_effect_id == "prov-9"


def test_normalize_pending_maps_to_unknown_non_final():
    corr = _corr()
    gov = ExecutionObservation(business_outcome=ExecutionBusinessOutcome.PENDING, final=False)
    obs = normalize_execution_observation(gov, corr, observation_id="o1", source="src")
    assert obs.business_outcome is BusinessOutcome.UNKNOWN
    assert obs.finality is Finality.NON_FINAL
