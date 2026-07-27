"""
binding_slots.py — bounded exact working memory.

A slot holds an exact, resolvable SlotRecord (never mutated into a different fact) plus a learned
SlotRepresentation (computed by the model encoder, may be refreshed). Admission/refresh/replacement/
eviction each emit an auditable event. `simulate_slots` streams the (authorized) workflow evidence
through a capacity-K slot buffer under a chosen admission policy and returns the final slot evidence
ids, the audit trail, and cost counters (retrieval calls, records re-encoded).

Fresh retrieval (the non-slot baseline) is `fresh_packet`: at query time it returns a bounded
candidate set — ALL authorized candidates in one-shot mode, but only a bounded RECENT window in
streaming / multi-step mode (so distant required evidence falls out of view).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .schema import Evidence
from .admission_policies import priority, build_ctx, collapse_duplicates, protected_ids, CHAIN_RELATIONS

RECENT_WINDOW_SECTIONS = 6                 # bounded recent view for fresh streaming retrieval
FRESH_CAP = 32                             # bounded fresh packet size


@dataclass
class SlotRecord:
    slot_id: int
    evidence_id: int
    subject_type: int
    subject_id: int
    relation_type: int
    object_type: int
    object_id_or_value: int
    timestamp: int
    version: int
    status: int
    source_authority: float
    document_id: int
    section_id: int
    admission_reason: str
    retention_reason: str

    @classmethod
    def of(cls, slot_id, e: Evidence, admission_reason, retention_reason=""):
        return cls(slot_id, e.evidence_id, e.subject_type, e.subject_id, e.relation_type,
                   e.object_type, e.object_id_or_value, e.timestamp, e.version, e.status,
                   e.source_authority, e.document_id, e.section_id, admission_reason, retention_reason)


def _authorized(events, tenant, role_idx):
    return [e for e in events if e.tenant_id == tenant and e.readable_by(role_idx)]


def fresh_packet(ex: Dict, K_cap=FRESH_CAP) -> Dict:
    """Deterministic fresh retrieval at query time. Returns evidence ids + cost counters."""
    events = _authorized(ex["events"], ex["tenant"], ex["role_idx"])
    q_sec = ex["events"][ex["query_pos"]].section_id if ex["query_pos"] < len(ex["events"]) else ex["n_sections"] - 1
    if ex["mode"] == "one_shot":
        cands = events                                             # sees everything (broad)
    else:
        lo = max(0, q_sec - RECENT_WINDOW_SECTIONS)
        cands = [e for e in events if lo <= e.section_id <= q_sec]  # bounded recent window
    # deterministic priority ordering, bounded
    ctx = build_ctx(cands)
    ranked = sorted(cands, key=lambda e: priority(e, ctx, "P2"), reverse=True)[:K_cap]
    return {"ids": [e.evidence_id for e in ranked],
            "retrieval_calls": 1, "records_encoded": len(ranked)}


def global_packet(ex: Dict, K: int) -> Dict:
    """S1G: query-time GLOBAL deterministic retrieval over the full authorized ledger, top-K by
    enterprise priority. Distinguishes retrieval value from memory value (sees distant evidence too,
    but must re-encode K records at every query)."""
    events = _authorized(ex["events"], ex["tenant"], ex["role_idx"])
    events = [e for e in events if e.tag != "query"]
    ctx = build_ctx(events)
    ranked = sorted(events, key=lambda e: priority(e, ctx, "P2"), reverse=True)[:K]
    ids = [e.evidence_id for e in ranked]
    return {"ids": ids, "retrieval_calls": 1, "records_encoded": len(ids),
            "required_survived": all((i < 0) or (i in ids) for i in ex["required_ids"])}


def _bucket_of(e: Evidence, ctx) -> str:
    from .schema import ACTIVE, SUPERSEDED
    k = e.key_tuple()[:3]
    if k in ctx["conflict_keys"]:
        return "conflict"
    if e.status in (ACTIVE, SUPERSEDED) and e.relation_type in CHAIN_RELATIONS:
        return "version"
    if e.relation_type in CHAIN_RELATIONS:
        return "chain"
    return "general"


def simulate_slots_roles(ex: Dict, K: int, policy="P2", buckets=None) -> Dict:
    """Role-aware allocation: K split into chain/conflict/version/general sub-pools, each evicted
    independently. Tests whether semantic interference in one shared pool causes the S3→S4 gap."""
    if buckets is None:
        q = max(1, K // 4)
        buckets = {"chain": q, "conflict": q, "version": q, "general": K - 3 * q}
    events = sorted(_authorized(ex["events"], ex["tenant"], ex["role_idx"]),
                    key=lambda e: (e.section_id, e.timestamp))
    id_of = {e.evidence_id: e for e in ex["events"]}
    pools = {b: [] for b in buckets}
    seen = []
    encoded = 0
    for e in events:
        if e.tag == "query":
            continue
        seen.append(e); ctx = build_ctx(seen, query_anchor=ex["req"])
        b = _bucket_of(e, ctx)
        pool = pools[b]; cap = buckets[b]
        if e.evidence_id in pool:
            continue
        if len(pool) < cap:
            pool.append(e.evidence_id); encoded += 1
        else:
            cur = min(pool, key=lambda i: priority(id_of[i], ctx, policy))
            if priority(e, ctx, policy) > priority(id_of[cur], ctx, policy):
                pool.remove(cur); pool.append(e.evidence_id); encoded += 1
    ids = [i for b in pools.values() for i in b][:K]
    return {"ids": ids, "audit": [], "retrieval_calls": 0, "records_encoded": encoded,
            "required_survived": all((i < 0) or (i in ids) for i in ex["required_ids"])}


def simulate_slots(ex: Dict, K: int, policy="P2", oracle=False) -> Dict:
    """Stream authorized evidence section-by-section through a K-capacity slot buffer."""
    events = sorted(_authorized(ex["events"], ex["tenant"], ex["role_idx"]),
                    key=lambda e: (e.section_id, e.timestamp))
    id_of = {e.evidence_id: e for e in ex["events"]}
    q_anchor = ex["req"]                            # query subject id (chain-reachability anchor)
    required = set(ex["required_ids"]) if oracle else None
    slots: List[int] = []
    audit: List[Dict] = []
    encoded = 0
    seen_so_far: List[Evidence] = []
    for e in events:
        if e.tag == "query":
            continue
        seen_so_far.append(e)
        ctx = build_ctx(seen_so_far, query_anchor=q_anchor)
        if e.evidence_id in slots:
            audit.append({"event": "refresh", "evidence_id": e.evidence_id}); continue
        if policy in ("P3", "P4", "P5"):            # duplicate collapse: reject an exact duplicate
            ek = e.key_tuple() + (e.version, e.status)
            if any(id_of[i].key_tuple() + (id_of[i].version, id_of[i].status) == ek for i in slots):
                audit.append({"event": "reject_duplicate", "evidence_id": e.evidence_id}); continue
        if len(slots) < K:
            slots.append(e.evidence_id); encoded += 1
            audit.append({"event": "admit", "evidence_id": e.evidence_id, "reason": policy,
                          "priority": round(priority(e, ctx, policy, required), 2), "slots": list(slots)})
        else:
            prot = protected_ids(slots, id_of, ctx, policy)          # P4/P5: never evict these
            evictable = [i for i in slots if i not in prot] or list(slots)
            cur = min(evictable, key=lambda i: priority(id_of[i], ctx, policy, required))
            if priority(e, ctx, policy, required) > priority(id_of[cur], ctx, policy, required):
                slots.remove(cur); slots.append(e.evidence_id); encoded += 1
                audit.append({"event": "replace", "evict": cur, "evict_reason": "low_priority",
                              "admit": e.evidence_id, "slots": list(slots)})
            else:
                audit.append({"event": "reject", "evidence_id": e.evidence_id})
    if oracle:                                     # guarantee required evidence is present
        req = [r for r in ex["required_ids"] if r >= 0 and id_of.get(r) is not None]
        for rid in req:
            if rid not in slots:
                evictable = [i for i in slots if i not in req]     # never evict another required
                if len(slots) >= K and evictable:
                    slots.remove(evictable[0])
                slots.append(rid); encoded += 1
    return {"ids": slots[:K], "audit": audit, "retrieval_calls": 0, "records_encoded": encoded,
            "required_survived": all((r < 0) or (r in slots) for r in ex["required_ids"])}
