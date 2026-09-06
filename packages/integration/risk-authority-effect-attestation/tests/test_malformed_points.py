"""SE-5: malformed, small-order, non-canonical and identity public points refuse
before trust is granted — at TEA's record construction, and again at this
package's key admission if a record is forged around the check.

The corpus is the one the BR-2C candidate measured: the signature backend
alone accepts a key-less forgery under five of these twelve; libsodium's point
check refuses all twelve. This package reaches the check only through TEA's
``TrustAnchorRecord.verification_key()`` and re-implements nothing.
"""

from __future__ import annotations

import dataclasses

import pytest

import ugence_risk_authority_effect_attestation as ea
from ugence_trusted_evidence_authority import TrustAnchorRecord, TrustedEvidenceContractError
from _fixtures import anchor_of, attestation, provider_signer, verifier, verify

R = ea.EffectAttestationRefusalReason

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
KEYLESS_FORGERY = ("01" + "00" * 31) + "00" * 32


@pytest.mark.parametrize("name", sorted(SMALL_ORDER_AND_NON_CANONICAL_KEYS))
def test_a_small_order_or_non_canonical_anchor_cannot_even_be_constructed(name):
    fields = {f.name: getattr(anchor_of(provider_signer()), f.name)
              for f in dataclasses.fields(TrustAnchorRecord)}
    fields["public_key"] = SMALL_ORDER_AND_NON_CANONICAL_KEYS[name]
    with pytest.raises(TrustedEvidenceContractError):
        TrustAnchorRecord(**fields)


@pytest.mark.parametrize("name", sorted(SMALL_ORDER_AND_NON_CANONICAL_KEYS))
def test_a_record_forged_around_construction_is_refused_at_key_admission(name):
    """``object.__setattr__`` past TEA's constructor: the point is re-validated here."""

    anchor = anchor_of(provider_signer())
    object.__setattr__(anchor, "public_key", SMALL_ORDER_AND_NON_CANONICAL_KEYS[name])
    forged = dataclasses.replace(attestation(), signature=KEYLESS_FORGERY)
    result = verify(verifier(anchor), forged)
    assert result.outcome is ea.EffectAttestationVerificationOutcome.REFUSED
    assert result.refusal_reason is R.KEY_MATERIAL_INVALID, (name, result.detail)
    with pytest.raises(Exception):
        ea.anchor_verification_key(anchor)  # the package-level admission refuses too


@pytest.mark.parametrize("bad", ["", "ab" * 31, "AB" * 32, "0x" + "ab" * 31, "zz" * 32, "ab" * 33])
def test_malformed_key_encodings_are_unconstructible(bad):
    fields = {f.name: getattr(anchor_of(provider_signer()), f.name)
              for f in dataclasses.fields(TrustAnchorRecord)}
    fields["public_key"] = bad
    with pytest.raises(TrustedEvidenceContractError):
        TrustAnchorRecord(**fields)


def test_a_genuine_key_passes_the_point_check_and_a_forgery_still_fails_under_it():
    anchor = anchor_of(provider_signer())
    assert ea.anchor_verification_key(anchor) is not None
    forged = dataclasses.replace(attestation(), signature=KEYLESS_FORGERY)
    assert verify(verifier(anchor), forged).refusal_reason is R.SIGNATURE_INVALID


def test_the_malleable_s_plus_l_signature_is_refused():
    L = 2**252 + 27742317777372353535851937790883648493
    att = attestation()
    raw = bytes.fromhex(att.signature)
    scalar = int.from_bytes(raw[32:], "little")
    assert scalar < L
    malleated = (raw[:32] + (scalar + L).to_bytes(32, "little")).hex()
    result = verify(verifier(anchor_of(provider_signer())), dataclasses.replace(att, signature=malleated))
    assert result.refusal_reason is R.SIGNATURE_INVALID


def test_the_package_imports_no_cryptographic_library_of_its_own():
    """SE-5: the D-41 pair is reached only through TEA; nothing here is forked."""

    import ast
    import pathlib

    src = pathlib.Path(ea.__file__).resolve().parent
    for path in sorted(src.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            roots = set()
            if isinstance(node, ast.Import):
                roots = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = {node.module.split(".")[0]}
            assert not roots & {"cryptography", "nacl", "OpenSSL", "Crypto", "ed25519", "hashlib"} or (
                path.name == "canonical.py" and roots == {"hashlib"}
            ), (path.name, roots)
