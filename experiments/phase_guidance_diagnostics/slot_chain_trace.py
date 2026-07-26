"""
slot_chain_trace.py — Questions I & J: does the task create genuine slot pressure,
and where in the write/retain/evict/read chain does Phase act?

We re-implement GuidedBoundedSlots.write_stream READ-ONLY with instrumentation
(the experiment module is unchanged) to log per example:
  * final occupancy (active slots) and steps spent at full capacity,
  * hard writes (gate>0.5), matches (collision update), fresh allocations, evictions
    (allocation onto an active slot under no-free pressure),
  * target survival: at the topic-fact value token we record the chosen slot; at the
    end we check whether that slot still content-matches the topic write-key
    (cosine ≥ match_threshold) — i.e. the topic evidence was not overwritten/evicted,
  * whether the answer-position top-1 read lands on the surviving target slot.

If occupancy rarely saturates and the target almost always survives even at 3×,
the task is not a real slot-selection pressure test (plain content addressing wins).
"""
from __future__ import annotations
import torch
import torch.nn.functional as F
from experiments.phase_guidance_diagnostics import _common as C


@torch.no_grad()
def trace(model, ids, apos, examples, match_threshold=0.6):
    B, N = ids.shape
    h, g = model.encode(ids)
    hg = torch.cat([h, g], dim=-1)
    use_write = model.guide_write
    r_write = torch.sigmoid(model.g_write(hg)).squeeze(-1)
    k_guide = model.g_kguide(hg)
    p_retain = model.g_retain(hg).squeeze(-1)
    write_key = model.k_local(h) + (k_guide if use_write else 0.0)
    write_val = model.w_val(h)
    retain_in = p_retain if use_write else torch.zeros_like(p_retain)
    M = model.cfg.num_slots
    slots = model.slots

    # topic-fact value position per example (write label 1); fall back to topic decl.
    tv_pos = []
    for e in examples:
        p = next((j for j, l in enumerate(e.write_labels) if l == 1), 2)
        tv_pos.append(p)
    tv_pos = torch.tensor(tv_pos)

    keys = torch.zeros(B, M, write_key.shape[-1])
    values = torch.zeros(B, M, write_val.shape[-1])
    retain = torch.full((B, M), -1e4); usage = torch.zeros(B, M); active = torch.zeros(B, M)

    n_write = torch.zeros(B); n_match = torch.zeros(B); n_alloc = torch.zeros(B)
    n_evict = torch.zeros(B); full_steps = torch.zeros(B)
    target_slot = torch.full((B,), -1, dtype=torch.long)

    for t in range(N):
        wk = write_key[:, t]; wv = write_val[:, t]; gt = r_write[:, t]; rt = retain_in[:, t]
        sim = F.cosine_similarity(wk.unsqueeze(1), keys, dim=-1).masked_fill(active < 0.5, -2.0)
        best_sim, best_idx = sim.max(dim=-1)
        matched = best_sim >= match_threshold
        free = active < 0.5; has_free = free.any(dim=-1)
        free_idx = torch.argmax(free.float(), dim=-1)
        evict_idx = torch.argmin(retain + (active < 0.5) * 1e9, dim=-1)
        alloc_idx = torch.where(has_free, free_idx, evict_idx)
        idx = torch.where(matched, best_idx, alloc_idx)
        hard = gt > 0.5
        full_steps += (active.sum(dim=1) >= M).float()
        for b in range(B):
            if not hard[b]:
                continue
            n_write[b] += 1
            if matched[b]:
                n_match[b] += 1
            else:
                if has_free[b]:
                    n_alloc[b] += 1
                else:
                    n_evict[b] += 1
                    if idx[b] == target_slot[b]:
                        target_slot[b] = -1   # target evicted
            if t == tv_pos[b].item():
                target_slot[b] = idx[b]
        onehot = F.one_hot(idx, M).float()
        m = onehot * gt.unsqueeze(-1); m1 = m.unsqueeze(-1)
        keys = keys * (1 - m1) + m1 * wk.unsqueeze(1)
        values = values * (1 - m1) + m1 * wv.unsqueeze(1)
        retain = retain * (1 - m) + m * rt.unsqueeze(1)
        usage = usage * 0.999 + m
        active = torch.clamp(active + m, max=1.0)

    # target survival: chosen slot still content-matches topic write key?
    ar = torch.arange(B)
    survived = torch.zeros(B)
    for b in range(B):
        s = target_slot[b].item()
        if s >= 0 and active[b, s] > 0.5:
            wk = write_key[b, tv_pos[b]]
            cs = F.cosine_similarity(wk.unsqueeze(0), keys[b, s].unsqueeze(0)).item()
            survived[b] = 1.0 if cs >= match_threshold else 0.0

    # answer-position read top-1 lands on surviving target slot?
    hA = h[ar, apos]; gA = g[ar, apos]
    rq = model.q_read(hA) + (model.q_read_g(gA) if model.guide_read else 0.0)
    scores = torch.einsum("bd,bmd->bm", rq, keys) / (keys.shape[-1] ** 0.5)
    scores = scores.masked_fill(active < 0.5, float("-inf"))
    top1 = scores.argmax(dim=1)
    read_hits_target = ((top1 == target_slot) & (target_slot >= 0)).float()

    return {
        "final_occupancy_mean": active.sum(dim=1).mean().item(),
        "M": M,
        "frac_saturated_end": (active.sum(dim=1) >= M).float().mean().item(),
        "full_capacity_steps_mean": full_steps.mean().item(),
        "hard_writes_mean": n_write.mean().item(),
        "matches_mean": n_match.mean().item(),
        "allocations_mean": n_alloc.mean().item(),
        "evictions_mean": n_evict.mean().item(),
        "target_survival_rate": survived.mean().item(),
        "read_hits_target_rate": read_hits_target.mean().item(),
    }


def run(arm="D", pressure="3x", n=120, seed=17):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    ncand = C.PRESSURE_CAND[pressure]
    exs = C.generate_pressure(tok, "test", seed, n, ncand, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    apos = torch.tensor([e.answer_pos for e in exs])
    r = trace(model, ids, apos, exs)
    r.update({"arm": arm, "pressure": pressure, "n_candidates": ncand,
              "answer_acc": meta.get("metrics", {}).get("answer_acc")})
    C.save_json(f"slot_chain_trace_{arm}_p{pressure}.json", r)
    print(f"[slot_chain_trace {arm} p{pressure}] occ={r['final_occupancy_mean']:.1f}/{r['M']} "
          f"sat_end={r['frac_saturated_end']:.2f} evict={r['evictions_mean']:.1f} "
          f"target_survival={r['target_survival_rate']:.2f} "
          f"read_hits_target={r['read_hits_target_rate']:.2f}")
    return r


if __name__ == "__main__":
    for arm in ("C", "D"):
        for p in ("1x", "3x"):
            run(arm, p)
