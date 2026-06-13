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
ATTN_BASELINE_FEATURE = "attn_mean"   # the free signal the probe must beat


# ------------------------------ data ---------------------------------------- #
def load_dump(path: str) -> list[dict]:
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _design(records: list[dict]):
    X = np.array([[r["features"][f] for f in FEATURES] for r in records], dtype=float)
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

    def weights(self) -> dict:
        return {f: float(wi) for f, wi in zip(FEATURES, self.w)}


# ------------------------------ evaluation ---------------------------------- #
def evaluate(train: list[dict], test: list[dict], frac: float = 0.15) -> dict:
    Xtr, ytr, gtr = _design(train)
    Xte, yte, gte = _design(test)
    ranker = LogisticRanker().fit(Xtr, _topk_binary(ytr, gtr, frac))
    probe_recall = recall_at_budget(ranker.score(Xte), yte, gte, frac)
    attn_recall = recall_at_budget(Xte[:, FEATURES.index(ATTN_BASELINE_FEATURE)], yte, gte, frac)
    margin = probe_recall - attn_recall
    if margin > 0.05:
        verdict = f"PROMISING — probe beats attention on the held-out model by Δrecall {margin:+.3f}"
    elif margin < -0.02:
        verdict = f"WORSE than attention on held-out (Δ {margin:+.3f}) — overfit / no transfer"
    else:
        verdict = f"NO GAIN — probe ≈ attention on held-out (Δ {margin:+.3f}); attention suffices"
    return {"probe_recall": probe_recall, "attn_recall": attn_recall, "margin": margin,
            "verdict": verdict, "weights": ranker.weights()}


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
    # importance driven by attention + a value-geometry feature (coherence)
    W_shared = {"attn_mean": 1.0, "coherence": 0.8}
    # a model where the value-geometry term FLIPS sign (the Qwen↔Phi non-replication)
    W_flipped = {"attn_mean": 1.0, "coherence": -0.8}
    A = synthetic_records("A", W_shared, seed=0)
    B_same = synthetic_records("B", W_shared, seed=1)
    B_flip = synthetic_records("B", W_flipped, seed=2)

    print("Learned-probe pipeline — synthetic (CPU). go/no-go = held-out-model recall vs attention.\n")
    r1 = evaluate(A, B_same)
    print("  [transfers]   train A, test B (SAME importance law):")
    print(f"    probe {r1['probe_recall']:.3f} vs attn {r1['attn_recall']:.3f}  → {r1['verdict']}")
    r2 = evaluate(A, B_flip)
    print("  [no transfer] train A, test B (FLIPPED value-geometry law):")
    print(f"    probe {r2['probe_recall']:.3f} vs attn {r2['attn_recall']:.3f}  → {r2['verdict']}")
    print("\n  Reading: a probe only helps if the importance law TRANSFERS across models. The")
    print("  observed Qwen↔Phi flip is the 'no transfer' case — which is why the prior is poor.")


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
    print(f"  probe recall (held-out model) = {res['probe_recall']:.3f}")
    print(f"  attention-only recall         = {res['attn_recall']:.3f}")
    print(f"  margin                        = {res['margin']:+.3f}")
    print(f"  learned weights               = { {k: round(v,2) for k,v in res['weights'].items()} }")
    print(f"\n  GO/NO-GO: {res['verdict']}")
    print("\n  Decisive test is the HELD-OUT model. If no gain there, attention suffices — stop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
