"""Learned KV-importance probe — train a small ranker on per-block features and
test whether it beats the FREE attention-magnitude baseline ON A HELD-OUT MODEL.

The decisive question (per the negative result so far): a probe can fold in
attention + value geometry + position and *might* close attention's gap — but
only if the learned mapping TRANSFERS across models. So the eval is explicitly
train-on-some-models / test-on-a-held-out-model, and the go/no-go is the probe's
held-out recall vs attention-only recall.

Features come from `loo_importance.py --dump-features` (GPU). Training + eval
here are pure numpy (CPU). `--synthetic` validates the pipeline AND demonstrates
the transfer vs non-transfer cases without a GPU.
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

FEATURES = ["attn_mean", "attn_max", "attn_last", "coherence", "value_norm", "recency", "idx_frac"]
# Serving-SAFE subset: computable in one normal decode pass. Excludes attn_mean/max
# (multi-LAYER attention — NOT free; fused/flash kernels don't expose all-layer attn).
# attn_last = single-layer read-skip score; coherence/value_norm = one-layer value
# geometry; recency/idx_frac = free. The verdict is gated on THIS set (gate 2).
SERVING_SAFE = ["attn_last", "coherence", "value_norm", "recency", "idx_frac"]
ATTN_BASELINE_FEATURE = "attn_last"   # the free single-layer attention signal to beat
GO_BAR = 0.10                          # gate 1: held-out margin must clear +0.10 to matter


# ------------------------------ data ---------------------------------------- #
def load_dump(path: str) -> list[dict]:
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _design(records: list[dict], feats: list[str] = FEATURES):
    X = np.array([[r["features"][f] for f in feats] for r in records], dtype=float)
    y = np.array([r["label"] for r in records], dtype=float)
    groups = [(r["model"], r["seed"]) for r in records]
    return X, y, groups


def _topk_binary(y: np.ndarray, groups: list, frac: float) -> np.ndarray:
    """1 if a block is in the top-`frac` by importance WITHIN its (model,seed) group."""
    yb = np.zeros_like(y)
    for g in set(groups):
        idx = [i for i, gg in enumerate(groups) if gg == g]
        k = max(1, round(frac * len(idx)))
        top = sorted(idx, key=lambda i: y[i], reverse=True)[:k]
        yb[top] = 1.0
    return yb


def recall_at_budget(scores: np.ndarray, y: np.ndarray, groups: list, frac: float) -> float:
    """Mean over groups of: recall of the top-`frac` truly-important blocks within
    the score's top-`frac` budget."""
    recs = []
    for g in set(groups):
        idx = [i for i, gg in enumerate(groups) if gg == g]
        k = max(1, round(frac * len(idx)))
        important = set(sorted(idx, key=lambda i: y[i], reverse=True)[:k])
        picked = set(sorted(idx, key=lambda i: scores[i], reverse=True)[:k])
        recs.append(len(picked & important) / len(important))
    return float(np.mean(recs)) if recs else float("nan")


# ------------------------------ ranker -------------------------------------- #
class LogisticRanker:
    """Standardized logistic regression on 'is-top-K-important' — pure numpy.
    (Swap for LightGBM/sklearn later; this is enough for a go/no-go.)"""

    def __init__(self, iters: int = 600, lr: float = 0.5, l2: float = 1e-3):
        self.iters, self.lr, self.l2 = iters, lr, l2

    def fit(self, X: np.ndarray, yb: np.ndarray):
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Xs = (X - self.mu) / self.sd
        n, d = Xs.shape
        w, b = np.zeros(d), 0.0
        for _ in range(self.iters):
            p = 1.0 / (1.0 + np.exp(-(Xs @ w + b)))
            g = p - yb
            w -= self.lr * (Xs.T @ g / n + self.l2 * w)
            b -= self.lr * g.mean()
        self.w, self.b = w, b
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return ((X - self.mu) / self.sd) @ self.w + self.b

    def weights_named(self, feats: list[str]) -> dict:
        return {f: round(float(wi), 2) for f, wi in zip(feats, self.w)}


# ------------------------------ evaluation ---------------------------------- #
def _probe_recall(train, test, feats, frac):
    Xtr, ytr, gtr = _design(train, feats)
    Xte, yte, gte = _design(test, feats)
    ranker = LogisticRanker().fit(Xtr, _topk_binary(ytr, gtr, frac))
    return recall_at_budget(ranker.score(Xte), yte, gte, frac), ranker.weights_named(feats)


def evaluate(train: list[dict], test: list[dict], frac: float = 0.15) -> dict:
    """Train on `train` models, evaluate on the held-out `test` model. Reports BOTH
    a serving-safe probe (gate 2) and a full-feature probe, vs free attention. The
    verdict is gated on the SERVING-SAFE probe clearing +GO_BAR (gate 1)."""
    _, _, gte = _design(test, SERVING_SAFE)
    Xte_all, yte, _ = _design(test, FEATURES)
    attn_recall = recall_at_budget(Xte_all[:, FEATURES.index(ATTN_BASELINE_FEATURE)], yte, gte, frac)
    cheap_recall, cheap_w = _probe_recall(train, test, SERVING_SAFE, frac)
    full_recall, full_w = _probe_recall(train, test, FEATURES, frac)
    cheap_margin = cheap_recall - attn_recall
    full_margin = full_recall - attn_recall

    if cheap_margin >= GO_BAR:
        verdict = (f"GO — serving-safe probe beats attention by Δ{cheap_margin:+.3f} (≥{GO_BAR}) on the "
                   f"held-out model. NECESSARY-not-sufficient: now gate on Exp-B (decode quality + "
                   f"p99 latency) before adopting.")
    elif full_margin >= GO_BAR > cheap_margin:
        verdict = (f"RESEARCH-ONLY — only the EXPENSIVE-feature probe clears the bar "
                   f"(cheap Δ{cheap_margin:+.3f}, full Δ{full_margin:+.3f}); not serving-viable → don't ship.")
    else:
        verdict = (f"STOP — no probe clears +{GO_BAR} on held-out (cheap Δ{cheap_margin:+.3f}, "
                   f"full Δ{full_margin:+.3f}); attention is the selector.")
    return {"attn_recall": attn_recall, "cheap_recall": cheap_recall, "full_recall": full_recall,
            "cheap_margin": cheap_margin, "full_margin": full_margin, "margin": cheap_margin,
            "verdict": verdict, "cheap_weights": cheap_w, "full_weights": full_w}


# ------------------------------ synthetic ----------------------------------- #
def synthetic_records(model: str, weights: dict, n_seeds: int = 3, n_blocks: int = 80,
                      noise: float = 0.4, seed: int = 0) -> list[dict]:
    """Records whose importance = features·weights + noise — so a probe SHOULD
    recover the relationship if it transfers. Use different `weights` per model to
    simulate the cross-model non-replication we observed (Qwen vs Phi)."""
    rng = np.random.default_rng(seed)
    w = np.array([weights.get(f, 0.0) for f in FEATURES])
    recs = []
    for s in range(n_seeds):
        F = rng.standard_normal((n_blocks, len(FEATURES)))
        label = F @ w + noise * rng.standard_normal(n_blocks)
        for b in range(n_blocks):
            recs.append({"model": model, "seed": s, "block": b, "label": float(label[b]),
                         "features": {f: float(F[b, i]) for i, f in enumerate(FEATURES)}})
    return recs


def _synthetic_demo() -> None:
    # importance driven by serving-safe features (single-layer attn + value geometry)
    W_shared = {"attn_last": 1.0, "coherence": 0.8}
    W_flipped = {"attn_last": 1.0, "coherence": -0.8}   # value-geometry term FLIPS (Qwen↔Phi)
    A = synthetic_records("A", W_shared, seed=0)
    B_same = synthetic_records("B", W_shared, seed=1)
    B_flip = synthetic_records("B", W_flipped, seed=2)

    print("Learned-probe pipeline — synthetic (CPU). go/no-go = held-out-model recall vs attention.\n")
    r1 = evaluate(A, B_same)
    print(f"  [transfers]   train A, test B (SAME law):  attn {r1['attn_recall']:.2f}  "
          f"cheap {r1['cheap_recall']:.2f}  full {r1['full_recall']:.2f}")
    print(f"    → {r1['verdict']}\n")
    r2 = evaluate(A, B_flip)
    print(f"  [no transfer] train A, test B (FLIPPED law): attn {r2['attn_recall']:.2f}  "
          f"cheap {r2['cheap_recall']:.2f}  full {r2['full_recall']:.2f}")
    print(f"    → {r2['verdict']}")
    print("\n  Reading: a probe helps only if the importance law TRANSFERS across models AND the")
    print("  win comes from SERVING-SAFE features. The Qwen↔Phi flip is the 'no transfer' case.")


# ----------------------------------- CLI ------------------------------------ #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Learned KV-importance probe — held-out-model go/no-go")
    ap.add_argument("--synthetic", action="store_true", help="run the CPU synthetic demo")
    ap.add_argument("--dumps", default=None, help="comma list of feature dump files (one per model)")
    ap.add_argument("--test-model", default=None, help="model name to HOLD OUT for testing")
    ap.add_argument("--frac", type=float, default=0.15)
    args = ap.parse_args(argv)

    if args.synthetic or not args.dumps:
        _synthetic_demo()
        return 0

    records = []
    for p in args.dumps.split(","):
        records += load_dump(p.strip())
    models = sorted({r["model"] for r in records})
    test_model = args.test_model or models[-1]
    train = [r for r in records if r["model"] != test_model]
    test = [r for r in records if r["model"] == test_model]
    if not train or not test:
        ap.error(f"need ≥2 models; have {models}, holding out {test_model!r}")
    res = evaluate(train, test, frac=args.frac)
    print(f"Learned probe — train {sorted(set(r['model'] for r in train))}, TEST held-out '{test_model}'\n")
    print(f"  attention-only recall (held-out)   = {res['attn_recall']:.3f}")
    print(f"  serving-safe probe recall          = {res['cheap_recall']:.3f}   (Δ {res['cheap_margin']:+.3f})")
    print(f"  full-feature probe recall          = {res['full_recall']:.3f}   (Δ {res['full_margin']:+.3f})")
    print(f"  serving-safe weights               = {res['cheap_weights']}")
    print(f"\n  GO/NO-GO (gate1 ≥+{GO_BAR}, gate2 serving-safe-only): {res['verdict']}")
    print("\n  Gate 3 (not tested here): even on GO, confirm Exp-B — read-skip decode quality"
          "\n  (needle/greedy agreement) AND tokens/sec + p99 — before adopting. Recall ≠ product.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
