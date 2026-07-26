"""
decay_probe.py — Question D: is learned decay removing the topic?

The frozen experiment config uses decay_mode="none" (γ = 1, pure cumsum). So there
is NO learned decay to blame: the topic is NOT forgotten by decay; if anything it
is diluted by never-forgotten later tokens (see dilution_probe). To make this
concrete we run READ-ONLY interventions: from the frozen per-token increments
(kv_j, a_k_j) we re-accumulate S_t, A_t under an *imposed* γ (1.0, 0.999, 0.99,
0.95, 0.9) — never modifying the frozen layer — and re-probe topic decodability at
the answer position. This shows whether forgetting recent tokens (shorter γ) would
recover or destroy the distant topic signal.
"""
from __future__ import annotations
import torch
from experiments.phase_guidance_diagnostics import _common as C
from experiments.lightweight_phase_natural_language.datasets import BASE_NAMES

GAMMAS = [1.0, 0.999, 0.99, 0.95, 0.9]


@torch.no_grad()
def _scan_with_gamma(kv, a_k, gamma):
    """Re-accumulate S_t, A_t under scalar γ (read-only). kv:[B,N,H,Dh] complex."""
    B, N, H, Dh = kv.shape
    if gamma >= 1.0:
        return torch.cumsum(kv, dim=1), torch.cumsum(a_k, dim=1)
    S = torch.empty_like(kv); A = torch.empty_like(a_k)
    s = torch.zeros(B, H, Dh, dtype=kv.dtype); a = torch.zeros(B, H, Dh)
    for t in range(N):
        s = gamma * s + kv[:, t]; a = gamma * a + a_k[:, t]
        S[:, t] = s; A[:, t] = a
    return S, A


@torch.no_grad()
def _readout_g(model, S, A, intern):
    """Recompute the Phase g-readout from (S,A) and the frozen projections."""
    a_q = intern["a_q"]; phi_q = intern["phi_q"]
    q_phasor = torch.polar(a_q, phi_q)
    n_t = (q_phasor * S).real
    Z = (a_q * A).clamp(min=0.1)
    o_t = (n_t / Z)
    B, N, H, Dh = o_t.shape
    o = o_t.reshape(B, N, H * Dh)
    return model.phase.W_out(o) * model.phase.config.aux_scale


def run(arm="D", pressure="3x", n=500, seed=7):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.eval()
    lab_map = {b: i for i, b in enumerate(BASE_NAMES)}
    exs = C.generate_pressure(tok, "train", seed, n, 24, C.TARGET_LEN)
    ids = C.collate_ids(exs, tok.pad_id)
    h, _ = C.encode_features(model, ids)
    intern = C.phase_internals(model.phase, h)
    apos = torch.tensor([e.answer_pos for e in exs])
    ar = torch.arange(len(exs))
    y = torch.tensor([lab_map[tok.itos[e.tokens[2]]] for e in exs])
    ntr = int(0.7 * len(y)); perm = torch.randperm(len(y)); tri, tei = perm[:ntr], perm[ntr:]

    rows = {}
    # per-head effective decay is N/A (γ fixed 1); we instead report per-gamma probe.
    for gm in GAMMAS:
        S, A = _scan_with_gamma(intern["kv"], intern["a_k"], gm)
        gfull = _readout_g(model, S, A, intern)
        gA = gfull[ar, apos]
        pr = C.fit_linear_probe(gA[tri], y[tri], len(BASE_NAMES), gA[tei], y[tei])
        rows[str(gm)] = {"phase_top1": pr["top1"], "phase_top3": pr["topk"],
                         "horizon_tokens": (None if gm >= 1 else round(1.0 / (1 - gm), 1))}
        print(f"  gamma={gm:<6} phase_top1={pr['top1']:.3f} "
              f"horizon={rows[str(gm)]['horizon_tokens']}")
    res = {"arm": arm, "pressure": pressure, "decay_mode_in_config": model.phase.config.decay_mode,
           "note": "config has NO decay (gamma=1); rows are read-only imposed-gamma interventions",
           "chance": 1.0 / len(BASE_NAMES), "gammas": rows}
    C.save_json(f"decay_probe_{arm}_p{pressure}.json", res)
    return res


if __name__ == "__main__":
    run("D", "3x")
