"""
multitask_interference.py — Question L: are the answer and write objectives
interfering, corrupting the guidance/Phase gradients?

On the trained D model we compute, on a batch, the gradients of the two loss terms
  L_answer  (cross-entropy at <A>)   and   L_write (BCE on r_write at labels)
separately, w.r.t. (i) the guidance-head params (g_write/g_kguide/g_retain),
(ii) the Phase params, and report their per-loss gradient norms and the cosine
similarity between the two gradient vectors. Strongly negative cosine ⇒ the two
objectives pull the shared parameters in opposing directions (destructive
interference); near-zero write-gradient into Phase ⇒ the relevance signal barely
supervises Phase at all. We also report the realized write-F1 across arms.
"""
from __future__ import annotations
import torch
import torch.nn.functional as F
from experiments.phase_guidance_diagnostics import _common as C
from experiments.phase_guided_slots.train_eval import _collate


def _grad_vec(loss, params):
    """Flattened gradient aligned to `params`; zero-fill params this loss doesn't
    touch so the two loss gradient vectors are the same length (for cosine)."""
    grads = torch.autograd.grad(loss, params, retain_graph=True, allow_unused=True)
    flat = [(g if g is not None else torch.zeros_like(p)).reshape(-1)
            for g, p in zip(grads, params)]
    return torch.cat(flat) if flat else torch.zeros(1)


def _group(model, names):
    ps = []
    for n, p in model.named_parameters():
        if any(n.startswith(pre) for pre in names):
            ps.append(p)
    return ps


def run(arm="D", pressure="3x", n=64, seed=27):
    model, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
    model.train()
    exs = C.generate_pressure(tok, "train", seed, n, 24, C.TARGET_LEN)
    ids, wl, apos, aid = _collate(exs, tok.pad_id, "cpu")
    out = model(ids, apos, write_labels=wl)
    ans_loss = F.cross_entropy(out["answer_logits"], aid)
    r = out["r_write"]; mask = wl != -100
    tgt = wl.clamp(min=0).float()
    w_loss = F.binary_cross_entropy(r[mask], tgt[mask])

    groups = {"guidance_head": ["g_write", "g_kguide", "g_retain"],
              "phase": ["phase."]}
    res = {"arm": arm, "pressure": pressure,
           "realized_write_f1": meta.get("metrics", {}).get("write_f1"),
           "answer_acc": meta.get("metrics", {}).get("answer_acc"),
           "groups": {}}
    for gname, prefixes in groups.items():
        ps = _group(model, prefixes)
        if not ps:
            continue
        ga = _grad_vec(ans_loss, ps)
        gw = _grad_vec(w_loss, ps)
        cos = F.cosine_similarity(ga.unsqueeze(0), gw.unsqueeze(0)).item()
        res["groups"][gname] = {
            "answer_grad_norm": ga.norm().item(),
            "write_grad_norm": gw.norm().item(),
            "grad_cosine": cos,
            "write_to_answer_norm_ratio": gw.norm().item() / (ga.norm().item() + 1e-9)}
    C.save_json(f"multitask_interference_{arm}_p{pressure}.json", res)
    print(f"[multitask_interference {arm} p{pressure}] write_f1={res['realized_write_f1']}")
    for gname, d in res["groups"].items():
        print(f"  {gname:14s} |g_ans|={d['answer_grad_norm']:.3e} "
              f"|g_wr|={d['write_grad_norm']:.3e} cos={d['grad_cosine']:+.3f} "
              f"wr/ans={d['write_to_answer_norm_ratio']:.3e}")
    return res


if __name__ == "__main__":
    run("D", "3x")
