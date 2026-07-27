"""
relational_fields.py — ownership classification (§8) + the genuinely multi-record predicates.

In this bounded contract the "relational" predicates (material conflict, active-vs-stale version
selection, approval-role match) are still EXACTLY computable from the exact slot records by a bounded
O(K) scan — they need multi-record comparison but not a learned readout. This module documents the
ownership split and exposes the relational predicates so an arm may route only these to the quadratic
block if desired (F2). The empirical finding is that even these are best computed deterministically.
"""
from __future__ import annotations

from typing import List

from experiments.enterprise_slots_quadratic.schema import Evidence, ACTIVE, SUPERSEDED, RELATION_TYPES, OBJECT_TYPES

RT = {n: i for i, n in enumerate(RELATION_TYPES)}
OT = {n: i for i, n in enumerate(OBJECT_TYPES)}

OWNERSHIP = {
    "budget_status": "DETERMINISTIC",         # single record, exact
    "approval_requirement": "DETERMINISTIC",  # table lookup over (version, tier)
    "evidence_complete": "DETERMINISTIC",     # presence check
    "active_policy_status": "RELATIONAL",     # latest-active + conflict across governance records
    "material_conflict": "RELATIONAL",        # >1 active governance record of different version
    "approval_evidence_status": "RELATIONAL", # match approval record to required role
}


def governance_records(slots: List[Evidence]) -> List[Evidence]:
    return [e for e in slots if e.relation_type == RT["governed_by"] and e.object_type == OT["Policy"]]


def is_material_conflict(slots: List[Evidence]) -> bool:
    """Exact O(K) predicate: >1 ACTIVE governance record of differing version."""
    versions = {e.version for e in governance_records(slots) if e.status == ACTIVE}
    return len(versions) > 1
