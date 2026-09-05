"""The BR-2C candidate verifier, proved on its three seams.

Happy paths sign with a **test-only** private key held in this file, so every
adversarial property below is measured against a fixture that verifies first.
The verifier itself never sees a private key: ``tests/packaging/
test_milestone_boundary.py`` proves the module imports no signing primitive.

Covered: the frame reconstruction against a hand-built byte string; RFC 8032
strict scalar decoding (``S + L`` refused); the strict anchor corpus — the
identity point, its non-canonical encoding, the order-2, order-4 and order-8
points, ``y ≥ p`` encodings — refused at key admission, including the five
that the signature backend alone would accept under a key-less forgery (D-41
Ground 1, re-measured here rather than trusted); unknown-key, revoked-key,
disabled, not-yet-valid and expired refusals in D-28's order; malformed
signatures; role separation across the three namespaces; the directory-failure
mappings; the exact deny-all default; and that no answer is ever memoized.

**Candidate only.** Passing these proves the engineering the owner authorized;
it is not, and does not stand in for, the independent external cryptographic
review D-38 requires before ``0.3.0``.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from enum import Enum

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from nacl.bindings import crypto_core_ed25519_is_valid_point

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_SIGNING_FRAME_SPECIFICATION,
    BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER,
    BENCHMARK_VERIFICATION_REFUSAL_REASONS,
    BenchmarkApprovalVerifiedResult,
    BenchmarkApprovalVerifierPort,
    BenchmarkDenyAllVerifier,
    BenchmarkEd25519Verifier,
    BenchmarkPublisherTrustDirectoryPort,
    BenchmarkPublisherVerifiedResult,
    BenchmarkRegistryContractError,
    BenchmarkRegistryRefusalReason,
    BenchmarkRevocationVerifiedResult,
    BenchmarkTrustAnchorRecord,
    BenchmarkTrustAnchorResolution,
    BenchmarkTrustAnchorStatus,
    BenchmarkTrustRole,
    BenchmarkVerificationOutcome,
    canonical_digest,
)
from ugence_benchmark_registry_authority.verifier import _signing_input

R = BenchmarkRegistryRefusalReason
OUT = BenchmarkVerificationOutcome

# --------------------------------------------------------------------------- #
# Test-only keys. Fixed seeds, so every signature here is reproducible; they
# exist to prove the verifier and are the only private keys in the package tree.
# --------------------------------------------------------------------------- #
PUBLISHER_SK = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
APPROVER_SK = Ed25519PrivateKey.from_private_bytes(b"\x02" * 32)
REVOKER_SK = Ed25519PrivateKey.from_private_bytes(b"\x03" * 32)
STRANGER_SK = Ed25519PrivateKey.from_private_bytes(b"\x04" * 32)


def _hex_pub(sk: Ed25519PrivateKey) -> str:
    return sk.public_key().public_bytes_raw().hex()


#: The Ed25519 group order, for the malleability probe.
L = 2**252 + 27742317777372353535851937790883648493

#: The strict anchor corpus: every encoding libsodium's point check refuses.
#: F-01/F-03 shapes — the findings the trusted-evidence closure audit raised
#: about admitting a key — carried over as a corpus and never as code.
SMALL_ORDER_AND_NON_CANONICAL_KEYS = {
    "identity": "01" + "00" * 31,
    "identity_non_canonical": "01" + "00" * 30 + "80",
    "order_2": "ec" + "ff" * 30 + "7f",
    "order_4_a": "00" * 31 + "80",
    "order_4_b": "00" * 32,
    "order_8_a": "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
    "order_8_b": "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
    "order_8_c": "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
    "order_8_d": "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
    "y_ge_p": "ee" + "ff" * 30 + "7f",
    "y_eq_p_minus_1_plus_p": "ed" + "ff" * 30 + "7f",
    "all_ff": "ff" * 32,
}

#: A key-less forgery: R = identity, S = 0. Under a small-order public key the
#: verification equation degenerates and a backend that skips point validation
#: accepts it for any message.
KEYLESS_FORGERY = ("01" + "00" * 31) + "00" * 32


# --------------------------------------------------------------------------- #
# Fixtures: signed envelopes, anchors and an exact-triple directory
# --------------------------------------------------------------------------- #
def _sign(sk: Ed25519PrivateKey, envelope) -> str:
    return sk.sign(_signing_input(envelope)).hex()


def signed_publisher(sk: Ed25519PrivateKey = PUBLISHER_SK, **overrides):
    unsigned = fx.publisher_envelope(**overrides)
    return fx.publisher_envelope(detached_signature=_sign(sk, unsigned), **overrides)


def signed_approval(sk: Ed25519PrivateKey = APPROVER_SK, **overrides):
    unsigned = fx.approval_envelope(**overrides)
    return fx.approval_envelope(detached_signature=_sign(sk, unsigned), **overrides)


def signed_revocation(sk: Ed25519PrivateKey = REVOKER_SK, **overrides):
    unsigned = fx.revocation_envelope(**overrides)
    return fx.revocation_envelope(detached_signature=_sign(sk, unsigned), **overrides)


def publisher_anchor(**overrides) -> BenchmarkTrustAnchorRecord:
    return fx.trust_anchor_record(
        **{"public_key_material": _hex_pub(PUBLISHER_SK), **overrides}
    )


def approver_anchor(**overrides) -> BenchmarkTrustAnchorRecord:
    return fx.approver_trust_anchor_record(
        **{"public_key_material": _hex_pub(APPROVER_SK), **overrides}
    )


def revoker_anchor(**overrides) -> BenchmarkTrustAnchorRecord:
    return fx.revoker_trust_anchor_record(
        **{"public_key_material": _hex_pub(REVOKER_SK), **overrides}
    )


class ExactTripleDirectory:
    """A test-only directory: answers by exact (role, identity, key_id) and
    records every question it was asked, so role separation can be observed
    rather than assumed. Not shipped; the package holds no directory."""

    def __init__(self, *anchors: BenchmarkTrustAnchorRecord) -> None:
        self.anchors = {(a.role, a.identity, a.key_id): a for a in anchors}
        self.asked = []

    def resolve_anchor(self, role, identity, key_id):
        self.asked.append((role, identity, key_id))
        anchor = self.anchors.get((role, identity, key_id))
        return BenchmarkTrustAnchorResolution(
            role=role,
            identity=identity,
            key_id=key_id,
            anchor=anchor,
            refusal_reason=None if anchor is not None else R.TRUST_ANCHOR_NOT_FOUND,
        )


def verifier(*anchors) -> BenchmarkEd25519Verifier:
    return BenchmarkEd25519Verifier(ExactTripleDirectory(*anchors))


def full_verifier() -> BenchmarkEd25519Verifier:
    return verifier(publisher_anchor(), approver_anchor(), revoker_anchor())


SEAMS = (
    ("publisher", "verify_publisher_submission", signed_publisher, publisher_anchor,
     BenchmarkPublisherVerifiedResult, BenchmarkTrustRole.PUBLISHER),
    ("approval", "verify_approval", signed_approval, approver_anchor,
     BenchmarkApprovalVerifiedResult, BenchmarkTrustRole.APPROVER),
    ("revocation", "verify_revocation", signed_revocation, revoker_anchor,
     BenchmarkRevocationVerifiedResult, BenchmarkTrustRole.REVOKER),
)
SEAM_IDS = [seam[0] for seam in SEAMS]


# --------------------------------------------------------------------------- #
# Happy paths: each seam verifies a genuinely signed envelope
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seam", SEAMS, ids=SEAM_IDS)
def test_happy_each_seam_verifies_a_genuine_signature_and_binds_all_nine_facts(seam):
    _, method, sign, anchor_of, result_type, role = seam
    anchor = anchor_of()
    envelope = sign()
    result = getattr(verifier(anchor), method)(envelope, fx.TRUSTED_INSTANT)
    assert type(result) is result_type
    assert result.outcome is OUT.VERIFIED
    assert result.refusal_reason is None
    assert result.verified_digest == canonical_digest(envelope)
    assert result.signer_role is role
    assert result.signer_identity == anchor.identity
    assert result.signer_key_id == anchor.key_id
    assert result.signature_profile is fx.PROFILE
    assert result.anchor_record_digest == anchor.anchor_record_digest
    assert result.evaluated_at == fx.TRUSTED_INSTANT
    # Verification, never authority: §09's five derivations stay False.
    assert result.authority_verified is False


def test_happy_both_implementations_satisfy_the_port_and_a_directory_is_required():
    assert isinstance(full_verifier(), BenchmarkApprovalVerifierPort)
    assert isinstance(BenchmarkDenyAllVerifier(), BenchmarkApprovalVerifierPort)
    assert isinstance(ExactTripleDirectory(), BenchmarkPublisherTrustDirectoryPort)
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkEd25519Verifier(object())  # type: ignore[arg-type]
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkEd25519Verifier(ExactTripleDirectory)  # the class, not an instance


# --------------------------------------------------------------------------- #
# The signing frame, reconstructed by hand
# --------------------------------------------------------------------------- #
def _element(text: str) -> bytes:
    raw = text.encode("utf-8")
    return len(raw).to_bytes(4, "big") + raw


def test_the_publisher_frame_equals_a_hand_built_byte_string():
    envelope = fx.publisher_envelope()
    coordinate = envelope.coordinate
    expected = b"".join(
        _element(part)
        for part in (
            envelope.signing_frame_domain,
            envelope.signing_frame_version,
            coordinate.benchmark_id,
            coordinate.benchmark_family,
            coordinate.benchmark_version,
            coordinate.scope.kind.value,
            coordinate.scope.tenant_id,
            coordinate.geography.declaration.value,
            coordinate.geography.value,
            coordinate.domain.declaration.value,
            coordinate.domain.value,
            envelope.benchmark_identity_digest,
            envelope.benchmark_content_digest,
            envelope.publisher_identity,
            envelope.publisher_key_id,
            envelope.signature_profile.value,
        )
    )
    assert _signing_input(envelope) == expected
    assert expected.startswith(b"\x00\x00\x00I" + b"ugence.benchmark-registry-authority/")


def test_the_approval_frame_binds_the_recomputed_nested_digest_and_utc_instants():
    envelope = fx.approval_envelope(
        validity_from=datetime(2026, 1, 1, 1, 30, tzinfo=timezone(timedelta(hours=1)))
    )
    frame = _signing_input(envelope)
    assert _element(canonical_digest(envelope.publisher_submission_envelope)) in frame
    # Rendered in UTC with microseconds, exactly as canonicalization renders it.
    assert _element("2026-01-01T00:30:00.000000Z") in frame
    assert _element("2027-01-01T00:00:00.000000Z") in frame
    assert _element("ADMITTED") in frame
    assert _element(envelope.detached_signature) not in frame


def test_the_revocation_frame_covers_the_reason_and_effective_time_and_not_the_signature():
    envelope = fx.revocation_envelope()
    frame = _signing_input(envelope)
    assert _element(fx.REVOCATION_REASON) in frame
    assert _element("2026-06-01T00:00:00.000000Z") in frame
    assert _element(envelope.admitted_digest) in frame
    assert _element(envelope.detached_signature) not in frame


def test_every_frame_element_in_the_specification_is_read_in_order():
    """The verifier reads the pinned specification; it does not restate it."""

    for name, builder in (
        ("BenchmarkPublisherSubmissionEnvelope", fx.publisher_envelope),
        ("BenchmarkApprovalEnvelope", fx.approval_envelope),
        ("BenchmarkRevocationEnvelope", fx.revocation_envelope),
    ):
        envelope = builder()
        order = BENCHMARK_SIGNING_FRAME_SPECIFICATION["frames"][name]["element_order"]
        frame = _signing_input(envelope)
        position = 0
        for element in order:
            value = envelope
            for step in element.split("."):
                value = getattr(value, step)
            value = getattr(value, "value", value)
            if isinstance(value, datetime):
                value = value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            chunk = _element(value)
            assert frame[position : position + len(chunk)] == chunk, element
            position += len(chunk)
        assert position == len(frame)


def test_length_prefixing_makes_adjacent_elements_unambiguous():
    """``"ab" + "c"`` and ``"a" + "bc"`` never concatenate to one byte string."""

    a = fx.publisher_envelope(publisher_identity="ab", publisher_key_id="c")
    b = fx.publisher_envelope(publisher_identity="a", publisher_key_id="bc")
    assert _signing_input(a) != _signing_input(b)
    signed_a = signed_publisher(publisher_identity="ab", publisher_key_id="c")
    anchor_b = publisher_anchor(identity="a", key_id="bc")
    moved = fx.publisher_envelope(
        publisher_identity="a", publisher_key_id="bc",
        detached_signature=signed_a.detached_signature,
    )
    assert verifier(anchor_b).verify_publisher_submission(
        moved, fx.TRUSTED_INSTANT
    ).refusal_reason is R.SIGNATURE_INVALID


# --------------------------------------------------------------------------- #
# Signature refusals
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seam", SEAMS, ids=SEAM_IDS)
def test_any_tampered_signed_field_refuses_signature_invalid(seam):
    _, method, sign, anchor_of, _, _ = seam
    anchor = anchor_of()
    genuine = sign()
    frame = BENCHMARK_SIGNING_FRAME_SPECIFICATION["frames"][type(genuine).__name__]
    tampered_count = 0
    for element in frame["element_order"]:
        field = element.split(".")[0]
        if field in ("signing_frame_domain", "signing_frame_version", "coordinate",
                     "signature_profile", "publisher_submission_envelope_digest",
                     "publisher_submission_envelope"):
            continue
        current = getattr(genuine, field)
        if isinstance(current, datetime):
            replacement = current + timedelta(seconds=1)
        elif isinstance(current, Enum) or dataclasses.is_dataclass(current):
            continue
        elif not isinstance(current, str):
            continue
        elif field.endswith("_digest"):
            replacement = fx.OTHER_DIGEST
        elif field in ("publisher_identity", "approval_authority_identity",
                       "revoker_identity", "publisher_key_id",
                       "approval_authority_key_id", "revoker_key_id"):
            continue  # a moved identity or key changes the triple, tested below
        else:
            replacement = current + "x"
        tampered = dataclasses.replace(genuine, **{field: replacement})
        result = getattr(verifier(anchor), method)(tampered, fx.TRUSTED_INSTANT)
        assert result.outcome is OUT.REFUSED, field
        assert result.refusal_reason is R.SIGNATURE_INVALID, field
        assert result.anchor_record_digest == anchor.anchor_record_digest, field
        assert result.verified_digest == canonical_digest(tampered), field
        tampered_count += 1
    assert tampered_count >= 2


def test_a_nested_publisher_envelope_swap_under_an_approval_refuses():
    approval = signed_approval()
    other_publisher = fx.publisher_envelope(benchmark_content_digest=fx.OTHER_DIGEST)
    swapped = dataclasses.replace(approval, publisher_submission_envelope=other_publisher)
    result = verifier(approver_anchor()).verify_approval(swapped, fx.TRUSTED_INSTANT)
    assert result.refusal_reason is R.SIGNATURE_INVALID


@pytest.mark.parametrize("seam", SEAMS, ids=SEAM_IDS)
def test_a_signature_by_the_wrong_key_refuses_signature_invalid(seam):
    _, method, sign, anchor_of, _, _ = seam
    result = getattr(verifier(anchor_of()), method)(sign(STRANGER_SK), fx.TRUSTED_INSTANT)
    assert result.refusal_reason is R.SIGNATURE_INVALID


def test_a_well_formed_but_meaningless_signature_refuses_signature_invalid():
    result = verifier(publisher_anchor()).verify_publisher_submission(
        fx.publisher_envelope(), fx.TRUSTED_INSTANT
    )
    assert result.outcome is OUT.REFUSED
    assert result.refusal_reason is R.SIGNATURE_INVALID


def test_rfc8032_strict_decoding_refuses_the_malleable_s_plus_l_form():
    """§5.1.7: ``S`` at or above the group order is refused, before any backend."""

    genuine = signed_publisher()
    raw = bytes.fromhex(genuine.detached_signature)
    scalar = int.from_bytes(raw[32:], "little")
    assert scalar < L
    malleated = raw[:32] + (scalar + L).to_bytes(32, "little")
    envelope = dataclasses.replace(genuine, detached_signature=malleated.hex())
    result = verifier(publisher_anchor()).verify_publisher_submission(
        envelope, fx.TRUSTED_INSTANT
    )
    assert result.refusal_reason is R.SIGNATURE_INVALID
    # And with S = L exactly, and S = 2^256 - 1.
    for scalar_bytes in (L.to_bytes(32, "little"), b"\xff" * 32):
        envelope = dataclasses.replace(
            genuine, detached_signature=(raw[:32] + scalar_bytes).hex()
        )
        assert verifier(publisher_anchor()).verify_publisher_submission(
            envelope, fx.TRUSTED_INSTANT
        ).refusal_reason is R.SIGNATURE_INVALID


def test_a_signature_whose_r_is_a_small_order_point_is_refused():
    genuine = signed_publisher()
    raw = bytes.fromhex(genuine.detached_signature)
    for name, point in SMALL_ORDER_AND_NON_CANONICAL_KEYS.items():
        envelope = dataclasses.replace(
            genuine, detached_signature=(bytes.fromhex(point) + raw[32:]).hex()
        )
        assert verifier(publisher_anchor()).verify_publisher_submission(
            envelope, fx.TRUSTED_INSTANT
        ).refusal_reason is R.SIGNATURE_INVALID, name


def test_a_signature_is_bound_to_its_own_seam_and_role():
    """A publisher's genuine signature over its own frame verifies nothing else."""

    publisher = signed_publisher()
    directory = ExactTripleDirectory(
        publisher_anchor(),
        approver_anchor(
            identity=fx.PUBLISHER_IDENTITY, key_id=fx.PUBLISHER_KEY_ID,
            public_key_material=_hex_pub(PUBLISHER_SK),
        ),
    )
    with pytest.raises(BenchmarkRegistryContractError):
        # The approval seam accepts exactly an approval envelope — a caller's
        # contract violation, refused before any evaluation (D-42(a)).
        BenchmarkEd25519Verifier(directory).verify_approval(publisher, fx.TRUSTED_INSTANT)


# --------------------------------------------------------------------------- #
# Anchor admission: the strict corpus (F-01 / F-03 shapes)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", sorted(SMALL_ORDER_AND_NON_CANONICAL_KEYS))
def test_every_small_order_or_non_canonical_anchor_is_refused_at_admission(name):
    material = SMALL_ORDER_AND_NON_CANONICAL_KEYS[name]
    assert crypto_core_ed25519_is_valid_point(bytes.fromhex(material)) is False
    anchor = publisher_anchor(public_key_material=material)  # the record admits an encoding
    envelope = fx.publisher_envelope(detached_signature=KEYLESS_FORGERY)
    result = verifier(anchor).verify_publisher_submission(envelope, fx.TRUSTED_INSTANT)
    assert result.outcome is OUT.REFUSED
    assert result.refusal_reason is R.INDETERMINATE
    # The refusal names the revision of the key it refused.
    assert result.anchor_record_digest == anchor.anchor_record_digest


def test_the_second_backend_is_load_bearing_against_keyless_forgery():
    """D-41 Ground 1, re-measured: the signature backend alone accepts a forgery
    under at least the identity point; the verifier refuses every one.

    Recorded as the set actually accepted on this machine's backend versions,
    so a backend that tightens later shrinks the set without failing this, and
    one that loosens widens it and is still refused by the verifier.
    """

    envelope = fx.publisher_envelope(detached_signature=KEYLESS_FORGERY)
    message = _signing_input(envelope)
    accepted_by_signature_backend_alone = set()
    for name, material in SMALL_ORDER_AND_NON_CANONICAL_KEYS.items():
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(material)).verify(
                bytes.fromhex(KEYLESS_FORGERY), message
            )
            accepted_by_signature_backend_alone.add(name)
        except (InvalidSignature, ValueError):
            pass
        result = verifier(
            publisher_anchor(public_key_material=material)
        ).verify_publisher_submission(envelope, fx.TRUSTED_INSTANT)
        assert result.outcome is OUT.REFUSED, name
    assert "identity" in accepted_by_signature_backend_alone
    assert accepted_by_signature_backend_alone <= set(SMALL_ORDER_AND_NON_CANONICAL_KEYS)


def test_a_genuine_key_passes_the_point_check_and_a_forgery_still_fails_under_it():
    assert crypto_core_ed25519_is_valid_point(PUBLISHER_SK.public_key().public_bytes_raw())
    envelope = fx.publisher_envelope(detached_signature=KEYLESS_FORGERY)
    result = verifier(publisher_anchor()).verify_publisher_submission(
        envelope, fx.TRUSTED_INSTANT
    )
    assert result.refusal_reason is R.SIGNATURE_INVALID


def test_key_material_corrupted_after_construction_cannot_be_admitted():
    anchor = publisher_anchor()
    object.__setattr__(anchor, "public_key_material", "zz" * 32)
    result = verifier(anchor).verify_publisher_submission(
        signed_publisher(), fx.TRUSTED_INSTANT
    )
    assert result.outcome is OUT.REFUSED
    assert result.refusal_reason is R.INDETERMINATE


# --------------------------------------------------------------------------- #
# Anchor resolution and D-28's lifecycle order
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seam", SEAMS, ids=SEAM_IDS)
def test_an_unknown_key_refuses_trust_anchor_not_found_with_no_revision(seam):
    _, method, sign, _, _, _ = seam
    result = getattr(verifier(), method)(sign(), fx.TRUSTED_INSTANT)
    assert result.outcome is OUT.REFUSED
    assert result.refusal_reason is R.TRUST_ANCHOR_NOT_FOUND
    assert result.anchor_record_digest is None


def test_a_key_rotation_is_a_different_triple_and_the_old_signature_does_not_carry():
    rotated = publisher_anchor(key_id="publisher-key-2", public_key_material=_hex_pub(STRANGER_SK))
    envelope = signed_publisher(publisher_key_id="publisher-key-2")
    assert verifier(rotated).verify_publisher_submission(
        envelope, fx.TRUSTED_INSTANT
    ).refusal_reason is R.SIGNATURE_INVALID
    assert verifier(publisher_anchor()).verify_publisher_submission(
        envelope, fx.TRUSTED_INSTANT
    ).refusal_reason is R.TRUST_ANCHOR_NOT_FOUND


@pytest.mark.parametrize("seam", SEAMS, ids=SEAM_IDS)
def test_a_revoked_anchor_refuses_trust_anchor_revoked_and_binds_its_revision(seam):
    _, method, sign, anchor_of, _, _ = seam
    anchor = anchor_of(
        status=BenchmarkTrustAnchorStatus.REVOKED,
        revoked_at=fx.ANCHOR_REVOKED_AT,
        revocation_reason=fx.ANCHOR_REVOCATION_REASON,
    )
    result = getattr(verifier(anchor), method)(sign(), fx.TRUSTED_INSTANT)
    assert result.refusal_reason is R.TRUST_ANCHOR_REVOKED
    assert result.anchor_record_digest == anchor.anchor_record_digest


def test_revocation_is_retroactive_the_instant_before_revoked_at_still_refuses():
    anchor = publisher_anchor(
        status=BenchmarkTrustAnchorStatus.REVOKED,
        revoked_at=fx.ANCHOR_REVOKED_AT,
        revocation_reason=None,
    )
    before = fx.ANCHOR_REVOKED_AT - timedelta(days=30)
    assert verifier(anchor).verify_publisher_submission(
        signed_publisher(), before
    ).refusal_reason is R.TRUST_ANCHOR_REVOKED


def test_a_disabled_anchor_refuses_trust_anchor_disabled():
    anchor = publisher_anchor(status=BenchmarkTrustAnchorStatus.DISABLED)
    result = verifier(anchor).verify_publisher_submission(signed_publisher(), fx.TRUSTED_INSTANT)
    assert result.refusal_reason is R.TRUST_ANCHOR_DISABLED
    assert result.anchor_record_digest == anchor.anchor_record_digest


def test_the_half_open_validity_interval_is_applied_at_both_boundaries():
    anchor = publisher_anchor()
    v = verifier(anchor)
    envelope = signed_publisher()
    assert v.verify_publisher_submission(envelope, fx.VALIDITY_FROM).outcome is OUT.VERIFIED
    one_us = timedelta(microseconds=1)
    assert v.verify_publisher_submission(
        envelope, fx.VALIDITY_FROM - one_us
    ).refusal_reason is R.TRUST_ANCHOR_NOT_YET_VALID
    assert v.verify_publisher_submission(
        envelope, fx.VALIDITY_TO - one_us
    ).outcome is OUT.VERIFIED
    expired = v.verify_publisher_submission(envelope, fx.VALIDITY_TO)
    assert expired.refusal_reason is R.TRUST_ANCHOR_EXPIRED
    assert expired.anchor_record_digest == anchor.anchor_record_digest


def test_the_evaluation_order_is_revoked_before_disabled_before_interval():
    """A revoked anchor whose interval has elapsed reports REVOKED, never EXPIRED."""

    revoked_and_expired = publisher_anchor(
        status=BenchmarkTrustAnchorStatus.REVOKED,
        revoked_at=fx.ANCHOR_REVOKED_AT,
        revocation_reason=None,
    )
    after = fx.VALIDITY_TO + timedelta(days=1)
    assert verifier(revoked_and_expired).verify_publisher_submission(
        signed_publisher(), after
    ).refusal_reason is R.TRUST_ANCHOR_REVOKED
    disabled_and_not_yet = publisher_anchor(status=BenchmarkTrustAnchorStatus.DISABLED)
    assert verifier(disabled_and_not_yet).verify_publisher_submission(
        signed_publisher(), fx.VALIDITY_FROM - timedelta(days=1)
    ).refusal_reason is R.TRUST_ANCHOR_DISABLED
    assert BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER == (
        R.TRUST_ANCHOR_REVOKED, R.TRUST_ANCHOR_DISABLED,
        R.TRUST_ANCHOR_NOT_YET_VALID, R.TRUST_ANCHOR_EXPIRED,
    )


def test_lifecycle_is_evaluated_before_the_key_and_the_signature():
    """A revoked anchor with an invalid key refuses REVOKED — the stronger fact."""

    anchor = publisher_anchor(
        status=BenchmarkTrustAnchorStatus.REVOKED,
        revoked_at=fx.ANCHOR_REVOKED_AT,
        revocation_reason=None,
        public_key_material=SMALL_ORDER_AND_NON_CANONICAL_KEYS["identity"],
    )
    result = verifier(anchor).verify_publisher_submission(
        fx.publisher_envelope(detached_signature=KEYLESS_FORGERY), fx.TRUSTED_INSTANT
    )
    assert result.refusal_reason is R.TRUST_ANCHOR_REVOKED


# --------------------------------------------------------------------------- #
# Role separation across the three namespaces (D-26)
# --------------------------------------------------------------------------- #
def test_each_seam_asks_its_own_role_namespace_and_never_another():
    directory = ExactTripleDirectory(publisher_anchor(), approver_anchor(), revoker_anchor())
    v = BenchmarkEd25519Verifier(directory)
    v.verify_publisher_submission(signed_publisher(), fx.TRUSTED_INSTANT)
    v.verify_approval(signed_approval(), fx.TRUSTED_INSTANT)
    v.verify_revocation(signed_revocation(), fx.TRUSTED_INSTANT)
    assert directory.asked == [
        (BenchmarkTrustRole.PUBLISHER, fx.PUBLISHER_IDENTITY, fx.PUBLISHER_KEY_ID),
        (BenchmarkTrustRole.APPROVER, fx.APPROVAL_AUTHORITY_IDENTITY, fx.APPROVAL_AUTHORITY_KEY_ID),
        (BenchmarkTrustRole.REVOKER, fx.REVOKER_IDENTITY, fx.REVOKER_KEY_ID),
    ]


def test_an_anchor_authorized_for_one_role_never_authorizes_another():
    """The publisher's key, installed only in the publisher namespace, does not
    verify an approval that declares the same identity and key."""

    directory = ExactTripleDirectory(publisher_anchor())
    approval = signed_approval(
        PUBLISHER_SK,
        approval_authority_identity="publisher-alpha-as-approver",
        approval_authority_key_id=fx.PUBLISHER_KEY_ID,
    )
    result = BenchmarkEd25519Verifier(directory).verify_approval(approval, fx.TRUSTED_INSTANT)
    assert result.refusal_reason is R.TRUST_ANCHOR_NOT_FOUND
    assert directory.asked[-1][0] is BenchmarkTrustRole.APPROVER


# --------------------------------------------------------------------------- #
# The directory fails: D-28, never a fallback
# --------------------------------------------------------------------------- #
class _Unavailable:
    def resolve_anchor(self, role, identity, key_id):
        return BenchmarkTrustAnchorResolution(
            role=role, identity=identity, key_id=key_id,
            anchor=None, refusal_reason=R.TRUST_DIRECTORY_UNAVAILABLE,
        )


class _Raises:
    def resolve_anchor(self, role, identity, key_id):
        raise RuntimeError("directory offline")


class _WrongType:
    def resolve_anchor(self, role, identity, key_id):
        return publisher_anchor()  # a bare record, not a resolution


class _AnswersADifferentQuestion:
    def resolve_anchor(self, role, identity, key_id):
        other = publisher_anchor(key_id="publisher-key-2")
        return BenchmarkTrustAnchorResolution(
            role=other.role, identity=other.identity, key_id=other.key_id,
            anchor=other, refusal_reason=None,
        )


class _ReturnsNone:
    def resolve_anchor(self, role, identity, key_id):
        return None


class _LookalikeResolution:
    def resolve_anchor(self, role, identity, key_id):
        class Fake(BenchmarkTrustAnchorResolution):
            pass

        return Fake.__new__(Fake)


@pytest.mark.parametrize(
    "directory,expected",
    [
        (_Unavailable(), R.TRUST_DIRECTORY_UNAVAILABLE),
        (_Raises(), R.INDETERMINATE),
        (_WrongType(), R.INDETERMINATE),
        (_AnswersADifferentQuestion(), R.INDETERMINATE),
        (_ReturnsNone(), R.INDETERMINATE),
        (_LookalikeResolution(), R.INDETERMINATE),
    ],
    ids=["unavailable", "raises", "wrong-type", "different-triple", "none", "subclass"],
)
def test_a_failing_directory_refuses_and_never_falls_back(directory, expected):
    result = BenchmarkEd25519Verifier(directory).verify_publisher_submission(
        signed_publisher(), fx.TRUSTED_INSTANT
    )
    assert result.outcome is OUT.REFUSED
    assert result.refusal_reason is expected
    assert result.anchor_record_digest is None


def test_a_reason_the_result_may_not_carry_is_never_leaked_through_the_seam():
    """D-42(d): an unclassified condition is INDETERMINATE, never a bare raise."""

    class _LeaksAContractError:
        def resolve_anchor(self, role, identity, key_id):
            error = BenchmarkRegistryContractError("store broke")
            error.reason = R.STORE_INTEGRITY_INVALID  # not among D-35's twelve
            raise error

    result = BenchmarkEd25519Verifier(_LeaksAContractError()).verify_publisher_submission(
        signed_publisher(), fx.TRUSTED_INSTANT
    )
    assert result.refusal_reason is R.INDETERMINATE
    assert result.refusal_reason in BENCHMARK_VERIFICATION_REFUSAL_REASONS


# --------------------------------------------------------------------------- #
# The seam's contract-side preconditions raise (D-42(a))
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seam", SEAMS, ids=SEAM_IDS)
def test_a_naive_trusted_instant_is_a_contract_violation_not_a_refusal(seam):
    _, method, sign, anchor_of, _, _ = seam
    for candidate in (verifier(anchor_of()), BenchmarkDenyAllVerifier()):
        with pytest.raises(BenchmarkRegistryContractError):
            getattr(candidate, method)(sign(), datetime(2026, 4, 1))
        with pytest.raises(BenchmarkRegistryContractError):
            getattr(candidate, method)(sign(), "2026-04-01T00:00:00Z")  # type: ignore[arg-type]


def test_an_envelope_of_the_wrong_exact_type_is_refused_before_evaluation():
    directory = ExactTripleDirectory(publisher_anchor())
    v = BenchmarkEd25519Verifier(directory)
    with pytest.raises(BenchmarkRegistryContractError):
        v.verify_publisher_submission(signed_approval(), fx.TRUSTED_INSTANT)  # type: ignore[arg-type]
    with pytest.raises(BenchmarkRegistryContractError):
        v.verify_revocation(signed_publisher(), fx.TRUSTED_INSTANT)  # type: ignore[arg-type]

    class Lookalike:
        def __getattr__(self, name):
            return getattr(signed_publisher(), name)

    with pytest.raises(BenchmarkRegistryContractError):
        v.verify_publisher_submission(Lookalike(), fx.TRUSTED_INSTANT)  # type: ignore[arg-type]
    assert directory.asked == []


def test_an_envelope_corrupted_after_construction_is_never_bound():
    envelope = signed_publisher()
    object.__setattr__(envelope, "benchmark_identity_digest", "not a digest")
    with pytest.raises(BenchmarkRegistryContractError):
        verifier(publisher_anchor()).verify_publisher_submission(envelope, fx.TRUSTED_INSTANT)


# --------------------------------------------------------------------------- #
# The exact deny-all default
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seam", SEAMS, ids=SEAM_IDS)
def test_the_deny_all_default_refuses_a_genuine_signature_on_every_seam(seam):
    _, method, sign, _, result_type, role = seam
    envelope = sign()
    result = getattr(BenchmarkDenyAllVerifier(), method)(envelope, fx.TRUSTED_INSTANT)
    assert type(result) is result_type
    assert result.outcome is OUT.REFUSED
    assert result.refusal_reason is R.NO_TRUST_ANCHOR_CONFIGURED
    assert result.anchor_record_digest is None
    assert result.verified_digest == canonical_digest(envelope)
    assert result.signer_role is role
    assert result.evaluated_at == fx.TRUSTED_INSTANT


def test_the_deny_all_default_holds_no_directory_and_has_nothing_to_flip():
    deny = BenchmarkDenyAllVerifier()
    assert not hasattr(deny, "__dict__")
    assert deny.__slots__ == ()
    with pytest.raises(AttributeError):
        deny.allow = True  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        BenchmarkDenyAllVerifier(ExactTripleDirectory())  # type: ignore[call-arg]


# --------------------------------------------------------------------------- #
# Nothing is memoized (D-21)
# --------------------------------------------------------------------------- #
def test_the_same_envelope_is_re_evaluated_against_the_directory_every_time():
    directory = ExactTripleDirectory(publisher_anchor())
    v = BenchmarkEd25519Verifier(directory)
    envelope = signed_publisher()
    first = v.verify_publisher_submission(envelope, fx.TRUSTED_INSTANT)
    second = v.verify_publisher_submission(envelope, fx.TRUSTED_INSTANT)
    assert first == second and first is not second
    assert len(directory.asked) == 2
    directory.anchors.clear()
    third = v.verify_publisher_submission(envelope, fx.TRUSTED_INSTANT)
    assert third.refusal_reason is R.TRUST_ANCHOR_NOT_FOUND


def test_two_verifications_at_two_instants_are_two_distinct_evidence_bound_results():
    v = verifier(publisher_anchor())
    envelope = signed_publisher()
    a = v.verify_publisher_submission(envelope, fx.TRUSTED_INSTANT)
    b = v.verify_publisher_submission(envelope, fx.TRUSTED_INSTANT + timedelta(days=1))
    assert a.outcome is b.outcome is OUT.VERIFIED
    assert a != b and canonical_digest(a) != canonical_digest(b)


def test_every_refusal_the_verifier_produces_is_within_d35s_twelve():
    produced = set()
    cases = [
        (verifier(), signed_publisher()),
        (verifier(publisher_anchor()), fx.publisher_envelope()),
        (verifier(publisher_anchor(status=BenchmarkTrustAnchorStatus.DISABLED)), signed_publisher()),
        (BenchmarkEd25519Verifier(_Unavailable()), signed_publisher()),
        (BenchmarkEd25519Verifier(_Raises()), signed_publisher()),
        (BenchmarkDenyAllVerifier(), signed_publisher()),
        (verifier(publisher_anchor(public_key_material="01" + "00" * 31)), signed_publisher()),
    ]
    for candidate, envelope in cases:
        result = candidate.verify_publisher_submission(envelope, fx.TRUSTED_INSTANT)
        assert result.outcome is OUT.REFUSED
        produced.add(result.refusal_reason)
    assert produced <= set(BENCHMARK_VERIFICATION_REFUSAL_REASONS)
    assert len(produced) >= 6
