"""Ed25519 signing correctness, including an RFC 8032 test vector (CI gate)."""

from __future__ import annotations

from risk_authority.crypto.signing import SigningKey, VerifyKey


def test_rfc8032_test_vector_2():
    # RFC 8032, section 7.1, TEST 2.
    seed = bytes.fromhex(
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"
    )
    expected_pub = bytes.fromhex(
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
    )
    message = bytes.fromhex("72")
    expected_sig = bytes.fromhex(
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
        "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"
    )
    sk = SigningKey.from_seed(seed)
    assert sk.verify_key.public_bytes == expected_pub
    assert sk.sign(message) == expected_sig
    assert sk.verify_key.verify(message, expected_sig)


def test_sign_verify_round_trip():
    sk = SigningKey.from_seed(bytes(range(32)))
    msg = b"authority envelope payload"
    sig = sk.sign(msg)
    assert sk.verify_key.verify(msg, sig)


def test_tampered_message_fails():
    sk = SigningKey.from_seed(bytes(range(32)))
    sig = sk.sign(b"original")
    assert not sk.verify_key.verify(b"tampered", sig)


def test_wrong_key_fails():
    sk = SigningKey.from_seed(bytes(range(32)))
    other = SigningKey.from_seed(bytes(range(1, 33)))
    sig = sk.sign(b"msg")
    assert not other.verify_key.verify(b"msg", sig)


def test_malformed_signature_returns_false_not_raises():
    vk = SigningKey.from_seed(bytes(range(32))).verify_key
    assert vk.verify(b"msg", b"too-short") is False
    assert vk.verify(b"msg", b"\x00" * 64) is False
