"""G4 — the neutral audit reference: structure, determinism, and the lines it holds.

These tests prove the family rejects a malformed reference at construction,
canonicalizes deterministically across offsets, never reads a clock, leaves every
frozen provider dataclass untouched — and, the part that matters most for G4,
does **not** mint a second evidence reference or a second event vocabulary.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

import ugence_governance_contracts as g
from ugence_governance_contracts import api
from ugence_governance_contracts.contracts.audit import (
    AuditContractError,
    AuditReference,
)

_T0 = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
_IST = timezone(timedelta(hours=5, minutes=30))
_DIGEST = "a" * 64
_OTHER_DIGEST = "b" * 64


def _ref(**overrides) -> AuditReference:
    fields = dict(tenant_id="tenant-a",
                  store_ref="ugence_approval_workflow:ledger_events",
                  entry_ref="apr_1:3", entry_digest=_DIGEST)
    fields.update(overrides)
    return AuditReference(**fields)


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_a_reference_names_a_store_an_entry_and_a_digest():
    ref = _ref(correlation_id="corr-9", recorded_at=_T0)
    assert ref.tenant_id == "tenant-a"
    assert ref.store_ref == "ugence_approval_workflow:ledger_events"
    assert ref.entry_ref == "apr_1:3" and ref.entry_digest == _DIGEST
    assert ref.correlation_id == "corr-9" and ref.recorded_at == _T0
    assert [f.name for f in dataclasses.fields(ref)] == [
        "tenant_id", "store_ref", "entry_ref", "entry_digest",
        "correlation_id", "recorded_at"]


def test_every_locating_field_is_required():
    for field in ("tenant_id", "store_ref", "entry_ref"):
        with pytest.raises(AuditContractError, match=field):
            _ref(**{field: "   "})
        with pytest.raises(AuditContractError, match=field):
            _ref(**{field: None})


def test_the_entry_digest_must_be_a_sha256_hex_digest():
    for bad in ("", "  ", "not-a-digest", _DIGEST.upper(), "a" * 63, "a" * 65):
        with pytest.raises(AuditContractError, match="entry_digest"):
            _ref(entry_digest=bad)
    assert _ref(entry_digest=_DIGEST).entry_digest == _DIGEST


def test_a_naive_recorded_at_is_refused_rather_than_assumed_utc():
    with pytest.raises(AuditContractError, match="timezone-aware"):
        _ref(recorded_at=datetime(2026, 9, 5, 10, 0))
    with pytest.raises(AuditContractError, match="datetime"):
        _ref(recorded_at="2026-09-05T10:00:00Z")
    assert _ref(recorded_at=None).recorded_at is None  # optional, and absent is fine


def test_a_reference_is_frozen():
    ref = _ref()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.entry_digest = _OTHER_DIGEST  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_equal_references_written_with_different_offsets_share_one_digest():
    utc = _ref(recorded_at=_T0)
    ist = _ref(recorded_at=_T0.astimezone(_IST))
    assert utc.recorded_at.utcoffset() != ist.recorded_at.utcoffset()  # same instant
    assert utc.canonical_bytes() == ist.canonical_bytes()
    assert utc.canonical_digest() == ist.canonical_digest()


def test_every_field_participates_in_the_digest():
    base = _ref(correlation_id="corr-9", recorded_at=_T0)
    for changed in (
        _ref(tenant_id="tenant-b", correlation_id="corr-9", recorded_at=_T0),
        _ref(store_ref="ugence_authority_directory:directory_events",
             correlation_id="corr-9", recorded_at=_T0),
        _ref(entry_ref="apr_1:4", correlation_id="corr-9", recorded_at=_T0),
        _ref(entry_digest=_OTHER_DIGEST, correlation_id="corr-9", recorded_at=_T0),
        _ref(correlation_id="corr-8", recorded_at=_T0),
        _ref(correlation_id="corr-9", recorded_at=_T0 + timedelta(seconds=1)),
    ):
        assert changed.canonical_digest() != base.canonical_digest()


def test_the_digest_is_stable_across_constructions():
    assert _ref(recorded_at=_T0).canonical_digest() == _ref(recorded_at=_T0).canonical_digest()


def test_the_family_reads_no_clock():
    from ugence_governance_contracts.contracts import audit

    tree = ast.parse(pathlib.Path(audit.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            assert name not in ("now", "utcnow", "today", "time", "monotonic"), name
            if name == "astimezone":
                assert node.args, "zero-argument astimezone infers the local zone"


# --------------------------------------------------------------------------- #
# Correlation across stores — what G4 is actually for
# --------------------------------------------------------------------------- #
def test_two_references_to_one_entry_are_recognised_across_disagreeing_digests():
    """The point of the contract: spotting that two records cite the same entry,
    and that one of them saw different content."""

    a = _ref()
    b = _ref(entry_digest=_OTHER_DIGEST)
    assert a.points_to_same_entry(b) and b.points_to_same_entry(a)
    assert not a.agrees_with(b)
    assert a.agrees_with(_ref())


def test_references_into_different_stores_never_collide():
    approval = _ref(store_ref="ugence_approval_workflow:ledger_events")
    directory = _ref(store_ref="ugence_authority_directory:directory_events")
    assert not approval.points_to_same_entry(directory)
    with pytest.raises(AuditContractError):
        approval.points_to_same_entry("not-a-reference")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# The lines G4 must not cross
# --------------------------------------------------------------------------- #
def test_no_second_evidence_reference_is_minted():
    """D-4 names an ``AuditRef``/``EvidenceRef`` pair; ``EvidenceReference`` already
    covers the evidence half, so only one evidence reference may exist."""

    evidence_like = [n for n in api.__all__
                     if n.endswith("Reference") and "Evidence" in n]
    assert evidence_like == ["EvidenceReference"]
    assert "EvidenceRef" not in api.__all__ and not hasattr(api, "EvidenceRef")


def test_the_reference_carries_no_entry_body_and_no_event_vocabulary():
    # Pin the field set exactly rather than denying a list of names: a denylist
    # passes for any body-carrying field spelled outside it (``content``,
    # ``details``, …), which is no guard at all for a design invariant.
    names = [f.name for f in dataclasses.fields(AuditReference)]
    assert names == ["tenant_id", "store_ref", "entry_ref", "entry_digest",
                     "correlation_id", "recorded_at"]
    for forbidden in ("body", "payload", "content", "details", "event_type", "message",
                      "previous_event_hash", "chain_head", "actor_id", "new_state"):
        assert forbidden not in names, forbidden
    # No enum ships with this family: the kernel's frozen AuditEventType owns the names.
    from ugence_governance_contracts.contracts import audit

    assert audit.__all__ == ["AuditContractError", "AuditReference"]


def test_the_family_is_not_a_log_a_sink_or_a_verifier():
    surface = {n for n in dir(AuditReference) if not n.startswith("_")}
    for forbidden in ("append", "write", "read", "all", "verify_chain", "flush",
                      "close", "query", "sink"):
        assert forbidden not in surface, forbidden


def test_a_reference_carries_no_identity_of_its_own():
    """It is a value, not an entity: two producers citing one entry agree.

    A synthetic reference id would be minted independently by each producer, so
    two records citing the same entry would digest differently for no reason a
    consumer could act on.
    """

    names = {f.name for f in dataclasses.fields(AuditReference)}
    for synthetic in ("audit_id", "reference_id", "id", "uuid"):
        assert synthetic not in names, synthetic
    # Two producers, same entry, same content -> byte-identical reference.
    assert _ref().canonical_digest() == _ref().canonical_digest()
    assert _ref().canonical_bytes() == _ref().canonical_bytes()


# --------------------------------------------------------------------------- #
# Additive compatibility
# --------------------------------------------------------------------------- #
def test_g4_is_additive_and_the_provider_surface_is_untouched():
    assert g.CONTRACT_VERSION == "1.0.0"
    assert g.__version__ == "0.7.0"
    for name in ("ActionGovernanceRequest", "ActionGovernanceResult",
                 "ExecutionDispatchRequest", "ExecutionDispatchResult",
                 "AssertionGovernanceRequest", "AssertionGovernanceResult"):
        fields = {f.name for f in dataclasses.fields(getattr(api, name))}
        assert "audit_ref" not in fields and "audit_reference" not in fields, name


def test_the_family_is_exported_where_g7_and_g8_are():
    for name in ("AuditReference", "AuditContractError"):
        assert name in api.__all__
        assert getattr(api, name) is getattr(g, name)
        from ugence_governance_contracts import contracts

        assert name in contracts.__all__
