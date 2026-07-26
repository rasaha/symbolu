"""
shortcut_checks.py — Question K: can the relational reader answer WITHOUT the
bounded memory (i.e. via a query-time shortcut)?

We run the trained model with targeted corruptions at read time and measure answer
accuracy. If accuracy survives corruption of the bounded memory, the answer is not
coming from the slots:
  * intact                — reference
  * shuffle_slot_values   — permute values across slots (breaks content→value bind)
  * shuffle_slot_keys     — permute keys across slots (breaks addressing)
  * random_slot_values    — replace values with noise
  * mask_query_entity     — zero the topic-entity token embedding in the query span
  * remove_phase_at_query — zero gA at the read (D only)
  * zero_readout_memory   — force the slot-combined vector to zero (answer from h,g only)
"""
from __future__ import annotations
import torch
from experiments.phase_guidance_diagnostics import _common as C


@torch.no_grad()
def _forward(model, ids, apos, mode):
    B, N = ids.shape; ar = torch.arange(B)
    h, g = model.encode(ids)
    hg = torch.cat([h, g], dim=-1)
    r_write = torch.sigmoid(model.g_write(hg)).squeeze(-1)
    k_guide = model.g_kguide(hg); p_retain = model.g_retain(hg).squeeze(-1)
    wk = model.k_local(h) + (k_guide if model.guide_write else 0.0)
    wv = model.w_val(h)
    retain = p_retain if model.guide_write else torch.zeros_like(p_retain)
    state = model.slots.write_stream(wk, wv, r_write, retain, ids)

    if mode == "shuffle_slot_values":
        perm = torch.randperm(state.values.shape[1])
        state.values = state.values[:, perm]
    elif mode == "shuffle_slot_keys":
        perm = torch.randperm(state.keys.shape[1])
        state.keys = state.keys[:, perm]
    elif mode == "random_slot_values":
        state.values = torch.randn_like(state.values) * state.values.std()

    hA = h[ar, apos]; gA = g[ar, apos]
    if mode == "remove_phase_at_query":
        gA = torch.zeros_like(gA)
    rq = model.q_read(hA) + (model.q_read_g(gA) if model.guide_read else 0.0)
    vals, idx, attn = model.slots.read_topk(rq, state, model.cfg.top_k)
    combined = torch.einsum("bk,bkd->bd", attn, vals)
    if mode == "zero_readout_memory":
        combined = torch.zeros_like(combined)
    feat = model.readout(torch.cat([hA, gA, combined], dim=-1))
    logits = model.lm_head(model.norm_f(feat))
    return logits


@torch.no_grad()
def _forward_mask_query(model, ids, apos, examples):
    """Zero the topic-entity token in the query span, then normal forward."""
    ids2 = ids.clone()
    for i, e in enumerate(examples):
        # query is "... vendor <topic>" before <A>; the topic entity sits at
        # answer_pos-1. Overwrite it with <pad> (id 0) to remove the query cue.
        ids2[i, e.answer_pos - 1] = 0
    return _forward(model, ids2, apos, "intact")


def run(arm="D", pressure="3x", n=150, seed=19):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    exs = C.generate_pressure(tok, "test", seed, n, 24, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    apos = torch.tensor([e.answer_pos for e in exs])
    aid = torch.tensor([e.answer_id for e in exs])

    modes = ["intact", "shuffle_slot_values", "shuffle_slot_keys", "random_slot_values",
             "zero_readout_memory"]
    if arm.startswith("D") and arm != "D-no-guid":
        modes.append("remove_phase_at_query")
    res = {"arm": arm, "pressure": pressure, "n": n, "modes": {}}
    for mode in modes:
        acc = (_forward(model, ids, apos, mode).argmax(-1) == aid).float().mean().item()
        res["modes"][mode] = acc
    res["modes"]["mask_query_entity"] = (
        _forward_mask_query(model, ids, apos, exs).argmax(-1) == aid).float().mean().item()
    C.save_json(f"shortcut_checks_{arm}_p{pressure}.json", res)
    print(f"[shortcut_checks {arm} p{pressure}]")
    for m, a in res["modes"].items():
        print(f"  {m:24s} acc={a:.3f}")
    return res


if __name__ == "__main__":
    for arm in ("C", "D"):
        run(arm, "3x")
