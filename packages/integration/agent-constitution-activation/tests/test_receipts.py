"""`ACC-IA-4` — receipts pin identity fields and can carry no key material.

The field sets are asserted structurally in the public-API snapshot; here the
shapes' own validation is exercised, and the derivations are compared field by
field against the authority's record.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest
from _activation_fixtures import (
    GLOBAL_TENANT,
    GOVERNED_ROLE_REF,
    T_ACTIVATE,
    T_ISSUE,
    make_world,
)
from ugence_agent_constitution_activation import (
    ActivationReceipt,
    ActivationRequestError,
    IssuanceReceipt,
)


@pytest.fixture(scope="module")
def world_and_receipts():
    world = make_world()
    policy, issuance = world.issue_first_constitution()
    reference_map, activation = world.root.activate_constitution(
        coordinate=issuance.coordinate, activated_at=T_ACTIVATE
    )
    record = world.registry.get_issued(issuance.coordinate)
    return world, record, issuance, activation


def test_the_issuance_receipt_restates_the_record_exactly(world_and_receipts):
    _, record, receipt, _ = world_and_receipts
    assert receipt.record_id == record.record_id
    assert receipt.coordinate == record.coordinate
    assert receipt.policy_body_digest == record.policy_body_digest
    assert receipt.issuing_authority_id == record.issuing_authority_id
    assert receipt.key_id == record.key_id
    assert receipt.signature_alg == record.signature_alg
    assert receipt.approving_authority_id == record.approving_authority_id
    assert receipt.approval_ref == record.approval_ref
    assert receipt.approval_digest == record.approval_digest
    assert receipt.issued_at == record.issued_at


def test_the_issuance_receipt_carries_no_signature_and_no_artifact(
    world_and_receipts,
):
    _, record, receipt, _ = world_and_receipts
    field_names = {f.name for f in dataclasses.fields(IssuanceReceipt)}
    assert "signature" not in field_names
    assert "policy" not in field_names
    for value in (getattr(receipt, name) for name in field_names):
        assert not isinstance(value, (bytes, bytearray)), (
            "a receipt carried raw bytes"
        )
    assert record.signature, "the record itself is signed; the receipt just omits it"


def test_the_activation_receipt_lists_every_derived_entry(world_and_receipts):
    _, record, _, activation = world_and_receipts
    assert activation.record_id == record.record_id
    assert activation.coordinate == record.coordinate
    assert activation.activated_entries == (
        (GLOBAL_TENANT, GOVERNED_ROLE_REF),
    )
    assert activation.activated_at == T_ACTIVATE


def test_receipts_are_frozen(world_and_receipts):
    _, _, issuance, activation = world_and_receipts
    with pytest.raises(dataclasses.FrozenInstanceError):
        issuance.record_id = "other"
    with pytest.raises(dataclasses.FrozenInstanceError):
        activation.activated_entries = ()


def _issuance_kwargs(receipt, **overrides):
    fields = {
        f.name: getattr(receipt, f.name) for f in dataclasses.fields(IssuanceReceipt)
    }
    fields.update(overrides)
    return fields


@pytest.mark.parametrize(
    "overrides",
    [
        dict(record_id=""),
        dict(coordinate="not-a-coordinate"),
        dict(policy_body_digest="zz"),
        dict(key_id=7),
        dict(approval_digest="not-hex"),
        dict(issued_at=datetime(2026, 9, 1)),
    ],
    ids=["empty-record-id", "loose-coordinate", "short-digest", "non-str-key-id",
         "non-hex-digest", "naive-instant"],
)
def test_issuance_receipt_validation_refuses_alien_content(
    world_and_receipts, overrides
):
    _, _, receipt, _ = world_and_receipts
    with pytest.raises(ActivationRequestError):
        IssuanceReceipt(**_issuance_kwargs(receipt, **overrides))


@pytest.mark.parametrize(
    "entries",
    [
        [("t", "r")],
        (("only-one",),),
        ((1, "r"),),
        (("", "r"), ("", "r")),
        (("", "z-role"), ("", "a-role")),
        (("tenant-9", "r"),),
    ],
    ids=["list-not-tuple", "short-entry", "non-str-tenant", "duplicate",
         "descending", "foreign-tenant"],
)
def test_activation_receipt_validation_refuses_alien_entries(
    world_and_receipts, entries
):
    _, record, _, _ = world_and_receipts
    with pytest.raises(ActivationRequestError):
        ActivationReceipt(
            record_id=record.record_id,
            coordinate=record.coordinate,
            activated_entries=entries,
            activated_at=T_ACTIVATE,
        )


def test_activation_receipt_requires_a_tzaware_instant(world_and_receipts):
    _, record, _, _ = world_and_receipts
    with pytest.raises(ActivationRequestError):
        ActivationReceipt(
            record_id=record.record_id,
            coordinate=record.coordinate,
            activated_entries=((GLOBAL_TENANT, GOVERNED_ROLE_REF),),
            activated_at=T_ISSUE.replace(tzinfo=None) + timedelta(hours=1),
        )
