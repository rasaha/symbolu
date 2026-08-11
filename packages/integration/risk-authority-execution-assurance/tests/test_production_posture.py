"""F-2 remediation — production composition posture (audit finding F-2).

The outer production boundary must not rely on the caller having remembered to
construct a production-posture ingress. A ``production_mode=True``
``EffectAssuranceService`` must reject an ingress that is not itself configured for
production posture — closing the mis-wiring where a default/reference
``TrustedEffectIngress`` (which trusts a reference effect authenticator) could be
injected into a production service.

Invariant: production service ⇒ production-safe ingress ⇒ no reference effect
authenticator. Fail closed on any non-``True`` posture.
"""

from __future__ import annotations

import pytest

from ugence_decision_authority.execution.status import BusinessOutcome

from ugence_risk_authority_execution_assurance import (
    CompositionRejectedError,
    EffectAssuranceService,
    EffectReconciliationOutcome,
    ReferenceDecisionAuthorityReconciler,
    ReferenceEffectSourceAuthenticator,
    ReferenceReconcilerRejectedError,
    TrustedEffectIngress,
)

from ra8_scenario import ATTEMPT_ID, EXTERNAL_REQUEST, assess, default_context, make_observation
from ugence_risk_authority_execution_assurance import ExecutionCorrelator


class _ProdAuthenticator:
    """A non-reference (production-posture) effect authenticator stand-in."""

    is_reference_authenticator = False

    def authenticate(self, obs):
        return (True, ())


class _ProdReconciler:
    """A non-reference (production-posture) DA reconciler stand-in."""

    is_reference_reconciler = False

    def reconcile(self, correlation, observations, expected):  # pragma: no cover - unused here
        from ugence_risk_authority_execution_assurance import ReconciliationEvidence

        return ReconciliationEvidence(error="unused")


def _prod_ingress() -> TrustedEffectIngress:
    return TrustedEffectIngress(_ProdAuthenticator(), production_mode=True)


def _corr():
    return ExecutionCorrelator().mint(
        default_context(), attempt_id=ATTEMPT_ID, external_request_id=EXTERNAL_REQUEST,
        provider="cloud", idempotency_key="idem-1",
    )


# 1. production service + production ingress + non-reference authenticator → succeeds
def test_1_production_service_with_production_ingress_constructs():
    svc = EffectAssuranceService(
        ingress=_prod_ingress(), reconciler=_ProdReconciler(), production_mode=True
    )
    assert svc is not None


# 2. production service + default/non-production ingress → FAILS CLOSED
def test_2_production_service_rejects_default_ingress():
    non_prod_ingress = TrustedEffectIngress(_ProdAuthenticator())  # production_mode defaults False
    assert non_prod_ingress.production_mode is False
    with pytest.raises(CompositionRejectedError):
        EffectAssuranceService(
            ingress=non_prod_ingress, reconciler=_ProdReconciler(), production_mode=True
        )


# 3. production service + ingress containing ReferenceEffectSourceAuthenticator → FAILS CLOSED
def test_3_production_service_rejects_reference_authenticator_ingress():
    # A default ingress wrapping the reference authenticator (the exact documented
    # mis-wiring from the audit) is refused at the outer composition boundary.
    ref_ingress = TrustedEffectIngress(ReferenceEffectSourceAuthenticator())
    with pytest.raises(CompositionRejectedError):
        EffectAssuranceService(
            ingress=ref_ingress, reconciler=_ProdReconciler(), production_mode=True
        )


# 4. non-production / reference service + reference ingress → remains permitted
def test_4_reference_service_permits_reference_ingress():
    svc = EffectAssuranceService.reference()
    assert svc is not None
    # And an explicit non-production service with a reference ingress is allowed.
    svc2 = EffectAssuranceService(
        ingress=TrustedEffectIngress(ReferenceEffectSourceAuthenticator()),
        reconciler=ReferenceDecisionAuthorityReconciler(),
    )
    assert svc2 is not None


# 5. existing production-mode refusal for the reference DA reconciler remains intact
def test_5_reference_reconciler_refusal_intact():
    # With a production ingress isolated, the reference reconciler is still refused.
    with pytest.raises(ReferenceReconcilerRejectedError):
        EffectAssuranceService(
            ingress=_prod_ingress(),
            reconciler=ReferenceDecisionAuthorityReconciler(),
            production_mode=True,
        )


# 6. authenticator exceptions during admission → still REJECTED
def test_6_authenticator_exception_still_rejected():
    class Boom:
        is_reference_authenticator = False

        def authenticate(self, obs):
            raise RuntimeError("auth down")

    ing = TrustedEffectIngress(Boom(), production_mode=True)
    decision = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED), correlation=_corr())
    assert not decision.admitted
    assert "authenticator error" in decision.reasons


# 7. truthy non-bool authenticator results (1, "yes", object()) → still REJECTED
@pytest.mark.parametrize("truthy", [1, "yes", "MATCHED", object(), [1], {"a": 1}])
def test_7_truthy_non_bool_authenticator_rejected(truthy):
    class Truthy:
        is_reference_authenticator = False

        def authenticate(self, obs):
            return (truthy, ())  # not exactly True

    ing = TrustedEffectIngress(Truthy(), production_mode=True)
    decision = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED), correlation=_corr())
    assert not decision.admitted
    assert "untrusted producer" in decision.reasons


# 8. no F-2 remediation path can produce MATCHED merely because posture validation failed
def test_8_posture_failure_never_yields_matched():
    # The mis-wired production construction raises — there is no service, hence no
    # assessment can be produced at all (fail closed at construction, not a verdict).
    with pytest.raises(CompositionRejectedError):
        EffectAssuranceService(
            ingress=TrustedEffectIngress(ReferenceEffectSourceAuthenticator()),
            reconciler=_ProdReconciler(),
            production_mode=True,
        )
    # And separately: an untrusted observation on a (permitted) reference service is
    # rejected at the trust boundary → never MATCHED.
    ref_svc = EffectAssuranceService.reference()
    out = assess(ref_svc, [make_observation("o1", BusinessOutcome.SUCCEEDED, source="")])
    assert out.outcome is not EffectReconciliationOutcome.MATCHED
    assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE


# posture property is immutable (read-only) — no setter to downgrade it after construction
def test_ingress_production_posture_is_read_only():
    ing = _prod_ingress()
    assert ing.production_mode is True
    with pytest.raises(AttributeError):
        ing.production_mode = False  # type: ignore[misc]
