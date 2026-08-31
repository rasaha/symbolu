"""Signature binding, key entitlement, and immutable trust anchors (ADR §14, §15)."""

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
    coordinate_of,
    make_authority,
    make_policy,
    make_signer,
)
from ugence_policy_authority.api import (
    ISSUANCE_SIGNING_DOMAIN,
    REVOCATION_SIGNING_DOMAIN,
    DenyAllSignatureVerifier,
    Ed25519PolicySigner,
    KeyEntitlement,
    KeyVerificationStatus,
    PolicyAuthorityRequestError,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyVerificationKey,
    SigningKey,
    VerifyKey,
)
from ugence_uvi_policy_contracts.api import PolicyFamily

SIGNED_FIELDS = [
    "record_id",
    "adapter_id",
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
    return authority, authority.issue(make_policy())


def _verify(ring, record, *, as_of=T_MID, entitlement=KeyEntitlement.ISSUE_POLICY):
    return ring.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id=record.coordinate.tenant_id,
        required_entitlement=entitlement,
        as_of=as_of,
    )


# --------------------------------------------------------------------------- #
# Signature binding
# --------------------------------------------------------------------------- #
def test_a_valid_signature_verifies_under_the_named_key():
    authority, record = _issued()
    assert _verify(authority.key_ring, record).status is KeyVerificationStatus.VALID


@pytest.mark.parametrize("field", SIGNED_FIELDS)
def test_altering_any_signed_field_invalidates_verification(field):
    authority, record = _issued()
    substitutes = {
        "record_id": "rec-tampered",
        "adapter_id": "attacker.adapter/v1",
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
    assert not _verify(authority.key_ring, tampered).valid


@pytest.mark.parametrize(
    "component",
    ["policy_family", "policy_id", "version", "content_digest", "scope", "tenant_id"],
)
def test_altering_any_coordinate_component_invalidates_verification(component):
    from ugence_policy_authority.api import issuance_signing_payload

    authority, record = _issued()
    substitutes = {
        "policy_family": "READINESS",
        "policy_id": "other-policy",
        "version": "9.9.9",
        "content_digest": "f" * 64,
        "scope": "TENANT",
        "tenant_id": "smuggled-tenant",
    }
    tampered_coordinate = replace(record.coordinate, **{component: substitutes[component]})
    payload = issuance_signing_payload(
        record_id=record.record_id,
        coordinate=tampered_coordinate,
        adapter_id=record.adapter_id,
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
        expected_tenant_id=tampered_coordinate.tenant_id,
        required_entitlement=KeyEntitlement.ISSUE_POLICY,
        as_of=T_MID,
    ).valid


def test_the_signed_payload_binds_every_required_field():
    _, record = _issued()
    payload = record.signing_payload().decode("utf-8")
    coordinate = record.coordinate
    for required in (
        "ugence.policy-authority",
        "v0.1",
        "ugence.policy-authority/v0.1",
        "ugence.policy-authority/canonicalization/v1",
        record.record_id,
        record.adapter_id,
        coordinate.policy_family,
        coordinate.policy_id,
        coordinate.version,
        coordinate.content_digest,
        coordinate.scope,
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


def test_issuance_and_revocation_payloads_are_domain_separated():
    from ugence_policy_authority.api import (
        PolicyRevocationReasonCode,
        revocation_signing_payload,
    )

    _, record = _issued()
    issuance = record.signing_payload()
    revocation = revocation_signing_payload(
        revocation_id=record.record_id,
        coordinate=record.coordinate,
        reason_code=PolicyRevocationReasonCode.OTHER,
        revoking_authority_id=record.issuing_authority_id,
        key_id=record.key_id,
        signature_alg=record.signature_alg,
        revoked_at=record.issued_at,
    )
    assert issuance.startswith(ISSUANCE_SIGNING_DOMAIN.encode())
    assert revocation.startswith(REVOCATION_SIGNING_DOMAIN.encode())
    assert issuance != revocation


# --------------------------------------------------------------------------- #
# Key resolution, entitlement and window
# --------------------------------------------------------------------------- #
def test_an_unknown_key_fails_closed():
    _, record = _issued()
    assert _verify(PolicyKeyRing(), record).status is KeyVerificationStatus.UNKNOWN_KEY


def test_a_revoked_key_fails_closed():
    authority, record = _issued()
    ring = authority.key_ring.with_key(authority.key_ring.resolve(record.key_id).revoke())
    assert _verify(ring, record).status is KeyVerificationStatus.REVOKED_KEY


@pytest.mark.parametrize("as_of", [T_BEFORE, T_AFTER])
def test_an_out_of_window_key_fails_closed(as_of):
    signer = make_signer()
    ring = PolicyKeyRing([signer.verification_key(not_before=T_FROM, not_after=T_TO)])
    result = ring.verify(
        key_id=signer.key_id,
        payload=b"x",
        signature=b"\x00" * 64,
        expected_authority_id=signer.authority_id,
        expected_tenant_id="",
        required_entitlement=KeyEntitlement.ISSUE_POLICY,
        as_of=as_of,
    )
    assert result.status is KeyVerificationStatus.KEY_NOT_IN_WINDOW


def test_a_wrong_authority_key_fails_closed():
    signer = make_signer(authority_id="some.other.authority")
    result = PolicyKeyRing([signer.verification_key()]).verify(
        key_id=signer.key_id,
        payload=b"x",
        signature=b"\x00" * 64,
        expected_authority_id=ISSUING_AUTHORITY,
        expected_tenant_id="",
        required_entitlement=KeyEntitlement.ISSUE_POLICY,
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.WRONG_AUTHORITY


def test_a_tenant_bound_key_cannot_serve_another_tenant():
    signer = make_signer()
    result = PolicyKeyRing([signer.verification_key(tenant_id="tenant-a")]).verify(
        key_id=signer.key_id,
        payload=b"x",
        signature=b"\x00" * 64,
        expected_authority_id=signer.authority_id,
        expected_tenant_id="tenant-b",
        required_entitlement=KeyEntitlement.ISSUE_POLICY,
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.WRONG_TENANT
    assert "tenant-a" not in result.detail


def test_an_issue_only_key_is_not_entitled_to_revoke():
    authority, record = _issued()
    result = _verify(
        authority.key_ring, record, entitlement=KeyEntitlement.REVOKE_POLICY
    )
    assert result.status is KeyVerificationStatus.NOT_ENTITLED


def test_a_revoke_only_key_is_not_entitled_to_issue():
    authority = make_authority()
    revoker_key = authority.key_ring.resolve(authority.revocation_signer.key_id)
    assert revoker_key.entitlements == frozenset({KeyEntitlement.REVOKE_POLICY})
    result = authority.key_ring.verify(
        key_id=revoker_key.key_id,
        payload=b"x",
        signature=b"\x00" * 64,
        expected_authority_id=revoker_key.authority_id,
        expected_tenant_id="",
        required_entitlement=KeyEntitlement.ISSUE_POLICY,
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.NOT_ENTITLED


def test_keys_resolve_by_exact_key_id_only():
    signer = make_signer(key_id="policy-authority-key-1")
    ring = PolicyKeyRing([signer.verification_key()])
    assert ring.resolve("policy-authority-key-1") is not None
    for near_miss in ("policy-authority-key-2", "POLICY-AUTHORITY-KEY-1", "policy-authority-key-1 ", ""):
        assert ring.resolve(near_miss) is None


def test_a_signature_from_a_different_key_does_not_verify():
    authority, record = _issued()
    attacker = make_signer(key_id=record.key_id, seed=9)
    forged = replace(record, signature=attacker.sign(record.signing_payload()))
    assert not _verify(authority.key_ring, forged).valid


def test_the_deny_all_verifier_denies_everything():
    authority, record = _issued()
    result = DenyAllSignatureVerifier().verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id="",
        required_entitlement=KeyEntitlement.ISSUE_POLICY,
        as_of=T_MID,
    )
    assert result.status is KeyVerificationStatus.NO_VERIFIER_CONFIGURED

    from ugence_policy_authority.api import resolve_policy

    assert resolve_policy(
        reference=make_policy().reference,
        expected_reference_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=DenyAllSignatureVerifier(),
        adapters=authority.adapters,
    ).reason is PolicyResolutionReason.KEY_UNKNOWN


# --------------------------------------------------------------------------- #
# Immutable trust anchors — the corrected key-ring defect
# --------------------------------------------------------------------------- #
def test_mutating_the_caller_owned_mapping_after_construction_has_no_effect():
    signer = make_signer()
    caller_map = {signer.key_id: signer.verification_key()}
    ring = PolicyKeyRing(caller_map)

    attacker = make_signer(authority_id="attacker", key_id="attacker-key", seed=13)
    caller_map["attacker-key"] = attacker.verification_key()
    caller_map.pop(signer.key_id)
    caller_map.clear()

    assert ring.resolve("attacker-key") is None
    assert ring.resolve(signer.key_id) is not None
    assert len(ring.keys) == 1


def test_mutating_a_caller_owned_sequence_after_construction_has_no_effect():
    signer = make_signer()
    caller_list = [signer.verification_key()]
    ring = PolicyKeyRing(caller_list)
    caller_list.clear()
    assert ring.resolve(signer.key_id) is not None


def test_the_exposed_key_view_is_read_only():
    signer = make_signer()
    ring = PolicyKeyRing([signer.verification_key()])
    attacker = make_signer(authority_id="attacker", key_id="attacker-key", seed=17)

    with pytest.raises(TypeError):
        ring.keys["attacker-key"] = attacker.verification_key()
    with pytest.raises(TypeError):
        del ring.keys[signer.key_id]
    assert ring.resolve("attacker-key") is None


def test_with_key_returns_a_new_ring_and_leaves_the_original_untouched():
    authority, record = _issued()
    original_ids = set(authority.key_ring.keys)
    replacement = authority.key_ring.with_key(
        authority.key_ring.resolve(record.key_id).revoke()
    )
    assert set(authority.key_ring.keys) == original_ids
    assert authority.key_ring.resolve(record.key_id).revoked is False
    assert replacement.resolve(record.key_id).revoked is True
    assert replacement is not authority.key_ring


def test_an_attacker_key_cannot_be_injected_post_construction():
    authority, record = _issued()
    attacker = make_signer(authority_id=ISSUING_AUTHORITY, key_id=record.key_id, seed=23)
    forged = replace(record, signature=attacker.sign(record.signing_payload()))

    # Try every mutation route a caller has.
    for attempt in (
        lambda: authority.key_ring.keys.update({record.key_id: attacker.verification_key()}),
        lambda: authority.key_ring.keys.__setitem__(record.key_id, attacker.verification_key()),
        lambda: setattr(authority.key_ring, "_keys", {}),
    ):
        with pytest.raises((TypeError, AttributeError)):
            attempt()

    assert not _verify(authority.key_ring, forged).valid


def test_key_entitlements_are_defensively_copied():
    signer = make_signer()
    caller_entitlements = {KeyEntitlement.ISSUE_POLICY}
    key = PolicyVerificationKey(
        key_id="k",
        verify_key=signer.verification_key().verify_key,
        authority_id="a",
        entitlements=caller_entitlements,
    )
    caller_entitlements.add(KeyEntitlement.REVOKE_POLICY)
    assert key.entitlements == frozenset({KeyEntitlement.ISSUE_POLICY})
    assert isinstance(key.entitlements, frozenset)


def test_a_key_ring_rejects_a_mismatched_mapping_key():
    signer = make_signer()
    with pytest.raises(PolicyAuthorityRequestError, match="does not match"):
        PolicyKeyRing({"wrong-id": signer.verification_key()})


def test_a_key_ring_rejects_a_non_anchor_entry():
    with pytest.raises(PolicyAuthorityRequestError, match="PolicyVerificationKey"):
        PolicyKeyRing({"k": object()})


# --------------------------------------------------------------------------- #
# Private key material
# --------------------------------------------------------------------------- #
def test_no_record_or_result_can_carry_private_key_material():
    from ugence_policy_authority import api

    for name in api.__all__:
        obj = getattr(api, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        if obj is SigningKey:
            continue
        for f in dataclasses.fields(obj):
            assert f.type is not SigningKey, (name, f.name)
            for banned in ("seed", "private", "signing_key", "secret"):
                assert banned not in f.name, (name, f.name)


def test_the_issued_record_serialization_carries_no_key_material():
    from ugence_policy_authority.core.canonical import canonical_bytes

    _, record = _issued()
    encoded = canonical_bytes(
        {f.name: getattr(record, f.name) for f in dataclasses.fields(record) if f.name != "policy"}
    )
    assert b"seed" not in encoded and b"private" not in encoded


def test_a_signing_key_never_reveals_its_seed_in_a_repr():
    assert "redacted" in repr(SigningKey.from_seed(b"\x02" * 32))
    assert "seed" not in repr(make_signer()).lower()


def test_a_key_ring_repr_lists_only_key_ids():
    signer = make_signer()
    text = repr(PolicyKeyRing([signer.verification_key()]))
    assert signer.key_id in text
    assert "VerifyKey" not in text


# --------------------------------------------------------------------------- #
# Ed25519 conformance
# --------------------------------------------------------------------------- #
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


def test_signature_verification_is_boolean_and_never_raises():
    key = make_signer().verification_key().verify_key
    for junk in (b"", b"\x00", b"\xff" * 64, b"z" * 63, "not bytes", None):
        assert key.verify(b"message", junk) is False


def test_a_non_canonical_scalar_is_rejected_per_rfc_8032():
    """S must be reduced mod L; an oversized scalar must not verify."""

    key = SigningKey.from_seed(b"\x05" * 32)
    signature = bytearray(key.sign(b"m"))
    signature[32:64] = (2**252 + 27742317777372353535851937790883648493).to_bytes(32, "little")
    assert key.verify_key.verify(b"m", bytes(signature)) is False


def test_malformed_key_material_is_refused():
    with pytest.raises(ValueError):
        SigningKey(b"too short")
    with pytest.raises(ValueError):
        VerifyKey(b"too short")
    for kwargs in (
        dict(authority_id="", key_id="k"),
        dict(authority_id="a", key_id=""),
    ):
        with pytest.raises(PolicyAuthorityRequestError):
            Ed25519PolicySigner(signing_key=SigningKey.from_seed(b"\x01" * 32), **kwargs)
    with pytest.raises(PolicyAuthorityRequestError):
        Ed25519PolicySigner(authority_id="a", key_id="k", signing_key=b"\x01" * 32)
    with pytest.raises(PolicyAuthorityRequestError):
        PolicyVerificationKey(
            key_id="", verify_key=make_signer().verification_key().verify_key, authority_id="a"
        )
    with pytest.raises(PolicyAuthorityRequestError, match="at least one capability"):
        PolicyVerificationKey(
            key_id="k",
            verify_key=make_signer().verification_key().verify_key,
            authority_id="a",
            entitlements=frozenset(),
        )


def test_the_modular_inverse_agrees_with_fermat_on_every_input_including_zero():
    """The same contract this package's own copy of the reference Ed25519 must meet.

    `policy-authority` carries its own stdlib-only RFC 8032 implementation rather than
    importing another authority's internals (ADR §21), so the extended-Euclid
    optimisation had to be applied twice — and pinned twice. ``pow(0, -1, Q)`` raises
    where Fermat's form returns 0, so the zero case is asserted explicitly.
    """

    from ugence_policy_authority.core.ed25519 import _Q, _inv

    for x in (0, _Q, 2 * _Q, 1, 2, 121666, _Q - 1, _Q + 1, 2 ** 200):
        assert _inv(x) == pow(x, _Q - 2, _Q), x
