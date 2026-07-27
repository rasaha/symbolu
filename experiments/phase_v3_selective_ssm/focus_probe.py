"""
focus_probe.py — §13 independent state/readout probes with controls.

Freeze a trained variant, extract per-position features, and train identical lightweight
L2-regularized probes on:
    local            : token/local representation only (no Phase)  → chance baseline
    state            : Phase recurrent state (concat real/imag)
    raw_readout      : Re(q⊙S)/Z before the read gate C_t
    selective_readout: after C_t
    local+state      : concatenation
    shuffled_state   : state shuffled across examples (control)  → chance
    random_state     : random features (control)                 → chance

Metrics: focus Top-1 / Top-K accuracy, relevance F1 / AUROC (from readout at event
positions), and calibration (ECE). Controls are reported beside every result.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from .config import PROBE_L2, PROBE_EPOCHS
from . import dataset as D


@torch.no_grad()
def _extract(model, data, vocab, device="cpu"):
    """Return probe-position focus features {name: X[n,dim]}, y_focus[n], and event-level
    readout features X_evt[m,D] with relevance labels y_rel[m]."""
    feats_probe = {}
    ys, xevt, yrel = [], [], []
    for i in range(0, len(data), 32):
        b = data[i:i + 32]
        ids, wtgt, probe_pos, focus = D.collate(b, vocab.PAD, device)
        f = model.features(ids)
        ar = torch.arange(ids.shape[0], device=device)
        local = model.embed(ids)[ar, probe_pos]
        row = {
            "local": local,
            "state": f["state"][ar, probe_pos],
            "raw_readout": f["raw_readout"][ar, probe_pos],
            "selective_readout": f["selective_readout"][ar, probe_pos],
        }
        row["local+state"] = torch.cat([row["local"], row["state"]], dim=-1)
        for k, v in row.items():
            feats_probe.setdefault(k, []).append(v)
        ys.append(focus)
        # event-level relevance from selective readout
        for j, e in enumerate(b):
            if not e["event_pos"]:
                continue
            ep = torch.tensor(e["event_pos"], device=device)
            xevt.append(f["selective_readout"][j, ep])
            yrel.append(torch.tensor([1.0 if r else 0.0 for r in e["event_relevant"]], device=device))
    X = {k: torch.cat(v, 0) for k, v in feats_probe.items()}
    y = torch.cat(ys, 0)
    Xe = torch.cat(xevt, 0) if xevt else torch.zeros(0, model.embed_dim)
    ye = torch.cat(yrel, 0) if yrel else torch.zeros(0)
    return X, y, Xe, ye


def _fit_linear(Xtr, ytr, Xte, yte, num_classes, epochs=PROBE_EPOCHS, l2=PROBE_L2, seed=0):
    torch.manual_seed(seed)
    mu, sd = Xtr.mean(0, keepdim=True), Xtr.std(0, keepdim=True) + 1e-5
    Xtr = (Xtr - mu) / sd; Xte = (Xte - mu) / sd
    W = torch.zeros(Xtr.shape[1], num_classes, requires_grad=True)
    b = torch.zeros(num_classes, requires_grad=True)
    opt = torch.optim.Adam([W, b], lr=0.05, weight_decay=l2)
    for _ in range(epochs):
        opt.zero_grad()
        loss = F.cross_entropy(Xtr @ W + b, ytr)
        loss.backward(); opt.step()
    with torch.no_grad():
        logits = Xte @ W + b
        prob = logits.softmax(-1)
        top1 = (logits.argmax(-1) == yte).float().mean().item()
        k = min(3, num_classes)
        topk = (logits.topk(k, -1).indices == yte.unsqueeze(1)).any(1).float().mean().item()
        # ECE (15 bins)
        conf, pred = prob.max(-1)
        ece = 0.0
        for lo in torch.linspace(0, 1, 16)[:-1]:
            m = (conf >= lo) & (conf < lo + 1 / 15)
            if m.any():
                ece += m.float().mean().item() * abs(
                    (pred[m] == yte[m]).float().mean().item() - conf[m].mean().item())
    return {"top1": top1, "topk": topk, "ece": ece}


def _fit_binary(Xtr, ytr, Xte, yte, epochs=PROBE_EPOCHS, l2=PROBE_L2, seed=0):
    if Xtr.shape[0] == 0 or ytr.sum() == 0 or ytr.sum() == len(ytr):
        return {"f1": 0.0, "auroc": 0.5}
    torch.manual_seed(seed)
    mu, sd = Xtr.mean(0, keepdim=True), Xtr.std(0, keepdim=True) + 1e-5
    Xtr = (Xtr - mu) / sd; Xte = (Xte - mu) / sd
    W = torch.zeros(Xtr.shape[1], 1, requires_grad=True)
    b = torch.zeros(1, requires_grad=True)
    opt = torch.optim.Adam([W, b], lr=0.05, weight_decay=l2)
    pw = ((ytr == 0).sum() / (ytr.sum() + 1e-6)).clamp(0.2, 5.0)
    for _ in range(epochs):
        opt.zero_grad()
        logit = (Xtr @ W + b).squeeze(-1)
        loss = F.binary_cross_entropy_with_logits(logit, ytr, pos_weight=pw)
        loss.backward(); opt.step()
    with torch.no_grad():
        logit = (Xte @ W + b).squeeze(-1)
        pred = (logit > 0).float()
        tp = (pred * yte).sum(); fp = (pred * (1 - yte)).sum(); fn = ((1 - pred) * yte).sum()
        prec = tp / (tp + fp + 1e-6); rec = tp / (tp + fn + 1e-6)
        f1 = (2 * prec * rec / (prec + rec + 1e-6)).item()
        # AUROC via rank statistic
        order = logit.argsort()
        yr = yte[order]; npos = yr.sum().item(); nneg = (1 - yr).sum().item()
        if npos == 0 or nneg == 0:
            auroc = 0.5
        else:
            ranks = torch.arange(1, len(yr) + 1, dtype=torch.float)
            auroc = ((ranks[yr == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg)).item()
    return {"f1": f1, "auroc": auroc}


def probe_all(model, vocab, dcfg, distance, seed=0, n_train=600, n_eval=400, device="cpu"):
    tr = D.generate(vocab, dcfg, distance, n_train, 5000 + seed)
    te = D.generate(vocab, dcfg, distance, n_eval, 9000 + seed)
    Xtr, ytr, Etr, rtr = _extract(model, tr, vocab, device)
    Xte, yte, Ete, rte = _extract(model, te, vocab, device)
    E = dcfg.num_entities
    g = torch.Generator().manual_seed(seed)
    results = {}
    for name in ("local", "state", "raw_readout", "selective_readout", "local+state"):
        results[name] = _fit_linear(Xtr[name], ytr, Xte[name], yte, E, seed=seed)
    # controls
    perm = torch.randperm(Xtr["state"].shape[0], generator=g)
    results["shuffled_state"] = _fit_linear(Xtr["state"][perm], ytr, Xte["state"], yte, E, seed=seed)
    results["random_state"] = _fit_linear(torch.randn_like(Xtr["state"]), ytr,
                                           torch.randn_like(Xte["state"]), yte, E, seed=seed)
    # relevance (from selective readout at event positions)
    rel = _fit_binary(Etr, rtr, Ete, rte, seed=seed)
    results["relevance"] = rel
    results["chance"] = 1.0 / E
    return results
