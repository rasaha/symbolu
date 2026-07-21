"""
Input validation for the Governance Truth layer.

TAP-E4 consumes three upstream records through their frozen public interfaces. Before
resolving governance we assert the inputs are internally coherent (correct schema
versions, referential consistency, provenance attached). This never mutates or repairs
upstream records — it only refuses to run on malformed input.
"""

from __future__ import annotations

from typing import List, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import IntentRecord
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import RetrievalRecord
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    RelationshipRecord, SCHEMA_VERSION as E3_SCHEMA_VERSION,
)


def validate_inputs(intent: IntentRecord, retrieval: RetrievalRecord,
                    relationship: RelationshipRecord) -> Tuple[bool, Tuple[str, ...]]:
    problems: List[str] = []
    if not intent.request_id:
        problems.append("intent has empty request_id")
    if not retrieval.retrieval_id:
        problems.append("retrieval has empty retrieval_id")
    if relationship.schema_version != E3_SCHEMA_VERSION:
        problems.append("relationship schema_version mismatch")
    if not relationship.relationship_record_id:
        problems.append("relationship has empty relationship_record_id")
    # referential consistency: the relationship record must descend from this retrieval
    if (relationship.retrieval_record_id
            and relationship.retrieval_record_id != retrieval.retrieval_id):
        problems.append("relationship.retrieval_record_id does not match retrieval")
    for a in relationship.relationship_assertions:
        if not a.source_provenance:
            problems.append(f"assertion {a.assertion_id} lacks provenance")
        if not a.evidence_unit_ids:
            problems.append(f"assertion {a.assertion_id} lacks evidence_unit_ids")
    return (not problems, tuple(problems))


def require_valid(intent: IntentRecord, retrieval: RetrievalRecord,
                  relationship: RelationshipRecord) -> None:
    ok, problems = validate_inputs(intent, retrieval, relationship)
    if not ok:
        raise ValueError(f"invalid TAP-E4 inputs: {problems}")
