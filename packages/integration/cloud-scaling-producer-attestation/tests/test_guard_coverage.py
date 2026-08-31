"""Guard-coverage properties for the shared-engine sweep of this package.

Two kinds of test live here, and the distinction is the whole point of the file.

**Evidence tests** measure the claim behind each declared exclusion in this package's
entry in ``scripts/cloud_scaling/guard_sweep.py``. The shared engine's closed exclusion
vocabulary requires every excluded guard to name a test that measures the exclusion's
claim, so an exclusion is a checkable statement rather than an assertion of confidence.
Each of these passes with the excluded guard *removed* as well as present — that is what
``diagnostic-only`` and ``unreachable-behind-earlier-guard`` mean, and a test here that
started killing its own exclusion would be reported as a stale exclusion by the sweep.

**Isolating tests** close former survivors of the in-package fork's sweep for which a
constructible isolating input exists. Under the adoption ruling those sites are scored,
not excluded: each test below fails when exactly its guard is neutralised, and asserts the
*typed* half of the refusal — an exception class or an outcome member, never a message
substring alone — so no kill here is attributable to prose.
"""

from __future__ import annotations

import dataclasses

import pytest

from ugence_cloud_scaling_producer_attestation import (
    ProducerAttestationCanonicalFieldError,
    ProducerAttestationConfigurationError,
    ProducerAttestationExactTypeError,
    ProducerAttestationSigningBoundaryError,
    ProducerAttestationV2,
    ProducerAttestationVerifier,
    ProducerAuthenticityOutcome,
    ProducerAuthenticityResult,
    VerifiedArtifactIntegrityError,
    VerifiedProducerAttestation,
    anchor_coordinate_digest,
    anchor_record_digest,
)
from ugence_cloud_scaling_producer_attestation.identifiers import (
    _assert_domain_separation,
)
from ugence_cloud_scaling_producer_attestation.signing import (
    ProducerAttestationSigningInput,
)
from ugence_cloud_scaling_producer_attestation.trust import (
    TrustAnchorResolution,
    anchor_verification_key,
    producer_anchor_coordinate,
    require_production_resolver,
)

from _producer_fixtures import (
    AS_OF,
    ISSUER_ID,
    PRODUCER_KEY_ID,
    build_signer,
)

O = ProducerAuthenticityOutcome


def _fabricate(attestation, **overrides):
    """An attestation that skipped ``__post_init__`` entirely — the fabrication route."""

    fabricated = object.__new__(ProducerAttestationV2)
    for field in dataclasses.fields(ProducerAttestationV2):
        object.__setattr__(fabricated, field.name, getattr(attestation, field.name))
    for name, value in overrides.items():
        object.__setattr__(fabricated, name, value)
    return fabricated


# ======================================================================================= #
# Evidence for the declared exclusions
# ======================================================================================= #


def test_the_import_time_separations_hold_for_the_installed_distributions():
    """Evidence for excluding the module-level ``_assert_domain_separation()`` call.

    The exclusion's reason is ``unscorable-by-single-checkout-fixture``: several of the
    separations compare against values imported from separately versioned distributions,
    and this fixture installs exactly one resolution — one in which every separation
    holds, which is what this asserts. The guards *inside* the function are scored by
    re-running it with drifted values (GI-1); the call site's own effect is visible only
    under a resolution this suite cannot install.
    """

    _assert_domain_separation()


def test_a_non_str_signature_is_refused_by_decode_with_the_same_typed_pair(
    candidate, attestation
):
    """Evidence for excluding ``type(self.signature) is not str`` as diagnostic-only.

    The named successor is the ``decode_signature`` call below it: for every non-str
    value both raise ``ProducerAttestationCanonicalFieldError`` with the
    ``MALFORMED_SIGNATURE`` outcome, so the guard changes which line refuses and nothing
    a caller may branch on. Asserted on the typed pair only — deliberately not on the
    message, which is the one thing the two lines do not share.
    """

    with pytest.raises(ProducerAttestationCanonicalFieldError) as excinfo:
        dataclasses.replace(attestation, signature=42)
    assert excinfo.value.outcome is O.MALFORMED_SIGNATURE


def test_the_token_guard_precedes_every_signing_input_content_check():
    """Evidence for the five ``unreachable-behind-earlier-guard`` signing-input checks.

    A caller-assembled signing input with *every* content field malformed at once is
    refused by the issuance-token guard alone: the boundary error names the token, so no
    content check ever saw its malformed value. The one supported route,
    ``mint_producer_attestation``, passes values it validated itself.
    """

    with pytest.raises(ProducerAttestationSigningBoundaryError) as excinfo:
        ProducerAttestationSigningInput(
            signed_input="not-bytes",
            producer_id=" not canonical ",
            issuer="",
            producer_key_id="\ttab",
            signature_profile="some.other/profile/v1",
        )
    assert "cannot be constructed directly" in str(excinfo.value)


def test_a_none_resolver_is_refused_by_the_authority_check_with_the_same_error():
    """Evidence for excluding ``resolver is None`` in trust.py as diagnostic-only.

    ``None`` cannot reach the named successor — the ``is_production_authoritative``
    check — with anything but the same ``ProducerAttestationConfigurationError``, so the
    guard's removal changes the message and nothing typed. Asserted on the class alone.
    """

    with pytest.raises(ProducerAttestationConfigurationError):
        require_production_resolver(None)


def test_no_caller_construction_reaches_the_checks_behind_the_verification_token():
    """Evidence for the two ``unreachable-behind-earlier-guard`` verified.py exclusions.

    A caller constructing a ``VerifiedProducerAttestation`` with non-canonical digests
    and a self-inconsistent artifact digest is refused by the construction-token guard
    alone — the integrity error names the token, so neither the canonical-digest calls
    nor the artifact-digest comparison behind it ever ran.
    """

    junk = {
        field.name: "not-canonical"
        for field in dataclasses.fields(VerifiedProducerAttestation)
        if field.name != "construction_token"
    }
    with pytest.raises(VerifiedArtifactIntegrityError) as excinfo:
        VerifiedProducerAttestation(**junk)
    assert "constructed directly" in str(excinfo.value)


def test_a_none_collaborator_is_refused_with_the_same_configuration_error(directory):
    """Evidence for excluding the verifier's two ``is None`` guards as diagnostic-only.

    A ``None`` resolver or verifier always fails the ``hasattr`` successor with the same
    ``ProducerAttestationConfigurationError``; the ``is None`` guards buy a better
    message. Asserted on the class alone, so this passes with either line removed —
    which is exactly the exclusion's claim.
    """

    from ugence_cloud_scaling_producer_attestation import Ed25519ProducerSignatureVerifier

    with pytest.raises(ProducerAttestationConfigurationError):
        ProducerAttestationVerifier(
            trust_anchor_resolver=None,
            signature_verifier=Ed25519ProducerSignatureVerifier(),
        )
    with pytest.raises(ProducerAttestationConfigurationError):
        ProducerAttestationVerifier(
            trust_anchor_resolver=directory,
            signature_verifier=None,
        )


def test_a_resolution_cannot_carry_a_non_anchor_record():
    """Evidence for excluding the verifier's anchor-record revalidation.

    ``TrustAnchorResolution`` refuses at construction to carry anything but a
    ``TrustAnchorRecord``, so between it and the resolution exact-type check — scored
    and killed — no supported resolver return reaches the anchor revalidation with a
    wrong-typed anchor.
    """

    coordinate = producer_anchor_coordinate(
        issuer=ISSUER_ID, producer_key_id=PRODUCER_KEY_ID
    )
    with pytest.raises(Exception):
        TrustAnchorResolution(coordinate=coordinate, anchor=42)


# ======================================================================================= #
# Isolating tests — former fork survivors with a constructible isolating input
# ======================================================================================= #


def test_a_non_canonical_payload_digest_is_refused_as_malformed_not_mismatched(
    attestation,
):
    """The canonical-format check owns non-canonical digests; the equality check owns
    canonical-but-wrong ones. A non-canonical spelling must be refused as
    ``ATTESTATION_MALFORMED`` — the format diagnosis — not as ``PAYLOAD_MISMATCH``,
    which would misreport a spelling defect as a self-inconsistency."""

    with pytest.raises(ProducerAttestationCanonicalFieldError) as excinfo:
        dataclasses.replace(
            attestation, signing_payload_digest="sha256:" + "G" * 64
        )
    assert excinfo.value.outcome is O.ATTESTATION_MALFORMED


def test_a_canonical_timestamp_string_round_trips_through_from_dict(attestation):
    """``from_dict`` must parse the canonical ``...Z`` timestamp spelling.

    The wire form of ``issued_at`` is a string; skipping the parse would hand the
    constructor a str and refuse every serialized attestation.
    """

    data = {
        field.name: getattr(attestation, field.name)
        for field in dataclasses.fields(ProducerAttestationV2)
        if field.name in ProducerAttestationV2._ALLOWED_KEYS
    }
    data["issued_at"] = attestation.issued_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    rebuilt = ProducerAttestationV2.from_dict(data)
    assert rebuilt == attestation


@pytest.mark.parametrize(
    "overrides",
    [
        {"producer_id": " padded "},
        {"issuer": ""},
        {"producer_key_id": "tab\tinside"},
    ],
    ids=["producer_id", "issuer", "producer_key_id"],
)
def test_the_reference_signer_refuses_non_canonical_coordinates(overrides):
    """Each of the signer constructor's three canonical-identifier admissions is applied
    at the constructor, not merely available: a non-canonical coordinate never becomes a
    configured signer."""

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        build_signer(**overrides)


def test_the_reference_signer_refuses_a_non_key_signing_key():
    """The exact-type admission on the signing key is applied at the constructor."""

    from ugence_cloud_scaling_producer_attestation import (
        ReferenceEd25519ProducerAttestationSigner,
    )

    with pytest.raises(ProducerAttestationExactTypeError):
        ReferenceEd25519ProducerAttestationSigner(
            producer_id="producer",
            issuer=ISSUER_ID,
            producer_key_id=PRODUCER_KEY_ID,
            signing_key=42,
        )


def test_the_signer_refuses_a_non_signing_input_with_the_exact_type_error():
    """``sign_producer_attestation`` refuses a non-``ProducerAttestationSigningInput``
    with the typed exact-type error — not with whatever attribute error a duck-typed
    value happens to produce further in."""

    with pytest.raises(ProducerAttestationExactTypeError):
        build_signer().sign_producer_attestation(42)


def test_anchor_coordinate_digest_refuses_a_non_coordinate():
    with pytest.raises(ProducerAttestationExactTypeError):
        anchor_coordinate_digest(42)


def test_anchor_record_digest_refuses_a_non_record():
    with pytest.raises(ProducerAttestationExactTypeError):
        anchor_record_digest(42)


def test_anchor_verification_key_refuses_a_non_record():
    with pytest.raises(ProducerAttestationExactTypeError):
        anchor_verification_key(42)


def test_a_result_cannot_carry_a_wrong_typed_verified_attestation():
    """The result's exact-type check on the verified branch is its own decision point:
    a wrong-typed artifact earns the typed ``TypeError``, and the consumption-boundary
    revalidation behind it answers a different question (see the class docstring)."""

    class _LookAlike:
        pass

    with pytest.raises(TypeError):
        ProducerAuthenticityResult(verified_attestation=_LookAlike())


def test_a_result_cannot_carry_a_wrong_typed_refusal():
    """The refusal branch's exact-type check is load-bearing on its own: nothing behind
    it re-checks the refusal, so removing it admits a result carrying an arbitrary
    object where a typed refusal is owed."""

    class _NotARefusal:
        outcome = "VERIFIED"

    with pytest.raises(TypeError):
        ProducerAuthenticityResult(refusal=_NotARefusal())


def test_a_non_decodable_signature_is_refused_as_malformed_signature(
    candidate, verifier, attestation
):
    """Gate 9's refusal names its own outcome. A fabricated attestation carrying a
    non-decodable signature passes every reconciliation and anchor gate — the signature
    is not part of the signed payload — and must be refused as ``MALFORMED_SIGNATURE``,
    the diagnosis that tells an operator the spelling is wrong, not as the general
    ``VERIFICATION_UNAVAILABLE``."""

    fabricated = _fabricate(attestation, signature="z" * 128)
    result = verifier.verify(candidate=candidate, attestation=fabricated, as_of=AS_OF)
    assert result.verified_attestation is None
    assert result.refusal is not None
    assert result.refusal.outcome is O.MALFORMED_SIGNATURE
