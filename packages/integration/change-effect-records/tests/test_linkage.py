"""The linkage-entry contracts: what they declare, and what they refuse to imply.

Item 3.4 declares how a record *would* be appended. These tests hold the two things
that matter: the declaration is complete and checkable, and it claims nothing about the
existing ledger's ability to host the graph.
"""

from __future__ import annotations

import pytest

from ugence_change_effect_records import RECORD_TYPES, ContractViolation
from ugence_change_effect_records import linkage


def test_every_record_type_has_exactly_one_linkage_kind():
    assert set(linkage.LINKAGE_KINDS) == {cls.__name__ for cls in RECORD_TYPES}
    assert len(set(linkage.LINKAGE_KINDS.values())) == 13, "no two types share a kind"


def test_every_kind_is_prefixed_and_versioned():
    for name, kind in linkage.LINKAGE_KINDS.items():
        assert kind.startswith(linkage.LINKAGE_KIND_PREFIX + "."), name
        assert kind.endswith(".v1"), name


def test_the_kind_lookup_takes_a_type_name_and_not_a_record():
    """It cannot be handed a record, so it cannot be mistaken for a writer."""

    assert linkage.entry_kind_for("ClassificationRecord").endswith("classification.v1")
    with pytest.raises(ContractViolation):
        linkage.entry_kind_for("NotARecordType")
    with pytest.raises(ContractViolation):
        linkage.entry_kind_for("")


def test_the_payload_is_a_locator_and_not_a_copy_of_the_record():
    """The entry names the record by digest; it does not restate its contents."""

    keys = set(linkage.linkage_payload_keys())
    assert keys == {
        "chain_id", "record_digest", "predecessor_digest", "transition_kind",
        "contract_version"}
    for leaked in ("results", "blocking_obligations", "bundle", "delta_digest", "signer"):
        assert leaked not in keys


def test_the_uniqueness_constraint_is_the_rule_s_triple():
    assert linkage.UNIQUENESS_CONSTRAINT == (
        "chain_id", "predecessor_digest", "transition_kind")


def test_the_two_transition_kinds_that_carry_a_discriminator_carry_it():
    """One-opening-per-obligation and reserve-per-authorization are the same constraint,
    not second mechanisms, which is only true if the discriminator is in the kind."""

    kinds = linkage.TRANSITION_KINDS
    assert "INVESTIGATION_OPEN:<obligation_id>" in kinds
    assert "ADMISSION_RESERVE:<authorization_digest>" in kinds


def test_every_required_capability_is_a_declared_gap_and_says_why():
    assert set(linkage.REQUIRED_AUDIT_ROOT_CAPABILITIES) == {
        "ATOMIC_CONDITIONAL_APPEND",
        "LINEARIZABLE_CHAIN_HEAD",
        "LINEARIZABLE_CONTROL_REGISTER",
        "LINEARIZABLE_TARGET_VERSION_REGISTRY",
    }
    for name, (status, guarantee, why) in linkage.REQUIRED_AUDIT_ROOT_CAPABILITIES.items():
        assert status == "DECLARED_GAP", name
        assert guarantee.endswith(".") and why.endswith("."), name


def test_declaring_a_kind_claims_nothing_about_the_existing_ledger():
    """The module must not be readable as "the ledger can host this"."""

    source = (linkage.__file__)
    text = open(source, encoding="utf-8").read().lower()
    assert "appends nothing" in text
    assert "has not been shown to" in text
    assert "declared_gap" in text


def test_the_fail_closed_refusal_is_named():
    assert linkage.CAPABILITY_UNAVAILABLE_REFUSAL == "APPEND_UNIQUENESS_UNAVAILABLE"


def test_the_entry_contract_is_bound_but_never_instantiated():
    """Bound so the declaration is checkable against a real type; never constructed."""

    from ugence_control_plane_root import LedgerEntry

    assert linkage.LINKAGE_ENTRY_CONTRACT is LedgerEntry
    assert "kind" in LedgerEntry.__dataclass_fields__, (
        "the kinds declared here are LedgerEntry.kind values")
    assert "payload" in LedgerEntry.__dataclass_fields__


def test_the_linkage_tables_are_read_only():
    with pytest.raises(TypeError):
        linkage.LINKAGE_KINDS["ClassificationRecord"] = "x"  # type: ignore[index]
    with pytest.raises(TypeError):
        linkage.REQUIRED_AUDIT_ROOT_CAPABILITIES["X"] = ()  # type: ignore[index]


def test_linkage_is_not_re_exported_from_the_package_surface():
    """The curated API is record shapes. Reaching the ledger declaration is deliberate.

    Keeping it off ``__all__`` means a caller who wants it imports the module by name,
    which is a visible act in a diff rather than an incidental one.
    """

    import ugence_change_effect_records as pkg

    for symbol in ("LINKAGE_KINDS", "entry_kind_for", "REQUIRED_AUDIT_ROOT_CAPABILITIES"):
        assert symbol not in pkg.__all__
