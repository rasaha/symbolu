"""The strict Ed25519 corpus, pinned permanently after the closure audit.

The independent TEV-2 closure audit found three related weaknesses in the
handwritten implementation this package used to carry:

* **F-01** — non-canonical and small-order encodings were not rejected where
  the standard requires it (RFC 8032 §5.1.3: "if x = 0 and x_0 = 1, decoding
  fails");
* **F-03** — correctly-sized but cryptographically worthless public keys could
  be registered as trust anchors, and an identity-point anchor admits a
  *universal forgery*: with A = identity the verification equation
  ``[S]B = R + [k]A`` holds for ``R = [S]B`` and any ``S`` an attacker likes;
* **F-06** — the malformed corpus was never exercised as a permanent test, so
  nothing would have noticed a regression.

The correction was architectural: the handwritten implementation is gone, and
``authority/backend.py`` calls ``cryptography`` for signing and verification and
libsodium (through ``PyNaCl``) for the strict point validation that
``cryptography`` deliberately does not perform at key-construction time. This
module is the standing proof that the corpus stays refused, so the corpus is a
regression test rather than a one-off audit artifact.

Two refusal surfaces, deliberately different
--------------------------------------------
* An **untrustworthy public key** is refused at *construction* — it raises, and
  so can never be held, registered as a trust anchor, or verified against. That
  is the F-03 fix, and a returned ``False`` would not have been strong enough:
  the point must not enter the system at all.
* A **malformed signature** against a genuine key returns ``False``. Verifying
  a signature is a question with a fail-closed boolean answer, and every
  malformation in the corpus below produces exactly that, never an exception a
  caller might catch and mistake for a different condition.
"""

from __future__ import annotations

import pytest
from ugence_trusted_evidence_authority.api import (
    ED25519_PUBLIC_KEY_SIZE,
    ED25519_SIGNATURE_SIZE,
    TrustedEvidenceSigningKey,
    TrustedEvidenceVerificationKey,
)

#: The edwards25519 group order, RFC 8032 §5.1 — signatures with S >= L are
#: malleable restatements of a valid signature and §5.1.7 requires refusal.
GROUP_ORDER = 2 ** 252 + 27742317777372353535851937790883648493

#: The prime of the field, 2^255 - 19. A y coordinate at or above it has no
#: canonical encoding, so several byte strings would name one point.
FIELD_PRIME = 2 ** 255 - 19

#: NOT A PRODUCTION SEED — a fixed, published test value.
CORPUS_SEED = bytes(range(32))
CORPUS_MESSAGE = b"strict-corpus-message"


def _signing_key() -> TrustedEvidenceSigningKey:
    return TrustedEvidenceSigningKey(CORPUS_SEED)


def _le(value: int) -> bytes:
    return (value % 2 ** 256).to_bytes(32, "little")


#: The eight points of the edwards25519 torsion subgroup, in both their
#: canonical and (where one exists) non-canonical spellings, plus the two
#: non-canonical y >= p encodings. Every one of these is either a small-order
#: point — which carries no discrete-logarithm security whatsoever — or a
#: spelling the standard says must not decode.
UNTRUSTWORTHY_POINTS = [
    pytest.param("01" + "00" * 31, id="identity-y1-x0-0"),
    pytest.param("01" + "00" * 30 + "80", id="identity-y1-x0-1-noncanonical"),
    pytest.param("ec" + "ff" * 30 + "7f", id="order2-y-p-minus-1"),
    pytest.param("ec" + "ff" * 31, id="order2-y-p-minus-1-x0-1"),
    pytest.param("00" * 32, id="order4-all-zero"),
    pytest.param("00" * 31 + "80", id="order4-x0-1"),
    pytest.param(
        "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
        id="order8-a",
    ),
    pytest.param(
        "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
        id="order8-b",
    ),
    pytest.param("ed" + "ff" * 30 + "7f", id="y-equals-p-noncanonical"),
    pytest.param("ee" + "ff" * 30 + "7f", id="y-equals-p-plus-1-noncanonical"),
    pytest.param("ff" * 32, id="all-ff"),
    pytest.param(_le(2).hex(), id="off-curve-y-2"),
]

#: The small-order points as raw bytes, for reuse as a forged ``R``.
LOW_ORDER_BYTES = [
    bytes.fromhex(case.values[0]) for case in UNTRUSTWORTHY_POINTS[:8]
]


# --------------------------------------------------------------------------- #
# Public keys — refused at construction, so they never enter the system (F-03)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("public_hex", UNTRUSTWORTHY_POINTS)
def test_an_untrustworthy_point_cannot_become_a_verification_key(public_hex):
    with pytest.raises(ValueError):
        TrustedEvidenceVerificationKey(bytes.fromhex(public_hex))


def test_the_identity_point_universal_forgery_is_unreachable():
    """The concrete attack F-03 enabled, proved closed at its entry point.

    An identity-point anchor makes ``[S]B = R + [k]A`` hold for ``R = [S]B`` and
    *any* ``S``, so an attacker with no key at all can mint a signature that
    verifies. The forgery is unreachable because the key it needs cannot be
    constructed — which is why this is a construction-time refusal rather than
    a verification-time one.
    """

    identity = bytes.fromhex("01" + "00" * 31)
    with pytest.raises(ValueError) as excinfo:
        TrustedEvidenceVerificationKey(identity)
    assert "not a valid Ed25519 public key" in str(excinfo.value)


def test_a_genuine_public_key_is_accepted():
    """The corpus above would be vacuous if nothing at all were accepted."""

    key = _signing_key().verification_key
    rebuilt = TrustedEvidenceVerificationKey(key.public_key_bytes)
    assert rebuilt.public_key_bytes == key.public_key_bytes
    assert rebuilt == key


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"\x00" * (ED25519_PUBLIC_KEY_SIZE - 1), id="short"),
        pytest.param(b"\x00" * (ED25519_PUBLIC_KEY_SIZE + 1), id="long"),
        pytest.param(bytearray(32), id="bytearray-not-bytes"),
        pytest.param("f" * 64, id="hex-string-not-bytes"),
        pytest.param(None, id="none"),
        pytest.param(42, id="int"),
    ],
)
def test_malformed_key_material_is_refused_at_construction(bad):
    with pytest.raises(ValueError):
        TrustedEvidenceVerificationKey(bad)


# --------------------------------------------------------------------------- #
# Signatures — a fail-closed False against a genuine key
# --------------------------------------------------------------------------- #

def _malformed_signature_cases():
    key = _signing_key()
    signature = key.sign(CORPUS_MESSAGE)
    r, s = signature[:32], signature[32:]
    s_int = int.from_bytes(s, "little")
    cases = [
        pytest.param(CORPUS_MESSAGE + b"!", signature, id="altered-message"),
        pytest.param(b"", signature, id="empty-message-wrong"),
        pytest.param(
            CORPUS_MESSAGE, bytes([r[0] ^ 0x01]) + r[1:] + s, id="altered-R"
        ),
        pytest.param(
            CORPUS_MESSAGE, r + bytes([s[0] ^ 0x01]) + s[1:], id="altered-S"
        ),
        pytest.param(CORPUS_MESSAGE, signature[:-1], id="truncated-63"),
        pytest.param(CORPUS_MESSAGE, signature + b"\x00", id="extended-65"),
        pytest.param(CORPUS_MESSAGE, b"", id="empty-signature"),
        pytest.param(CORPUS_MESSAGE, b"\x00" * 64, id="all-zero-signature"),
        # RFC 8032 §5.1.7 — every restatement of S at or above the group order
        pytest.param(CORPUS_MESSAGE, r + _le(GROUP_ORDER), id="S-equals-L"),
        pytest.param(CORPUS_MESSAGE, r + _le(GROUP_ORDER + 1), id="S-equals-L-plus-1"),
        pytest.param(CORPUS_MESSAGE, r + _le(s_int + GROUP_ORDER), id="S-plus-L"),
        pytest.param(
            CORPUS_MESSAGE, r + _le(s_int + 2 * GROUP_ORDER), id="S-plus-2L"
        ),
        pytest.param(CORPUS_MESSAGE, r + _le(2 ** 255), id="S-high-bit-set"),
        pytest.param(CORPUS_MESSAGE, r + b"\xff" * 32, id="S-all-ff"),
        # Non-canonical and small-order R
        pytest.param(
            CORPUS_MESSAGE,
            bytes.fromhex("ed" + "ff" * 30 + "7f") + s,
            id="R-y-equals-p",
        ),
        pytest.param(
            CORPUS_MESSAGE,
            bytes.fromhex("ee" + "ff" * 30 + "7f") + s,
            id="R-y-equals-p-plus-1",
        ),
        pytest.param(
            CORPUS_MESSAGE,
            bytes.fromhex("01" + "00" * 30 + "80") + s,
            id="R-noncanonical-identity",
        ),
        pytest.param(CORPUS_MESSAGE, b"\xff" * 64, id="all-ff-signature"),
    ]
    for index, point in enumerate(LOW_ORDER_BYTES):
        cases.append(
            pytest.param(CORPUS_MESSAGE, point + s, id=f"R-low-order-{index}")
        )
    return cases


@pytest.mark.parametrize("message,signature", _malformed_signature_cases())
def test_every_malformed_signature_is_false_and_never_raises(message, signature):
    verifier = _signing_key().verification_key
    assert verifier.verify(message, signature) is False


def test_the_baseline_signature_verifies():
    """Without this, every refusal above could be a broken fixture."""

    key = _signing_key()
    assert key.verification_key.verify(CORPUS_MESSAGE, key.sign(CORPUS_MESSAGE)) is True


def test_a_signature_does_not_verify_under_a_different_genuine_key():
    other = TrustedEvidenceSigningKey(bytes(range(32, 64)))
    key = _signing_key()
    signature = key.sign(CORPUS_MESSAGE)
    assert other.verification_key.verify(CORPUS_MESSAGE, signature) is False


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param("a string", id="str"),
        pytest.param(None, id="none"),
        pytest.param(42, id="int"),
        pytest.param(bytearray(ED25519_SIGNATURE_SIZE), id="bytearray"),
        pytest.param(memoryview(bytes(ED25519_SIGNATURE_SIZE)), id="memoryview"),
        pytest.param([0] * ED25519_SIGNATURE_SIZE, id="list-of-ints"),
    ],
)
def test_non_bytes_signature_material_is_false_and_never_raises(bad):
    verifier = _signing_key().verification_key
    assert verifier.verify(CORPUS_MESSAGE, bad) is False


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param("a string", id="str"),
        pytest.param(None, id="none"),
        pytest.param(42, id="int"),
        pytest.param(bytearray(b"message"), id="bytearray"),
    ],
)
def test_non_bytes_message_material_is_false_and_never_raises(bad):
    key = _signing_key()
    signature = key.sign(CORPUS_MESSAGE)
    assert key.verification_key.verify(bad, signature) is False


# --------------------------------------------------------------------------- #
# Sizes and canonicality of the corpus itself
# --------------------------------------------------------------------------- #

def test_the_corpus_constants_are_the_standard_constants():
    """A wrong constant here would silently weaken every case above."""

    assert GROUP_ORDER == 2 ** 252 + 27742317777372353535851937790883648493
    assert FIELD_PRIME == 2 ** 255 - 19
    assert bytes.fromhex("ed" + "ff" * 30 + "7f") == _le(FIELD_PRIME)
    assert bytes.fromhex("ec" + "ff" * 30 + "7f") == _le(FIELD_PRIME - 1)
