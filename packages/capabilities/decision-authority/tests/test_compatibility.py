"""Phase 5E — backward-compatibility guards for the frozen serialization surface.

The serialized *shape* (the field-name set) of every public contract is frozen: a
change to it is a MAJOR release (it breaks persisted/serialized data). This pins
the shape fingerprint and checks representative round-trips, complementing the
pinned content hashes in ``test_kernel_extraction`` (still enforced by the
reference-domain suite) and the frozen vocabulary/lifecycle/port fingerprints.
"""

from __future__ import annotations

from decision_governance.common import canonical_hash
from decision_governance.actions import (
    ActionMapping,
    ActionRequest,
    ContextEnvelopeRecord,
)
from decision_governance.decisions import (
    DecisionCase,
    DecisionRecord,
    RecommendationRecord,
)
from decision_governance.execution import (
    ExecutionIntent,
    ExecutionRecord,
    ReconciliationResult,
)
from decision_governance.ports.linked_record import LinkedRecordSnapshot

SERIALIZATION_SHAPE_FINGERPRINT = (
    "d3401c91e5a297e6dfabd63c48d8245d880004c30dcbeb1c6cea79566a863585")

_PUBLIC_MODELS = [
    DecisionRecord, DecisionCase, RecommendationRecord, ActionRequest, ActionMapping,
    ContextEnvelopeRecord, ExecutionIntent, ExecutionRecord, ReconciliationResult,
    LinkedRecordSnapshot,
]


def test_serialization_shape_is_frozen():
    shape = {m.__name__: sorted(m.model_fields.keys()) for m in _PUBLIC_MODELS}
    assert canonical_hash(shape) == SERIALIZATION_SHAPE_FINGERPRINT


def test_linked_record_snapshot_field_names_are_stable():
    # Explicit human-readable guard on the most consumer-facing contract.
    assert set(LinkedRecordSnapshot.model_fields) == {
        "record_type", "record_id", "version", "tenant_id", "status",
        "content_hash", "subject_ref", "policy_refs", "created_at", "metadata"}


def test_representative_round_trip_is_lossless():
    snap = LinkedRecordSnapshot(
        record_type="assessment", record_id="a1", version=2, tenant_id="t",
        status="FINALIZED", subject_ref="s1", metadata={"blocked": "true"})
    assert LinkedRecordSnapshot(**snap.model_dump()) == snap
