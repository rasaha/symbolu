"""
Upstream-input validation for TAP-E5.

E5 consumes four frozen upstream records through their public interfaces. Before assembling
we assert the inputs are internally coherent (schema versions and referential consistency).
This never mutates or repairs upstream records — it only refuses to run on malformed input.
"""

from __future__ import annotations

from typing import List, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import IntentRecord
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
    RetrievalRecord, SCHEMA_VERSION as E2_VERSION,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    RelationshipRecord, SCHEMA_VERSION as E3_VERSION,
)
from truth_assurance_pipeline.tap_e4_governance_truth.schema import (
    GovernanceRecord, SCHEMA_VERSION as E4_VERSION,
)


def validate_inputs(intent: IntentRecord, retrieval: RetrievalRecord,
                    relationship: RelationshipRecord,
                    governance: GovernanceRecord) -> Tuple[bool, Tuple[str, ...]]:
    problems: List[str] = []
    if not intent.request_id:
        problems.append("intent has empty request_id")
    if retrieval.schema_version != E2_VERSION:
        problems.append("retrieval schema_version mismatch")
    if relationship.schema_version != E3_VERSION:
        problems.append("relationship schema_version mismatch")
    if governance.schema_version != E4_VERSION:
        problems.append("governance schema_version mismatch")
    if (relationship.retrieval_record_id
            and relationship.retrieval_record_id != retrieval.retrieval_id):
        problems.append("relationship.retrieval_record_id does not match retrieval")
    if (governance.relationship_record_id
            and governance.relationship_record_id != relationship.relationship_record_id):
        problems.append("governance.relationship_record_id does not match relationship")
    return (not problems, tuple(problems))


def require_valid(intent: IntentRecord, retrieval: RetrievalRecord,
                  relationship: RelationshipRecord, governance: GovernanceRecord) -> None:
    ok, problems = validate_inputs(intent, retrieval, relationship, governance)
    if not ok:
        raise ValueError(f"invalid TAP-E5 inputs: {problems}")
