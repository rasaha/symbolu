"""Every refusal route, each measured against a positive control.

Order follows the verifier: input admission, contract admission, reconciliation
against the caller's facts, anchor resolution, lifecycle, key admission,
payload, signature. Each test asserts the **one** typed reason, so a refusal
that moved to a different check would be visible rather than merely still red.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest

import ugence_reasoning_method_result_attestation as ra
from ugence_trusted_evidence_authority import KeyRevocation
from _fixtures import (
    AS_OF,
    OTHER_ENGINE_ID,
    PRODUCED_AT,
    SIGNED_AT,
    ONE_US,
    STRANGER_SEED,
    VALID_FROM,
    VALID_TO,
    anchor_of,
    directory,
    engine_signer,
    result,
    signed,
    verifier,
    verify,
)

R = ra.ComparisonResultRefusalReason
OUT = ra.ComparisonResultVerificationOutcome


def _refused(r, reason):
    assert r.outcome is OUT.REFUSED
    assert r.refusal_reason is reason, (r.refusal_reason, r.detail)
    assert r.factual_correctness_established is False
    return r


# --------------------------------------------------------------------------- #
# 1. Unsigned, malformed, unsupported
# --------------------------------------------------------------------------- #
def test_an_absent_signed_result_is_refused_not_defaulted():
    _refused(verify(verifier(anchor_of(engine_signer())), None), R.ATTESTATION_ABSENT)


def test_a_duck_typed_signed_result_is_refused_before_anything_is_read():
    class Lookalike:
        def __getattr__(self, name):
            return getattr(signed(), name)

    asked = []
    store = directory(anchor_of(engine_signer()))

    class Spy:
        def resolve(self, coordinate, *, as_of=None):
            asked.append(coordinate)
            return store.resolve(coordinate)

    v = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=Spy())
    _refused(verify(v, Lookalike()), R.UNSUPPORTED_EXACT_TYPE)
    assert asked == []


def test_a_signed_result_subclass_is_refused():
    class Sub(ra.SignedComparisonResult):
        pass

    sr = signed()
    sub = Sub(**{f.name: getattr(sr, f.name) for f in dataclasses.fields(sr)})
    _refused(verify(verifier(anchor_of(engine_signer())), sub), R.UNSUPPORTED_EXACT_TYPE)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("schema_version", "reasoning_method.signed_comparison_result.v0", R.UNSUPPORTED_SCHEMA_VERSION),
        ("signing_domain", "ugence.other/comparison/v1", R.UNSUPPORTED_SIGNING_DOMAIN),
        ("signature_algorithm", "RSA-PSS", R.UNSUPPORTED_ALGORITHM),
        ("signature_algorithm", "ed25519", R.UNSUPPORTED_ALGORITHM),
        ("signature_profile", "ugence.other/signature/v1", R.UNSUPPORTED_PROFILE),
        ("signature_encoding", "ugence.other/encoding/base64/v1", R.UNSUPPORTED_ENCODING),
    ],
)
def test_an_unsupported_contract_identifier_is_refused_by_name(field, value, reason):
    sr = dataclasses.replace(signed(), **{field: value})
    _refused(verify(verifier(anchor_of(engine_signer())), sr), reason)


@pytest.mark.parametrize("bad", ["", "ab" * 63, "AB" * 64, "0x" + "ab" * 63, "zz" * 64, " " + "ab" * 64])
def test_a_malformed_signature_encoding_is_unconstructible(bad):
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        dataclasses.replace(signed(), signature=bad)


def test_a_well_formed_signature_that_does_not_verify_refuses_signature_invalid():
    sr = dataclasses.replace(signed(), signature="ab" * 64)
    r = _refused(verify(verifier(anchor_of(engine_signer())), sr), R.SIGNATURE_INVALID)
    assert r.anchor_record_digest == ra.anchor_record_digest(anchor_of(engine_signer()))
    assert r.signing_payload_digest == sr.signing_payload_digest


def test_a_signature_by_a_different_key_refuses_signature_invalid():
    stranger = engine_signer(STRANGER_SEED)  # same identity and key id, different key
    _refused(verify(verifier(anchor_of(engine_signer())), signed(stranger)), R.SIGNATURE_INVALID)


# --------------------------------------------------------------------------- #
# 2. Result substitution after signing; signature and wrapper substitution
# --------------------------------------------------------------------------- #
def test_a_result_that_differs_from_the_callers_refuses_result_mismatch():
    """The caller holds a different result; the wrapper wraps the original."""

    sr = signed()
    for change in (
        dict(request_id="cmp.other"),
        dict(request_digest="b" * 64),
        dict(engine_version="0.3.0"),
        dict(produced_at=PRODUCED_AT + timedelta(seconds=1)),
    ):
        _refused(verify(verifier(anchor_of(engine_signer())), sr, res=result(**change)), R.RESULT_MISMATCH)


def test_a_signature_lifted_onto_another_wrapper_refuses():
    """Genuine signature over result A, presented on a wrapper of result B, with the
    caller holding B: the payload recomputed from B does not verify."""

    a = signed()
    b_res = result(request_id="cmp.other")
    lifted = dataclasses.replace(a, result=b_res)
    _refused(verify(verifier(anchor_of(engine_signer())), lifted, res=b_res), R.SIGNATURE_INVALID)


def test_a_wrapper_with_swapped_metadata_and_the_original_signature_refuses():
    a = signed()
    swapped = dataclasses.replace(a, signed_at=SIGNED_AT + timedelta(seconds=1))
    _refused(verify(verifier(anchor_of(engine_signer())), swapped), R.SIGNATURE_INVALID)


# --------------------------------------------------------------------------- #
# 3. Wrong engine, signer identity, key id, anchor revision
# --------------------------------------------------------------------------- #
def test_the_wrong_expected_engine_refuses_before_the_directory_is_asked():
    asked = []

    class Spy:
        def resolve(self, coordinate, *, as_of=None):
            asked.append(coordinate)
            return directory(anchor_of(engine_signer())).resolve(coordinate)

    v = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=Spy())
    _refused(verify(v, signed(), engine=OTHER_ENGINE_ID), R.WRONG_ENGINE_IDENTITY)
    assert asked == []


def test_an_unknown_key_id_refuses_anchor_unknown():
    anchor = anchor_of(engine_signer())
    r = _refused(verify(verifier(anchor), signed(engine_signer(signer_key_id="engine-key-2"))), R.ANCHOR_UNKNOWN)
    assert r.anchor_record_digest is None


def test_an_unknown_engine_identity_refuses_anchor_unknown():
    """The caller expects another engine, whose result the other engine signed, but
    only the comparison engine's anchor is configured."""

    other = engine_signer(STRANGER_SEED, signer_identity=OTHER_ENGINE_ID)
    foreign = result(engine=OTHER_ENGINE_ID)
    sr = ra.sign_comparison_result(foreign, signer=other, signed_at=SIGNED_AT)
    r = _refused(verify(verifier(anchor_of(engine_signer())), sr, res=foreign, engine=OTHER_ENGINE_ID), R.ANCHOR_UNKNOWN)
    assert r.anchor_record_digest is None


def test_a_wrong_expected_anchor_revision_refuses_and_names_the_real_one():
    anchor = anchor_of(engine_signer())
    other_revision = ra.anchor_record_digest(anchor_of(engine_signer(), trust_anchor_set_version="2"))
    r = _refused(verify(verifier(anchor), signed(), expected_anchor=other_revision), R.ANCHOR_REVISION_MISMATCH)
    assert r.anchor_record_digest == ra.anchor_record_digest(anchor)
    assert verify(verifier(anchor), signed(), expected_anchor=ra.anchor_record_digest(anchor)).outcome is OUT.VERIFIED


# --------------------------------------------------------------------------- #
# 4. Anchor lifecycle, in TEA's order, at the caller's instant
# --------------------------------------------------------------------------- #
def test_a_revoked_anchor_refuses_revoked_even_when_also_expired():
    revoked = dataclasses.replace(
        anchor_of(engine_signer(), effective_to=VALID_TO),
        revocation=KeyRevocation(effective_at=SIGNED_AT - timedelta(days=1)),
    )
    r = _refused(verify(verifier(revoked), signed()), R.ANCHOR_REVOKED)
    assert r.anchor_record_digest == ra.anchor_record_digest(revoked)
    _refused(verify(verifier(revoked), signed(), as_of=VALID_TO + timedelta(days=1)), R.ANCHOR_REVOKED)


def test_a_disabled_anchor_refuses_disabled():
    disabled = dataclasses.replace(anchor_of(engine_signer()), disabled=True)
    _refused(verify(verifier(disabled), signed()), R.ANCHOR_DISABLED)


def test_the_half_open_validity_window_is_applied_at_both_boundaries():
    anchor = anchor_of(engine_signer())
    v = verifier(anchor)
    sr = signed()
    assert verify(v, sr, as_of=VALID_FROM).outcome is OUT.VERIFIED
    _refused(verify(v, sr, as_of=VALID_FROM - ONE_US), R.ANCHOR_NOT_YET_VALID)
    assert verify(v, sr, as_of=VALID_TO - ONE_US).outcome is OUT.VERIFIED
    _refused(verify(v, sr, as_of=VALID_TO), R.ANCHOR_EXPIRED)


def test_a_naive_as_of_is_a_caller_contract_violation_and_the_directory_is_never_asked():
    asked = []

    class Spy:
        def resolve(self, coordinate, *, as_of=None):
            asked.append(coordinate)
            return directory(anchor_of(engine_signer())).resolve(coordinate)

    v = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=Spy())
    for bad in (datetime(2026, 9, 6, 12, 5), "2026-09-06T12:05:00Z", None):
        with pytest.raises(ra.ComparisonResultAttestationContractError):
            verify(v, signed(), as_of=bad)
    assert asked == []


# --------------------------------------------------------------------------- #
# 5. Directory failures: never a fallback
# --------------------------------------------------------------------------- #
class _Raises:
    def resolve(self, coordinate, *, as_of=None):
        raise RuntimeError("offline")


class _WrongType:
    def resolve(self, coordinate, *, as_of=None):
        return anchor_of(engine_signer())


class _None:
    def resolve(self, coordinate, *, as_of=None):
        return None


class _AnswersAnotherCoordinate:
    def resolve(self, coordinate, *, as_of=None):
        other = anchor_of(engine_signer(signer_key_id="engine-key-9"))
        return ra.TrustAnchorResolution.resolved(other.coordinate, other)


class _SwapsAnchorAfterConstruction:
    def resolve(self, coordinate, *, as_of=None):
        genuine = directory(anchor_of(engine_signer())).resolve(coordinate)
        swapped = anchor_of(engine_signer(signer_key_id="engine-key-9"))
        object.__setattr__(genuine, "anchor", swapped)
        return genuine


class _DuckTypedAnchorInGenuineResolution:
    def resolve(self, coordinate, *, as_of=None):
        genuine = directory(anchor_of(engine_signer())).resolve(coordinate)
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
    def resolve(self, coordinate, *, as_of=None):
        class Fake(ra.TrustAnchorResolution):
            pass

        genuine = directory(anchor_of(engine_signer())).resolve(coordinate)
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
    v = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=resolver)
    r = _refused(verify(v, signed()), reason)
    assert r.anchor_record_digest is None


def test_a_deny_all_directory_refuses_anchor_unknown():
    v = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=ra.DenyAllTrustAnchorDirectory())
    _refused(verify(v, signed()), R.ANCHOR_UNKNOWN)


# --------------------------------------------------------------------------- #
# 6. Nothing is memoized; results are evidence-bound values
# --------------------------------------------------------------------------- #
def test_nothing_is_memoized_the_directory_is_consulted_every_time():
    asked = []
    store = directory(anchor_of(engine_signer()))

    class Spy:
        def resolve(self, coordinate, *, as_of=None):
            asked.append(coordinate)
            return store.resolve(coordinate)

    v = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=Spy())
    sr = signed()
    first = verify(v, sr)
    second = verify(v, sr)
    assert first == second and first is not second
    assert len(asked) == 2
    later = verify(v, sr, as_of=AS_OF + timedelta(days=1))
    assert later != first and later.outcome is OUT.VERIFIED


def test_every_refusal_reason_the_verifier_produces_is_a_member_of_the_closed_vocabulary():
    seen = set()
    v_ok = verifier(anchor_of(engine_signer()))
    cases = [
        (v_ok, None, {}),
        (v_ok, signed(), {"engine": OTHER_ENGINE_ID}),
        (v_ok, signed(), {"res": result(request_id="cmp.other")}),
        (v_ok, dataclasses.replace(signed(), signature="ab" * 64), {}),
        (verifier(), signed(), {}),
        (ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=_Raises()), signed(), {}),
    ]
    for v, sr, kw in cases:
        r = verify(v, sr, **kw)
        assert r.outcome is OUT.REFUSED
        seen.add(r.refusal_reason)
    assert seen <= set(ra.ComparisonResultRefusalReason)
    assert len(seen) >= 6
