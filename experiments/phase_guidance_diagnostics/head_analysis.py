"""
head_analysis.py — Question E: are the Phase heads carrying distinct useful signals?

Per head (from the pre-W_out readout o_t[:,:,h,:], the head's own contribution):
  * topic-decoding top-1 from that head alone,
  * head output norm,
  * pairwise correlation between heads,
  * effective rank of the stacked per-head readout (participation ratio of the
    covariance eigenspectrum),
  * head ablation: drop each head (zero its o_t slice) and re-probe full-g topic acc.
"""
from __future__ import annotations
import torch
from experiments.phase_guidance_diagnostics import _common as C
from experiments.lightweight_phase_natural_language.datasets import BASE_NAMES


@torch.no_grad()
def _per_head_o(model, intern):
    a_q = intern["a_q"]; phi_q = intern["phi_q"]; S = intern["S"]; A = intern["A"]
    q_phasor = torch.polar(a_q, phi_q)
    n_t = (q_phasor * S).real
    Z = (a_q * A).clamp(min=0.1)
    return n_t / Z    # [B,N,H,Dh]


@torch.no_grad()
def run(arm="D", pressure="3x", n=500, seed=7):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    H, Dh = model.phase.num_heads, model.phase.head_dim
    lab_map = {b: i for i, b in enumerate(BASE_NAMES)}
    exs = C.generate_pressure(tok, "train", seed, n, 24, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    h, g = C.encode_features(model, ids)
    intern = C.phase_internals(model.phase, h)
    o = _per_head_o(model, intern)                 # [B,N,H,Dh]
    ar = torch.arange(len(exs)); apos = torch.tensor([e.answer_pos for e in exs])
    oA = o[ar, apos]                                # [B,H,Dh]
    y = torch.tensor([lab_map[tok.itos[e.tokens[2]]] for e in exs])
    ntr = int(0.7 * len(y)); perm = torch.randperm(len(y)); tri, tei = perm[:ntr], perm[ntr:]

    per_head = {}
    for hh in range(H):
        xh = oA[:, hh]
        pr = C.fit_linear_probe(xh[tri], y[tri], len(BASE_NAMES), xh[tei], y[tei])
        per_head[f"head_{hh}"] = {
            "topic_top1": pr["top1"], "topic_top3": pr["topk"],
            "out_norm": xh.norm(dim=-1).mean().item()}

    # head ablation on full-g probe
    full = oA.reshape(len(exs), -1)
    base = C.fit_linear_probe(full[tri], y[tri], len(BASE_NAMES), full[tei], y[tei])["top1"]
    abl = {}
    for hh in range(H):
        masked = oA.clone(); masked[:, hh] = 0.0
        fm = masked.reshape(len(exs), -1)
        acc = C.fit_linear_probe(fm[tri], y[tri], len(BASE_NAMES), fm[tei], y[tei])["top1"]
        abl[f"drop_head_{hh}"] = {"topic_top1": acc, "delta_vs_full": acc - base}

    # pairwise correlation between head readouts (flatten Dh, corr of per-example vectors)
    flat = oA.reshape(len(exs), H, Dh)
    corr = torch.zeros(H, H)
    for a in range(H):
        for b in range(H):
            va = flat[:, a].reshape(-1); vb = flat[:, b].reshape(-1)
            va = va - va.mean(); vb = vb - vb.mean()
            corr[a, b] = (va @ vb) / (va.norm() * vb.norm() + 1e-9)

    # effective rank (participation ratio) of the [B, H*Dh] answer-state matrix
    Xc = full - full.mean(0, keepdim=True)
    cov = Xc.T @ Xc / len(exs)
    ev = torch.linalg.eigvalsh(cov).clamp(min=0)
    eff_rank = (ev.sum() ** 2 / (ev.pow(2).sum() + 1e-12)).item()

    res = {"arm": arm, "pressure": pressure, "num_heads": H, "head_dim": Dh,
           "full_topic_top1": base, "chance": 1.0 / len(BASE_NAMES),
           "per_head": per_head, "ablation": abl,
           "pairwise_corr": corr.tolist(),
           "mean_abs_offdiag_corr": (corr - torch.eye(H)).abs().sum().item() / (H * (H - 1)),
           "effective_rank": eff_rank, "max_rank": H * Dh}
    C.save_json(f"head_analysis_{arm}_p{pressure}.json", res)
    print(f"[head_analysis {arm} p{pressure}] full_top1={base:.3f} "
          f"eff_rank={eff_rank:.1f}/{H*Dh} mean|corr|={res['mean_abs_offdiag_corr']:.3f}")
    for hh in range(H):
        print(f"  head {hh}: top1={per_head[f'head_{hh}']['topic_top1']:.3f} "
              f"norm={per_head[f'head_{hh}']['out_norm']:.3f} "
              f"ablate_delta={abl[f'drop_head_{hh}']['delta_vs_full']:+.3f}")
    return res


if __name__ == "__main__":
    run("D", "3x")
