"""
deterministic_fields.py — EXACT field extraction from the exact slot records (no learning).

Every field in this contract is a deterministic function of the exact evidence retained in the
bounded P5 slots. We read the exact SlotRecord fields (the ledger preserves them) and compute the
typed value — bounded O(K), never N×N. Where a field's required evidence is absent from the working
set, the extractor returns the field's UNKNOWN / MISSING state (never a confident guess). This is the
F1 arm; F5 restricts each extractor to its contract-eligible masked subset.
"""
from __future__ import annotations

from typing import Dict, List

from experiments.enterprise_slots_quadratic.schema import (Evidence, ACTIVE, SUPERSEDED,
                                                           SUBJECT_TYPES, RELATION_TYPES, OBJECT_TYPES)
from experiments.enterprise_slots_quadratic.dataset import N_TIERS
from .field_contracts import (BUDGET_STATUS, POLICY_STATUS, APPROVAL_REQUIREMENT, APPROVAL_EVIDENCE,
                              MATERIAL_CONFLICT, EVIDENCE_COMPLETE)

RT = {n: i for i, n in enumerate(RELATION_TYPES)}
OT = {n: i for i, n in enumerate(OBJECT_TYPES)}
BUDGET_THRESHOLD = 1


def _idx(vocab, name):
    return vocab.index(name)


def extract_fields(slots: List[Evidence], query_req: int, table, contract_cfg) -> Dict[str, int]:
    """Return each field as its typed vocab index, computed exactly from the exact slot records."""
    # deterministic sub-queries over the bounded slot set (O(K))
    budget = next((e for e in slots if e.relation_type == RT["has_budget"] and e.subject_id == query_req), None)
    gov = [e for e in slots if e.relation_type == RT["governed_by"] and e.object_type == OT["Policy"]]
    active_pols = [e for e in slots if e in gov and e.status == ACTIVE]
    approvals = [e for e in slots if e.relation_type == RT["authorized_by"] and e.subject_id == query_req
                 and e.status == ACTIVE]

    # budget_status
    if budget is None:
        budget_status = _idx(BUDGET_STATUS, "MISSING")
        tier = None
    else:
        tier = budget.object_id_or_value
        budget_status = _idx(BUDGET_STATUS, "SUFFICIENT" if tier >= BUDGET_THRESHOLD else "INSUFFICIENT")

    # active_policy_status + material_conflict (relational but exactly computable over slots)
    versions = {e.version for e in active_pols}
    if not active_pols:
        policy_status = _idx(POLICY_STATUS, "MISSING"); version = None; conflict = False
    elif len(versions) > 1:
        policy_status = _idx(POLICY_STATUS, "CONFLICTED"); version = max(versions); conflict = True
    else:
        policy_status = _idx(POLICY_STATUS, "IDENTIFIED"); version = max(versions); conflict = False
    material_conflict = _idx(MATERIAL_CONFLICT, "YES" if conflict else "NO")

    # evidence_complete
    complete = budget is not None and active_pols and not conflict
    evidence_complete = _idx(EVIDENCE_COMPLETE, "YES" if complete else "NO")

    # approval_requirement (deterministic given tier+version)
    if tier is None or version is None:
        approval_requirement = _idx(APPROVAL_REQUIREMENT, "UNKNOWN")
        required_role = None
    else:
        required_role = table[version][tier]
        approval_requirement = _idx(APPROVAL_REQUIREMENT, f"ROLE_{required_role}")

    # approval_evidence_status (match an approval record to the required role)
    if required_role is None:
        approval_evidence = _idx(APPROVAL_EVIDENCE, "UNKNOWN")
    else:
        matches = [e for e in approvals if e.object_id_or_value == required_role]
        others = [e for e in approvals if e.object_id_or_value != required_role]
        if matches and others:
            approval_evidence = _idx(APPROVAL_EVIDENCE, "CONFLICTED")
        elif matches:
            approval_evidence = _idx(APPROVAL_EVIDENCE, "PRESENT_VALID")
        else:
            approval_evidence = _idx(APPROVAL_EVIDENCE, "MISSING")

    return {"budget_status": budget_status, "active_policy_status": policy_status,
            "approval_requirement": approval_requirement, "approval_evidence_status": approval_evidence,
            "material_conflict": material_conflict, "evidence_complete": evidence_complete}
