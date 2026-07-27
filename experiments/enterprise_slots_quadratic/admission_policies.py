"""
admission_policies.py — transparent slot admission/eviction strategies (P0–P5).

A policy assigns a RETENTION PRIORITY to each candidate evidence record; when slots overflow, the
lowest-priority record is evicted. P2/P3 use only DETERMINISTIC structural signals (status, version,
authority, relation kind, duplicates) — never task labels. P5 (oracle) may read the required set;
P4 (learned) is trained separately and never alters access control or provenance.
"""
from __future__ import annotations

from typing import Dict, List

from .schema import Evidence, ACTIVE, SUPERSEDED, EXPIRED, REVOKED

CHAIN_RELATIONS = {0, 1, 2, 3, 4}     # requires_approval/has_budget/awarded_to/governed_by/supersedes


def _latest_version_by_key(events: List[Evidence]) -> Dict[tuple, int]:
    best: Dict[tuple, int] = {}
    for e in events:
        k = e.key_tuple()[:3]                       # (subject_type, subject_id, relation_type)
        best[k] = max(best.get(k, -1), e.version)
    return best


def priority(e: Evidence, ctx: Dict, policy: str, required_ids=None) -> float:
    """Higher = more worth retaining. ctx carries cross-record deterministic context."""
    if policy == "P0":                              # FIFO: oldest first out → priority = arrival order
        return float(e.timestamp)
    if policy == "P1":                              # recency: newest wins
        return float(e.timestamp)
    if policy == "P5":                              # oracle: required evidence is paramount
        base = 100.0 if (required_ids and e.evidence_id in required_ids) else 0.0
        return base + float(e.timestamp) * 1e-3
    # P2 / P3 — deterministic enterprise priority (no labels)
    s = 0.0
    if e.relation_type in CHAIN_RELATIONS:
        s += 4.0                                    # required-chain-link kind
    if e.status == ACTIVE:
        s += 3.0                                    # active constraint
    if ctx["conflict_keys"] and e.key_tuple()[:3] in ctx["conflict_keys"]:
        s += 3.0                                    # unresolved conflict participant
    s += 2.0 * float(e.source_authority)            # authoritative
    if e.version >= ctx["latest_version"].get(e.key_tuple()[:3], 0):
        s += 2.0                                    # latest valid version
    s += 1e-3 * float(e.timestamp)                  # recency tie-break
    return s


def build_ctx(events: List[Evidence]) -> Dict:
    latest = _latest_version_by_key(events)
    # conflict keys: same (subject,relation) with >1 ACTIVE record of different version/object
    active_by_key: Dict[tuple, set] = {}
    for e in events:
        if e.status == ACTIVE:
            active_by_key.setdefault(e.key_tuple()[:3], set()).add((e.version, e.object_id_or_value))
    conflict_keys = {k for k, v in active_by_key.items() if len(v) > 1}
    return {"latest_version": latest, "conflict_keys": conflict_keys}


def collapse_duplicates(slot_ids: List[int], id_of: Dict[int, Evidence]) -> List[int]:
    """P3: keep one representative per exact key (prefer ACTIVE, then latest version)."""
    best: Dict[tuple, int] = {}
    for eid in slot_ids:
        e = id_of[eid]; k = e.key_tuple()
        cur = best.get(k)
        if cur is None:
            best[k] = eid
        else:
            ce = id_of[cur]
            if (e.status == ACTIVE, e.version) > (ce.status == ACTIVE, ce.version):
                best[k] = eid
    return list(best.values())
