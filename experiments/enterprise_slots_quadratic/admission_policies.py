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


ENTERPRISE = {"P2", "P3", "P4", "P5"}


def priority(e: Evidence, ctx: Dict, policy: str, required_ids=None) -> float:
    """Higher = more worth retaining. ctx carries cross-record deterministic context."""
    if policy == "P0":                              # FIFO: oldest first out → priority = arrival order
        return -float(e.timestamp)                  # lowest priority = oldest (evicted first)
    if policy == "P1":                              # recency: newest wins
        return float(e.timestamp)
    if policy == "P6":                              # oracle: required evidence is paramount
        base = 100.0 if (required_ids and e.evidence_id in required_ids) else 0.0
        return base + float(e.timestamp) * 1e-3
    # P2–P5 — deterministic enterprise priority (no labels); P4/P5 add eviction PROTECTION (below)
    s = 0.0
    if e.relation_type in CHAIN_RELATIONS:
        s += 4.0                                    # required-chain-link kind
    if ctx.get("query_subjects") and e.subject_id in ctx["query_subjects"]:
        s += 4.0                                    # relevant to the query subject / discovered chain
    if e.status == ACTIVE:
        s += 3.0                                    # active constraint
    if ctx["conflict_keys"] and e.key_tuple()[:3] in ctx["conflict_keys"]:
        s += 3.0                                    # unresolved conflict participant
    s += 2.0 * float(e.source_authority)            # authoritative
    if e.version >= ctx["latest_version"].get(e.key_tuple()[:3], 0):
        s += 2.0                                    # latest valid version
    s += 1e-3 * float(e.timestamp)                  # recency tie-break
    return s


def build_ctx(events: List[Evidence], query_anchor=None) -> Dict:
    latest = _latest_version_by_key(events)
    # material conflict = >1 ACTIVE governance (chain-relation) record for the same (subject,
    # relation) with different version/object. Restricted to CHAIN_RELATIONS so transactional
    # noise (e.g. many Invoice `bills` records) is NOT mistaken for a governance conflict.
    active_by_key: Dict[tuple, set] = {}
    for e in events:
        if e.status == ACTIVE and e.relation_type in CHAIN_RELATIONS:
            active_by_key.setdefault(e.key_tuple()[:3], set()).add((e.version, e.object_id_or_value))
    conflict_keys = {k for k, v in active_by_key.items() if len(v) > 1}
    # deterministic transitive chain reachability from the query anchor subject (no labels):
    # follow chain-relation edges subject -> (object as next subject) among observed records.
    query_subjects = set()
    if query_anchor is not None:
        query_subjects.add(query_anchor)            # query anchor = the request subject_id
        for _ in range(4):                          # bounded transitive closure over subject ids
            for e in events:
                if e.relation_type in CHAIN_RELATIONS and e.subject_id in query_subjects:
                    query_subjects.add(e.object_id_or_value)
    return {"latest_version": latest, "conflict_keys": conflict_keys, "query_subjects": query_subjects}


def protected_ids(slot_ids, id_of, ctx, policy) -> set:
    """Records the policy must not evict. P4: both sides of a material conflict. P5: also the
    active + a superseded version of any key that has both (for version comparison)."""
    prot = set()
    if policy not in ("P4", "P5"):
        return prot
    from .schema import ACTIVE, SUPERSEDED
    by_key = {}
    for eid in slot_ids:
        by_key.setdefault(id_of[eid].key_tuple()[:3], []).append(eid)
    for k, ids in by_key.items():
        if policy in ("P4", "P5") and k in ctx["conflict_keys"]:
            prot.update(ids)                        # protect all conflict participants
        if policy == "P5":
            has_active = any(id_of[i].status == ACTIVE for i in ids)
            has_super = any(id_of[i].status == SUPERSEDED for i in ids)
            if has_active and has_super:
                # keep one active + the latest superseded
                act = max((i for i in ids if id_of[i].status == ACTIVE), key=lambda i: id_of[i].version)
                sup = max((i for i in ids if id_of[i].status == SUPERSEDED), key=lambda i: id_of[i].version)
                prot.update({act, sup})
    return prot


def collapse_duplicates(slot_ids: List[int], id_of: Dict[int, Evidence]) -> List[int]:
    """P3+: collapse only TRUE duplicates — identical key AND version AND status. Records that
    differ in version or status (active vs superseded, conflicting versions) are DISTINCT facts and
    are never collapsed, so conflict pairs and active/stale pairs survive dedup."""
    best: Dict[tuple, int] = {}
    order = {eid: i for i, eid in enumerate(slot_ids)}
    for eid in slot_ids:
        e = id_of[eid]; k = e.key_tuple() + (e.version, e.status)
        if k not in best or e.source_authority > id_of[best[k]].source_authority:
            best[k] = eid
    return sorted(best.values(), key=lambda i: order[i])
