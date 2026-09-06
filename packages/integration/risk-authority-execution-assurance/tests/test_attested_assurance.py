"""RI-2 / RI-3 / RI-5 at the composition layer (``EffectAssuranceService.assess``).

What is and is not shown here, stated once:

* reference grade: an observer-attested observation flows through the attested
  ingress into genuine DA reconciliation and can reach ``MATCHED``;
* production posture: no provider-only path reaches ``MATCHED``. The withholding
  branch is exercised through a **labelled test double** that stands in for the
  verifier port; it proves the gate is wired, not that a production flow exists;
* production posture with the only production-admissible resolver in the
  repository (``DenyAllTrustAnchorDirectory``) refuses every attestation, so a
  genuine production ``MATCHED`` is unreachable until the RI-4 TEA milestone.
"""

from __future__ import annotations

from datetime import datetime

import pytest

import ugence_risk_authority_effect_attestation as ea
from ugence_decision_authority.execution.status import BusinessOutcome
from ugence_governance_contracts.contracts.execution import ExecutionBusinessOutcome

from ugence_risk_authority_execution_assurance import (
    ATTESTATION_REFUSED,
    INVALID_VERIFICATION_INSTANT,
    NO_ATTESTATION_VERIFIER,
    UNATTESTED_REFUSED_IN_PRODUCTION,
    AttestedEffectInput,
    EffectAssuranceService,
    EffectReasonCode,
    EffectReconciliationOutcome,
    ReferenceDecisionAuthorityReconciler,
    ReferenceEffectSourceAuthenticator,
    TrustedEffectIngress,
)

from ra8_scenario import FIXED_NOW, default_context, default_expected, make_observation
from test_attested_ingress import (
    AS_OF,
    SET,
    SpyDirectory,
    _ProdAuthenticator,
    anchor_of,
    attestation,
    observer_signer,
    provider_signer,
    raw_observation,
    verifier,
)


def _assess(service, *, attested=(), observations=(), instant=AS_OF):
    return service.assess(
        default_context(),
        attempt_id="idem-1#attempt-1",
        expected=default_expected(),
        observations=observations,
        external_request_id="ext-req-1",
        idempotency_key="idem-1",
        provider="cloud",
        produced_at=FIXED_NOW,
        attested=attested,
        verification_instant=instant,
    )


def _reference_service(v):
    return EffectAssuranceService(
        ingress=TrustedEffectIngress(ReferenceEffectSourceAuthenticator(), attestation_verifier=v),
        reconciler=ReferenceDecisionAuthorityReconciler(),
    )


def _input(att, observation_id="o-att-1"):
    return AttestedEffectInput(observation_id=observation_id, attestation=att, source="reference-effect-source",
                               source_version="1")


# ----------------------------------------------------------------------------- #
# reference grade: observer attestation reaches genuine reconciliation
# ----------------------------------------------------------------------------- #
def test_reference_grade_observer_attestation_reaches_matched_through_da_reconciliation():
    svc = _reference_service(verifier(anchor_of(observer_signer())))
    out = _assess(svc, attested=[_input(attestation(observer_signer()))])
    assert out.outcome is EffectReconciliationOutcome.MATCHED
    (decision,) = out.ingress_decisions
    assert decision.admitted and decision.observation.provenance.is_independent_observer
    assert decision.attestation.factual_correctness_established is False


def test_reference_grade_provider_attestation_also_reaches_matched_because_the_gate_is_production_only():
    svc = _reference_service(verifier(anchor_of(provider_signer())))
    out = _assess(svc, attested=[_input(attestation(provider_signer()))])
    assert out.outcome is EffectReconciliationOutcome.MATCHED
    assert svc._ingress.production_mode is False  # reference posture, gate not applied


def test_reference_grade_adverse_provider_evidence_still_surfaces():
    svc = _reference_service(verifier(anchor_of(provider_signer())))
    failed = attestation(provider_signer(), raw_observation(business_outcome=ExecutionBusinessOutcome.FAILED))
    out = _assess(svc, attested=[_input(failed)])
    assert out.outcome is EffectReconciliationOutcome.MISMATCH
    assert out.assessment.is_material


# ----------------------------------------------------------------------------- #
# RI-5 at the composition layer
# ----------------------------------------------------------------------------- #
def test_absent_or_naive_verification_instant_rejects_every_attested_input_without_resolving():
    spy = SpyDirectory(anchor_of(observer_signer()))
    svc = _reference_service(verifier(spy=spy))
    for bad in (None, datetime(2026, 9, 6, 12, 5), FIXED_NOW.replace(tzinfo=None)):
        out = _assess(svc, attested=[_input(attestation(observer_signer()))], instant=bad)
        assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE
        assert out.assessment.reason_codes == (EffectReasonCode.EFFECT_SOURCE_UNAVAILABLE,)
        assert out.ingress_decisions[0].reasons[0] == INVALID_VERIFICATION_INSTANT
    # produced_at was set on every call above and was never used as the instant
    assert spy.calls == []


def test_a_reference_service_without_a_verifier_refuses_attested_input():
    out = _assess(EffectAssuranceService.reference(), attested=[_input(attestation(observer_signer()))])
    assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE
    assert out.ingress_decisions[0].reasons == (NO_ATTESTATION_VERIFIER,)


def test_a_non_input_in_the_attested_sequence_is_rejected_not_unwrapped():
    svc = _reference_service(verifier(anchor_of(observer_signer())))
    out = _assess(svc, attested=[attestation(observer_signer())])  # type: ignore[list-item]
    assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE
    assert out.ingress_decisions[0].reasons == ("not an AttestedEffectInput",)


# ----------------------------------------------------------------------------- #
# RI-2 / RI-3 / RI-4 in production posture
# ----------------------------------------------------------------------------- #
class _ProdReconcilerDouble:
    """Production-posture stand-in that delegates to the genuine DA reference kernel.

    Labelled test double: it exists so the production gate can be exercised over real
    DA records. It is not a production reconciler and proves nothing about one.
    """

    is_reference_reconciler = False

    def __init__(self):
        self._inner = ReferenceDecisionAuthorityReconciler()

    def reconcile(self, correlation, observations, expected):
        return self._inner.reconcile(correlation, observations, expected)


class _ProductionPostureVerifierDouble:
    """Labelled test double for the verifier port in production posture.

    Wraps a reference verifier over TEA's static directory and states
    ``production_mode = True`` so a production ingress accepts it. It is used only to
    show that a VERIFIED **provider** attestation cannot reach ``MATCHED`` in
    production. It is never used to claim a positive production result.
    """

    production_mode = True

    def __init__(self, *anchors):
        self._inner = verifier(*anchors)

    def verify(self, **kw):
        return self._inner.verify(**kw)


def _production_service(v):
    return EffectAssuranceService(
        ingress=TrustedEffectIngress(_ProdAuthenticator(), production_mode=True, attestation_verifier=v),
        reconciler=_ProdReconcilerDouble(),
        production_mode=True,
    )


def test_14_no_provider_only_path_produces_a_production_matched():
    svc = _production_service(_ProductionPostureVerifierDouble(anchor_of(provider_signer())))
    out = _assess(svc, attested=[_input(attestation(provider_signer()))])
    (decision,) = out.ingress_decisions
    assert decision.admitted  # provenance verified: the provider did report this
    assert decision.observation.provenance.attester_role is ea.EffectAttesterRole.EXECUTING_PROVIDER
    assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE
    assert out.assessment.reason_codes == (EffectReasonCode.INDEPENDENT_OBSERVER_REQUIRED,)
    assert out.assessment.is_material is False  # withheld MATCHED is not a mismatch signal
    assert out.handoff is None or out.handoff.emitted is False


def test_14b_adverse_provider_evidence_is_not_suppressed_in_production():
    svc = _production_service(_ProductionPostureVerifierDouble(anchor_of(provider_signer())))
    failed = attestation(provider_signer(), raw_observation(business_outcome=ExecutionBusinessOutcome.FAILED))
    out = _assess(svc, attested=[_input(failed)])
    assert out.outcome is EffectReconciliationOutcome.MISMATCH
    assert out.assessment.is_material


def test_production_unattested_observations_are_rejected_and_never_reconciled():
    svc = _production_service(_ProductionPostureVerifierDouble(anchor_of(observer_signer())))
    out = _assess(svc, observations=[make_observation("o1", BusinessOutcome.SUCCEEDED)])
    assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE
    assert out.ingress_decisions[0].reasons == (UNATTESTED_REFUSED_IN_PRODUCTION,)
    assert out.evidence.records == ()


def test_ri4_blocker_pinned_production_with_the_only_admissible_resolver_refuses_everything():
    prod_verifier = ea.Ed25519EffectAttestationVerifier(
        trust_anchor_resolver=ea.DenyAllTrustAnchorDirectory(), production_mode=True
    )
    svc = _production_service(prod_verifier)
    out = _assess(svc, attested=[_input(attestation(observer_signer())), _input(attestation(provider_signer()), "o-att-2")])
    assert out.outcome is EffectReconciliationOutcome.UNVERIFIABLE
    assert out.assessment.reason_codes == (EffectReasonCode.EFFECT_SOURCE_UNAVAILABLE,)
    for decision in out.ingress_decisions:
        assert decision.reasons == (ATTESTATION_REFUSED, "ANCHOR_UNKNOWN")
    # and the reference directory cannot be substituted to get past it
    with pytest.raises(ea.EffectAttestationConfigurationError):
        ea.Ed25519EffectAttestationVerifier(
            trust_anchor_resolver=ea.StaticTrustAnchorDirectory([anchor_of(observer_signer())], **SET),
            production_mode=True,
        )
