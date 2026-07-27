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
from .admission_policies import priority, build_ctx, collapse_duplicates

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


def simulate_slots(ex: Dict, K: int, policy="P2", oracle=False) -> Dict:
    """Stream authorized evidence section-by-section through a K-capacity slot buffer."""
    events = sorted(_authorized(ex["events"], ex["tenant"], ex["role_idx"]),
                    key=lambda e: (e.section_id, e.timestamp))
    id_of = {e.evidence_id: e for e in ex["events"]}
    required = set(ex["required_ids"]) if oracle else None
    slots: List[int] = []
    audit: List[Dict] = []
    encoded = 0
    seen_so_far: List[Evidence] = []
    for e in events:
        if e.tag == "query":
            continue
        seen_so_far.append(e)
        ctx = build_ctx(seen_so_far)
        if e.evidence_id in slots:
            audit.append({"event": "refresh", "evidence_id": e.evidence_id}); continue
        if len(slots) < K:
            slots.append(e.evidence_id); encoded += 1
            audit.append({"event": "admit", "evidence_id": e.evidence_id, "reason": policy})
        else:
            # evict the lowest-priority current slot if the new record ranks higher
            cur = min(slots, key=lambda i: priority(id_of[i], ctx, policy, required))
            if priority(e, ctx, policy, required) > priority(id_of[cur], ctx, policy, required):
                slots.remove(cur); slots.append(e.evidence_id); encoded += 1
                audit.append({"event": "replace", "evict": cur, "admit": e.evidence_id})
            else:
                audit.append({"event": "reject", "evidence_id": e.evidence_id})
        if policy == "P3":
            slots = collapse_duplicates(slots, id_of)
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
