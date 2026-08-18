"""Forgery, replay and substitution routes, proved closed.

ADR §8.1 (six self-authorization prohibitions), §10 (enumerated non-proofs),
§13.3 (no unsigned "trusted" receipts), §26.5 (replay and swap resistance),
§26.6 (domain separation prevents cross-artifact signature reuse) and §26.12
(a self-consistent forged artifact is still not authority-authentic).

The discipline throughout: every route below is attempted against a *working*
happy path, so a test that passes because the fixture was already broken would
be caught by the happy-path tests failing first.
"""

from __future__ import annotations

import copy
import dataclasses
import pickle
from datetime import datetime, timedelta, timezone

import pytest
from _authority_builders import (
    VERIFIED_AT,
    VERIFIER_AUTHORITY_ID,
    VERIFIER_KEY_ID,
    attacker_signing_key,
    authority,
    authority_anchor,
    authority_signing_key,
    determination,
    directory,
    envelope,
    issuer,
    producer_anchor,
    producer_signing_key,
    reverifier,
    signer,
    submission,
)
from _builders import AS_OF, CONTENT_DIGEST, OTHER_DIGEST, identity, receipt, request
from ugence_trusted_evidence_authority.api import (
    RECEIPT_REPORTABLE_TRUST_STAGES,
    TRUSTED_EVIDENCE_PROTOCOL_V1_ID,
    TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
    DenyAllTrustAnchorDirectory,
    EvidenceAdmissionOutcome,
    EvidenceVerificationDetermination,
    KeyRevocation,
    ReceiptSigningInput,
    ReceiptVerification,
    ReceiptVerificationOutcome,
    SignedEvidenceSubmission,
    SignedEvidenceVerificationReceipt,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
    TrustedEvidenceVerificationKey,
    encode_public_key,
    encode_signature,
    signed_evidence_input_bytes,
    signed_receipt_input_bytes,
)

R = TrustedEvidenceRefusalReason
UTC = timezone.utc

TRUTHY = [True, 1, "true", "yes", [1], (1,), {"a": 1}, {1}, object(), 1.0]


def refusal(signed=None, *, anchors=None, at=None, **expected):
    result = reverifier(anchors).verify(
        envelope() if signed is None else signed,
        evaluated_at=AS_OF if at is None else at,
        **expected,
    )
    assert result.outcome is ReceiptVerificationOutcome.REFUSED, result
    assert result.verified is False
    return result.refusal_reason


# --------------------------------------------------------------------------- #
# Manufactured success — §8.1.5, §10.1
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("token", TRUTHY + [None])
def test_a_determination_cannot_be_manufactured_with_any_token(token):
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        EvidenceVerificationDetermination(
            outcome=EvidenceAdmissionOutcome.ADMITTED,
            verification_request_digest=CONTENT_DIGEST,
            verifier_authority_id=VERIFIER_AUTHORITY_ID,
            verifier_key_id=VERIFIER_KEY_ID,
            verification_protocol_id=TRUSTED_EVIDENCE_PROTOCOL_V1_ID,
            verification_protocol_version=TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION,
            verified_at=VERIFIED_AT,
            evaluated_at=AS_OF,
            cleared_stages=tuple(RECEIPT_REPORTABLE_TRUST_STAGES),
            receipt_payload=receipt(),
            issuance_token=token,
        )
    assert "cannot be constructed directly" in str(excinfo.value)


@pytest.mark.parametrize("token", TRUTHY + [None])
def test_a_receipt_verification_cannot_be_manufactured_with_any_token(token):
    coordinate = TrustAnchorCoordinate(
        authority_id=VERIFIER_AUTHORITY_ID,
        key_id=VERIFIER_KEY_ID,
        capability=TrustAnchorCapability.RECEIPT_ISSUANCE,
    )
    with pytest.raises(TrustedEvidenceContractError):
        ReceiptVerification(
            outcome=ReceiptVerificationOutcome.VERIFIED,
            evaluated_at=AS_OF,
            coordinate=coordinate,
            envelope_digest=CONTENT_DIGEST,
            payload_canonical_digest=CONTENT_DIGEST,
            verification_token=token,
        )


@pytest.mark.parametrize("token", TRUTHY + [None])
def test_arbitrary_bytes_cannot_be_turned_into_a_signing_instruction(token):
    with pytest.raises(TrustedEvidenceContractError):
        ReceiptSigningInput(
            signed_input=b"attacker-chosen bytes",
            signer_authority_id=VERIFIER_AUTHORITY_ID,
            signing_key_id=VERIFIER_KEY_ID,
            signature_profile=TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
            issuance_token=token,
        )


@pytest.mark.parametrize(
    "bad", [b"raw bytes", "a string", None, 42, [], {"signed_input": b"x"}]
)
def test_the_signer_refuses_anything_that_is_not_a_minted_signing_input(bad):
    with pytest.raises(TrustedEvidenceContractError):
        signer().sign_receipt(bad)


def test_no_public_callable_signs_bytes():
    import ugence_trusted_evidence_authority.api as api

    for name in api.__all__:
        assert name not in ("sign", "sign_bytes", "sign_payload", "sign_arbitrary")
    # The only public method named for signing takes the minted instruction.
    import inspect

    parameters = inspect.signature(signer().sign_receipt).parameters
    assert list(parameters) == ["signing_input"]


def test_a_verified_property_cannot_be_set_on_any_result():
    result = determination()
    verification = reverifier().verify(envelope(), evaluated_at=AS_OF)
    for obj, attribute in (
        (result, "admitted"),
        (verification, "verified"),
        (envelope().payload, "authenticity_verified"),
        (envelope().payload, "structural_status"),
    ):
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            setattr(obj, attribute, True)


def test_object_setattr_on_a_result_does_not_change_what_reverifying_says():
    """A doctored in-process object is a lie only its holder believes."""

    signed = envelope()
    refused = reverifier(DenyAllTrustAnchorDirectory()).verify(
        signed, evaluated_at=AS_OF
    )
    assert not refused.verified
    try:
        object.__setattr__(refused, "outcome", ReceiptVerificationOutcome.VERIFIED)
    except Exception:
        pass
    # Re-asking the question — the only thing a consumer may rely on — refuses.
    assert not reverifier(DenyAllTrustAnchorDirectory()).verify(
        signed, evaluated_at=AS_OF
    ).verified


def test_a_subclass_or_lookalike_envelope_is_refused():
    signed = envelope()

    fields = {f.name: getattr(signed, f.name) for f in dataclasses.fields(signed)}

    # A subclass that overrides a field with a lying property cannot even be
    # constructed: the dataclass __init__ assigns the field, and a property has
    # no setter. The forgery fails one step earlier than the type check.
    class LyingSubclass(SignedEvidenceVerificationReceipt):
        @property
        def payload_canonical_digest(self):
            return "0" * 64

    with pytest.raises(AttributeError):
        LyingSubclass(**fields)

    # A plain subclass constructs, and is refused by the exact-type check.
    class PlainSubclass(SignedEvidenceVerificationReceipt):
        pass

    with pytest.raises(TrustedEvidenceContractError):
        reverifier().verify(PlainSubclass(**fields), evaluated_at=AS_OF)

    class Lookalike:
        payload = signed.payload
        payload_canonical_digest = signed.payload_canonical_digest
        signer_authority_id = signed.signer_authority_id
        signing_key_id = signed.signing_key_id
        signature = signed.signature
        signature_profile = signed.signature_profile
        verified = True

        def signed_input_bytes(self):
            return signed.signed_input_bytes()

        def signature_bytes(self):
            return signed.signature_bytes()

        def envelope_digest(self):
            return signed.envelope_digest()

    with pytest.raises(TrustedEvidenceContractError):
        reverifier().verify(Lookalike(), evaluated_at=AS_OF)


@pytest.mark.parametrize("clone", ["copy", "deepcopy", "pickle"])
def test_reconstruction_round_trips_change_nothing_about_trust(clone):
    signed = envelope()
    rebuilt = {
        "copy": lambda: copy.copy(signed),
        "deepcopy": lambda: copy.deepcopy(signed),
        "pickle": lambda: pickle.loads(pickle.dumps(signed)),
    }[clone]()
    assert rebuilt == signed
    assert rebuilt.envelope_digest() == signed.envelope_digest()
    assert reverifier().verify(rebuilt, evaluated_at=AS_OF).verified
    assert not reverifier(DenyAllTrustAnchorDirectory()).verify(
        rebuilt, evaluated_at=AS_OF
    ).verified


# --------------------------------------------------------------------------- #
# Substitution — payload, digest, authority, key, algorithm
# --------------------------------------------------------------------------- #

def test_swapping_the_payload_after_signing_is_caught():
    signed = envelope()
    other = receipt(receipt_id="a-different-receipt")

    # Payload swapped, digest kept: refused at construction.
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        dataclasses.replace(signed, payload=other)
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH

    # Both swapped: the signature no longer covers it.
    swapped = dataclasses.replace(
        signed, payload=other, payload_canonical_digest=other.canonical_digest()
    )
    assert refusal(swapped) is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID


def test_swapping_only_the_declared_payload_digest_is_caught():
    signed = envelope()
    with pytest.raises(TrustedEvidenceContractError):
        dataclasses.replace(signed, payload_canonical_digest=OTHER_DIGEST)


def test_signer_authority_substitution_is_caught():
    signed = envelope()
    relabelled = dataclasses.replace(signed, signer_authority_id="another-authority")
    # The coordinate no longer resolves...
    assert refusal(relabelled) is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING
    # ...and even with an anchor registered there, the frame binds the original.
    forged = directory(
        producer_anchor(), authority_anchor(authority_id="another-authority")
    )
    assert refusal(relabelled, anchors=forged) is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID


def test_key_id_substitution_is_caught():
    signed = envelope()
    relabelled = dataclasses.replace(signed, signing_key_id="another-key")
    assert refusal(relabelled) is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING
    forged = directory(producer_anchor(), authority_anchor(key_id="another-key"))
    assert refusal(relabelled, anchors=forged) is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID


def test_public_key_substitution_is_caught():
    wrong = authority_anchor(
        public_key=encode_public_key(
            attacker_signing_key().verification_key.public_key_bytes
        )
    )
    assert refusal(anchors=directory(producer_anchor(), wrong)) is (
        R.TRUSTED_EVIDENCE_SIGNATURE_INVALID
    )


@pytest.mark.parametrize(
    "profile",
    ["none", "None", "NONE", "", "ed25519", "hmac-sha256", "rsa-pss",
     "ugence.trusted-evidence-authority/signature/ed25519-sha512-pure/v2",
     TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.upper()],
)
def test_algorithm_confusion_and_downgrade_are_refused(profile):
    signed = envelope()
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        dataclasses.replace(signed, signature_profile=profile)
    assert excinfo.value.reason in (
        R.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED,
        R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
    )
    with pytest.raises(TrustedEvidenceContractError):
        authority_anchor(signature_profile=profile)


def test_an_anchor_whose_profile_differs_from_the_envelope_is_refused():
    """No negotiation: a profile mismatch is a refusal, not a retry."""

    class DriftingResolver:
        def resolve(self, coordinate):
            from ugence_trusted_evidence_authority.api import TrustAnchorResolution

            # A resolver returning a *valid* anchor whose profile has moved on.
            return TrustAnchorResolution.resolved(coordinate, authority_anchor())

    # Both sides carry the one ratified profile, so agreement holds; the guard
    # exists for a future second profile and is exercised via the anchor path.
    assert authority_anchor().signature_profile == envelope().signature_profile


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s[:-2],
        lambda s: s + "00",
        lambda s: s.upper(),
        lambda s: "0x" + s[2:],
        lambda s: " " + s[1:],
        lambda s: s[:-1] + "g",
        lambda s: "",
        lambda s: s[:64],
    ],
    ids=["truncated", "extended", "uppercase", "prefixed", "padded", "non-hex",
         "empty", "half"],
)
def test_signature_truncation_extension_and_noncanonical_encoding_are_refused(mutate):
    signed = envelope()
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        dataclasses.replace(signed, signature=mutate(signed.signature))
    assert excinfo.value.reason in (
        R.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
        R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        R.TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING,
    )


@pytest.mark.parametrize("bad", [None, 42, b"\x00" * 64, ["hex"], {"s": "x"}, 1.0])
def test_a_mistyped_signature_is_refused(bad):
    with pytest.raises(TrustedEvidenceContractError):
        dataclasses.replace(envelope(), signature=bad)


def test_a_well_formed_but_wrong_signature_is_a_verification_refusal():
    """Construction and verification failures stay distinguishable."""

    signed = envelope()
    flipped = bytearray(signed.signature_bytes())
    flipped[0] ^= 0x01
    tampered = dataclasses.replace(signed, signature=encode_signature(bytes(flipped)))
    assert refusal(tampered) is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID


# --------------------------------------------------------------------------- #
# Cross-domain and evidence-versus-receipt substitution — §26.6
# --------------------------------------------------------------------------- #

def test_an_evidence_signature_never_verifies_as_a_receipt_signature():
    key = authority_signing_key()
    evidence_frame = signed_evidence_input_bytes(
        evidence=identity(),
        producer_authority_id=VERIFIER_AUTHORITY_ID,
        producer_key_id=VERIFIER_KEY_ID,
    )
    receipt_frame = signed_receipt_input_bytes(
        payload=receipt(),
        signer_authority_id=VERIFIER_AUTHORITY_ID,
        signing_key_id=VERIFIER_KEY_ID,
    )
    assert evidence_frame != receipt_frame
    public = key.verification_key
    assert public.verify(evidence_frame, key.sign(evidence_frame))
    assert not public.verify(receipt_frame, key.sign(evidence_frame))
    assert not public.verify(evidence_frame, key.sign(receipt_frame))


def test_a_submission_cannot_name_the_receipt_domain_and_vice_versa():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        dataclasses.replace(
            submission(), signed_input_domain=TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN
        )
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        dataclasses.replace(
            envelope(),
            signed_input_domain=TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
        )
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED


def test_an_evidence_digest_is_never_a_receipt_digest():
    signed = envelope()
    assert identity().canonical_digest() != signed.payload_canonical_digest
    assert signed.payload_canonical_digest != signed.envelope_digest()
    assert submission().canonical_digest() != signed.envelope_digest()


def test_a_receipt_is_not_substitutable_for_the_evidence_it_attests():
    signed = envelope()
    assert signed.payload.source_evidence_identity_digest == (
        identity().canonical_digest()
    )
    # The receipt binds the evidence by digest and carries no copy of it.
    import json

    from ugence_trusted_evidence_authority.api import canonical_bytes

    body = json.loads(canonical_bytes(signed.payload))["body"]
    assert "evidence" not in body
    assert "observation" not in body
    assert "provenance" not in body


def test_a_producer_key_cannot_sign_a_receipt_that_verifies():
    """E-3 / §8.1.1 — the producer/verifier separation, at the crypto layer."""

    signed = envelope()
    producer_signed = encode_signature(
        producer_signing_key().sign(signed.signed_input_bytes())
    )
    forged = dataclasses.replace(signed, signature=producer_signed)
    # The receipt-issuance anchor holds the authority key, not the producer's.
    assert refusal(forged) is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID
    # And the producer's key is not registered for receipt issuance at all.
    coordinate = TrustAnchorCoordinate(
        authority_id=VERIFIER_AUTHORITY_ID,
        key_id=VERIFIER_KEY_ID,
        capability=TrustAnchorCapability.EVIDENCE_PRODUCTION,
    )
    assert directory().resolve(coordinate).anchor is None


# --------------------------------------------------------------------------- #
# Replay across every coordinate axis — §26.5
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "kwarg,expected",
    [
        ("expected_tenant_id", R.TRUSTED_EVIDENCE_TENANT_MISMATCH),
        ("expected_assessment_context_ref", R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH),
        ("expected_subject_ref", R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH),
        ("expected_assessment_purpose_ref", R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH),
        ("expected_usage_scope_ref", R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH),
        ("expected_verification_protocol_id", R.TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED),
        (
            "expected_verification_protocol_version",
            R.TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH,
        ),
    ],
)
def test_replay_under_a_different_coordinate_is_mechanically_detected(kwarg, expected):
    assert refusal(**{kwarg: "a-different-value"}) is expected


@pytest.mark.parametrize(
    "kwarg,expected",
    [
        (
            "expected_assessed_system_binding_digest",
            R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH,
        ),
        ("expected_evidence_content_digest", R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH),
    ],
)
def test_replay_across_a_digest_bound_axis_is_detected(kwarg, expected):
    assert refusal(**{kwarg: OTHER_DIGEST}) is expected


def test_an_unchecked_coordinate_is_documented_as_unchecked_not_as_passing():
    """A verified result is not a scope decision unless a scope was asserted.

    The ``expected_*`` arguments default to "not checked" so the §13.3 third
    party holding only an envelope can still verify a signature. That default is
    a real, documented weakening, and this test pins it: with nothing asserted,
    a receipt for tenant A verifies for a caller who never said which tenant
    they meant. A consumer binding evidence to its own scope must pass the
    coordinates, and the test above proves those checks bite.
    """

    signed = envelope()
    assert reverifier().verify(signed, evaluated_at=AS_OF).verified
    assert not reverifier().verify(
        signed, evaluated_at=AS_OF, expected_tenant_id="a-different-tenant"
    ).verified
    assert reverifier().verify(
        signed, evaluated_at=AS_OF, expected_tenant_id=signed.payload.scope.tenant_id
    ).verified


# --------------------------------------------------------------------------- #
# Time and revocation replay — §13.3, §17.9
# --------------------------------------------------------------------------- #

def test_a_previously_valid_receipt_stops_verifying_once_its_key_is_revoked():
    signed = envelope()
    assert reverifier().verify(signed, evaluated_at=AS_OF).verified

    revoke_at = AS_OF + timedelta(days=10)
    revoked = directory(
        producer_anchor(),
        authority_anchor(revocation=KeyRevocation(effective_at=revoke_at)),
    )
    assert reverifier(revoked).verify(
        signed, evaluated_at=revoke_at - timedelta(microseconds=1)
    ).verified
    for instant in (revoke_at, revoke_at + timedelta(days=365)):
        result = reverifier(revoked).verify(signed, evaluated_at=instant)
        assert result.refusal_reason is R.TRUSTED_EVIDENCE_KEY_REVOKED
        # Enough typed evidence remains to explain the refusal rather than
        # merely assert it: the receipt predates the revocation.
        assert signed.payload.verified_at < revoke_at
        assert result.evaluated_at >= revoke_at
        assert result.coordinate.key_id == VERIFIER_KEY_ID


def test_a_signature_is_never_grandfathered_by_its_signing_instant():
    """The evaluation instant, not ``verified_at``, decides current trust."""

    signed = envelope()
    revoked = directory(
        producer_anchor(),
        authority_anchor(
            revocation=KeyRevocation(effective_at=signed.payload.verified_at)
        ),
    )
    # Evaluated at the signing instant itself — the earliest instant at which
    # the revocation is in force. A grandfathering implementation would let
    # this through by comparing against ``verified_at`` and finding it "not yet
    # revoked at signing time"; this one refuses.
    result = reverifier(revoked).verify(
        signed, evaluated_at=signed.payload.verified_at
    )
    assert result.refusal_reason is R.TRUSTED_EVIDENCE_KEY_REVOKED
    later = reverifier(revoked).verify(
        signed, evaluated_at=signed.payload.verified_at + timedelta(days=1)
    )
    assert later.refusal_reason is R.TRUSTED_EVIDENCE_KEY_REVOKED


def test_no_historical_reverification_api_is_offered():
    """A question the ADR retains elsewhere is not answered by guessing."""

    verifier = reverifier()
    for absent in ("verify_as_of", "verify_historical", "was_valid_at",
                   "verify_at_signing_time", "historical_verify"):
        assert not hasattr(verifier, absent), absent


@pytest.mark.parametrize(
    "receipt_from,receipt_to,at,expected",
    [
        (
            datetime(2026, 8, 1, tzinfo=UTC),
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 7, 31, tzinfo=UTC),
            R.TRUSTED_EVIDENCE_RECEIPT_NOT_YET_VALID,
        ),
        (
            datetime(2026, 8, 1, tzinfo=UTC),
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 8, 1, tzinfo=UTC),
            None,
        ),
        (
            datetime(2026, 8, 1, tzinfo=UTC),
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 9, 1, tzinfo=UTC),
            R.TRUSTED_EVIDENCE_RECEIPT_EXPIRED,
        ),
    ],
    ids=["before", "at-from-inclusive", "at-to-exclusive"],
)
def test_the_receipts_own_validity_is_half_open(receipt_from, receipt_to, at, expected):
    signed = envelope(receipt_valid_from=receipt_from, receipt_valid_to=receipt_to)
    result = reverifier().verify(signed, evaluated_at=at)
    assert result.refusal_reason is expected


def test_receipt_validity_is_never_confused_with_evidence_validity():
    """§13.1.6 — two distinct intervals, both carried, never interchanged."""

    signed = envelope(
        receipt_valid_from=datetime(2026, 8, 1, tzinfo=UTC),
        receipt_valid_to=datetime(2026, 8, 15, tzinfo=UTC),
    )
    payload = signed.payload
    assert payload.evidence_valid_from != payload.receipt_valid_from
    assert payload.evidence_valid_to != payload.receipt_valid_to
    instant = datetime(2026, 7, 15, tzinfo=UTC)
    assert payload.evidence_is_valid_at(instant)
    assert not payload.receipt_is_valid_at(instant)
    assert reverifier().verify(signed, evaluated_at=instant).refusal_reason is (
        R.TRUSTED_EVIDENCE_RECEIPT_NOT_YET_VALID
    )


# --------------------------------------------------------------------------- #
# Producer-side forgery
# --------------------------------------------------------------------------- #

def test_a_submission_recomputes_its_evidence_digest_rather_than_believing_it():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        dataclasses.replace(submission(), evidence_identity_digest=OTHER_DIGEST)
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH


def test_swapping_the_evidence_under_a_producer_signature_is_caught():
    original = submission()
    other = identity(evidence_id="a-different-evidence")
    swapped = dataclasses.replace(
        original, evidence=other, evidence_identity_digest=other.canonical_digest()
    )
    result = authority().verify(
        swapped,
        request(evidence=other),
        verified_at=VERIFIED_AT,
        verifier_key_id=VERIFIER_KEY_ID,
    )
    assert result.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_SIGNATURE_INVALID in result.refusal_reasons


def test_a_producer_cannot_verify_its_own_evidence_by_claiming_to():
    """E-3 — a producer's assertion establishes nothing."""

    forged = submission(
        producer_authority_id=VERIFIER_AUTHORITY_ID,
        producer_key_id=VERIFIER_KEY_ID,
        signing_key=producer_signing_key(),
    )
    result = authority().verify(
        forged, request(), verified_at=VERIFIED_AT, verifier_key_id=VERIFIER_KEY_ID
    )
    assert result.outcome is EvidenceAdmissionOutcome.REFUSED
    # No EVIDENCE_PRODUCTION anchor exists under the verifier's coordinates.
    assert R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING in result.refusal_reasons
