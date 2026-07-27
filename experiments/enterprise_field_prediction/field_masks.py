"""
field_masks.py — bounded, contract-eligible evidence subset per field (§9).

Each field may read only the slots its contract deems eligible, selected using ONLY runtime-observable
schema fields: evidence relation type, subject linkage to the query anchor, object type, version/status
metadata. No final labels, required-evidence annotations, oracle field values, or answer-derived
features are used — auditable exactly like the validated slot-policy leak test. The masks shrink each
field's effective working set (smaller sufficient sets) without enlarging K.
"""
from __future__ import annotations

from typing import Dict, List

from experiments.enterprise_slots_quadratic.schema import Evidence, RELATION_TYPES, OBJECT_TYPES

RT = {n: i for i, n in enumerate(RELATION_TYPES)}
OT = {n: i for i, n in enumerate(OBJECT_TYPES)}


def _eligible(field: str, e: Evidence, query_req: int) -> bool:
    if field == "budget_status":
        return e.relation_type == RT["has_budget"] and e.subject_id == query_req
    if field in ("active_policy_status", "material_conflict"):
        return e.relation_type == RT["governed_by"] and e.object_type == OT["Policy"]
    if field == "approval_evidence_status":
        return e.relation_type == RT["authorized_by"] and e.subject_id == query_req
    if field in ("approval_requirement", "evidence_complete"):
        # need both the budget and the active policy — eligible = either of those record kinds
        return ((e.relation_type == RT["has_budget"] and e.subject_id == query_req)
                or (e.relation_type == RT["governed_by"] and e.object_type == OT["Policy"]))
    return True


def field_mask(field: str, slots: List[Evidence], query_req: int) -> List[bool]:
    return [_eligible(field, e, query_req) for e in slots]


def masked_slots(field: str, slots: List[Evidence], query_req: int) -> List[Evidence]:
    return [e for e, keep in zip(slots, field_mask(field, slots, query_req)) if keep]
