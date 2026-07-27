"""
evaluate.py — information-health metrics (no sklearn dependency).

Per target: AUROC, AUPRC, F1, precision, recall, Brier, ECE. Plus macro averages, breakdowns by
sequence length and evidence distance, false-positive rate on harmless-unusual events, and
false-negative rate on true unresolved recurrence. AUROC is never treated as sufficient alone.
"""
from __future__ import annotations

import math
import torch

from .dataset import TARGETS
from .train import collate


def auroc(scores, labels):
    s = torch.as_tensor(scores, dtype=torch.float64); y = torch.as_tensor(labels, dtype=torch.float64)
    pos = y == 1; neg = y == 0
    npos, nneg = int(pos.sum()), int(neg.sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    order = s.argsort()
    ranks = torch.zeros_like(s); ranks[order] = torch.arange(1, len(s) + 1, dtype=torch.float64)
    # average ranks for ties
    _, inv, counts = torch.unique(s, return_inverse=True, return_counts=True)
    sums = torch.zeros(len(counts), dtype=torch.float64).scatter_add_(0, inv, ranks)
    ranks = (sums / counts)[inv]
    auc = (ranks[pos].sum() - npos * (npos + 1) / 2) / (npos * nneg)
    return float(auc)


def auprc(scores, labels):
    s = torch.as_tensor(scores, dtype=torch.float64); y = torch.as_tensor(labels, dtype=torch.float64)
    if y.sum() == 0:
        return float("nan")
    order = s.argsort(descending=True); y = y[order]
    tp = torch.cumsum(y, 0); fp = torch.cumsum(1 - y, 0)
    precision = tp / (tp + fp).clamp(min=1e-9)
    recall = tp / y.sum()
    ap = 0.0; prev_r = 0.0
    for p, r in zip(precision.tolist(), recall.tolist()):
        ap += p * (r - prev_r); prev_r = r
    return float(ap)


def prf(scores, labels, thr=0.5):
    p = (torch.as_tensor(scores) >= thr).float(); y = torch.as_tensor(labels).float()
    tp = float((p * y).sum()); fp = float((p * (1 - y)).sum()); fn = float(((1 - p) * y).sum())
    prec = tp / max(1e-9, tp + fp); rec = tp / max(1e-9, tp + fn)
    f1 = 2 * prec * rec / max(1e-9, prec + rec)
    return prec, rec, f1


def brier(scores, labels):
    return float(((torch.as_tensor(scores, dtype=torch.float64) -
                   torch.as_tensor(labels, dtype=torch.float64)) ** 2).mean())


def ece(scores, labels, bins=10):
    s = torch.as_tensor(scores, dtype=torch.float64); y = torch.as_tensor(labels, dtype=torch.float64)
    e = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        m = (s >= lo) & (s < hi if b < bins - 1 else s <= hi)
        if m.sum() == 0:
            continue
        e += float(m.float().mean()) * abs(float(s[m].mean()) - float(y[m].mean()))
    return e


@torch.no_grad()
def predict(model, data, schema, device="cpu", batch_size=32, phase_mode="normal"):
    model.eval()
    probs = {t: [] for t in TARGETS}; labs = {t: [] for t in TARGETS}
    dists = []; harmless_flags = []
    for i in range(0, len(data), batch_size):
        b = data[i:i + batch_size]
        cats, num, det, qp, pk, vl, labels = collate(b, schema, device)
        logits, _ = model(cats, num, det, qp, pk, vl, phase_mode=phase_mode)
        for t in TARGETS:
            probs[t] += torch.sigmoid(logits[t]).tolist(); labs[t] += labels[t].tolist()
        dists += [ex["min_relevant_distance"] for ex in b]
        harmless_flags += [any(e["tag"] == "harmless_unusual" for e in ex["events"]) for ex in b]
    return probs, labs, dists, harmless_flags


def metrics_for(probs, labs):
    out = {}
    for t in TARGETS:
        s, y = probs[t], labs[t]
        prec, rec, f1 = prf(s, y)
        out[t] = {"auroc": auroc(s, y), "auprc": auprc(s, y), "f1": f1, "precision": prec,
                  "recall": rec, "brier": brier(s, y), "ece": ece(s, y),
                  "pos_rate": float(torch.as_tensor(y).float().mean())}
    valid = [out[t]["auroc"] for t in TARGETS if not math.isnan(out[t]["auroc"])]
    out["macro_auroc"] = sum(valid) / max(1, len(valid))
    out["macro_auprc"] = sum(out[t]["auprc"] for t in TARGETS if not math.isnan(out[t]["auprc"])) / len(TARGETS)
    out["macro_brier"] = sum(out[t]["brier"] for t in TARGETS) / len(TARGETS)
    return out


def evaluate(model, data, schema, device="cpu", phase_mode="normal"):
    probs, labs, dists, harmless = predict(model, data, schema, device, phase_mode=phase_mode)
    res = metrics_for(probs, labs)
    # false-positive on harmless-unusual: predicted anomaly where no true anomaly, harmless present
    fp = tot = 0
    for p, y, h in zip(probs["sequence_anomaly"], labs["sequence_anomaly"], harmless):
        if h and y == 0:
            tot += 1; fp += (p >= 0.5)
    res["anomaly_fp_on_harmless"] = fp / max(1, tot)
    # false-negative on true recurrence
    fn = totr = 0
    for p, y in zip(probs["unresolved_recurrence"], labs["unresolved_recurrence"]):
        if y == 1:
            totr += 1; fn += (p < 0.5)
    res["recurrence_fn"] = fn / max(1, totr)
    # by-distance buckets (persistence + recurrence, the long-range targets)
    buckets = {"near(<64)": [], "mid(64-256)": [], "far(>256)": []}
    for j, d in enumerate(dists):
        key = "near(<64)" if d < 64 else "mid(64-256)" if d < 256 else "far(>256)"
        buckets[key].append(j)
    res["by_distance"] = {}
    for key, idxs in buckets.items():
        if len(idxs) < 8:
            continue
        sub = {t: {"s": [probs[t][j] for j in idxs], "y": [labs[t][j] for j in idxs]} for t in TARGETS}
        res["by_distance"][key] = {t: auroc(sub[t]["s"], sub[t]["y"]) for t in
                                   ("persistence", "unresolved_recurrence")}
    return res
