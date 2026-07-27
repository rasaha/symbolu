"""
duplicate_equivalence.py — explicit evidence-equivalence logic (§9/§10) replacing unsafe semantic
dedup. Classifies a candidate pair and permits AUTOMATIC collapse ONLY for EXACT_DUPLICATE and
SOURCE_REDUNDANT (provenance preserved). Active/stale, conflict pairs, qualifier changes, and
distinct validity windows are NEVER collapsed. Every collapse decision is auditable.
"""
from __future__ import annotations

from typing import Dict, List

from experiments.enterprise_slots_quadratic.schema import Evidence, ACTIVE, SUPERSEDED

EXACT_DUPLICATE, SOURCE_REDUNDANT, SEMANTICALLY_SIMILAR_BUT_DISTINCT, CONFLICT_PAIR, \
    VERSION_PAIR, NON_DUPLICATE = ("EXACT_DUPLICATE", "SOURCE_REDUNDANT",
                                   "SEMANTICALLY_SIMILAR_BUT_DISTINCT", "CONFLICT_PAIR",
                                   "VERSION_PAIR", "NON_DUPLICATE")
COLLAPSIBLE = {EXACT_DUPLICATE, SOURCE_REDUNDANT}


def _core(e: Evidence):
    return (e.tenant_id, e.subject_type, e.subject_id, e.relation_type,
            e.object_type, e.object_id_or_value)


def classify_pair(a: Evidence, b: Evidence) -> str:
    if _core(a) != _core(b):
        # same (subject, relation) but different object with both active ⇒ material conflict
        if (a.tenant_id, a.subject_type, a.subject_id, a.relation_type) == \
           (b.tenant_id, b.subject_type, b.subject_id, b.relation_type):
            if a.status == ACTIVE and b.status == ACTIVE and a.object_id_or_value != b.object_id_or_value:
                return CONFLICT_PAIR
            return SEMANTICALLY_SIMILAR_BUT_DISTINCT
        return NON_DUPLICATE
    # same core fact from here
    if a.version != b.version or {a.status, b.status} == {ACTIVE, SUPERSEDED}:
        return VERSION_PAIR                                      # active/stale or version differs
    if a.status != b.status:
        return VERSION_PAIR
    if (a.valid_from, a.valid_to) != (b.valid_from, b.valid_to):
        return SEMANTICALLY_SIMILAR_BUT_DISTINCT                 # different validity windows
    if abs(a.source_authority - b.source_authority) > 1e-9 or a.document_id != b.document_id:
        return SOURCE_REDUNDANT                                  # same fact, different source
    return EXACT_DUPLICATE


def dedup(slot_ids: List[int], id_of: Dict[int, Evidence]):
    """Collapse ONLY EXACT_DUPLICATE / SOURCE_REDUNDANT; keep the highest-authority representative.
    Returns (kept_ids, audit) where audit records each collapse decision with its classification."""
    kept: List[int] = []
    audit: List[Dict] = []
    for eid in slot_ids:
        e = id_of[eid]; collapsed = False
        for k in kept:
            cls = classify_pair(e, id_of[k])
            if cls in COLLAPSIBLE:
                keep, drop = (eid, k) if e.source_authority > id_of[k].source_authority else (k, eid)
                audit.append({"kind": cls, "kept": keep, "dropped": drop,
                              "provenance_preserved": True})
                if keep == eid:
                    kept[kept.index(k)] = eid
                collapsed = True
                break
        if not collapsed:
            kept.append(eid)
    return kept, audit
