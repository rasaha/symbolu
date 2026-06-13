"""Exp-A: leave-one-block-out (LOO) KV-importance harness (CPU-testable, GPU-ready).

Answers the only open question (docs/SEMANTIC_TIERING_GPU_PROTOCOL.md §3): does a
coherence score predict which KV the model actually needs *beyond* what attention
magnitude already predicts? Ground truth = the change in the model's next-token
distribution when block b is masked (LOO). The decisive statistic is the PARTIAL
correlation ρ(coherence, importance | attention) — coherence's incremental power.

  * Synthetic path (`--synthetic`): a known generative model with a tunable
    semantic-vs-attention importance mix (w_sem). Runs on CPU, tests the whole
    pipeline (LOO → stats → decision) today.
  * Real path (`--model`): documented GPU hook (torch + transformers). It is a
    marked scaffold, NOT yet implemented — fill the two hooks and run on a pod.

Usage:
  python -m ndol.experiments.loo_importance --synthetic --w-sem 0.5
  python -m ndol.experiments.loo_importance --model Qwen2.5-7B   # -> raises with guidance
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass

from .coherence import coherence_scores, context_centroid


# ------------------------------- statistics -------------------------------- #
def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 2:
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    d = math.sqrt(sxx * syy)
    return sxy / d if d else 0.0


def spearman(x: list[float], y: list[float]) -> float:
    return pearson(_ranks(x), _ranks(y))


def partial_spearman(x: list[float], y: list[float], z: list[float]) -> float:
    """ρ(x, y | z) on ranks — x's correlation with y after removing z's effect."""
    rxy, rxz, ryz = spearman(x, y), spearman(x, z), spearman(y, z)
    denom = math.sqrt(max(1e-12, (1 - rxz ** 2) * (1 - ryz ** 2)))
    return (rxy - rxz * ryz) / denom


def _softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    ex = [math.exp(v - m) for v in logits]
    s = sum(ex)
    return [e / s for e in ex]


def _kl(p: list[float], q: list[float]) -> float:
    return sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0 and qi > 0)


# ------------------------------ synthetic model ---------------------------- #
@dataclass
class SyntheticConfig:
    n_blocks: int = 400
    dim: int = 48
    vocab: int = 32
    w_sem: float = 0.5          # semantic share of true importance (attention-invisible)
    signal_noise: float = 0.10
    seed: int = 0


def _synthetic_world(cfg: SyntheticConfig):
    """A toy decoder: next-token logits = Σ_b strength_b · dir_b. Masking block b
    removes its contribution; LOO importance = KL(full ‖ full−b). strength_b is a
    tunable mix of an attention-visible and a semantic latent, so the harness has
    a known ground truth to recover."""
    rng = random.Random(cfg.seed)
    centroid = context_centroid([[rng.gauss(0, 1) for _ in range(cfg.dim)]])  # unit dir
    centroid = [rng.gauss(0, 1) for _ in range(cfg.dim)]
    nrm = math.sqrt(sum(c * c for c in centroid)) or 1.0
    centroid = [c / nrm for c in centroid]

    a_lat, s_lat, block_vecs, dirs, strength = [], [], [], [], []
    for _ in range(cfg.n_blocks):
        a = rng.random()           # attention-visible latent
        s = rng.random()           # semantic latent
        a_lat.append(a)
        s_lat.append(s)
        # block value-vector with cosine-to-centroid ≈ s (so coherence recovers s)
        o = [rng.gauss(0, 1) for _ in range(cfg.dim)]
        proj = sum(oi * ci for oi, ci in zip(o, centroid))
        o = [oi - proj * ci for oi, ci in zip(o, centroid)]
        on = math.sqrt(sum(v * v for v in o)) or 1.0
        o = [v / on for v in o]
        v = [s * ci + math.sqrt(max(0.0, 1 - s * s)) * oi for ci, oi in zip(centroid, o)]
        block_vecs.append(v)
        dirs.append([rng.gauss(0, 1) for _ in range(cfg.vocab)])   # logit direction
        strength.append((1 - cfg.w_sem) * a + cfg.w_sem * s)        # true importance driver

    # observable signals
    attention = [a_lat[i] + rng.gauss(0, cfg.signal_noise) for i in range(cfg.n_blocks)]
    coherence = coherence_scores(block_vecs, centroid, mode="cos_value")
    coherence = [coherence[i] + rng.gauss(0, cfg.signal_noise) for i in range(cfg.n_blocks)]

    full_logits = [0.0] * cfg.vocab
    for b in range(cfg.n_blocks):
        for t in range(cfg.vocab):
            full_logits[t] += strength[b] * dirs[b][t]
    p_full = _softmax(full_logits)

    def loo_importance(b: int) -> float:
        without = [full_logits[t] - strength[b] * dirs[b][t] for t in range(cfg.vocab)]
        return _kl(p_full, _softmax(without))

    return attention, coherence, loo_importance


def run_synthetic(cfg: SyntheticConfig) -> dict:
    attention, coherence, loo = _synthetic_world(cfg)
    n = cfg.n_blocks
    true = [loo(b) for b in range(n)]   # full LOO (cheap in synthetic; sampled on real models)

    rho_attn = spearman(attention, true)
    rho_coh = spearman(coherence, true)
    rho_partial = partial_spearman(coherence, true, attention)   # the decisive 'w_sem' proxy

    # needle recall: high-importance, low-attention blocks
    hi = sorted(true)[int(0.85 * n)]
    lo_attn = sorted(attention)[int(0.50 * n)]
    needles = [i for i in range(n) if true[i] >= hi and attention[i] <= lo_attn]
    budget = int(0.10 * n)

    def top(scores):
        return set(sorted(range(n), key=lambda i: scores[i], reverse=True)[:budget])

    def recall(scores):
        S = top(scores)
        return (sum(1 for i in needles if i in S) / len(needles)) if needles else float("nan")

    return {
        "rho_attn": rho_attn,
        "rho_coh": rho_coh,
        "rho_partial_coh_given_attn": rho_partial,
        "needle_recall_attn": recall(attention),
        "needle_recall_coh": recall(coherence),
        "n_needles": len(needles),
    }


# ------------------------------ real-model hook ---------------------------- #
def run_real(model: str, task: str = "needle", **kw):
    """GPU path — NOT YET IMPLEMENTED (documented scaffold).

    To implement (see docs/SEMANTIC_TIERING_GPU_PROTOCOL.md §2–§3):
      HOOK 1 — capture per-block KV (mean value/key vectors) + attention block
               scores from the model's decode step (reuse ReadSkipController's
               block_score for attention; coherence via experiments.coherence.score_torch).
      HOOK 2 — for a stratified sample of blocks, mask the block in the KV and
               re-run the forward; true_importance(b) = KL(full ‖ masked) on the
               next-token distribution.
    Then feed (attention, coherence, true) into spearman/partial_spearman/needle
    recall above and apply pre-registered Decision Rule A.
    """
    raise NotImplementedError(
        "Real-model LOO needs torch + transformers + GPU. This is a marked scaffold — "
        "fill HOOK 1 (capture per-block KV + attention/coherence scores) and HOOK 2 "
        "(masked re-forward → KL) per docs/SEMANTIC_TIERING_GPU_PROTOCOL.md §2–§3, then "
        "reuse the stats in this module. Run --synthetic to exercise the pipeline on CPU."
    )


# ----------------------------------- CLI ----------------------------------- #
def _decision(rho_partial: float, nr_coh: float, nr_attn: float) -> str:
    if rho_partial > 0.1 and nr_coh > nr_attn + 0.05:
        return "USEFUL (coherence adds incremental predictive power) — proceed to Exp B"
    return "NOT USEFUL here (w_sem≈0; attention suffices) — drop unless Exp B disagrees"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exp-A: LOO KV-importance signal predictivity")
    ap.add_argument("--synthetic", action="store_true", help="run the CPU synthetic model")
    ap.add_argument("--w-sem", type=float, default=0.5, help="(synthetic) semantic importance share")
    ap.add_argument("--n-blocks", type=int, default=400)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--model", default=None, help="(GPU) HF model id — real path, not yet implemented")
    args = ap.parse_args(argv)

    if args.model and not args.synthetic:
        run_real(args.model)   # raises with guidance
        return 0

    if not args.synthetic:
        ap.error("pass --synthetic (CPU) or --model <id> (GPU scaffold)")

    # average over seeds for stability
    keys = ["rho_attn", "rho_coh", "rho_partial_coh_given_attn",
            "needle_recall_attn", "needle_recall_coh"]
    acc = {k: 0.0 for k in keys}
    for sd in range(args.seeds):
        r = run_synthetic(SyntheticConfig(n_blocks=args.n_blocks, w_sem=args.w_sem, seed=sd))
        for k in keys:
            acc[k] += r[k]
    avg = {k: v / args.seeds for k, v in acc.items()}

    print(f"Exp-A (synthetic, w_sem={args.w_sem}, n_blocks={args.n_blocks}, seeds={args.seeds})\n")
    print(f"  Spearman(attention, importance)            = {avg['rho_attn']:+.3f}")
    print(f"  Spearman(coherence, importance)            = {avg['rho_coh']:+.3f}")
    print(f"  PARTIAL  (coherence, importance | attn)    = {avg['rho_partial_coh_given_attn']:+.3f}  <- decisive")
    print(f"  needle recall  attention / coherence       = {avg['needle_recall_attn']:.3f} / {avg['needle_recall_coh']:.3f}")
    print(f"\n  decision: {_decision(avg['rho_partial_coh_given_attn'], avg['needle_recall_coh'], avg['needle_recall_attn'])}")
    print("\n  NOTE: synthetic — proves the harness + decision rule. Real w_sem is unknown;"
          "\n  run the --model path on a GPU pod to measure it on a real model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
