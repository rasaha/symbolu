"""Targeted properties that make individual security gates load-bearing.

Written *for* the gate-removal sweep. A guard that survives its own removal is not
necessarily wrong — a sibling may refuse the same input — but a guard nobody exercises
directly is a guard nobody has checked. Each property here isolates one gate so that
neutralising it fails a test naming that gate, rather than being caught incidentally by a
neighbour or not at all.

Three families:

* **drift sentinels** — the import-time separations. Neutralising one changes nothing while
  the ratified constants hold, so these tests make the constant drift and assert the guard
  fires. They are the only way an import-time assertion can be exercised at all.
* **validation helpers** — the exact-type checks inside the canonical helpers, called
  directly so the typed refusal is asserted rather than whatever a downstream call happens
  to raise.
* **defence in depth against fabrication** — the verifier re-checks contract facts that
  ``ProducerAttestationV2.__post_init__`` already pins. Through the public constructor those
  branches are unreachable; against an ``object.__new__`` fabrication they are the only
  thing standing, which is exactly when they matter.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from _producer_fixtures import (
    AS_OF,
    ISSUER_ID,
    PRODUCER_ID,
    PRODUCER_KEY_ID,
    build_attestation,
    build_directory,
    build_signer,
    build_verifier,
)

import ugence_cloud_scaling_producer_attestation as pkg
from ugence_cloud_scaling_producer_attestation import (
    Ed25519ProducerSignatureVerifier,
    ProducerAttestationCanonicalFieldError,
    ProducerAttestationConfigurationError,
    ProducerAttestationExactTypeError,
    ProducerAttestationSigningBoundaryError,
    ProducerAttestationV2,
    ProducerAttestationVerifier,
    ProducerAuthenticityOutcome,
    TrustAnchorCapability,
    mint_producer_attestation,
)

O = ProducerAuthenticityOutcome


def _fields(cls) -> tuple[str, ...]:
    return tuple(f.name for f in dataclasses.fields(cls))


def _fabricate(attestation, **overrides):
    """An attestation that skipped ``__post_init__`` entirely.

    ``object.__new__`` produces the exact type with no validation whatsoever, which is the
    only way to present the verifier with a contract fact its own constructor would have
    refused. Everything the verifier re-checks exists for exactly this input.
    """

    fabricated = object.__new__(ProducerAttestationV2)
    for name in _fields(ProducerAttestationV2):
        object.__setattr__(fabricated, name, getattr(attestation, name))
    for name, value in overrides.items():
        object.__setattr__(fabricated, name, value)
    return fabricated


# ======================================================================================= #
# 1. Drift sentinels — the import-time separations
# ======================================================================================= #


@pytest.mark.parametrize(
    "constant,value,fragment",
    [
        (
            "PRODUCER_ATTESTATION_V2_SCHEMA_VERSION",
            "cloud-scaling-producer-attestation-evidence-1",
            "frozen v1 tag",
        ),
        (
            "PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE",
            "cloud_scaling.capacity_action",
            "D-4 routing purpose",
        ),
        (
            "PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE",
            "ugence.policy_authority.policy_signing",
            "policy-signing purpose",
        ),
        ("PRODUCER_ATTESTATION_SIGNATURE_PROFILE", "some.other/profile/v1", "profile"),
        ("PRODUCER_ATTESTATION_SIGNATURE_ENCODING", "some.other/encoding/v1", "encoding"),
        ("SUBJECT_TYPE_CAPACITY_SUBJECT", "cloud_scaling.other_subject", "D-4"),
    ],
)
def test_a_drifted_identifier_fails_the_import_time_separation(
    monkeypatch, constant, value, fragment
):
    """GI-1: each import-time separation fires when the identifier it guards drifts.

    The assertions are kept in a function precisely so they can be re-run at test time,
    following Phase 5A's ``identifiers.py``. Monkeypatching the constant and calling it is
    what turns an import-time-only guard into something a test can actually exercise.
    """

    from ugence_cloud_scaling_producer_attestation import identifiers

    monkeypatch.setattr(identifiers, constant, value, raising=True)
    with pytest.raises(ImportError) as exc:
        identifiers._assert_domain_separation()
    assert fragment in str(exc.value) or fragment.lower() in str(exc.value).lower()


def test_a_drifted_admitted_purpose_set_fails_the_separation(monkeypatch):
    """GI-2: the admitted SET is checked too, not only the single purpose."""

    from ugence_cloud_scaling_producer_attestation import identifiers

    monkeypatch.setattr(
        identifiers,
        "SUPPORTED_V2_SIGNING_PURPOSES",
        frozenset({"ugence.policy_authority.policy_signing"}),
    )
    with pytest.raises(ImportError):
        identifiers._assert_domain_separation()


def test_admitting_the_v1_purpose_fails_the_separation(monkeypatch):
    """GI-3: v1's purpose can never be admitted against the v2 contract."""

    from ugence_cloud_scaling_producer_attestation import identifiers
    from ugence_cloud_scaling_authorization_contracts import PRODUCER_SIGNING_PURPOSE

    monkeypatch.setattr(
        identifiers,
        "SUPPORTED_V2_SIGNING_PURPOSES",
        frozenset({PRODUCER_SIGNING_PURPOSE}),
    )
    with pytest.raises(ImportError):
        identifiers._assert_domain_separation()


#: The two explicitly named borrowed capabilities, each with the phrase that only *that*
#: check emits.
#:
#: Matching the phrase is what keeps each branch **scored**: the catch-all below refuses
#: every wrong value, so a test that only asserted ``ImportError`` would still pass with
#: either specific branch disabled and would silently stop exercising it. Matching the
#: message means disabling a specific branch changes which refusal is reached, and the
#: parametrised case for that branch fails.
#:
#: Scored is not the same as load-bearing, and the distinction is deliberate here — see
#: :func:`test_the_catch_all_is_the_load_bearing_capability_separation`. Removing either
#: explicit branch alone does **not** open the attack, because the catch-all refuses the
#: same value. The explicit branches buy typed attribution and a diagnostic that names the
#: cross-domain reuse; the catch-all is what actually fails closed.
CAPABILITY_SEPARATIONS = [
    (
        TrustAnchorCapability.RECEIPT_ISSUANCE,
        "receipt-issuance",
        "collapse ADR E-3's producer/verifier separation",
    ),
    (
        TrustAnchorCapability.EVIDENCE_PRODUCTION,
        "evidence-production",
        "cross-domain privilege reuse the dedicated capability exists to refuse",
    ),
]


@pytest.mark.parametrize(
    "capability, label, expected_phrase",
    CAPABILITY_SEPARATIONS,
    ids=[label for _, label, _ in CAPABILITY_SEPARATIONS],
)
def test_a_borrowed_capability_fails_the_separation_with_its_own_refusal(
    monkeypatch, capability, label, expected_phrase
):
    """GI-4: neither TEV capability may verify a Cloud Scaling producer attestation.

    ``RECEIPT_ISSUANCE`` would collapse ADR E-3's producer/verifier separation.
    ``EVIDENCE_PRODUCTION`` is the cross-domain privilege reuse an independent closure
    audit demonstrated: because the repository keeps one trust-anchor store, sharing that
    capability made a key trusted to sign Trusted Evidence equally entitled to attest a
    capacity recommendation.

    Each is asserted by the phrase only its own check emits, so each branch is **scored**
    on its own rather than on the catch-all below it. That is an attribution property, not
    a claim that either branch is individually load-bearing — the catch-all would refuse
    both of these values too, which
    :func:`test_the_catch_all_is_the_load_bearing_capability_separation` asserts.
    """

    from ugence_cloud_scaling_producer_attestation import identifiers

    monkeypatch.setattr(
        identifiers, "PRODUCER_ATTESTATION_CAPABILITY", capability
    )
    with pytest.raises(ImportError) as excinfo:
        identifiers._assert_domain_separation()
    assert expected_phrase in str(excinfo.value), str(excinfo.value)


def test_any_other_capability_fails_the_separation_as_drift(monkeypatch):
    """GI-4b: the catch-all, scored on a value the two specific checks do not name.

    A capability that is neither of the two named ones and is not the dedicated member —
    a member added to the enum later, say — must still fail closed. Nothing above this
    check refuses it, so this case scores the final assertion and only it, and it is the
    case that would fail if the catch-all were removed.
    """

    from ugence_cloud_scaling_producer_attestation import identifiers

    class _UnratifiedCapability:
        """Not a TrustAnchorCapability member at all. Drift, in its most literal form."""

        name = "SOME_FUTURE_CAPABILITY"

    monkeypatch.setattr(
        identifiers, "PRODUCER_ATTESTATION_CAPABILITY", _UnratifiedCapability()
    )
    with pytest.raises(ImportError) as excinfo:
        identifiers._assert_domain_separation()
    assert "drifted from the one dedicated Cloud Scaling capability" in str(excinfo.value)


def test_the_catch_all_is_the_load_bearing_capability_separation():
    """GI-4c: which of the three separations actually fails closed, stated as a property.

    The mutation sweep kills all three, and it is easy to read three kills as three
    independently load-bearing gates. They are not, and over-claiming here would misdescribe
    the design. The order in ``_assert_domain_separation`` is: ``RECEIPT_ISSUANCE``, then
    ``EVIDENCE_PRODUCTION``, then ``is not _DEDICATED``. The third one's condition is
    satisfied by **every** value the first two catch, because neither borrowed capability is
    the dedicated one — so it alone is what closes the hole, and the two explicit branches
    exist for the message they emit.

    Asserted against the live enum rather than restated in a comment, so a future edit that
    made a borrowed capability the dedicated one — or that reordered the checks so an
    explicit branch became the only refusal for some value — would break this and force the
    wording in ``GUARD_SWEEP.md`` to be revisited.
    """

    from ugence_cloud_scaling_producer_attestation import identifiers

    dedicated = TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION
    assert identifiers.PRODUCER_ATTESTATION_CAPABILITY is dedicated

    # The claim, in one line: the catch-all's condition already refuses both values the
    # explicit branches name. Removing either explicit branch therefore changes only the
    # message, not the verdict.
    for borrowed, _label, _phrase in CAPABILITY_SEPARATIONS:
        assert borrowed is not dedicated

    # And the converse: the catch-all refuses values nothing above it names, which is why
    # removing *it* would open the attack rather than merely blur a diagnostic.
    #
    # TEV declares exactly three capabilities today, and the two explicit branches name both
    # non-dedicated members, so the value the catch-all uniquely refuses right now is one
    # that is not a member at all — the drift GI-4b scores. Pinning the roster means adding
    # a fourth member forces this property, and the wording it backs, to be revisited.
    named = {borrowed for borrowed, _label, _phrase in CAPABILITY_SEPARATIONS}
    assert set(TrustAnchorCapability) == named | {dedicated}, (
        "TEV's capability roster changed; a member outside the dedicated one and the two "
        "named borrowed ones is refused by the catch-all alone, so GUARD_SWEEP.md's "
        "scored-vs-load-bearing note must be re-checked against the new member"
    )

    class _UnratifiedCapability:
        name = "SOME_FUTURE_CAPABILITY"

    drifted = _UnratifiedCapability()
    for borrowed, _label, _phrase in CAPABILITY_SEPARATIONS:
        assert drifted is not borrowed
    assert drifted is not dedicated


def test_the_reference_signer_refuses_to_publish_a_receipt_issuance_anchor(monkeypatch):
    """GI-5: and the signer refuses to publish itself under it, at the one place a key's
    public half is derived from its private half."""

    from ugence_cloud_scaling_producer_attestation import signing

    monkeypatch.setattr(
        signing,
        "PRODUCER_ATTESTATION_CAPABILITY",
        TrustAnchorCapability.RECEIPT_ISSUANCE,
    )
    with pytest.raises(ProducerAttestationSigningBoundaryError):
        build_signer().trust_anchor(
            trust_anchor_set_id="s", trust_anchor_set_version="1"
        )


# ======================================================================================= #
# 2. Validation helpers — typed refusals, asserted directly
# ======================================================================================= #


@pytest.mark.parametrize("value", [42, None, b"bytes", 3.5, ["a"]])
def test_require_nfc_text_refuses_a_non_string_with_a_typed_error(value):
    """GI-6: a typed refusal, not whatever ``unicodedata.normalize`` happens to raise."""

    from ugence_cloud_scaling_producer_attestation.canonical import require_nfc_text

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        require_nfc_text("field", value)


def test_require_nfc_text_refuses_a_str_subclass():
    """GI-7: exactly ``str``. A subclass may override comparison."""

    from ugence_cloud_scaling_producer_attestation.canonical import require_nfc_text

    class Sneaky(str):
        def __eq__(self, other):  # pragma: no cover - the point is it is never consulted
            return True

        def __hash__(self):
            return 0

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        require_nfc_text("field", Sneaky("value"))


@pytest.mark.parametrize("whitespace", ["\t", "\n", "\r", "\x0b"])
def test_require_canonical_identifier_refuses_control_whitespace(whitespace):
    """GI-8: control whitespace inside an identifier, distinct from surrounding spaces."""

    from ugence_cloud_scaling_producer_attestation.canonical import (
        require_canonical_identifier,
    )

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        require_canonical_identifier("field", f"pro{whitespace}ducer")


@pytest.mark.parametrize("value", [42, None, "2026-01-01", 1735689600.0])
def test_require_aware_utc_refuses_a_non_datetime_with_a_typed_error(value):
    """GI-9: a typed refusal, not an ``AttributeError`` on ``.tzinfo``."""

    from ugence_cloud_scaling_producer_attestation.canonical import require_aware_utc

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        require_aware_utc("field", value)


def test_require_exact_type_refuses_a_subclass_and_admits_the_exact_type():
    """GI-10: the exact-type helper itself, both directions."""

    from ugence_cloud_scaling_producer_attestation.canonical import require_exact_type

    class SubDatetime(datetime):
        pass

    exact = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert require_exact_type("f", exact, datetime) is exact
    with pytest.raises(ProducerAttestationExactTypeError):
        require_exact_type("f", SubDatetime(2026, 1, 1, tzinfo=timezone.utc), datetime)


# ======================================================================================= #
# 3. The signer's coordinate checks
# ======================================================================================= #


@pytest.mark.parametrize(
    "attribute,value",
    [("issuer", "attacker.rogue-authority"), ("producer_id", "attacker.impersonator")],
)
def test_a_signer_refuses_an_input_addressed_to_other_coordinates(attribute, value):
    """GI-11: each advertised coordinate is checked separately, not just the key id.

    A signer that answered for an issuer or producer it does not speak for would let a
    verifier resolve the LABELLED anchor and check a signature made under a different
    identity.
    """

    inner = build_signer()

    class MisaddressingSigner:
        is_reference_signer = True
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = pkg.PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def sign_producer_attestation(self, signing_input):
            object.__setattr__(signing_input, attribute, value)
            return inner.sign_producer_attestation(signing_input)

    with pytest.raises(ProducerAttestationSigningBoundaryError):
        mint_producer_attestation(
            signer=MisaddressingSigner(),
            tenant_id="tenant-1",
            subject_id="checkout-api",
            recommendation_id="rec-phase5a-1",
            recommendation_digest="sha256:" + "a" * 64,
            issued_at=datetime(2026, 1, 1, 0, 3, 10, tzinfo=timezone.utc),
        )


def test_a_signer_advertising_another_profile_is_refused():
    """GI-12: this package signs under exactly one ratified profile."""

    class OtherProfileSigner:
        is_reference_signer = True
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = "some.other/profile/v1"

        def sign_producer_attestation(self, signing_input):  # pragma: no cover
            raise AssertionError("never reached")

    with pytest.raises(ProducerAttestationConfigurationError):
        mint_producer_attestation(
            signer=OtherProfileSigner(),
            tenant_id="tenant-1",
            subject_id="checkout-api",
            recommendation_id="rec-phase5a-1",
            recommendation_digest="sha256:" + "a" * 64,
            issued_at=datetime(2026, 1, 1, 0, 3, 10, tzinfo=timezone.utc),
        )


def test_a_signer_returning_a_non_string_signature_is_refused():
    """GI-13: the signature must come back as exactly a str."""

    class BytesSigner:
        is_reference_signer = True
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = pkg.PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def sign_producer_attestation(self, signing_input):
            return b"\xde\xad" * 32

    with pytest.raises(ProducerAttestationSigningBoundaryError):
        mint_producer_attestation(
            signer=BytesSigner(),
            tenant_id="tenant-1",
            subject_id="checkout-api",
            recommendation_id="rec-phase5a-1",
            recommendation_digest="sha256:" + "a" * 64,
            issued_at=datetime(2026, 1, 1, 0, 3, 10, tzinfo=timezone.utc),
        )


def test_minting_without_a_signer_is_refused():
    """GI-14: there is no default signer to fall back to."""

    with pytest.raises(ProducerAttestationConfigurationError):
        mint_producer_attestation(
            signer=None,
            tenant_id="tenant-1",
            subject_id="checkout-api",
            recommendation_id="rec-phase5a-1",
            recommendation_digest="sha256:" + "a" * 64,
            issued_at=datetime(2026, 1, 1, 0, 3, 10, tzinfo=timezone.utc),
        )


# ======================================================================================= #
# 4. Collaborator shape, checked at construction
# ======================================================================================= #


def test_a_resolver_without_a_resolve_method_is_refused_at_construction():
    """GI-15: a malformed collaborator fails when the verifier is built, not mid-flight."""

    class NotAResolver:
        pass

    with pytest.raises(ProducerAttestationConfigurationError) as exc:
        ProducerAttestationVerifier(
            trust_anchor_resolver=NotAResolver(),
            signature_verifier=Ed25519ProducerSignatureVerifier(),
        )
    assert "resolve" in str(exc.value)


def test_a_signature_verifier_without_its_method_is_refused_at_construction():
    """GI-16: and the same on the signature side."""

    class NotAVerifier:
        pass

    with pytest.raises(ProducerAttestationConfigurationError) as exc:
        ProducerAttestationVerifier(
            trust_anchor_resolver=build_directory(),
            signature_verifier=NotAVerifier(),
        )
    assert "verify_producer_signature" in str(exc.value)


def test_a_production_resolver_declaring_nothing_is_refused_by_the_helper():
    """GI-17: ``require_production_resolver`` refuses a bare object, not only a directory."""

    with pytest.raises(ProducerAttestationConfigurationError):
        pkg.require_production_resolver(object())


# ======================================================================================= #
# 5. Defence in depth against a fabricated attestation
# ======================================================================================= #


@pytest.mark.parametrize(
    "field,value,outcome",
    [
        (
            "schema_version",
            "cloud-scaling-producer-attestation-evidence-1",
            O.UNSUPPORTED_SCHEMA_VERSION,
        ),
        (
            "signing_purpose",
            "ugence.policy_authority.policy_signing",
            O.UNSUPPORTED_SIGNING_PURPOSE,
        ),
        ("signature_algorithm", "ed448", O.UNSUPPORTED_ALGORITHM),
        ("signature_profile", "some.other/profile/v1", O.UNSUPPORTED_PROFILE),
        ("signature_encoding", "some.other/encoding/v1", O.UNSUPPORTED_ENCODING),
        ("subject_type", "cloud_scaling.other_subject", O.WRONG_SUBJECT),
    ],
)
def test_the_verifier_re_checks_every_contract_fact_against_a_fabrication(
    candidate, verifier, field, value, outcome
):
    """GI-18: the verifier does not trust the constructor to have run.

    ``ProducerAttestationV2.__post_init__`` pins each of these, so through the public
    constructor the verifier's own checks are unreachable. Against an ``object.__new__``
    fabrication — which skips ``__post_init__`` entirely — they are the only thing standing,
    and each produces its own typed refusal rather than a generic one.
    """

    fabricated = _fabricate(build_attestation(candidate), **{field: value})
    result = verifier.verify(candidate=candidate, attestation=fabricated, as_of=AS_OF)

    assert result.verified_attestation is None
    assert result.refusal.outcome is outcome


def test_recomputing_the_payload_digest_does_not_rescue_a_doctored_attestation(
    candidate, verifier
):
    """GI-19: the attacker who remembers to recompute the digest still fails.

    A gate that only catches an attacker who *forgot* to update a derived value proves
    nothing. Here the fabrication doctors a signed field **and** recomputes
    ``signing_payload_digest`` to match, so the attestation is internally self-consistent.
    It fails anyway, at the signature: the signature covers the bytes the producer actually
    signed, and those are no longer the bytes this attestation renders.
    """

    from ugence_cloud_scaling_producer_attestation import canonical_digest

    genuine = build_attestation(candidate)
    fabricated = _fabricate(genuine, issued_at=genuine.issued_at.replace(microsecond=1))
    object.__setattr__(
        fabricated,
        "signing_payload_digest",
        canonical_digest(fabricated.signing_payload()),
    )
    assert fabricated.signing_payload_digest != genuine.signing_payload_digest

    result = verifier.verify(candidate=candidate, attestation=fabricated, as_of=AS_OF)
    assert result.verified_attestation is None
    assert result.refusal.outcome is O.SIGNATURE_INVALID


def test_a_stale_payload_digest_fails_the_recomputation_gate(candidate, verifier):
    """GI-20: and the payload-digest gate itself, isolated.

    The same fabrication *without* the recomputed digest is caught earlier, by the check
    that the recomputed payload's digest equals the one the attestation carries — before
    any key is resolved and before any signature is checked.
    """

    genuine = build_attestation(candidate)
    fabricated = _fabricate(genuine, issued_at=genuine.issued_at.replace(microsecond=1))

    result = verifier.verify(candidate=candidate, attestation=fabricated, as_of=AS_OF)
    assert result.verified_attestation is None
    assert result.refusal.outcome is O.PAYLOAD_MISMATCH


def test_a_verified_artifact_cannot_be_minted_under_another_verification_profile(
    monkeypatch, candidate, verifier
):
    """GI-21: the artifact pins the named procedure it was reached under."""

    from ugence_cloud_scaling_producer_attestation import verification

    monkeypatch.setattr(verification, "VERIFICATION_PROFILE", "some.other/profile/v9")
    result = verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    assert result.verified_attestation is None
    assert result.refusal.outcome is O.VERIFICATION_UNAVAILABLE


def test_a_verified_artifact_cannot_be_minted_under_another_profile_version(
    monkeypatch, candidate, verifier
):
    """GI-22: and its version, separately."""

    from ugence_cloud_scaling_producer_attestation import verification

    monkeypatch.setattr(verification, "VERIFICATION_PROFILE_VERSION", "99")
    result = verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    assert result.verified_attestation is None
    assert result.refusal.outcome is O.VERIFICATION_UNAVAILABLE
