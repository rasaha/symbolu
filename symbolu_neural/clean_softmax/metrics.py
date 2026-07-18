"""Eval metrics for the clean-softmax experiment (dependency-free)."""
from __future__ import annotations

from typing import Dict

import math
import torch
import torch.nn.functional as F


@torch.no_grad()
def val_loss_ppl(aux_logits_fn, val_ids, block, batch) -> Dict[str, float]:
    from .data import iter_val_blocks
    tot, n = 0.0, 0
    for x, y in iter_val_blocks(val_ids, block, batch):
        logits = aux_logits_fn(x)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
        tot += loss.item() * y.numel(); n += y.numel()
    avg = tot / max(n, 1)
    return {"val_loss": avg, "ppl": math.exp(min(avg, 20)), "val_tokens": n}


@torch.no_grad()
def ece_and_entropy_corr(aux_logits_fn, val_ids, block, batch, n_bins=10) -> Dict[str, float]:
    from .data import iter_val_blocks
    confs, corrects, ent, err = [], [], [], []
    for x, y in iter_val_blocks(val_ids, block, batch):
        logits = aux_logits_fn(x)
        p = logits.softmax(-1).reshape(-1, logits.size(-1))
        yt = y.reshape(-1)
        pred = p.argmax(-1)
        confs.append(p.max(-1).values); corrects.append((pred == yt).float())
        H = -(p.clamp_min(1e-9) * p.clamp_min(1e-9).log()).sum(-1)
        ent.append(H); err.append((pred != yt).float())
    conf = torch.cat(confs); corr = torch.cat(corrects)
    H = torch.cat(ent); e = torch.cat(err)
    # ECE
    ece = 0.0
    edges = torch.linspace(0, 1, n_bins + 1)
    for i in range(n_bins):
        m = (conf > edges[i]) & (conf <= edges[i + 1]) if i > 0 else (conf <= edges[1])
        if m.any():
            ece += (m.float().mean() * (corr[m].mean() - conf[m].mean()).abs()).item()
    # entropy<->error correlation (LM's own predictive entropy vs error)
    if H.std() > 0 and e.std() > 0:
        hc = H - H.mean(); ec = e - e.mean()
        r = ((hc * ec).mean() / (hc.std(unbiased=False) * ec.std(unbiased=False))).item()
    else:
        r = float("nan")
    return {"ece": ece, "lm_entropy_error_corr": r}


@torch.no_grad()
def sample(model_forward, tok, prompt: str, n: int = 200, temp: float = 0.8,
           block: int = 256) -> str:
    import torch as _t
    ids = tok.encode(prompt).unsqueeze(0)
    for _ in range(n):
        logits = model_forward(ids[:, -block:])
        nxt = _t.multinomial((logits[0, -1] / temp).softmax(-1), 1)
        ids = _t.cat([ids, nxt.view(1, 1)], dim=1)
    return tok.decode(ids[0].tolist())
