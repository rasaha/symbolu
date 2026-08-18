"""Conformance to RFC 8032, proved against the RFC's own published vectors.

The package does **not** implement Ed25519. Signing, verification and public-key
derivation come from ``cryptography`` (OpenSSL), and strict trust-anchor point
validation comes from libsodium through ``PyNaCl``; ``authority/backend.py`` is
the only module that touches either, and there is no in-package curve
arithmetic and no fallback to any. An earlier revision of this package shipped a
handwritten pure-Python implementation, justified in part by a misreading of ADR
§23 — which governs *Ugence package* dependency direction, not maintained
third-party cryptographic primitives. Closure-audit findings F-01, F-02, F-03
and F-06 were consequences of that choice, and the correction was to delete it.

These vectors remain, and remain load-bearing: they are what proves the backend
this package actually calls is the standard algorithm, and — because they were
pinned before the backend changed and reproduced unchanged after — that the
substitution altered no byte any verifier depends on.

The seeds here are the RFC's published test keys. They are, by construction,
among the best-known Ed25519 private keys in existence and are **not production
key material**.
"""

from __future__ import annotations

import pytest
from ugence_trusted_evidence_authority.api import (
    ED25519_PUBLIC_KEY_SIZE,
    ED25519_SEED_SIZE,
    ED25519_SIGNATURE_SIZE,
    TrustedEvidenceSigningKey,
    TrustedEvidenceVerificationKey,
    encode_public_key,
    encode_signature,
)

#: RFC 8032 §7.1 — (secret key, public key, message, signature). Verbatim.
#: NOT PRODUCTION KEYS: these are the RFC's own published test vectors.
RFC_8032_VECTORS = [
    pytest.param(
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
        id="TEST-1-empty-message",
    ),
    pytest.param(
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
        "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
        id="TEST-2-one-byte",
    ),
    pytest.param(
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
        "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
        id="TEST-3-two-bytes",
    ),
    pytest.param(
        "f5e5767cf153319517630f226876b86c8160cc583bc013744c6bf255f5cc0ee5",
        "278117fc144c72340f67d0f2316e8386ceffbf2b2428c9c51fef7c597f1d426e",
        "08b8b2b733424243760fe426a4b54908632110a66c2f6591eabd3345e3e4eb98"
        "fa6e264bf09efe12ee50f8f54e9f77b1e355f6c50544e23fb1433ddf73be84d8"
        "79de7c0046dc4996d9e773f4bc9efe5738829adb26c81b37c93a1b270b20329d"
        "658675fc6ea534e0810a4432826bf58c941efb65d57a338bbd2e26640f89ffbc"
        "1a858efcb8550ee3a5e1998bd177e93a7363c344fe6b199ee5d02e82d522c4fe"
        "ba15452f80288a821a579116ec6dad2b3b310da903401aa62100ab5d1a36553e"
        "06203b33890cc9b832f79ef80560ccb9a39ce767967ed628c6ad573cb116dbef"
        "efd75499da96bd68a8a97b928a8bbc103b6621fcde2beca1231d206be6cd9ec7"
        "aff6f6c94fcd7204ed3455c68c83f4a41da4af2b74ef5c53f1d8ac70bdcb7ed1"
        "85ce81bd84359d44254d95629e9855a94a7c1958d1f8ada5d0532ed8a5aa3fb2"
        "d17ba70eb6248e594e1a2297acbbb39d502f1a8c6eb6f1ce22b3de1a1f40cc24"
        "554119a831a9aad6079cad88425de6bde1a9187ebb6092cf67bf2b13fd65f270"
        "88d78b7e883c8759d2c4f5c65adb7553878ad575f9fad878e80a0c9ba63bcbcc"
        "2732e69485bbc9c90bfbd62481d9089beccf80cfe2df16a2cf65bd92dd597b07"
        "07e0917af48bbb75fed413d238f5555a7a569d80c3414a8d0859dc65a46128ba"
        "b27af87a71314f318c782b23ebfe808b82b0ce26401d2e22f04d83d1255dc51a"
        "ddd3b75a2b1ae0784504df543af8969be3ea7082ff7fc9888c144da2af58429e"
        "c96031dbcad3dad9af0dcbaaaf268cb8fcffead94f3c7ca495e056a9b47acdb7"
        "51fb73e666c6c655ade8297297d07ad1ba5e43f1bca32301651339e22904cc8c"
        "42f58c30c04aafdb038dda0847dd988dcda6f3bfd15c4b4c4525004aa06eeff8"
        "ca61783aacec57fb3d1f92b0fe2fd1a85f6724517b65e614ad6808d6f6ee34df"
        "f7310fdc82aebfd904b01e1dc54b2927094b2db68d6f903b68401adebf5a7e08"
        "d78ff4ef5d63653a65040cf9bfd4aca7984a74d37145986780fc0b16ac451649"
        "de6188a7dbdf191f64b5fc5e2ab47b57f7f7276cd419c17a3ca8e1b939ae49e4"
        "88acba6b965610b5480109c8b17b80e1b7b750dfc7598d5d5011fd2dcc5600a3"
        "2ef5b52a1ecc820e308aa342721aac0943bf6686b64b2579376504ccc493d97e"
        "6aed3fb0f9cd71a43dd497f01f17c0e2cb3797aa2a2f256656168e6c496afc5f"
        "b93246f6b1116398a346f1a641f3b041e989f7914f90cc2c7fff357876e506b5"
        "0d334ba77c225bc307ba537152f3f1610e4eafe595f6d9d90d11faa933a15ef1"
        "369546868a7f3a45a96768d40fd9d03412c091c6315cf4fde7cb68606937380d"
        "b2eaaa707b4c4185c32eddcdd306705e4dc1ffc872eeee475a64dfac86aba41c"
        "0618983f8741c5ef68d3a101e8a3b8cac60c905c15fc910840b94c00a0b9d0",
        "0aab4c900501b3e24d7cdf4663326a3a87df5e4843b2cbdb67cbf6e460fec350"
        "aa5371b1508f9f4528ecea23c436d94b5e8fcd4f681e30a6ac00a9704a188a03",
        id="TEST-1024",
    ),
    pytest.param(
        "833fe62409237b9d62ec77587520911e9a759cec1d19755b7da901b96dca3d42",
        "ec172b93ad5e563bf4932c70e1245034c35467ef2efd4d64ebf819683467e2bf",
        "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
        "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
        "dc2a4459e7369633a52b1bf277839a00201009a3efbf3ecb69bea2186c26b589"
        "09351fc9ac90b3ecfdfbc7c66431e0303dca179c138ac17ad9bef1177331a704",
        id="TEST-SHA-abc",
    ),
]


@pytest.mark.parametrize("seed_hex,public_hex,message_hex,signature_hex", RFC_8032_VECTORS)
def test_the_public_key_derives_exactly_as_the_rfc_specifies(
    seed_hex, public_hex, message_hex, signature_hex
):
    key = TrustedEvidenceSigningKey(bytes.fromhex(seed_hex))
    assert encode_public_key(key.verification_key.public_key_bytes) == public_hex


@pytest.mark.parametrize("seed_hex,public_hex,message_hex,signature_hex", RFC_8032_VECTORS)
def test_the_signature_reproduces_the_rfc_vector_byte_for_byte(
    seed_hex, public_hex, message_hex, signature_hex
):
    """Ed25519 is deterministic, so a conforming signer produces exactly this."""

    key = TrustedEvidenceSigningKey(bytes.fromhex(seed_hex))
    assert encode_signature(key.sign(bytes.fromhex(message_hex))) == signature_hex


@pytest.mark.parametrize("seed_hex,public_hex,message_hex,signature_hex", RFC_8032_VECTORS)
def test_the_rfc_signature_verifies_under_the_rfc_public_key(
    seed_hex, public_hex, message_hex, signature_hex
):
    """Verification is checked against the RFC's *own* signature bytes.

    Note this path never touches ``seed_hex``: it proves the verifier accepts a
    signature it did not produce, which is the property a third party relies on.
    """

    del seed_hex  # deliberately unused: verification needs no private material
    verifier = TrustedEvidenceVerificationKey(bytes.fromhex(public_hex))
    assert verifier.verify(bytes.fromhex(message_hex), bytes.fromhex(signature_hex))


@pytest.mark.parametrize("seed_hex,public_hex,message_hex,signature_hex", RFC_8032_VECTORS)
def test_a_single_flipped_bit_anywhere_fails_verification(
    seed_hex, public_hex, message_hex, signature_hex
):
    verifier = TrustedEvidenceVerificationKey(bytes.fromhex(public_hex))
    signature = bytes.fromhex(signature_hex)
    message = bytes.fromhex(message_hex)
    for index in (0, 31, 32, 62):
        tampered = bytearray(signature)
        tampered[index] ^= 0x01
        assert not verifier.verify(message, bytes(tampered))
    if message:
        tampered_message = bytearray(message)
        tampered_message[0] ^= 0x01
        assert not verifier.verify(bytes(tampered_message), signature)


def test_the_sizes_are_the_rfc_sizes():
    assert ED25519_SEED_SIZE == 32
    assert ED25519_PUBLIC_KEY_SIZE == 32
    assert ED25519_SIGNATURE_SIZE == 64


def test_a_signature_with_s_at_or_above_the_group_order_is_refused():
    """RFC 8032 §5.1.7 malleability check — a naive implementation omits this."""

    public_hex, signature_hex = (
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    )
    order = 2 ** 252 + 27742317777372353535851937790883648493
    signature = bytes.fromhex(signature_hex)
    verifier = TrustedEvidenceVerificationKey(bytes.fromhex(public_hex))
    assert verifier.verify(b"", signature)

    s = int.from_bytes(signature[32:], "little")
    malleable = signature[:32] + (s + order).to_bytes(32, "little")
    assert len(malleable) == 64
    assert not verifier.verify(b"", malleable)


@pytest.mark.parametrize(
    "bad",
    [b"", b"\x00" * 63, b"\x00" * 65, "a string", None, 42, bytearray(64)],
)
def test_malformed_signature_material_is_false_never_an_exception(bad):
    """A single fail-closed boolean, so a caller has one thing to branch on.

    The key here is a genuine one. The all-zero key this test previously used
    is the identity point, and it is now refused at construction — which is
    closure-audit F-03 closed, and the reason the test needed a real key.
    """

    verifier = TrustedEvidenceVerificationKey(
        bytes.fromhex(RFC_8032_VECTORS[0].values[1])
    )
    assert verifier.verify(b"message", bad) is False


@pytest.mark.parametrize("bad", [b"", b"\x00" * 31, b"\x00" * 33, "hex", None, 42])
def test_malformed_key_material_is_refused_at_construction(bad):
    with pytest.raises(ValueError):
        TrustedEvidenceSigningKey(bad)
    with pytest.raises(ValueError):
        TrustedEvidenceVerificationKey(bad)


def test_the_all_zero_public_key_is_refused_at_construction():
    """The identity point is a universal-forgery key and never a trust anchor.

    Correctly-sized but cryptographically worthless key material was accepted
    before the correction (closure-audit **F-03**); the strict libsodium point
    check now refuses it where it would enter the system.
    """

    with pytest.raises(ValueError):
        TrustedEvidenceVerificationKey(bytes(ED25519_PUBLIC_KEY_SIZE))


def test_no_key_generation_entry_point_exists():
    """Key generation needs entropy; this package must be a pure function.

    ``os``, ``secrets`` and ``random`` are banned package-wide so every output
    is a pure function of its inputs, and credential issuance is outside the
    TEV-2 boundary. A seed enters through the constructor from the composition
    root and nowhere else.
    """

    for absent in ("generate", "random", "new", "create", "from_random"):
        assert not hasattr(TrustedEvidenceSigningKey, absent), absent


def test_signing_is_deterministic():
    """Ed25519 is deterministic; two signings of one message are byte-identical."""

    key = TrustedEvidenceSigningKey(bytes(range(32)))
    assert key.sign(b"message") == key.sign(b"message")
    assert key.sign(b"message") != key.sign(b"message!")
