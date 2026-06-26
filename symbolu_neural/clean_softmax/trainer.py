"""Train one ablation and evaluate it. Used by train.py and run_ablations.py."""
from __future__ import annotations

import time
from typing import Dict, Optional

import torch
import torch.nn.functional as F

from .config import ExpConfig
from .model import SymbolUSoftmaxModel
from .data import make_batches
from .metrics import val_loss_ppl, ece_and_entropy_corr


def train_and_eval(cfg: ExpConfig, train_ids, val_ids, block=128, batch=24,
                   steps=250, lr=3e-3, seed=0, log_every=0) -> Dict[str, float]:
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    model = SymbolUSoftmaxModel(cfg)
    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01)
    it = make_batches(train_ids, block, batch, generator=gen)
    model.train()
    t0 = time.time()
    for step in range(steps):
        x, y = next(it)
        aux = model(x)
        logits = aux["logits"]
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
        if cfg.entropy_refine and "ponder_cost" in aux:
            loss = loss + cfg.ponder_weight * aux["ponder_cost"]
        if cfg.entropy_cal_weight > 0 and "entropy_vec" in aux:
            # correlate symbolic H_D with per-position LM NLL (calibration shaping)
            with torch.no_grad():
                nll = F.cross_entropy(logits.reshape(-1, logits.size(-1)),
                                      y.reshape(-1), reduction="none").reshape(y.shape)
            H = aux["entropy_vec"][..., 0]
            Hn = H - H.mean(); en = nll - nll.mean()
            corr = (Hn * en).mean() / (Hn.std().clamp_min(1e-6) * en.std().clamp_min(1e-6))
            loss = loss + cfg.entropy_cal_weight * (1 - corr)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if log_every and (step + 1) % log_every == 0:
            print(f"    step {step+1}/{steps} loss={loss.item():.3f}")
    train_time = time.time() - t0

    model.eval()
    fwd = lambda x: model(x)["logits"]
    m = val_loss_ppl(fwd, val_ids, block, batch)
    m.update(ece_and_entropy_corr(fwd, val_ids, block, batch))
    m["params"] = model.num_params()
    m["trainable_params"] = model.num_params(trainable_only=True)
    m["train_time_s"] = round(train_time, 1)
    m["ms_per_step"] = round(1000 * train_time / steps, 1)
    return m, model


@torch.no_grad()
def _acc(logp, y):
    pred = logp.argmax(-1).reshape(-1)
    yt = y.reshape(-1)
    return (pred == yt).float().mean().item()


def head_grounding_control(train_ids, val_ids, cfg: ExpConfig, block=128, batch=24,
                           steps=150, lr=3e-3, seed=0, shuffle=False) -> Dict[str, float]:
    """Shuffled-label control for the typed heads on a frozen backbone.

    Synthetic per-char labels (vritti = ord%5, aspect = ord%10). With real labels
    a probe on the frozen backbone should beat chance; with globally-shuffled
    labels it should collapse to chance (the kill-criterion bites). This isolates
    'do the typed heads learn *anything* decodable' from the LM question.
    """
    from .augment import TypedHeadBank
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    model = SymbolUSoftmaxModel(cfg)               # backbone (untrained is fine: probe test)
    for p in model.lm.parameters():
        p.requires_grad_(False)
    heads = TypedHeadBank(cfg.backbone.d_model)
    opt = torch.optim.Adam(heads.parameters(), lr=lr)

    def labels_for(x):
        lv = (x % 5)
        la = (x % 10)
        if shuffle:
            B, L = x.shape
            pv = torch.randperm(B * L, generator=gen)
            lv = lv.reshape(-1)[pv].reshape(B, L)
            pa = torch.randperm(B * L, generator=gen)
            la = la.reshape(-1)[pa].reshape(B, L)
        return lv, la

    it = make_batches(train_ids, block, batch, generator=gen)
    heads.train()
    for _ in range(steps):
        x, _ = next(it)
        with torch.no_grad():
            h = model.lm.hidden(x)
        out = heads(h)
        lv, la = labels_for(x)
        loss = (F.nll_loss(out["log_p_v"].reshape(-1, 5), lv.reshape(-1)) +
                F.nll_loss(out["log_p_w"].reshape(-1, 10), la.reshape(-1)))
        opt.zero_grad(); loss.backward(); opt.step()

    heads.eval()
    from .data import iter_val_blocks
    av, aa, maj_v = [], [], []
    with torch.no_grad():
        for x, _ in iter_val_blocks(val_ids, block, batch):
            h = model.lm.hidden(x)
            out = heads(h)
            lv, la = labels_for(x)
            av.append(_acc(out["log_p_v"], lv)); aa.append(_acc(out["log_p_w"], la))
    return {"vritti_acc": sum(av) / len(av), "aspect_acc": sum(aa) / len(aa),
            "vritti_chance": 0.2, "aspect_chance": 0.1, "shuffled": shuffle}
