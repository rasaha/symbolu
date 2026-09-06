"""Every refusal route the owner named, each measured against a positive control.

Order follows the verifier: input admission, contract admission, reconciliation
against the caller's facts, anchor resolution, lifecycle, key admission,
payload, signature. Each test asserts the **one** typed reason, so a refusal
that moved to a different check would be visible rather than merely still red.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest

import ugence_risk_authority_effect_attestation as ea
from ugence_governance_contracts import ExecutionBusinessOutcome
from ugence_trusted_evidence_authority import KeyRevocation
from _fixtures import (
    AS_OF,
    ATTESTED_AT,
    ONE_US,
    OTHER_TENANT,
    STRANGER_SEED,
    TENANT,
    VALID_FROM,
    VALID_TO,
    anchor_of,
    attestation,
    directory,
    observation,
    provider_signer,
    verifier,
    verify,
)

R = ea.EffectAttestationRefusalReason
OUT = ea.EffectAttestationVerificationOutcome


def _refused(result, reason):
    assert result.outcome is OUT.REFUSED
    assert result.refusal_reason is reason, (result.refusal_reason, result.detail)
    assert result.factual_correctness_established is False
    return result


# --------------------------------------------------------------------------- #
# 1. Unsigned, malformed, unsupported
# --------------------------------------------------------------------------- #
def test_an_absent_attestation_is_refused_not_defaulted():
    _refused(verify(verifier(anchor_of(provider_signer())), None), R.ATTESTATION_ABSENT)


def test_a_duck_typed_attestation_is_refused_before_anything_is_read():
    class Lookalike:
        def __getattr__(self, name):
            return getattr(attestation(), name)

    directory_ = directory(anchor_of(provider_signer()))
    asked = []
    original = directory_.resolve
    directory_ = type("Spy", (), {"resolve": lambda self, c: (asked.append(c), original(c))[1]})()
    v = ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=directory_)
    _refused(verify(v, Lookalike()), R.UNSUPPORTED_EXACT_TYPE)
    assert asked == []


def test_an_attestation_subclass_is_refused():
    class Sub(ea.EffectAttestation):
        pass

    att = attestation()
    sub = Sub(**{f.name: getattr(att, f.name) for f in dataclasses.fields(att)})
    _refused(verify(verifier(anchor_of(provider_signer())), sub), R.UNSUPPORTED_EXACT_TYPE)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("schema_version", "risk_authority.effect_attestation.v0", R.UNSUPPORTED_SCHEMA_VERSION),
        ("signing_domain", "ugence.other/effect/v1", R.UNSUPPORTED_SIGNING_DOMAIN),
        ("signature_algorithm", "RSA-PSS", R.UNSUPPORTED_ALGORITHM),
        ("signature_algorithm", "ed25519", R.UNSUPPORTED_ALGORITHM),
        ("signature_profile", "ugence.other/signature/v1", R.UNSUPPORTED_PROFILE),
        ("signature_encoding", "ugence.other/encoding/base64/v1", R.UNSUPPORTED_ENCODING),
    ],
)
def test_an_unsupported_contract_identifier_is_refused_by_name(field, value, reason):
    att = dataclasses.replace(attestation(), **{field: value})
    _refused(verify(verifier(anchor_of(provider_signer())), att), reason)


@pytest.mark.parametrize("bad", ["", "ab" * 63, "AB" * 64, "0x" + "ab" * 63, "zz" * 64, " " + "ab" * 64])
def test_a_malformed_signature_encoding_is_unconstructible(bad):
    with pytest.raises(ea.EffectAttestationContractError):
        dataclasses.replace(attestation(), signature=bad)


def test_a_well_formed_signature_that_does_not_verify_refuses_signature_invalid():
    att = dataclasses.replace(attestation(), signature="ab" * 64)
    result = _refused(verify(verifier(anchor_of(provider_signer())), att), R.SIGNATURE_INVALID)
    assert result.anchor_record_digest == ea.anchor_record_digest(anchor_of(provider_signer()))
    assert result.signing_payload_digest == att.signing_payload_digest


def test_a_signature_by_a_different_key_refuses_signature_invalid():
    stranger = provider_signer(STRANGER_SEED)  # same identity and key id, different key
    att = attestation(stranger)
    _refused(verify(verifier(anchor_of(provider_signer())), att), R.SIGNATURE_INVALID)


# --------------------------------------------------------------------------- #
# 2. Observation mutation after signing; signature and wrapper substitution
# --------------------------------------------------------------------------- #
def test_an_observation_mutated_after_signing_refuses_observation_mismatch():
    """The caller holds the mutated observation; the attestation wraps the original."""

    att = attestation()
    mutated = observation(business_outcome=ExecutionBusinessOutcome.FAILED)
    _refused(verify(verifier(anchor_of(provider_signer())), att, obs=mutated), R.OBSERVATION_MISMATCH)
    for change in (
        dict(observed_parameters={"order_id": "o-1", "amount": "12.51"}),
        dict(observed_parameters={"order_id": "o-1"}),
        dict(final=False),
        dict(reason="x"),
        dict(provider_trace_id="trace-2"),
        dict(fingerprint="fp-2"),
    ):
        _refused(verify(verifier(anchor_of(provider_signer())), att, obs=observation(**change)),
                 R.OBSERVATION_MISMATCH)


def test_the_wrapped_observation_mutated_in_place_after_signing_refuses():
    """A frozen dataclass forced open with object.__setattr__ on the wrapped object."""

    att = attestation()
    object.__setattr__(att.observation, "reason", "tampered")
    # The caller's own observation is the original; the wrapper's digest now differs.
    _refused(verify(verifier(anchor_of(provider_signer())), att), R.OBSERVATION_MISMATCH)


def test_a_signature_lifted_onto_another_wrapper_refuses():
    """Genuine signature over observation A, presented on a wrapper of observation B,
    with the caller holding B: the payload recomputed from B does not verify."""

    a = attestation()
    b_obs = observation(fingerprint="fp-2")
    lifted = dataclasses.replace(a, observation=b_obs)
    _refused(verify(verifier(anchor_of(provider_signer())), lifted, obs=b_obs), R.SIGNATURE_INVALID)


def test_a_wrapper_with_swapped_metadata_and_the_original_signature_refuses():
    a = attestation()
    for change in (
        dict(attested_at=ATTESTED_AT + timedelta(seconds=1)),
        dict(tenant_id=OTHER_TENANT),
    ):
        swapped = dataclasses.replace(a, **change)
        tenant = change.get("tenant_id", TENANT)
        result = verify(verifier(anchor_of(provider_signer())), swapped, tenant=tenant)
        assert result.outcome is OUT.REFUSED
        assert result.refusal_reason in (R.SIGNATURE_INVALID, R.WRONG_TENANT)


# --------------------------------------------------------------------------- #
# 3. Wrong tenant, attester identity, key id, anchor revision
# --------------------------------------------------------------------------- #
def test_the_wrong_tenant_refuses_before_the_directory_is_asked():
    asked = []

    class Spy:
        def resolve(self, coordinate):
            asked.append(coordinate)
            return directory(anchor_of(provider_signer())).resolve(coordinate)

    v = ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=Spy())
    _refused(verify(v, attestation(), tenant=OTHER_TENANT), R.WRONG_TENANT)
    _refused(verify(v, attestation(tenant_id=OTHER_TENANT)), R.WRONG_TENANT)
    assert asked == []


def test_an_unknown_attester_identity_or_key_id_refuses_anchor_unknown():
    anchor = anchor_of(provider_signer())
    for signer in (
        provider_signer(attester_identity="provider-beta"),
        provider_signer(attester_key_id="provider-key-2"),
    ):
        result = _refused(verify(verifier(anchor), attestation(signer)), R.ANCHOR_UNKNOWN)
        assert result.anchor_record_digest is None


def test_an_attestation_claiming_another_identity_over_the_real_key_refuses():
    """The genuine key signs, but the wrapper names a different identity: the anchor
    resolved for the claimed identity is not the signing key's."""

    other = provider_signer(STRANGER_SEED, attester_identity="provider-beta")
    anchors = (anchor_of(provider_signer()), anchor_of(other))
    att = attestation(provider_signer())
    forged = dataclasses.replace(att, attester_identity="provider-beta")
    _refused(verify(verifier(*anchors), forged), R.SIGNATURE_INVALID)


def test_a_wrong_expected_anchor_revision_refuses_and_names_the_real_one():
    anchor = anchor_of(provider_signer())
    other_revision = ea.anchor_record_digest(anchor_of(provider_signer(), trust_anchor_set_version="2"))
    result = _refused(
        verify(verifier(anchor), attestation(), expected_anchor=other_revision),
        R.ANCHOR_REVISION_MISMATCH,
    )
    assert result.anchor_record_digest == ea.anchor_record_digest(anchor)
    assert verify(verifier(anchor), attestation(),
                  expected_anchor=ea.anchor_record_digest(anchor)).outcome is OUT.VERIFIED


# --------------------------------------------------------------------------- #
# 4. Anchor lifecycle, in TEA's order, at the caller's instant
# --------------------------------------------------------------------------- #
def test_a_revoked_anchor_refuses_revoked_even_when_also_expired():
    revoked = anchor_of(
        provider_signer(),
        effective_to=VALID_TO,
    )
    revoked = dataclasses.replace(
        revoked, revocation=KeyRevocation(effective_at=ATTESTED_AT - timedelta(days=1))
    )
    result = _refused(verify(verifier(revoked), attestation()), R.ANCHOR_REVOKED)
    assert result.anchor_record_digest == ea.anchor_record_digest(revoked)
    _refused(verify(verifier(revoked), attestation(), as_of=VALID_TO + timedelta(days=1)),
             R.ANCHOR_REVOKED)


def test_a_disabled_anchor_refuses_disabled():
    disabled = dataclasses.replace(anchor_of(provider_signer()), disabled=True)
    _refused(verify(verifier(disabled), attestation()), R.ANCHOR_DISABLED)


def test_the_half_open_validity_window_is_applied_at_both_boundaries():
    anchor = anchor_of(provider_signer())
    v = verifier(anchor)
    att = attestation()
    assert verify(v, att, as_of=VALID_FROM).outcome is OUT.VERIFIED
    _refused(verify(v, att, as_of=VALID_FROM - ONE_US), R.ANCHOR_NOT_YET_VALID)
    assert verify(v, att, as_of=VALID_TO - ONE_US).outcome is OUT.VERIFIED
    _refused(verify(v, att, as_of=VALID_TO), R.ANCHOR_EXPIRED)


def test_a_naive_as_of_is_a_caller_contract_violation_and_the_directory_is_never_asked():
    asked = []

    class Spy:
        def resolve(self, coordinate):
            asked.append(coordinate)
            return directory(anchor_of(provider_signer())).resolve(coordinate)

    v = ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=Spy())
    for bad in (datetime(2026, 9, 6, 12, 5), "2026-09-06T12:05:00Z", None):
        with pytest.raises(ea.EffectAttestationContractError):
            verify(v, attestation(), as_of=bad)
    assert asked == []


# --------------------------------------------------------------------------- #
# 5. Directory failures: never a fallback
# --------------------------------------------------------------------------- #
class _Raises:
    def resolve(self, coordinate):
        raise RuntimeError("offline")


class _WrongType:
    def resolve(self, coordinate):
        return anchor_of(provider_signer())


class _None:
    def resolve(self, coordinate):
        return None


class _AnswersAnotherCoordinate:
    def resolve(self, coordinate):
        other = anchor_of(provider_signer(attester_key_id="provider-key-9"))
        return ea.TrustAnchorResolution.resolved(other.coordinate, other)


class _SwapsAnchorAfterConstruction:
    def resolve(self, coordinate):
        genuine = directory(anchor_of(provider_signer())).resolve(coordinate)
        swapped = anchor_of(provider_signer(attester_key_id="provider-key-9"))
        object.__setattr__(genuine, "anchor", swapped)
        return genuine


class _DuckTypedAnchorInGenuineResolution:
    def resolve(self, coordinate):
        genuine = directory(anchor_of(provider_signer())).resolve(coordinate)
        real = genuine.anchor

        class Duck:
            pass

        duck = Duck()
        for f in dataclasses.fields(real):
            setattr(duck, f.name, getattr(real, f.name))
        duck.coordinate = real.coordinate
        duck.canonical_digest = lambda: "0" * 64
        duck.lifecycle_refusal_at = lambda instant: None
        duck.verification_key = real.verification_key
        object.__setattr__(genuine, "anchor", duck)
        return genuine


class _LookalikeResolution:
    def resolve(self, coordinate):
        class Fake(ea.TrustAnchorResolution):
            pass

        genuine = directory(anchor_of(provider_signer())).resolve(coordinate)
        return Fake(coordinate=genuine.coordinate, anchor=genuine.anchor)


@pytest.mark.parametrize(
    "resolver,reason",
    [
        (_Raises(), R.ANCHOR_UNAVAILABLE),
        (_WrongType(), R.ANCHOR_UNAVAILABLE),
        (_None(), R.ANCHOR_UNAVAILABLE),
        (_LookalikeResolution(), R.ANCHOR_UNAVAILABLE),
        (_AnswersAnotherCoordinate(), R.ANCHOR_COORDINATE_MISMATCH),
        (_SwapsAnchorAfterConstruction(), R.ANCHOR_COORDINATE_MISMATCH),
        (_DuckTypedAnchorInGenuineResolution(), R.ANCHOR_UNAVAILABLE),
    ],
    ids=["raises", "wrong-type", "none", "subclass-resolution", "other-coordinate",
         "post-construction-anchor-swap", "duck-typed-anchor"],
)
def test_a_failing_or_substituted_directory_refuses_closed(resolver, reason):
    v = ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=resolver)
    result = _refused(verify(v, attestation()), reason)
    assert result.anchor_record_digest is None


def test_a_deny_all_directory_refuses_anchor_unknown():
    v = ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=ea.DenyAllTrustAnchorDirectory())
    _refused(verify(v, attestation()), R.ANCHOR_UNKNOWN)


# --------------------------------------------------------------------------- #
# 6. Nothing is memoized; results are evidence-bound values
# --------------------------------------------------------------------------- #
def test_nothing_is_memoized_the_directory_is_consulted_every_time():
    asked = []
    store = directory(anchor_of(provider_signer()))

    class Spy:
        def resolve(self, coordinate):
            asked.append(coordinate)
            return store.resolve(coordinate)

    v = ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=Spy())
    att = attestation()
    first = verify(v, att)
    second = verify(v, att)
    assert first == second and first is not second
    assert len(asked) == 2
    later = verify(v, att, as_of=AS_OF + timedelta(days=1))
    assert later != first and later.outcome is OUT.VERIFIED


def test_every_refusal_reason_the_verifier_produces_is_a_member_of_the_closed_vocabulary():
    seen = set()
    v_ok = verifier(anchor_of(provider_signer()))
    cases = [
        (v_ok, None, {}),
        (v_ok, attestation(), {"tenant": OTHER_TENANT}),
        (v_ok, attestation(), {"obs": observation(final=False)}),
        (v_ok, dataclasses.replace(attestation(), signature="ab" * 64), {}),
        (verifier(), attestation(), {}),
        (ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=_Raises()), attestation(), {}),
    ]
    for v, att, kw in cases:
        result = verify(v, att, **kw)
        assert result.outcome is OUT.REFUSED
        seen.add(result.refusal_reason)
    assert seen <= set(ea.EffectAttestationRefusalReason)
    assert len(seen) >= 6
