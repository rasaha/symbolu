"""
shortcut_checks.py — verify the answer depends on BOUNDED MEMORY (not a query-time
shortcut) and that retrieval is non-trivial.

Corruptions at read time (answer accuracy under each):
  intact
  shuffle_slot_values   — permute values across slots  (must collapse)
  zero_slot_values      — zero values                  (must collapse)
  random_slot_values    — noise values                 (must collapse)
  remove_target_slot    — deactivate the slot holding the target entity (must collapse)
  shuffle_slot_keys     — permute keys                  (must now HARM: Top-K<occupancy)
  mask_query_entity     — blank the queried contract id in the query
  shuffle_query         — random query tokens

Required: value/target corruptions collapse accuracy; key/query corruption materially
harms (unlike v1 where Top-K read all slots so keys were irrelevant).
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn.functional as F

from experiments.phase_guided_slots_v2.train_eval import collate
from experiments.phase_guided_slots_v2.memory_trace import trace_example_batch  # for slot_entity

HERE = Path(__file__).resolve().parent


@torch.no_grad()
def _build_state(model, ids):
    h, g = model.encode(ids)
    r_write, p_retain = model.guidance(h, g)
    wk = model.k_local(h)                     # pure content key
    wv = model.w_val(h)
    state = model.slots.write_stream(wk, wv, r_write, p_retain, ids)
    return h, g, state


@torch.no_grad()
def _answer(model, h, g, state, apos, mode, examples=None, ids=None):
    B = h.shape[0]; ar = torch.arange(B)
    keys, values, active = state.keys.clone(), state.values.clone(), state.active
    if mode == "shuffle_slot_values":
        values = values[:, torch.randperm(values.shape[1])]
    elif mode == "zero_slot_values":
        values = torch.zeros_like(values)
    elif mode == "random_slot_values":
        values = torch.randn_like(values) * values.std()
    elif mode == "shuffle_slot_keys":
        keys = keys[:, torch.randperm(keys.shape[1])]
    hA = h[ar, apos]; gA = g[ar, apos]
    rq = model.q_read(hA)
    if model.use_phase and model.guide:
        rq = rq + model.g_readbonus(gA)
    scores = torch.einsum("bd,bmd->bm", rq, keys) / (keys.shape[-1] ** 0.5)
    scores = scores.masked_fill(active < 0.5, float("-inf"))
    K = min(model.cfg.top_k, keys.shape[1])
    topv, topi = scores.topk(K, dim=-1)
    finite = torch.isfinite(topv)
    attn = torch.softmax(topv.masked_fill(~finite, float("-inf")), dim=-1)
    attn = torch.where(finite.any(-1, keepdim=True), attn, torch.zeros_like(attn))
    vals = torch.gather(values, 1, topi.unsqueeze(-1).expand(-1, -1, values.shape[-1]))
    combined = torch.einsum("bk,bkd->bd", attn, vals)
    feat = model.readout(torch.cat([hA, gA, combined], dim=-1))
    return model.lm_head(model.norm_f(feat))


@torch.no_grad()
def _acc(logits, aid):
    return (logits.argmax(-1) == aid).float().mean().item()


@torch.no_grad()
def run_checks(model, examples, pad_id):
    model.eval()
    ids, wl, apos, aid = collate(examples, pad_id, "cpu")
    h, g, state = _build_state(model, ids)
    res = {}
    for mode in ("intact", "shuffle_slot_values", "zero_slot_values", "random_slot_values",
                 "shuffle_slot_keys"):
        res[mode] = _acc(_answer(model, h, g, state, apos, mode), aid)

    # remove_target_slot: deactivate the slot holding the target entity
    _, per = trace_example_batch(model, ids, examples)
    # rebuild state and zero the target slot's value/key per example using trace ids
    # (approximate: use the read to find target slot then remove). We recompute
    # slot_entity by re-tracing and mask its value.
    res["remove_target_slot"] = _remove_target(model, ids, examples, h, g, apos, aid)

    # mask_query_entity: blank the queried contract token in the query span
    ids_mask = ids.clone()
    for i, e in enumerate(examples):
        # query "... contract C*" -> contract id sits at answer_pos-1 for latest_value
        ids_mask[i, e.answer_pos - 1] = pad_id
    h2, g2, st2 = _build_state(model, ids_mask)
    res["mask_query_entity"] = _acc(_answer(model, h2, g2, st2, apos, "intact"), aid)

    # shuffle_query: randomize the query span tokens
    ids_sq = ids.clone()
    for i, e in enumerate(examples):
        qs = e.answer_pos  # tokens after <Q> up to <A>
        # find <Q> position
        ids_sq[i, :qs] = ids_sq[i, :qs]  # body untouched
    # simplest: permute the query-region ids per example
    for i, e in enumerate(examples):
        lo = e.answer_pos - 6; hi = e.answer_pos
        if lo > 0:
            perm = torch.randperm(hi - lo)
            ids_sq[i, lo:hi] = ids_sq[i, lo:hi][perm]
    h3, g3, st3 = _build_state(model, ids_sq)
    res["shuffle_query"] = _acc(_answer(model, h3, g3, st3, apos, "intact"), aid)
    return res


@torch.no_grad()
def _remove_target(model, ids, examples, h, g, apos, aid):
    """Deactivate, per example, the slot best matching the target contract's write
    key (the slot holding the queried evidence), then re-read. If the answer came
    from that slot, accuracy must collapse."""
    from types import SimpleNamespace
    h_, g_, state = _build_state(model, ids)
    keys = state.keys.clone(); values = state.values.clone(); active = state.active.clone()
    for i, e in enumerate(examples):
        anchors = [j for j, l in enumerate(e.write_labels) if l == 1]
        tanchor = next((j for k, j in enumerate(anchors)
                        if k < len(e.facts) and e.facts[k].entity_id == e.gold_support_entity_ids[0]),
                       None)
        if tanchor is None:
            continue
        wk = model.k_local(h_[i:i + 1, tanchor])                       # [1,Ds]
        sim = F.cosine_similarity(wk, keys[i], dim=-1).masked_fill(active[i] < 0.5, -2)
        active[i, int(sim.argmax().item())] = 0.0
    st = SimpleNamespace(keys=keys, values=values, active=active)
    return _acc(_answer(model, h_, g_, st, apos, "intact"), aid)
