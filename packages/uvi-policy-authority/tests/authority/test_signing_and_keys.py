"""Signature and key-material rules (GV-2C-b §7)."""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from datetime import timedelta

import pytest

from _authority_fixtures import (
    ISSUING_AUTHORITY,
    T_AFTER,
    T_BEFORE,
    T_FROM,
    T_MID,
    T_TO,
    make_authority,
    make_key_ring,
    make_policy,
    make_signer,
)
from ugence_uvi_policy_authority.api import (
    ISSUANCE_SIGNING_DOMAIN,
    REVOCATION_SIGNING_DOMAIN,
    DenyAllSignatureVerifier,
    Ed25519PolicySigner,
    IssuedPolicyRecord,
    KeyVerificationStatus,
    PolicyAuthorityRequestError,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyVerificationKey,
    SigningKey,
    VerifyKey,
    resolve_policy,
)
from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyScope

SIGNED_FIELDS = [
    "record_id",
    "policy_body_digest",
    "issuing_authority_id",
    "key_id",
    "signature_alg",
    "approving_authority_id",
    "approval_ref",
    "approval_digest",
    "issued_at",
]


def _issued():
    authority = make_authority()
    record = authority.issue(make_policy())
    return authority, record


def test_a_valid_signature_verifies_under_the_named_key():
    authority, record = _issued()
    result = authority.key_ring.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id=record.policy_reference.tenant_id,
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.VALID and result.valid


@pytest.mark.parametrize("field", SIGNED_FIELDS)
def test_altering_any_signed_field_invalidates_verification(field):
    authority, record = _issued()
    substitutes = {
        "record_id": "rec-tampered",
        "policy_body_digest": "d" * 64,
        "issuing_authority_id": "attacker.authority",
        "key_id": "other-key",
        "signature_alg": "not-ed25519",
        "approving_authority_id": "attacker.approver",
        "approval_ref": "APPROVAL-FORGED",
        "approval_digest": "e" * 64,
        "issued_at": T_MID + timedelta(seconds=1),
    }
    tampered = replace(record, **{field: substitutes[field]})
    assert tampered.signing_payload() != record.signing_payload()

    result = authority.key_ring.verify(
        key_id=tampered.key_id,
        payload=tampered.signing_payload(),
        signature=tampered.signature,
        expected_authority_id=tampered.issuing_authority_id,
        expected_tenant_id=tampered.policy_reference.tenant_id,
        as_of=T_MID,
    )
    assert not result.valid


@pytest.mark.parametrize(
    "component",
    ["policy_id", "version", "content_digest", "policy_family", "scope", "tenant_id"],
)
def test_altering_any_reference_component_invalidates_verification(component):
    authority, record = _issued()
    ref = record.policy_reference
    substitutes = {
        "policy_id": "other-policy",
        "version": "9.9.9",
        "content_digest": "f" * 64,
        "policy_family": PolicyFamily.READINESS,
        "scope": PolicyScope.TENANT,
        "tenant_id": "smuggled-tenant",
    }
    changes = {component: substitutes[component]}
    if component == "scope":
        changes["tenant_id"] = "t-x"
    if component == "tenant_id":
        changes["scope"] = PolicyScope.TENANT
    tampered_ref = replace(ref, **changes)

    from ugence_uvi_policy_authority.payload import issuance_signing_payload

    payload = issuance_signing_payload(
        record_id=record.record_id,
        reference=tampered_ref,
        policy_body_digest=record.policy_body_digest,
        approving_authority_id=record.approving_authority_id,
        approval_ref=record.approval_ref,
        approval_digest=record.approval_digest,
        issuing_authority_id=record.issuing_authority_id,
        key_id=record.key_id,
        signature_alg=record.signature_alg,
        issued_at=record.issued_at,
    )
    assert payload != record.signing_payload()
    assert not authority.key_ring.verify(
        key_id=record.key_id,
        payload=payload,
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id=tampered_ref.tenant_id,
        as_of=T_MID,
    ).valid


def test_an_unknown_key_fails_closed():
    _, record = _issued()
    empty = PolicyKeyRing()
    result = empty.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id="",
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.UNKNOWN_KEY


def test_a_revoked_key_fails_closed():
    authority, record = _issued()
    revoked_ring = authority.key_ring.with_key(
        authority.key_ring.resolve(record.key_id).revoke()
    )
    result = revoked_ring.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id="",
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.REVOKED_KEY


@pytest.mark.parametrize("as_of", [T_BEFORE, T_AFTER])
def test_an_out_of_window_key_fails_closed(as_of):
    signer = make_signer()
    ring = make_key_ring(signer, not_before=T_FROM, not_after=T_TO)
    result = ring.verify(
        key_id=signer.key_id,
        payload=b"x",
        signature=b"\x00" * 64,
        expected_authority_id=signer.authority_id,
        expected_tenant_id="",
        as_of=as_of,
    )
    assert result.status is KeyVerificationStatus.KEY_NOT_IN_WINDOW


def test_a_wrong_authority_key_fails_closed():
    signer = make_signer(authority_id="some.other.authority")
    ring = make_key_ring(signer)
    result = ring.verify(
        key_id=signer.key_id,
        payload=b"x",
        signature=b"\x00" * 64,
        expected_authority_id=ISSUING_AUTHORITY,
        expected_tenant_id="",
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.WRONG_AUTHORITY


def test_a_tenant_bound_key_cannot_verify_another_tenants_artifact():
    signer = make_signer()
    ring = make_key_ring(signer, tenant_id="tenant-a")
    result = ring.verify(
        key_id=signer.key_id,
        payload=b"x",
        signature=b"\x00" * 64,
        expected_authority_id=signer.authority_id,
        expected_tenant_id="tenant-b",
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.WRONG_TENANT


def test_a_signature_from_a_different_key_does_not_verify():
    authority, record = _issued()
    attacker = make_signer(key_id=record.key_id, seed=9)
    forged = replace(record, signature=attacker.sign(record.signing_payload()))
    assert not authority.key_ring.verify(
        key_id=forged.key_id,
        payload=forged.signing_payload(),
        signature=forged.signature,
        expected_authority_id=forged.issuing_authority_id,
        expected_tenant_id="",
        as_of=T_MID,
    ).valid


def test_keys_resolve_by_exact_key_id_only():
    signer = make_signer(key_id="uvi-pa-key-1")
    ring = make_key_ring(signer)
    assert ring.resolve("uvi-pa-key-1") is not None
    for near_miss in ("uvi-pa-key-2", "UVI-PA-KEY-1", "uvi-pa-key-1 ", ""):
        assert ring.resolve(near_miss) is None


def test_the_deny_all_verifier_denies_everything():
    authority, record = _issued()
    result = DenyAllSignatureVerifier().verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id="",
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.NO_VERIFIER_CONFIGURED
    assert not result.valid

    resolution = resolve_policy(
        reference=record.policy_reference,
        expected_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=DenyAllSignatureVerifier(),
    )
    assert resolution.reason is PolicyResolutionReason.KEY_UNKNOWN


def test_no_record_or_result_can_carry_private_key_material():
    """No stored/returned contract object has a field able to hold a private key.

    ``SigningKey`` itself is excluded: it *is* the key material, held only by a
    signer. What must never happen is a record, result, registry entry, or
    verification object carrying one.
    """

    from ugence_uvi_policy_authority import api

    key_material_types = {SigningKey}
    for name in api.__all__:
        obj = getattr(api, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        if obj in key_material_types or issubclass(obj, Ed25519PolicySigner):
            continue
        for f in dataclasses.fields(obj):
            assert f.type is not SigningKey, (name, f.name)
            assert "seed" not in f.name, (name, f.name)
            assert "private" not in f.name, (name, f.name)
            assert "signing_key" not in f.name, (name, f.name)


def test_the_issued_record_carries_no_key_material():
    _, record = _issued()
    names = {f.name for f in dataclasses.fields(record)}
    assert "key_id" in names
    assert not {n for n in names if "seed" in n or "private" in n or "signing_key" in n}
    from ugence_uvi_policy_authority.canonical import canonical_bytes

    assert b"seed" not in canonical_bytes(record)


def test_a_signing_key_never_reveals_its_seed_in_a_repr():
    signer = make_signer()
    assert "seed" not in repr(signer).lower()
    assert "redacted" in repr(SigningKey.from_seed(b"\x02" * 32))


def test_issuance_and_revocation_payloads_are_domain_separated():
    from ugence_uvi_policy_authority.payload import (
        issuance_signing_payload,
        revocation_signing_payload,
    )
    from ugence_uvi_policy_authority.api import PolicyRevocationReasonCode

    _, record = _issued()
    issuance = record.signing_payload()
    revocation = revocation_signing_payload(
        revocation_id=record.record_id,
        reference=record.policy_reference,
        reason_code=PolicyRevocationReasonCode.OTHER,
        revoking_authority_id=record.issuing_authority_id,
        key_id=record.key_id,
        signature_alg=record.signature_alg,
        revoked_at=record.issued_at,
    )
    assert issuance.startswith(ISSUANCE_SIGNING_DOMAIN.encode())
    assert revocation.startswith(REVOCATION_SIGNING_DOMAIN.encode())
    assert issuance != revocation


def test_the_signed_payload_binds_every_required_field():
    _, record = _issued()
    payload = record.signing_payload().decode("utf-8")
    ref = record.policy_reference
    for required in (
        "ugence.uvi.policy-authority",
        record.authority_protocol_version,
        record.record_id,
        ref.policy_id,
        ref.policy_family.value,
        ref.version,
        ref.content_digest,
        ref.scope.value,
        record.policy_body_digest,
        record.approving_authority_id,
        record.approval_ref,
        record.approval_digest,
        record.issuing_authority_id,
        record.key_id,
        record.signature_alg,
        "2026-06-01T00:00:00.000000Z",
    ):
        assert required in payload, required


def test_signature_verification_is_boolean_and_never_raises():
    key = make_signer().verification_key().verify_key
    for junk in (b"", b"\x00", b"\xff" * 64, b"z" * 63, "not bytes", None):
        assert key.verify(b"message", junk) is False


def test_malformed_key_material_is_refused():
    with pytest.raises(ValueError):
        SigningKey(b"too short")
    with pytest.raises(ValueError):
        VerifyKey(b"too short")
    with pytest.raises(PolicyAuthorityRequestError):
        Ed25519PolicySigner(authority_id="", key_id="k", signing_key=SigningKey.from_seed(b"\x01" * 32))
    with pytest.raises(PolicyAuthorityRequestError):
        Ed25519PolicySigner(authority_id="a", key_id="", signing_key=SigningKey.from_seed(b"\x01" * 32))
    with pytest.raises(PolicyAuthorityRequestError):
        Ed25519PolicySigner(authority_id="a", key_id="k", signing_key=b"\x01" * 32)
    with pytest.raises(PolicyAuthorityRequestError):
        PolicyVerificationKey(key_id="", verify_key=make_signer().verification_key().verify_key, authority_id="a")


def test_ed25519_round_trip_matches_the_rfc_shape():
    key = SigningKey.from_seed(bytes(range(32)))
    signature = key.sign(b"canonical payload")
    assert len(signature) == 64
    assert key.verify_key.verify(b"canonical payload", signature) is True
    assert key.verify_key.verify(b"canonical payloae", signature) is False
    assert len(key.verify_key.public_bytes) == 32


def test_signing_is_deterministic():
    key = SigningKey.from_seed(b"\x07" * 32)
    assert key.sign(b"m") == key.sign(b"m")
