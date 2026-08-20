"""Both committed inventories are re-derived from the live surface and compared."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib

import pytest

import _builders as fx
from ugence_benchmark_registry_authority import api
from ugence_benchmark_registry_authority.contracts.canonical import (
    _contract_type_registry_snapshot,
)

PKG = pathlib.Path(__file__).resolve().parents[2]
CONTRACTS = json.loads((PKG / "public_contract_inventory.json").read_text())
DOMAINS = json.loads((PKG / "canonical_domain_inventory.json").read_text())
VECTORS = json.loads((PKG / "pinned_canonical_vectors.json").read_text())

ROWS = {row["class_name"]: row for row in CONTRACTS["public_data_contracts"]}
BUILDERS = dict(fx.PINNED_VECTOR_BUILDERS)


def _root_classes():
    return {
        cls.__name__: domain
        for cls, (domain, root_ok) in _contract_type_registry_snapshot().items()
        if root_ok
    }


# --------------------------------------------------------------------------- #
# Canonical-domain inventory
# --------------------------------------------------------------------------- #
def test_happy_the_domain_inventory_equals_the_sealed_registry():
    assert DOMAINS["root_canonicalizable"] == _root_classes()


def test_the_domain_inventory_lists_the_three_nested_only_br1_classes():
    assert DOMAINS["nested_admissible_only"] == [
        "BenchmarkApplicabilityCoordinate",
        "BenchmarkCoordinate",
        "BenchmarkScope",
    ]


def test_every_shipped_class_has_exactly_one_distinct_domain():
    domains = list(DOMAINS["root_canonicalizable"].values())
    assert len(domains) == 18
    assert len(set(domains)) == 18


def test_the_domain_inventory_matches_the_pinned_domain_tuple():
    assert set(DOMAINS["root_canonicalizable"].values()) == set(
        api.BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS
    )


def test_no_domain_exists_for_an_artifact_that_does_not_exist():
    for name in DOMAINS["root_canonicalizable"]:
        assert hasattr(api, name), name


def test_the_reserved_authority_issued_names_have_no_domain():
    for reserved in api.BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES:
        assert reserved not in DOMAINS["root_canonicalizable"]


def test_the_post_admission_rejection_payload_appears_in_the_domain_inventory():
    assert (
        "BenchmarkPostAdmissionRejectionEventPayload"
        in DOMAINS["root_canonicalizable"]
    )


# --------------------------------------------------------------------------- #
# Pinned canonical vectors
# --------------------------------------------------------------------------- #
def test_there_is_one_pinned_vector_per_shipped_artifact():
    assert set(VECTORS["vectors"]) == set(_root_classes())


@pytest.mark.parametrize("name", sorted(VECTORS["vectors"]))
def test_every_pinned_vector_reproduces_and_its_digest_recomputes(name):
    raw = api.canonical_bytes(BUILDERS[name]())
    assert raw.decode("utf-8") == VECTORS["vectors"][name]["canonical_bytes"]
    assert hashlib.sha256(raw).hexdigest() == VECTORS["vectors"][name]["digest"]


def test_the_post_admission_rejection_payload_has_a_pinned_vector():
    assert "BenchmarkPostAdmissionRejectionEventPayload" in VECTORS["vectors"]


def test_the_revocation_event_payload_has_a_pinned_vector():
    assert "BenchmarkRevocationEventPayload" in VECTORS["vectors"]


def test_every_pinned_digest_is_distinct():
    digests = [v["digest"] for v in VECTORS["vectors"].values()]
    assert len(set(digests)) == len(digests)


# --------------------------------------------------------------------------- #
# Public-contract inventory — every column re-derived
# --------------------------------------------------------------------------- #
def test_there_is_one_row_per_shipped_data_contract():
    assert set(ROWS) == set(_root_classes())


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_row_records_the_live_domain_and_fields(name):
    row = ROWS[name]
    instance = BUILDERS[name]()
    assert row["digest_domain"] == _root_classes()[name]
    assert row["fields"] == [f.name for f in dataclasses.fields(instance)]
    assert row["caller_constructible"] is True
    assert row["canonicalizable"] is True


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_row_records_the_live_false_trust_properties(name):
    instance = BUILDERS[name]()
    for prop in ROWS[name]["permanently_false_trust_properties"]:
        assert getattr(instance, prop) is False
    for prop in api.BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES:
        assert prop in ROWS[name]["permanently_false_trust_properties"]


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_row_records_the_live_declared_recorded_at_presence(name):
    instance = BUILDERS[name]()
    present = "declared_recorded_at" in {
        f.name for f in dataclasses.fields(instance)
    }
    assert ROWS[name]["carries_declared_recorded_at"] is present


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_row_records_the_live_terminality(name):
    instance = BUILDERS[name]()
    assert ROWS[name]["terminal"] is bool(getattr(instance, "is_terminal", False))


@pytest.mark.parametrize("name", sorted(ROWS))
def test_no_row_declares_a_caller_supplied_upstream_digest(name):
    assert ROWS[name]["caller_supplied_upstream_digest_fields"] == []


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_rows_derived_digest_properties_are_live_read_only_properties(name):
    cls = type(BUILDERS[name]())
    for prop in ROWS[name]["derived_digest_properties"]:
        descriptor = getattr(cls, prop)
        assert isinstance(descriptor, property)
        assert descriptor.fset is None


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_rows_prev_event_digest_rule_matches_live_behaviour(name):
    instance = BUILDERS[name]()
    rule = ROWS[name]["prev_event_digest_rule"]
    if not hasattr(instance, "prev_event_digest"):
        assert rule.startswith("not applicable")
        return
    if instance.prev_event_digest is None:
        assert rule.startswith("None")
    else:
        assert rule.startswith("equals the independently recomputed")


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_rows_reachable_actor_identities_actually_resolve(name):
    instance = BUILDERS[name]()
    for actor in ROWS[name]["mechanically_reachable_actor_identities"]:
        assert isinstance(getattr(instance, actor), str)


def test_the_chain_rows_record_their_exact_transition_and_predecessor():
    expected = {
        "BenchmarkSubmissionRecordPayload": ("initial -> SUBMITTED", None, None),
        "BenchmarkPostAdmissionRejectionEventPayload": (
            "ADMITTED -> REJECTED",
            "ADMITTED",
            "ADMITTED",
        ),
        "BenchmarkRegistrationEventPayload": (
            "ADMITTED -> REGISTERED",
            "ADMITTED",
            "ADMITTED",
        ),
        "BenchmarkRevocationEventPayload": (
            "REGISTERED -> REVOKED",
            "REGISTERED",
            None,
        ),
    }
    for name, (transition, state, outcome) in expected.items():
        row = ROWS[name]
        assert row["transition_represented"] == transition
        assert row["required_predecessor_state"] == state
        assert row["required_predecessor_declared_outcome"] == outcome


def test_the_conflict_record_row_records_that_it_represents_no_transition():
    row = ROWS["BenchmarkConflictRecordPayload"]
    assert row["transition_represented"].startswith("none")
    assert row["required_predecessor_state"] is None


def test_every_row_names_the_later_milestone_that_owns_the_authority_result():
    for name, row in ROWS.items():
        assert row["later_milestone_authority_issued_result"].startswith("BR-2")


def test_the_inventory_documents_that_the_claim_applies_to_data_contracts_only():
    note = CONTRACTS["note"]
    assert "PUBLIC DATA CONTRACTS ONLY" in note
    assert "Protocols, enums, errors, constants" in note


def test_every_other_public_symbol_is_marked_with_its_kind_and_not_canonicalizable():
    others = CONTRACTS["other_public_symbols"]
    assert others
    for row in others:
        assert row["canonicalizable"] is False
        assert row["kind"] in {
            "closed_vocabulary_enum",
            "typed_error",
            "protocol_port",
            "frozen_descriptor",
            "abstract_type_declaration",
            "pure_validation_function",
            "pinned_constant",
        }


def test_the_two_inventories_and_the_api_manifest_agree_on_the_surface():
    manifest = json.loads((PKG / "public_api.json").read_text())
    covered = {row["class_name"] for row in CONTRACTS["public_data_contracts"]} | {
        row["symbol"] for row in CONTRACTS["other_public_symbols"]
    }
    assert covered == set(manifest["symbols"])


def test_the_four_ports_are_marked_as_protocol_ports_not_data_contracts():
    kinds = {
        row["symbol"]: row["kind"] for row in CONTRACTS["other_public_symbols"]
    }
    for port in (
        "BenchmarkRegistryStorePort",
        "BenchmarkPublisherTrustDirectoryPort",
        "BenchmarkApprovalVerifierPort",
        "BenchmarkClockPort",
    ):
        assert kinds[port] == "protocol_port"


def test_the_consistency_descriptor_is_marked_a_frozen_descriptor():
    kinds = {
        row["symbol"]: row["kind"] for row in CONTRACTS["other_public_symbols"]
    }
    assert kinds["BenchmarkRegistryStoreConsistencyDescriptor"] == (
        "frozen_descriptor"
    )
