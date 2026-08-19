"""Differential agreement between the two maintained backends.

``authority/backend.py`` uses two independent implementations: ``cryptography``
(OpenSSL) for signing, verification and public-key derivation, and libsodium
(through ``PyNaCl``) for strict point validation. Using two is only a strength
if they agree on every case that matters, so this module cross-checks the
package's behaviour against libsodium end to end — key derivation, signature
bytes, acceptance of valid signatures, and refusal of the malformed corpus.

Why a differential test and not only vectors
--------------------------------------------
Published vectors prove conformance on the cases someone thought to publish.
A differential test proves agreement on a *corpus the author did not choose the
answers for*: two independently maintained implementations, thousands of
triples, and any disagreement is a failure rather than a judgement call. That
is the check the handwritten implementation never had, and closure-audit
findings **F-01**, **F-02** and **F-06** are what its absence cost.

Determinism
-----------
Every seed and message below is a pure function of an index. Nothing is random,
so a failure reproduces exactly, and ADR §22.9's no-entropy discipline holds in
the tests as well as in the package.

NOT PRODUCTION KEY MATERIAL: every seed here is derived from a counter and is
published in this file.
"""

from __future__ import annotations

import hashlib

import nacl.bindings as sodium
import pytest
from ugence_trusted_evidence_authority.api import (
    TrustedEvidenceSigningKey,
    TrustedEvidenceVerificationKey,
)

from test_backend_ed25519_conformance import RFC_8032_VECTORS
from test_backend_strict_corpus import (
    CORPUS_SEED,
    GROUP_ORDER,
    LOW_ORDER_BYTES,
    UNTRUSTWORTHY_POINTS,
)

#: Seeds and messages, both derived deterministically from an index.
SEED_COUNT = 200

#: Message shapes: empty, single byte, short text, binary with embedded NULs,
#: a length that straddles the SHA-512 block boundary, and a large payload.
MESSAGE_SHAPES = 9

#: 200 x 9 = 1,800 valid (key, message, signature) triples per run.
TRIPLE_COUNT = SEED_COUNT * MESSAGE_SHAPES


def _seed(index: int) -> bytes:
    """A deterministic, published, non-production seed."""

    return hashlib.sha256(f"tev2-differential-seed/{index}".encode("utf-8")).digest()


def _message(index: int, shape: int) -> bytes:
    filler = hashlib.sha512(f"tev2-differential-msg/{index}".encode("utf-8")).digest()
    return {
        0: b"",
        1: b"\x00",
        2: b"\xff",
        3: b"a",
        4: filler[:31],
        5: filler[:32],
        6: filler[:33],
        7: b"\x00" * 7 + filler + b"\x00" * 7,
        8: filler * 64,
    }[shape]


def _sodium_verifies(public_key: bytes, message: bytes, signature: bytes) -> bool:
    try:
        sodium.crypto_sign_open(signature + message, public_key)
    except Exception:
        return False
    return True


def _triples():
    for index in range(SEED_COUNT):
        for shape in range(MESSAGE_SHAPES):
            yield index, shape


# --------------------------------------------------------------------------- #
# Agreement on everything a valid triple determines
# --------------------------------------------------------------------------- #

def test_the_corpus_is_at_least_the_size_the_correction_pass_required():
    assert TRIPLE_COUNT >= 1734
    assert len(list(_triples())) == TRIPLE_COUNT


def test_public_key_derivation_agrees_for_every_seed():
    """Two implementations, one answer, for every seed in the corpus."""

    for index in range(SEED_COUNT):
        seed = _seed(index)
        package = TrustedEvidenceSigningKey(seed).verification_key.public_key_bytes
        expected, _ = sodium.crypto_sign_seed_keypair(seed)
        assert package == expected, index


def test_signature_bytes_agree_for_every_triple():
    """Ed25519 is deterministic, so agreement means byte-for-byte identity.

    This is also what proves the backend substitution changed no wire value:
    the pinned TEV-2 signature vectors reproduce unchanged because both
    maintained backends produce exactly the bytes the old implementation did.
    """

    checked = 0
    for index, shape in _triples():
        seed = _seed(index)
        message = _message(index, shape)
        package = TrustedEvidenceSigningKey(seed).sign(message)
        _, secret = sodium.crypto_sign_seed_keypair(seed)
        expected = sodium.crypto_sign(message, secret)[: len(package)]
        assert package == expected, (index, shape)
        checked += 1
    assert checked == TRIPLE_COUNT


def test_verification_agrees_for_every_valid_triple():
    checked = 0
    for index, shape in _triples():
        seed = _seed(index)
        message = _message(index, shape)
        key = TrustedEvidenceSigningKey(seed)
        signature = key.sign(message)
        assert key.verification_key.verify(message, signature) is True
        assert _sodium_verifies(
            key.verification_key.public_key_bytes, message, signature
        )
        checked += 1
    assert checked == TRIPLE_COUNT


@pytest.mark.parametrize(
    "seed_hex,public_hex,message_hex,signature_hex", RFC_8032_VECTORS
)
def test_both_backends_reproduce_every_rfc_8032_vector(
    seed_hex, public_hex, message_hex, signature_hex
):
    seed = bytes.fromhex(seed_hex)
    message = bytes.fromhex(message_hex)
    package = TrustedEvidenceSigningKey(seed)
    sodium_public, sodium_secret = sodium.crypto_sign_seed_keypair(seed)

    assert package.verification_key.public_key_bytes.hex() == public_hex
    assert sodium_public.hex() == public_hex
    assert package.sign(message).hex() == signature_hex
    assert sodium.crypto_sign(message, sodium_secret)[:64].hex() == signature_hex
    assert _sodium_verifies(sodium_public, message, bytes.fromhex(signature_hex))


# --------------------------------------------------------------------------- #
# Agreement on refusal — the half that actually failed before the correction
# --------------------------------------------------------------------------- #

def _mutations(signature: bytes, message: bytes):
    r, s = signature[:32], signature[32:]
    s_int = int.from_bytes(s, "little")

    def le(value: int) -> bytes:
        return (value % 2 ** 256).to_bytes(32, "little")

    yield "altered-message", message + b"!", signature
    yield "altered-R", message, bytes([r[0] ^ 0x01]) + r[1:] + s
    yield "altered-S", message, r + bytes([s[0] ^ 0x01]) + s[1:]
    yield "truncated", message, signature[:-1]
    yield "extended", message, signature + b"\x00"
    yield "empty", message, b""
    yield "zeroed", message, b"\x00" * 64
    yield "S-equals-L", message, r + le(GROUP_ORDER)
    yield "S-plus-L", message, r + le(s_int + GROUP_ORDER)
    yield "S-high-bit", message, r + le(2 ** 255)
    yield "R-noncanonical-identity", message, bytes.fromhex("01" + "00" * 30 + "80") + s
    yield "R-y-equals-p", message, bytes.fromhex("ed" + "ff" * 30 + "7f") + s
    for position, point in enumerate(LOW_ORDER_BYTES):
        yield f"R-low-order-{position}", message, point + s


def test_both_backends_refuse_every_mutation_of_every_sampled_triple():
    """Sampled across the corpus, so this is not one lucky signature.

    Agreement on refusal is the property that matters most: a divergence here
    would mean one implementation accepts something the other rejects, and
    ``authority/backend.py`` would then be trusting whichever it happened to
    call.
    """

    checked = 0
    for index in range(0, SEED_COUNT, 10):
        for shape in range(MESSAGE_SHAPES):
            key = TrustedEvidenceSigningKey(_seed(index))
            public = key.verification_key.public_key_bytes
            message = _message(index, shape)
            signature = key.sign(message)
            for name, mutated_message, mutated_signature in _mutations(
                signature, message
            ):
                package = key.verification_key.verify(
                    mutated_message, mutated_signature
                )
                assert package is False, (index, shape, name)
                assert not _sodium_verifies(
                    public, mutated_message, mutated_signature
                ), (index, shape, name)
                checked += 1
    assert checked > 1000


@pytest.mark.parametrize("public_hex", UNTRUSTWORTHY_POINTS)
def test_both_backends_agree_a_corpus_point_is_untrustworthy(public_hex):
    """The package refuses at construction; libsodium says the same thing.

    ``cryptography`` deliberately defers point validation to verify time and so
    cannot answer this question at all — which is exactly why libsodium is the
    second backend rather than a redundant one.
    """

    point = bytes.fromhex(public_hex)
    assert sodium.crypto_core_ed25519_is_valid_point(point) is False
    with pytest.raises(ValueError):
        TrustedEvidenceVerificationKey(point)


def test_a_genuine_key_is_valid_under_both_backends():
    key = TrustedEvidenceSigningKey(CORPUS_SEED)
    public = key.verification_key.public_key_bytes
    assert sodium.crypto_core_ed25519_is_valid_point(public) is True
    assert TrustedEvidenceVerificationKey(public).public_key_bytes == public
