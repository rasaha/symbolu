"""Policy-object model tests: construction, serialization, ids, provenance,
references, schema versioning, lifecycle."""

from __future__ import annotations

import pytest

from ugence_policy_workflow_compiler.api import (
    AuthorityRequirement,
    AuthorityType,
    DecisionRule,
    PolicyPack,
    PolicyPackStatus,
    ProvenanceStatus,
    SourceDocument,
    ProvenanceSourceType,
    is_legal_transition,
)
from ugence_policy_workflow_compiler.models.policy_pack import IllegalLifecycleTransition
from ugence_policy_workflow_compiler.serialization import canonical_json, hashing


def test_object_has_stable_identity_fields():
    a = AuthorityRequirement(
        object_id="a.1", name="approver", decision_scope="x",
        authority_type=AuthorityType.HUMAN_APPROVER, provenance_refs=("s",),
    )
    assert a.object_id == "a.1"
    assert a.object_type.value == "AUTHORITY_REQUIREMENT"
    assert a.version == 1
    assert a.enabled is True


def test_models_are_frozen():
    a = AuthorityRequirement(object_id="a.1", name="x", decision_scope="x")
    with pytest.raises(Exception):
        a.name = "y"


def test_extra_fields_forbidden():
    with pytest.raises(Exception):
        AuthorityRequirement(object_id="a.1", name="x", decision_scope="x", bogus=1)


def test_provenance_status():
    with_prov = AuthorityRequirement(
        object_id="a.1", name="x", decision_scope="x", provenance_refs=("s",)
    )
    without = AuthorityRequirement(object_id="a.2", name="x", decision_scope="x")
    assert with_prov.provenance_status is ProvenanceStatus.SOURCED
    assert without.provenance_status is ProvenanceStatus.PROPOSED_ONLY


def test_deterministic_serialization(synthetic_pack):
    a = canonical_json.dumps(synthetic_pack)
    b = canonical_json.dumps(synthetic_pack)
    assert a == b
    # digest stable
    assert hashing.digest(synthetic_pack) == hashing.digest(synthetic_pack)


def test_object_index_and_iteration(synthetic_pack):
    index = synthetic_pack.object_index()
    assert "rule.1" in index
    assert "auth.1" in index
    ids = [o.object_id for o in synthetic_pack.all_objects()]
    assert len(ids) == len(set(ids))  # no duplicates in a well-formed pack


def test_schema_version_default(synthetic_pack):
    assert synthetic_pack.schema_version == "policy_pack.v1"


def test_lifecycle_legal_and_illegal_transitions():
    assert is_legal_transition(PolicyPackStatus.APPROVED, PolicyPackStatus.COMPILED)
    assert not is_legal_transition(PolicyPackStatus.DRAFT, PolicyPackStatus.RELEASED)
    assert not is_legal_transition(PolicyPackStatus.REVIEW_REQUIRED, PolicyPackStatus.COMPILED)
    assert not is_legal_transition(PolicyPackStatus.INVALID, PolicyPackStatus.APPROVED)


def test_with_status_rejects_illegal():
    pack = PolicyPack(pack_id="p", name="n", status=PolicyPackStatus.DRAFT)
    with pytest.raises(IllegalLifecycleTransition):
        pack.with_status(PolicyPackStatus.RELEASED)


def test_with_status_allows_legal():
    pack = PolicyPack(pack_id="p", name="n", status=PolicyPackStatus.APPROVED)
    compiled = pack.with_status(PolicyPackStatus.COMPILED)
    assert compiled.status is PolicyPackStatus.COMPILED
    assert pack.status is PolicyPackStatus.APPROVED  # original unchanged (frozen)


def test_source_document_type():
    d = SourceDocument(
        object_id="s", name="doc", source_type=ProvenanceSourceType.REGULATION,
        title="Reg 1",
    )
    assert d.object_type.value == "SOURCE_DOCUMENT"


def test_round_trip_validate(synthetic_pack):
    dumped = canonical_json.dumps(synthetic_pack)
    restored = PolicyPack.model_validate(canonical_json.loads(dumped))
    assert canonical_json.dumps(restored) == dumped
