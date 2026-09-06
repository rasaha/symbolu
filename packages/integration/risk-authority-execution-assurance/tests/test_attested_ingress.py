"""RI-1 to RI-5 — attested admission on ``TrustedEffectIngress``.

Reference-grade throughout: the trust-anchor directory is TEA's
``StaticTrustAnchorDirectory``, which production refuses (RI-4). The tests that
name production prove refusals and the blocker; none demonstrates a production
``MATCHED`` flow, because no production resolver exists in this repository.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta, timezone

import pytest

import ugence_risk_authority_effect_attestation as ea
from ugence_decision_authority.execution.status import BusinessOutcome, Finality
from ugence_governance_contracts.contracts.execution import (
    ExecutionBusinessOutcome,
    ExecutionObservation,
)

from ugence_risk_authority_execution_assurance import (
    ATTESTATION_REFUSED,
    ATTESTATION_VERIFIER_FAULT,
    INVALID_VERIFICATION_INSTANT,
    NO_ATTESTATION_VERIFIER,
    UNATTESTED_REFUSED_IN_PRODUCTION,
    AttestationVerifierRejectedError,
    EffectAttestationProvenance,
    EffectObservation,
    EffectReasonCode,
    EffectReconciliationOutcome,
    ExecutionCorrelator,
    IngressDisposition,
    ReferenceEffectIngressRejectedError,
    ReferenceEffectSourceAuthenticator,
    TrustedEffectIngress,
    independent_observer_supports,
    production_matched_gate,
)

from ra8_scenario import ATTEMPT_ID, EXTERNAL_REQUEST, PROVIDER, TENANT, default_context, make_observation

PROVIDER_ROLE = ea.EffectAttesterRole.EXECUTING_PROVIDER
OBSERVER_ROLE = ea.EffectAttesterRole.INDEPENDENT_OBSERVER
ATTESTED_AT = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
AS_OF = datetime(2026, 9, 6, 12, 5, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
VALID_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
SET = dict(trust_anchor_set_id="effect-anchors", trust_anchor_set_version="1")


# ----------------------------------------------------------------------------- #
# fixtures
# ----------------------------------------------------------------------------- #
def raw_observation(**overrides) -> ExecutionObservation:
    kwargs = dict(
        business_outcome=ExecutionBusinessOutcome.SUCCEEDED,
        observed_parameters={"target": "i-123"},
        final=True,
        reason="",
        provider_trace_id="eff-1",
        fingerprint="fp-1",
    )
    kwargs.update(overrides)
    return ExecutionObservation(**kwargs)


def provider_signer(seed: bytes = b"\x01" * 32, **overrides):
    kwargs = dict(attester_identity="provider-alpha", attester_key_id="pk-1", attester_role=PROVIDER_ROLE)
    kwargs.update(overrides)
    return ea.ReferenceEd25519EffectAttestationSigner(seed, **kwargs)


def observer_signer(seed: bytes = b"\x02" * 32, **overrides):
    kwargs = dict(attester_identity="observer-omega", attester_key_id="ok-1", attester_role=OBSERVER_ROLE)
    kwargs.update(overrides)
    return ea.ReferenceEd25519EffectAttestationSigner(seed, **kwargs)


def anchor_of(signer, **overrides):
    kwargs = dict(SET, effective_from=VALID_FROM, effective_to=VALID_TO)
    kwargs.update(overrides)
    return signer.trust_anchor(**kwargs)


def attestation(signer=None, obs=None, tenant_id: str = TENANT):
    return ea.mint_effect_attestation(
        obs if obs is not None else raw_observation(),
        signer=signer if signer is not None else observer_signer(),
        tenant_id=tenant_id,
        attested_at=ATTESTED_AT,
    )


class SpyDirectory:
    """TEA's static directory behind a call counter: proves when it is consulted."""

    is_production_authoritative = False

    def __init__(self, *anchors):
        self._inner = ea.StaticTrustAnchorDirectory(list(anchors), **SET)
        self.calls = []

    def resolve(self, coordinate, *, as_of=None):
        self.calls.append(coordinate)
        return self._inner.resolve(coordinate)


def verifier(*anchors, spy: SpyDirectory | None = None):
    resolver = spy if spy is not None else ea.StaticTrustAnchorDirectory(list(anchors), **SET)
    return ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=resolver)


def ingress(v, authenticator=None, production_mode: bool = False):
    return TrustedEffectIngress(
        authenticator if authenticator is not None else ReferenceEffectSourceAuthenticator(),
        production_mode=production_mode,
        attestation_verifier=v,
    )


def corr(tenant_id: str = TENANT):
    return ExecutionCorrelator().mint(
        default_context(tenant_id=tenant_id),
        attempt_id=ATTEMPT_ID,
        external_request_id=EXTERNAL_REQUEST,
        provider=PROVIDER,
        idempotency_key="idem-1",
    )


def admit(ing, att, *, correlation=None, as_of=AS_OF, source="reference-effect-source", **kw):
    return ing.admit_attested(
        att,
        correlation=correlation if correlation is not None else corr(),
        as_of=as_of,
        observation_id="o-att-1",
        source=source,
        source_version="1",
        **kw,
    )


class _ProdAuthenticator:
    is_reference_authenticator = False

    def authenticate(self, obs):
        return (True, ())


# ----------------------------------------------------------------------------- #
# 1. verified independent-observer attestation follows the reference-grade path
# ----------------------------------------------------------------------------- #
def test_1_verified_observer_attestation_is_admitted_with_typed_provenance():
    ing = ingress(verifier(anchor_of(observer_signer())))
    decision = admit(ing, attestation(observer_signer()))
    assert decision.disposition is IngressDisposition.ADMITTED
    assert decision.attestation is not None
    assert decision.attestation.outcome is ea.EffectAttestationVerificationOutcome.VERIFIED
    obs = decision.observation
    assert type(obs) is EffectObservation
    p = obs.provenance
    assert type(p) is EffectAttestationProvenance
    assert p.attester_role is OBSERVER_ROLE and p.is_independent_observer
    assert p.attester_identity == "observer-omega" and p.attester_key_id == "ok-1"
    assert p.observation_digest.startswith("sha256:") and p.anchor_record_digest.startswith("sha256:")
    assert p.verified_at == AS_OF
    assert p.factual_correctness_established is False
    assert p.establishes == "PROVENANCE_AND_INTEGRITY_ONLY"
    # binding fields come from the governed correlation, never from the attester
    assert (obs.tenant_id, obs.attempt_id, obs.external_request_id) == (TENANT, ATTEMPT_ID, EXTERNAL_REQUEST)
    assert obs.business_outcome is BusinessOutcome.SUCCEEDED and obs.finality is Finality.FINAL
    assert obs.external_effect_id == "eff-1"


def test_1b_identity_key_and_role_never_travel_in_source_or_source_version():
    ing = ingress(verifier(anchor_of(observer_signer())))
    obs = admit(ing, attestation(observer_signer())).observation
    for packed in ("observer-omega", "ok-1", "INDEPENDENT_OBSERVER", "OBSERVER"):
        assert packed not in obs.source and packed not in obs.source_version


# ----------------------------------------------------------------------------- #
# 2. provider attestation is provider provenance and cannot establish production MATCHED
# ----------------------------------------------------------------------------- #
def test_2_verified_provider_attestation_is_provider_provenance_only():
    ing = ingress(verifier(anchor_of(provider_signer())))
    decision = admit(ing, attestation(provider_signer()))
    assert decision.admitted
    obs = decision.observation
    assert obs.provenance.attester_role is PROVIDER_ROLE
    assert obs.provenance.is_independent_observer is False
    assert independent_observer_supports([obs]) is False
    withheld = production_matched_gate(EffectReconciliationOutcome.MATCHED, [obs], production_mode=True)
    assert withheld is not None
    outcome, code, _ = withheld
    assert outcome is EffectReconciliationOutcome.UNVERIFIABLE
    assert code is EffectReasonCode.INDEPENDENT_OBSERVER_REQUIRED
    # reference grade: the gate does not apply
    assert production_matched_gate(EffectReconciliationOutcome.MATCHED, [obs], production_mode=False) is None
    # adverse verdicts are never suppressed, in any posture
    for adverse in (EffectReconciliationOutcome.MISMATCH, EffectReconciliationOutcome.CONFLICTED,
                    EffectReconciliationOutcome.PARTIAL, EffectReconciliationOutcome.UNKNOWN,
                    EffectReconciliationOutcome.MANUAL_REVIEW, EffectReconciliationOutcome.UNVERIFIABLE):
        assert production_matched_gate(adverse, [obs], production_mode=True) is None


def test_2b_observer_provenance_supports_matched_only_when_favorable_and_final():
    ing = ingress(verifier(anchor_of(observer_signer())))
    favorable = admit(ing, attestation(observer_signer())).observation
    assert independent_observer_supports([favorable]) is True
    assert production_matched_gate(EffectReconciliationOutcome.MATCHED, [favorable], production_mode=True) is None
    pending = admit(ing, attestation(observer_signer(), raw_observation(
        business_outcome=ExecutionBusinessOutcome.PENDING, final=False))).observation
    assert independent_observer_supports([pending]) is False
    failed = admit(ing, attestation(observer_signer(), raw_observation(
        business_outcome=ExecutionBusinessOutcome.FAILED))).observation
    assert independent_observer_supports([failed]) is False
    # a forged provenance object of the wrong type never counts
    forged = dataclasses.replace(make_observation("f", BusinessOutcome.SUCCEEDED), provenance=object())  # type: ignore[arg-type]
    assert independent_observer_supports([forged]) is False
    assert "provenance is not an EffectAttestationProvenance" in forged.binding_errors()
    # posture must be exactly True for the gate to apply
    for not_true in (1, "yes", None, object()):
        assert production_matched_gate(EffectReconciliationOutcome.MATCHED, [], production_mode=not_true) is None


# ----------------------------------------------------------------------------- #
# 3. wrong tenant or governed correlation
# ----------------------------------------------------------------------------- #
def test_3_wrong_tenant_and_non_correlation_reject():
    ing = ingress(verifier(anchor_of(observer_signer())))
    other = admit(ing, attestation(observer_signer()), correlation=corr(tenant_id="tenant_other"))
    assert not other.admitted
    assert other.reasons[0] == ATTESTATION_REFUSED and "WRONG_TENANT" in other.reasons
    assert other.attestation.refusal_reason is ea.EffectAttestationRefusalReason.WRONG_TENANT
    wrong_type = ing.admit_attested(attestation(observer_signer()), correlation=object(),  # type: ignore[arg-type]
                                    as_of=AS_OF, observation_id="o")
    assert not wrong_type.admitted and "not an ExecutionCorrelation" in wrong_type.reasons


# ----------------------------------------------------------------------------- #
# 4. wrong or cross-purpose attester role
# ----------------------------------------------------------------------------- #
def test_4_role_confusion_refuses_in_both_directions():
    both = verifier(anchor_of(provider_signer()), anchor_of(observer_signer()))
    ing = ingress(both)
    # a provider attestation demanded as an observer
    d = admit(ing, attestation(provider_signer()), expected_role=OBSERVER_ROLE)
    assert not d.admitted and "ROLE_MISMATCH" in d.reasons
    # and the inverse
    d = admit(ing, attestation(observer_signer()), expected_role=PROVIDER_ROLE)
    assert not d.admitted and "ROLE_MISMATCH" in d.reasons
    # an observer-role attestation whose only anchor is under the provider capability
    same_key_as_provider = observer_signer(seed=b"\x01" * 32, attester_identity="provider-alpha", attester_key_id="pk-1")
    d = admit(ingress(verifier(anchor_of(provider_signer()))), attestation(same_key_as_provider))
    assert not d.admitted and "ANCHOR_UNKNOWN" in d.reasons
    # expected_role of the wrong type
    d = admit(ing, attestation(observer_signer()), expected_role="INDEPENDENT_OBSERVER")  # type: ignore[arg-type]
    assert not d.admitted and d.attestation is None


# ----------------------------------------------------------------------------- #
# 5. tampered or substituted raw ExecutionObservation
# ----------------------------------------------------------------------------- #
def test_5_tampered_or_substituted_observation_refuses():
    ing = ingress(verifier(anchor_of(observer_signer())))
    genuine = attestation(observer_signer())
    tampered = dataclasses.replace(genuine, observation=raw_observation(final=False))
    d = admit(ing, tampered)
    assert not d.admitted and "SIGNATURE_INVALID" in d.reasons
    other = attestation(observer_signer(), raw_observation(observed_parameters={"target": "i-999"}))
    substituted = dataclasses.replace(other, signature=genuine.signature)
    d = admit(ing, substituted)
    assert not d.admitted and "SIGNATURE_INVALID" in d.reasons
    # a duck-typed wrapper is not an EffectAttestation
    class Duck:
        observation = raw_observation()
        attester_role = OBSERVER_ROLE

    d = admit(ing, Duck())  # type: ignore[arg-type]
    assert not d.admitted and "not an EffectAttestation" in d.reasons
    d = admit(ing, None)  # type: ignore[arg-type]
    assert not d.admitted and d.reasons[0] == ATTESTATION_REFUSED


# ----------------------------------------------------------------------------- #
# 6. revoked, expired, not-yet-valid or mismatched anchor
# ----------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "anchor_overrides, expected",
    [
        ({"effective_to": AS_OF - timedelta(days=1)}, "ANCHOR_EXPIRED"),
        ({"effective_from": AS_OF + timedelta(days=1)}, "ANCHOR_NOT_YET_VALID"),
    ],
)
def test_6_lifecycle_refusals(anchor_overrides, expected):
    ing = ingress(verifier(anchor_of(observer_signer(), **anchor_overrides)))
    d = admit(ing, attestation(observer_signer()))
    assert not d.admitted and expected in d.reasons


def test_6b_revoked_missing_and_mismatched_anchor():
    revoked = dataclasses.replace(
        anchor_of(observer_signer()),
        revocation=ea.KeyRevocation(effective_at=AS_OF - timedelta(hours=1)),
    )
    d = admit(ingress(verifier(revoked)), attestation(observer_signer()))
    assert not d.admitted and "ANCHOR_REVOKED" in d.reasons
    d = admit(ingress(verifier()), attestation(observer_signer()))
    assert not d.admitted and "ANCHOR_UNKNOWN" in d.reasons
    # same identity and key id, different key material: the signature does not verify
    impostor = observer_signer(seed=b"\x09" * 32)
    d = admit(ingress(verifier(anchor_of(impostor))), attestation(observer_signer()))
    assert not d.admitted and "SIGNATURE_INVALID" in d.reasons
    # a caller-pinned anchor revision that does not match
    ing = ingress(verifier(anchor_of(observer_signer())))
    assert admit(ing, attestation(observer_signer())).admitted


# ----------------------------------------------------------------------------- #
# 7. malformed, absent or naive injected instant — zero resolver consultation
# ----------------------------------------------------------------------------- #
class _Subclassed(datetime):
    pass


@pytest.mark.parametrize(
    "bad",
    [None, datetime(2026, 9, 6, 12, 5), "2026-09-06T12:05:00Z", date(2026, 9, 6),
     1_757_160_300, _Subclassed(2026, 9, 6, 12, 5, tzinfo=timezone.utc), object()],
    ids=["absent", "naive", "string", "date", "epoch-int", "datetime-subclass", "object"],
)
def test_7_bad_instant_rejects_before_any_resolver_or_verifier_call(bad):
    spy = SpyDirectory(anchor_of(observer_signer()))

    class CountingVerifier:
        production_mode = False
        calls = 0

        def __init__(self, inner):
            self._inner = inner

        def verify(self, **kw):
            CountingVerifier.calls += 1
            return self._inner.verify(**kw)

    counting = CountingVerifier(verifier(spy=spy))
    ing = ingress(counting)
    d = admit(ing, attestation(observer_signer()), as_of=bad)
    assert not d.admitted
    assert d.reasons[0] == INVALID_VERIFICATION_INSTANT
    assert d.attestation is None
    assert spy.calls == [] and CountingVerifier.calls == 0
    # the same ingress with a proper instant does consult exactly once
    assert admit(ing, attestation(observer_signer())).admitted
    assert len(spy.calls) == 1 and CountingVerifier.calls == 1


def test_7b_attested_at_is_not_the_verification_instant():
    """A claim inside the signed payload never stands in for the injected instant."""

    expired_by_claim = anchor_of(observer_signer(), effective_to=ATTESTED_AT + timedelta(minutes=1))
    ing = ingress(verifier(expired_by_claim))
    # attested_at (12:00) lies inside the window, but the injected instant (12:05) does not
    d = admit(ing, attestation(observer_signer()))
    assert not d.admitted and "ANCHOR_EXPIRED" in d.reasons


# ----------------------------------------------------------------------------- #
# 8. verifier fault and authenticator fault both fail closed
# ----------------------------------------------------------------------------- #
def test_8_verifier_fault_and_malformed_result_fail_closed():
    class Boom:
        production_mode = False

        def verify(self, **kw):
            raise RuntimeError("verifier down")

    d = admit(ingress(Boom()), attestation(observer_signer()))
    assert not d.admitted and d.reasons[0] == ATTESTATION_VERIFIER_FAULT

    class Liar:
        production_mode = False

        def verify(self, **kw):
            return True  # not a typed result

    d = admit(ingress(Liar()), attestation(observer_signer()))
    assert not d.admitted and d.reasons == (ATTESTATION_VERIFIER_FAULT, "malformed verifier result")

    class Optimist:
        """Returns a genuine-looking REFUSED result with a spoofed outcome pairing."""

        production_mode = False

        def verify(self, **kw):
            real = verifier(anchor_of(observer_signer())).verify(**kw)
            return dataclasses.replace(real, detail="unchanged")

    assert admit(ingress(Optimist()), attestation(observer_signer())).admitted


def test_8b_authenticator_fault_and_non_true_result_still_reject_after_verification():
    class Boom:
        is_reference_authenticator = False

        def authenticate(self, obs):
            raise RuntimeError("auth down")

    d = admit(ingress(verifier(anchor_of(observer_signer())), authenticator=Boom()), attestation(observer_signer()))
    assert not d.admitted and "authenticator error" in d.reasons
    assert d.attestation is not None and d.attestation.outcome is ea.EffectAttestationVerificationOutcome.VERIFIED

    class Truthy:
        is_reference_authenticator = False

        def authenticate(self, obs):
            return (1, ())

    d = admit(ingress(verifier(anchor_of(observer_signer())), authenticator=Truthy()), attestation(observer_signer()))
    assert not d.admitted and "untrusted producer" in d.reasons


def test_8c_no_verifier_configured_rejects_the_attested_path():
    ing = TrustedEffectIngress(ReferenceEffectSourceAuthenticator())
    assert ing.attestation_verifier is None
    d = admit(ing, attestation(observer_signer()))
    assert not d.admitted and d.reasons == (NO_ATTESTATION_VERIFIER,)
    with pytest.raises(ValueError):
        TrustedEffectIngress(ReferenceEffectSourceAuthenticator(), attestation_verifier=object())


# ----------------------------------------------------------------------------- #
# 9. unattested production observation rejects
# ----------------------------------------------------------------------------- #
def test_9_production_ingress_rejects_every_unattested_observation():
    prod_verifier = ea.Ed25519EffectAttestationVerifier(
        trust_anchor_resolver=ea.DenyAllTrustAnchorDirectory(), production_mode=True
    )
    for ing in (
        TrustedEffectIngress(_ProdAuthenticator(), production_mode=True),
        TrustedEffectIngress(_ProdAuthenticator(), production_mode=True, attestation_verifier=prod_verifier),
    ):
        d = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED), correlation=corr())
        assert not d.admitted and d.reasons == (UNATTESTED_REFUSED_IN_PRODUCTION,)
        # a malformed observation is still rejected for its own reason first
        d = ing.admit(make_observation("", BusinessOutcome.SUCCEEDED), correlation=corr())
        assert not d.admitted and d.reasons[0] == "malformed observation"
        # a wrong-tenant observation is still a binding mismatch
        d = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED, tenant_id="tenant_other"), correlation=corr())
        assert not d.admitted and d.reasons[0] == "binding mismatch"


# ----------------------------------------------------------------------------- #
# 10. StaticTrustAnchorDirectory refuses in production; the RI-4 blocker is pinned
# ----------------------------------------------------------------------------- #
def test_10_static_directory_refused_in_production_at_every_layer():
    static = ea.StaticTrustAnchorDirectory([anchor_of(observer_signer())], **SET)
    with pytest.raises(ea.EffectAttestationConfigurationError):
        ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=static, production_mode=True)
    # a reference-posture verifier behind a production ingress is refused
    with pytest.raises(AttestationVerifierRejectedError):
        TrustedEffectIngress(_ProdAuthenticator(), production_mode=True, attestation_verifier=verifier(anchor_of(observer_signer())))

    class Unstated:
        def verify(self, **kw):  # pragma: no cover - never reached
            raise AssertionError

    with pytest.raises(AttestationVerifierRejectedError):
        TrustedEffectIngress(_ProdAuthenticator(), production_mode=True, attestation_verifier=Unstated())
    # the reference authenticator is still refused in production (F-1 unchanged)
    with pytest.raises(ReferenceEffectIngressRejectedError):
        TrustedEffectIngress(ReferenceEffectSourceAuthenticator(), production_mode=True)


def test_10b_the_only_production_admissible_resolver_refuses_every_anchor():
    """RI-4 blocker, pinned: DenyAll is not a functional production resolver."""

    prod_verifier = ea.Ed25519EffectAttestationVerifier(
        trust_anchor_resolver=ea.DenyAllTrustAnchorDirectory(), production_mode=True
    )
    ing = TrustedEffectIngress(_ProdAuthenticator(), production_mode=True, attestation_verifier=prod_verifier)
    for signer in (observer_signer(), provider_signer()):
        d = admit(ing, attestation(signer))
        assert not d.admitted
        assert d.reasons == (ATTESTATION_REFUSED, "ANCHOR_UNKNOWN")
        assert d.attestation.refusal_reason is ea.EffectAttestationRefusalReason.ANCHOR_UNKNOWN


# ----------------------------------------------------------------------------- #
# 11. unsigned reference-grade behaviour remains labelled and unchanged
# ----------------------------------------------------------------------------- #
def test_11_reference_grade_unsigned_admission_is_unchanged():
    ing = TrustedEffectIngress(ReferenceEffectSourceAuthenticator())
    assert ing.production_mode is False and ReferenceEffectSourceAuthenticator.is_reference_authenticator is True
    d = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED), correlation=corr())
    assert d.admitted and d.observation.provenance is None and d.attestation is None
    d = ing.admit(make_observation("o1", BusinessOutcome.SUCCEEDED, source=""), correlation=corr())
    assert not d.admitted and "untrusted producer" in d.reasons


# ----------------------------------------------------------------------------- #
# 12. existing binding and domain rejections still occur on the attested path
# ----------------------------------------------------------------------------- #
def test_12_binding_and_authentication_checks_run_after_verification():
    ing = ingress(verifier(anchor_of(observer_signer())))
    # binding well-formedness: an empty observation id is malformed
    d = ing.admit_attested(attestation(observer_signer()), correlation=corr(), as_of=AS_OF, observation_id="   ")
    assert not d.admitted and d.reasons[0] == "malformed observation" and "missing observation_id" in d.reasons
    assert d.attestation is not None  # verification happened first, then the unchanged check rejected
    # producer authentication: the reference authenticator still needs a source
    d = admit(ing, attestation(observer_signer()), source="")
    assert not d.admitted and "untrusted producer" in d.reasons


# ----------------------------------------------------------------------------- #
# 13. effect_digest remains content-only
# ----------------------------------------------------------------------------- #
def test_13_effect_digest_ignores_provenance():
    ing = ingress(verifier(anchor_of(observer_signer())))
    stamped = admit(ing, attestation(observer_signer())).observation
    bare = dataclasses.replace(stamped, provenance=None, effect_digest="")
    assert bare.provenance is None
    assert bare.effect_digest == stamped.effect_digest
    other_role = dataclasses.replace(
        stamped, effect_digest="",
        provenance=dataclasses.replace(stamped.provenance, attester_role=PROVIDER_ROLE),
    )
    assert other_role.effect_digest == stamped.effect_digest
    assert len(stamped.effect_digest) == 64 and stamped.effect_digest != stamped.provenance.observation_digest


def test_13b_provenance_is_exact_typed():
    good = dict(attester_role=OBSERVER_ROLE, attester_identity="o", attester_key_id="k",
                observation_digest="sha256:" + "0" * 64, signing_payload_digest="sha256:" + "1" * 64,
                anchor_record_digest="sha256:" + "2" * 64, verified_at=AS_OF)
    EffectAttestationProvenance(**good)
    for field, bad in (("attester_role", "INDEPENDENT_OBSERVER"), ("attester_identity", ""),
                       ("attester_key_id", 1), ("verified_at", datetime(2026, 9, 6, 12, 5)),
                       ("verified_at", _Subclassed(2026, 9, 6, 12, 5, tzinfo=timezone.utc))):
        with pytest.raises(TypeError):
            EffectAttestationProvenance(**{**good, field: bad})
