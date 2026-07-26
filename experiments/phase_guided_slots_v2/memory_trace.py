"""
memory_trace.py — read-only, faithful re-implementation of GuidedBoundedSlots'
streaming write + Top-K read, instrumented with oracle fact identities.

The frozen/experiment module GuidedBoundedSlots is NOT modified. This mirrors its
exact decision rules (cosine match ≥ threshold → in-place supersede; else free slot
else evict lowest-retention active slot; soft-gated write) so we can log the full
memory chain per example:

  arrival order, per-write oracle entity_id, occupancy over time, write gate, match
  score, allocation vs merge vs eviction, evicted entity identity, retention, target
  slot identity, target survival at query, retrieved Top-K slots, gold supporting
  slots, and whether Top-K covers the whole active set.

`slot_entity[b,m]` tracks the oracle entity_id that last wrote slot m (or -2 for a
spurious non-anchor write, -1 for empty). A MERGE-OF-DISTINCT is a match-write whose
target slot currently holds a DIFFERENT entity_id (semantic collapse — the v1 bug).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import torch
import torch.nn.functional as F

from experiments.phase_guided_slots_v2.task_schema import Example


@torch.no_grad()
def trace_example_batch(model, ids, examples: List[Example], match_threshold=None):
    if match_threshold is None:
        match_threshold = getattr(model.slots, "match_threshold", 0.6)
    """Run the instrumented write/read for a batch. Returns a dict of aggregate
    metrics plus per-example records."""
    B, N = ids.shape
    device = ids.device
    ar = torch.arange(B)
    h, g = model.encode(ids)
    hg = torch.cat([h, g], dim=-1)
    r_write = torch.sigmoid(model.g_write(hg)).squeeze(-1)
    k_guide = model.g_kguide(hg)
    p_retain = model.g_retain(hg).squeeze(-1)
    wk_all = model.k_local(h) + (k_guide if model.guide_write else 0.0)
    wv_all = model.w_val(h)
    retain_all = p_retain if model.guide_write else torch.zeros_like(p_retain)
    M = model.cfg.num_slots
    Ds = wk_all.shape[-1]

    # per-position oracle entity id: anchor <sep> of a fact → its entity_id, else -2
    ent_at_pos = torch.full((B, N), -2, dtype=torch.long)
    apos = torch.tensor([e.answer_pos for e in examples])
    target_eid = torch.tensor([e.gold_support_entity_ids[0] for e in examples])
    for i, e in enumerate(examples):
        # reconstruct anchor positions: tokens where write_labels == 1, in order
        anchors = [j for j, l in enumerate(e.write_labels) if l == 1]
        for k, j in enumerate(anchors):
            if k < len(e.facts) and j < N:
                ent_at_pos[i, j] = e.facts[k].entity_id

    keys = torch.zeros(B, M, Ds)
    values = torch.zeros(B, M, wv_all.shape[-1])
    retain = torch.full((B, M), -1e4)
    usage = torch.zeros(B, M)
    active = torch.zeros(B, M)
    slot_entity = torch.full((B, M), -1, dtype=torch.long)

    n_hard = torch.zeros(B); n_match = torch.zeros(B); n_alloc = torch.zeros(B)
    n_evict = torch.zeros(B); n_merge_distinct = torch.zeros(B)
    full_steps = torch.zeros(B); occ_sum = torch.zeros(B)
    target_evicted = torch.zeros(B)

    for t in range(N):
        wk = wk_all[:, t]; wv = wv_all[:, t]; gt = r_write[:, t]; rt = retain_all[:, t]
        ent_t = ent_at_pos[:, t]
        sim = F.cosine_similarity(wk.unsqueeze(1), keys, dim=-1).masked_fill(active < 0.5, -2.0)
        best_sim, best_idx = sim.max(dim=-1)
        matched = best_sim >= match_threshold
        free = active < 0.5; has_free = free.any(dim=-1)
        free_idx = torch.argmax(free.float(), dim=-1)
        evict_idx = torch.argmin(retain + (active < 0.5) * 1e9, dim=-1)
        alloc_idx = torch.where(has_free, free_idx, evict_idx)
        idx = torch.where(matched, best_idx, alloc_idx)
        hard = gt > 0.5

        occ_sum += active.sum(dim=1)
        full_steps += (active.sum(dim=1) >= M).float()

        for b in range(B):
            if not hard[b]:
                continue
            n_hard[b] += 1
            slot = int(idx[b].item())
            if matched[b]:
                n_match[b] += 1
                if slot_entity[b, slot].item() >= 0 and ent_t[b].item() >= 0 \
                        and slot_entity[b, slot].item() != ent_t[b].item():
                    n_merge_distinct[b] += 1
            else:
                if has_free[b]:
                    n_alloc[b] += 1
                else:
                    n_evict[b] += 1
                    ev_ent = slot_entity[b, slot].item()
                    if ev_ent == target_eid[b].item():
                        target_evicted[b] = 1.0
            # update slot identity to the writer's entity (anchor → id, else -2)
            if ent_t[b].item() >= 0:
                slot_entity[b, slot] = ent_t[b]
            elif slot_entity[b, slot].item() < 0:
                slot_entity[b, slot] = ent_t[b]

        onehot = F.one_hot(idx, M).float()
        m = onehot * gt.unsqueeze(-1); m1 = m.unsqueeze(-1)
        keys = keys * (1 - m1) + m1 * wk.unsqueeze(1)
        values = values * (1 - m1) + m1 * wv.unsqueeze(1)
        retain = retain * (1 - m) + m * rt.unsqueeze(1)
        usage = usage * 0.999 + m
        active = torch.clamp(active + m, max=1.0)

    # target survival: some active slot still holds the target entity
    target_survived = ((slot_entity == target_eid.unsqueeze(1)) & (active > 0.5)).any(dim=1).float()

    # answer-position Top-K read
    hA = h[ar, apos]; gA = g[ar, apos]
    rq = model.q_read(hA) + (model.q_read_g(gA) if model.guide_read else 0.0)
    scores = torch.einsum("bd,bmd->bm", rq, keys) / (Ds ** 0.5)
    scores = scores.masked_fill(active < 0.5, float("-inf"))
    K = min(model.cfg.top_k, M)
    topv, topi = scores.topk(K, dim=-1)
    finite = torch.isfinite(topv)
    topk_ent = torch.gather(slot_entity, 1, topi)             # [B,K]
    topk_has_target = ((topk_ent == target_eid.unsqueeze(1)) & finite).any(dim=1).float()
    occ_end = active.sum(dim=1)
    frac_mem_read = torch.minimum(finite.sum(dim=1).float(), occ_end) / occ_end.clamp(min=1)

    def m_(x): return x.mean().item()
    agg = {
        "M": M, "top_k": K, "n": B,
        "mean_occupancy": m_(occ_sum / N),
        "final_occupancy": m_(occ_end),
        "capacity_saturation_rate": m_((occ_end >= M).float()),
        "frac_time_full": m_(full_steps / N),
        "hard_writes": m_(n_hard), "matches": m_(n_match),
        "allocations": m_(n_alloc), "evictions": m_(n_evict),
        "merge_of_distinct_rate": m_(n_merge_distinct),
        "target_eviction_rate": m_(target_evicted),
        "target_survival_rate": m_(target_survived),
        "topk_support_recall": m_(topk_has_target),
        "frac_memory_read": m_(frac_mem_read),
        "mean_distinct_ids": sum(e.meta["distinct_entity_ids"] for e in examples) / B,
    }
    return agg, {"target_survived": target_survived, "topk_has_target": topk_has_target,
                 "target_evicted": target_evicted, "occ_end": occ_end}


@torch.no_grad()
def trace_dataset(model, examples: List[Example], pad_id: int, batch=32):
    from experiments.phase_guided_slots_v2.train_eval import collate
    model.eval()
    keys = ["mean_occupancy", "final_occupancy", "capacity_saturation_rate",
            "frac_time_full", "hard_writes", "matches", "allocations", "evictions",
            "merge_of_distinct_rate", "target_eviction_rate", "target_survival_rate",
            "topk_support_recall", "frac_memory_read", "mean_distinct_ids"]
    acc = {k: 0.0 for k in keys}
    # per target position
    by_pos = {p: {"n": 0, "target_survival_rate": 0.0} for p in ("early", "middle", "late")}
    ntot = 0
    for i in range(0, len(examples), batch):
        b = examples[i:i + batch]
        ids, *_ = collate(b, pad_id, "cpu")
        agg, per = trace_example_batch(model, ids, b)
        for k in keys:
            acc[k] += agg[k] * len(b)
        for j, e in enumerate(b):
            bp = by_pos[e.target_position]
            bp["n"] += 1
            bp["target_survival_rate"] += per["target_survived"][j].item()
        ntot += len(b)
    out = {k: acc[k] / max(1, ntot) for k in keys}
    out["by_target_position"] = {p: {"n": d["n"],
                                     "target_survival_rate": d["target_survival_rate"] / max(1, d["n"])}
                                 for p, d in by_pos.items()}
    out["M"] = model.cfg.num_slots; out["top_k"] = model.cfg.top_k
    return out
