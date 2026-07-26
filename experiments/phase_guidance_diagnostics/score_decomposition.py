"""
score_decomposition.py — Question H: is the Phase signal overpowering precise
content addressing?

On the trained D model we decompose the bounded-slot READ score at the answer
position into its content term (q_read(hA)·key) and its Phase term
(q_read_g(gA)·key), and report the magnitude ratio
    R = |s_phase| / (|s_content| + eps).
We then run an inference-time sweep of a Phase coefficient β applied to BOTH the
write-key guide term and the read-query guide term (the full coupling), for
β ∈ {0,0.01,0.05,0.1,0.25,0.5,1.0}, and measure answer accuracy and the fraction
of top-1 slot reads changed relative to β=0 (content-only). β=1.0 reproduces the
trained model. This isolates whether a *small* Phase contribution helps while the
trained magnitude harms.
"""
from __future__ import annotations
import torch
import torch.nn.functional as F
from experiments.phase_guidance_diagnostics import _common as C

BETAS = [0.0, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0]


@torch.no_grad()
def forward_beta(model, ids, apos, beta):
    """Replicate GuidedSlotLM.forward with Phase-guidance terms scaled by beta."""
    B, N = ids.shape
    h, g = model.encode(ids)
    ar = torch.arange(B)
    # guidance
    hg = torch.cat([h, g], dim=-1)
    r_write = torch.sigmoid(model.g_write(hg)).squeeze(-1)
    k_guide = model.g_kguide(hg)
    p_retain = model.g_retain(hg).squeeze(-1)
    write_key = model.k_local(h) + beta * k_guide          # guide_write path
    write_val = model.w_val(h)
    retain = p_retain
    state = model.slots.write_stream(write_key, write_val, r_write, retain, ids)
    hA = h[ar, apos]; gA = g[ar, apos]
    read_query = model.q_read(hA) + beta * model.q_read_g(gA)
    vals, idx, attn = model.slots.read_topk(read_query, state, model.cfg.top_k)
    combined = torch.einsum("bk,bkd->bd", attn, vals)
    feat = model.readout(torch.cat([hA, gA, combined], dim=-1))
    logits = model.lm_head(model.norm_f(feat))
    return logits, idx[:, 0]


@torch.no_grad()
def decompose(model, ids, apos):
    B = ids.shape[0]; ar = torch.arange(B)
    h, g = model.encode(ids)
    hA = h[ar, apos]; gA = g[ar, apos]
    # rebuild slots at β=1 to get keys
    hg = torch.cat([h, g], dim=-1)
    r_write = torch.sigmoid(model.g_write(hg)).squeeze(-1)
    k_guide = model.g_kguide(hg); p_retain = model.g_retain(hg).squeeze(-1)
    state = model.slots.write_stream(model.k_local(h) + k_guide, model.w_val(h),
                                     r_write, p_retain, ids)
    Ds = state.keys.shape[-1]
    s_content = torch.einsum("bd,bmd->bm", model.q_read(hA), state.keys) / (Ds ** 0.5)
    s_phase = torch.einsum("bd,bmd->bm", model.q_read_g(gA), state.keys) / (Ds ** 0.5)
    active = state.active > 0.5
    sc = s_content.masked_fill(~active, float("nan"))
    sp = s_phase.masked_fill(~active, float("nan"))
    R = sp.abs().nanmean(dim=1) / (sc.abs().nanmean(dim=1) + 1e-6)
    return R


def run(arm="D", pressure="3x", n=100, seed=13):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    exs = C.generate_pressure(tok, "test", seed, n, 24, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    apos = torch.tensor([e.answer_pos for e in exs])
    aid = torch.tensor([e.answer_id for e in exs])

    R = decompose(model, ids, apos)
    q = torch.tensor([0.5, 0.9, 0.99])
    Rpct = torch.quantile(R, q).tolist()

    base_idx = None; sweep = {}
    for b in BETAS:
        logits, top1 = forward_beta(model, ids, apos, b)
        acc = (logits.argmax(-1) == aid).float().mean().item()
        if b == 0.0:
            base_idx = top1
        changed = (top1 != base_idx).float().mean().item()
        sweep[str(b)] = {"answer_acc": acc, "frac_read_changed_vs_content": changed}
        print(f"  beta={b:<5} acc={acc:.3f} read_changed_vs_content={changed:.3f}")

    res = {"arm": arm, "pressure": pressure,
           "R_ratio_phase_over_content": {"mean": R.mean().item(),
                                          "p50": Rpct[0], "p90": Rpct[1], "p99": Rpct[2]},
           "beta_sweep": sweep,
           "trained_acc_beta1": sweep["1.0"]["answer_acc"],
           "content_only_acc_beta0": sweep["0.0"]["answer_acc"]}
    C.save_json(f"score_decomposition_{arm}_p{pressure}.json", res)
    print(f"[score_decomposition] R mean={R.mean():.2f} p90={Rpct[1]:.2f} | "
          f"acc β0={res['content_only_acc_beta0']:.3f} β1={res['trained_acc_beta1']:.3f}")
    return res


if __name__ == "__main__":
    run("D", "3x")
