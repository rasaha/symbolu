"""The record: derivation, verification, the constants, and the refusals."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from _fixtures import OTHER, TENANT, document, draft
from ugence_workflow_drafts import (
    CLAIMED_OWNER_ASSURANCE,
    CONTRACT_VERSION,
    LIFECYCLE,
    LIMITS,
    ContractViolation,
    DraftSupersessionError,
    WorkflowDraft,
    canonical_text,
    draft_from_record,
    draft_id_for,
    draft_record,
    require_admissible_supersession,
    revision_digest,
    revision_digest_of,
    supersession_refusals,
    workflow_digest,
)


def test_the_digest_is_the_studios_own_canonical_encoding():
    """serialization/canonical.py: sorted keys, two-space indent, ensure_ascii off,
    trailing newline, ``sha256:`` prefix — so one digest of record, computed three ways."""

    doc = document(name="Ünïcode")
    text = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    assert canonical_text(doc) == text
    assert workflow_digest(doc) == "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert draft().workflow_digest == workflow_digest(document())
    assert draft().workflow_text == canonical_text(document())


def test_the_id_is_derived_never_chosen_and_the_digest_never_asserted():
    d = draft()
    assert d.draft_id.startswith("wfd_") and len(d.draft_id) == 36
    assert d.draft_id == draft_id_for(TENANT, revision_digest(d), "")
    assert draft() == d  # deterministic: no clock, no uuid
    with pytest.raises(ContractViolation, match="never chosen"):
        WorkflowDraft(draft_id="wfd_" + "0" * 32, tenant_id=TENANT, title="t",
                      contract_version="workflow_ir.v2", workflow=document(),
                      workflow_digest=d.workflow_digest)
    with pytest.raises(ContractViolation, match="does not match"):
        WorkflowDraft(draft_id="", tenant_id=TENANT, title="t", contract_version="workflow_ir.v2",
                      workflow=document(), workflow_digest="sha256:" + "0" * 64)


def test_a_revision_that_changes_anything_is_a_different_draft():
    base = draft()
    for over in ({"title": "Renamed"}, {"workflow": document(extra=1)},
                 {"claimed_owner_ref": "directory://people/owner-2"},
                 {"notes": "a note"}, {"contract_version": "workflow_ir.v1"},
                 {"registration_ref": "reg_" + "a" * 32, "registration_digest": "b" * 64},
                 {"supersedes": "wfd_" + "c" * 32}):
        assert draft(**over).draft_id != base.draft_id, over
    assert revision_digest_of(title="x", contract_version="workflow_ir.v1",
                              workflow_digest_value="sha256:" + "0" * 64) != revision_digest(base)


def test_lifecycle_and_assurance_are_constants_not_fields():
    d = draft()
    assert d.lifecycle == LIFECYCLE == "DRAFT"
    assert d.claimed_owner_assurance == CLAIMED_OWNER_ASSURANCE == "PRESENTED_UNPROVEN"
    names = {f.name for f in dataclasses.fields(WorkflowDraft)}
    assert "lifecycle" not in names and "claimed_owner_assurance" not in names
    assert "status" not in names and "approved" not in names
    assert d.__dataclass_params__.frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.title = "changed"  # type: ignore[misc]
    record = draft_record(d)
    assert record["draft"]["lifecycle"] == "DRAFT"
    assert record["draft"]["claimed_owner_assurance"] == "PRESENTED_UNPROVEN"
    assert record["draft"]["record_version"] == CONTRACT_VERSION


def test_a_record_round_trips_and_a_tampered_one_cannot_reconstruct():
    d = draft(notes="first", registration_ref="reg_" + "a" * 32, registration_digest="b" * 64)
    record = json.loads(json.dumps(draft_record(d)))
    assert draft_from_record(record) == d
    assert draft_from_record(record).record_digest() == d.record_digest()
    for mutate in (lambda r: r["draft"].__setitem__("title", "Tampered"),
                   lambda r: r["workflow"].__setitem__("nodes", []),
                   lambda r: r["draft"].__setitem__("lifecycle", "APPROVED"),
                   lambda r: r["draft"].__setitem__("claimed_owner_assurance", "IDP_AUTHENTICATED"),
                   lambda r: r["draft"].__setitem__("tenant_id", OTHER),
                   lambda r: r["draft"].__setitem__("record_version", "workflow_draft.v2")):
        broken = json.loads(json.dumps(record))
        mutate(broken)
        with pytest.raises(ContractViolation):
            draft_from_record(broken)
    with pytest.raises(ContractViolation):
        draft_from_record({"draft": {}})


@pytest.mark.parametrize("over,message", [
    ({"title": ""}, "title"),
    ({"title": "x" * (LIMITS["title_chars"] + 1)}, "title"),
    ({"title": "two\nlines"}, "single line"),
    ({"tenant_id": " "}, "tenant_id"),
    ({"contract_version": "workflow_ir.v9"}, "contract_version"),
    ({"contract_version": ""}, "contract_version"),
    ({"workflow": {}}, "non-empty JSON object"),
    ({"workflow": []}, "non-empty JSON object"),
    ({"workflow": {"blob": "x" * LIMITS["workflow_bytes"]}}, "exceed the limit"),
    ({"registration_ref": "reg_x"}, "travel together"),
    ({"registration_digest": "b" * 64}, "travel together"),
    ({"registration_ref": "reg_x", "registration_digest": "not-hex"}, "64 lowercase hex"),
    ({"supersedes": "reg_" + "0" * 32}, "must name a draft id"),
    ({"claimed_owner_ref": "x" * (LIMITS["ref_chars"] + 1)}, "claimed_owner_ref"),
    ({"notes": "x" * (LIMITS["notes_chars"] + 1)}, "notes"),
])
def test_structurally_invalid_input_is_a_typed_refusal(over, message):
    with pytest.raises(ContractViolation, match=message):
        draft(**over)


def test_supersession_rules_are_linear_and_require_a_change():
    first = draft()
    assert supersession_refusals(first, None) == ()
    successor = draft(title="Revised", supersedes=first.draft_id)
    assert supersession_refusals(successor, first) == ()
    (missing,) = supersession_refusals(successor, None)
    assert "not recorded" in missing
    (wrong,) = supersession_refusals(successor, draft(title="Someone else"))
    assert "not the one supersedes names" in wrong
    foreign = draft(tenant_id=OTHER, title="Revised", supersedes=first.draft_id)
    assert any("another tenant" in r for r in supersession_refusals(foreign, first))
    (taken,) = supersession_refusals(successor, first, "wfd_" + "9" * 32)
    assert "already superseded" in taken
    unchanged = draft(supersedes=first.draft_id)
    (nothing,) = supersession_refusals(unchanged, first)
    assert "changes nothing" in nothing
    with pytest.raises(DraftSupersessionError):
        require_admissible_supersession(unchanged, first)
    require_admissible_supersession(successor, first)


def test_a_draft_cannot_supersede_itself():
    """The id carries ``supersedes``, so self-reference is impossible to construct
    honestly; the refusal exists for a caller that tries anyway."""

    d = draft()
    with pytest.raises(ContractViolation):
        WorkflowDraft(draft_id=d.draft_id, tenant_id=TENANT, title=d.title,
                      contract_version=d.contract_version, workflow=d.workflow,
                      workflow_digest=d.workflow_digest, claimed_owner_ref=d.claimed_owner_ref,
                      supersedes=d.draft_id, recorded_by=d.recorded_by, validated_by=d.validated_by)
