"""Semantic-importance KV tiering — SYNTHETIC research-hypothesis experiment.

⚠️  THIS IS A CONTROLLED SYNTHETIC STUDY, NOT A REAL-LLM RESULT. ⚠️

HYPOTHESIS (the one non-cosmetic portfolio cross-application): choosing which KV
to keep hot by a SEMANTIC-coherence score — SCC's C_i = α·S_i + β·R_i + … with
S = cosine similarity — could retain more *output-relevant* KV than the standard
ATTENTION-MAGNITUDE selector (read-skip / H2O / Quest / SnapKV) **iff token
importance has a component that attention magnitude misses but a coherence score
captures.**

This script does NOT claim that is true on real models. It builds a world where
ground-truth importance is a *controllable mix* of an attention-visible factor
and a semantic factor, and measures how much true importance each selector
retains at a fixed KV budget. That isolates the mechanism and reduces the open
question to ONE measurable quantity:

    w_sem = the fraction of real KV importance that attention magnitude misses
            but a coherence score predicts.

If w_sem ≈ 0 on real models, semantic tiering is pointless (attention wins). If
w_sem is meaningfully > 0, it helps. **Measuring w_sem requires a GPU experiment
on a real model with a real coherence signal — this script cannot and does not
do that.** Treat all numbers here as mechanism illustration, not evidence.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class Config:
    n_tokens: int = 2000
    dim: int = 64
    budget_frac: float = 0.10      # keep 10% of KV hot
    w_sem: float = 0.5             # fraction of importance that is semantic (attention-invisible)
    signal_noise: float = 0.10     # observation noise on both signals
    sink: int = 8
    recent: int = 64
    seed: int = 0


def run_trial(cfg: Config) -> dict:
    rng = random.Random(cfg.seed)

    # A fixed "context centroid" direction; a token's semantic coherence is its
    # cosine to it (SCC's S[i,j] form, here token-vs-context).
    centroid = _unit([rng.gauss(0, 1) for _ in range(cfg.dim)])

    a_latent, s_latent, emb = [], [], []
    for _ in range(cfg.n_tokens):
        a_i = rng.random()                       # attention-visible importance driver
        s_i = rng.random()                       # semantic importance driver
        a_latent.append(a_i)
        s_latent.append(s_i)
        # embedding whose cosine to the centroid ≈ s_i (so the SCC cosine recovers s)
        o = [rng.gauss(0, 1) for _ in range(cfg.dim)]
        proj = _dot(o, centroid)
        o = _unit([oi - proj * ci for oi, ci in zip(o, centroid)])   # orthogonalize
        e = [s_i * ci + math.sqrt(max(0.0, 1 - s_i * s_i)) * oi for ci, oi in zip(centroid, o)]
        emb.append(_unit(e))

    # Observable signals (noisy) and the hidden ground-truth importance.
    attn = [a_latent[i] + rng.gauss(0, cfg.signal_noise) for i in range(cfg.n_tokens)]
    coh = [_dot(emb[i], centroid) + rng.gauss(0, cfg.signal_noise) for i in range(cfg.n_tokens)]
    true = [(1 - cfg.w_sem) * a_latent[i] + cfg.w_sem * s_latent[i] for i in range(cfg.n_tokens)]

    budget = int(cfg.n_tokens * cfg.budget_frac)
    pinned = set(range(cfg.sink)) | set(range(cfg.n_tokens - cfg.recent, cfg.n_tokens))

    def select(score: list[float]) -> set[int]:
        cand = sorted((i for i in range(cfg.n_tokens) if i not in pinned),
                      key=lambda i: score[i], reverse=True)
        keep = set(pinned)
        keep.update(cand[: max(0, budget - len(pinned))])
        return keep

    rand_score = [rng.random() for _ in range(cfg.n_tokens)]
    selectors = {
        "attention (magnitude)": select(attn),
        "semantic (coherence)": select(coh),
        "SCC (½·attn+½·coh)": select([0.5 * attn[i] + 0.5 * coh[i] for i in range(cfg.n_tokens)]),
        "oracle (true imp.)": select(true),
        "random+pins": select(rand_score),
    }

    total_imp = sum(true)
    captured = {name: sum(true[i] for i in S) / total_imp for name, S in selectors.items()}

    # "needles": genuinely important tokens that attention magnitude would miss
    # (high true importance, low attention) — the failure mode of attn selection.
    hi = sorted(true)[int(0.85 * cfg.n_tokens)]
    lo_attn = sorted(attn)[int(0.50 * cfg.n_tokens)]
    needles = [i for i in range(cfg.n_tokens) if true[i] >= hi and attn[i] <= lo_attn]
    needle_recall = {
        name: (sum(1 for i in needles if i in S) / len(needles)) if needles else float("nan")
        for name, S in selectors.items()
    }
    return {"captured": captured, "needle_recall": needle_recall, "n_needles": len(needles)}


def _avg_over_seeds(cfg: Config, seeds: int = 5) -> dict:
    acc_cap: dict[str, float] = {}
    acc_ndl: dict[str, float] = {}
    n_ndl = 0
    for sd in range(seeds):
        r = run_trial(Config(**{**cfg.__dict__, "seed": sd}))
        for k, v in r["captured"].items():
            acc_cap[k] = acc_cap.get(k, 0.0) + v
        for k, v in r["needle_recall"].items():
            acc_ndl[k] = acc_ndl.get(k, 0.0) + (0.0 if math.isnan(v) else v)
        n_ndl += r["n_needles"]
    return {"captured": {k: v / seeds for k, v in acc_cap.items()},
            "needle_recall": {k: v / seeds for k, v in acc_ndl.items()},
            "avg_needles": n_ndl / seeds}


def main() -> None:
    print("SEMANTIC-IMPORTANCE KV TIERING — synthetic mechanism study (NOT a real-LLM result)\n")
    print("Captured true-importance mass at 10% KV budget, vs w_sem")
    print("(w_sem = fraction of importance attention misses but coherence sees)\n")
    names = ["attention (magnitude)", "semantic (coherence)", "SCC (½·attn+½·coh)",
             "oracle (true imp.)", "random+pins"]
    print(f"{'w_sem':>7}" + "".join(f"{n.split(' ')[0][:9]:>11}" for n in names))
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        r = _avg_over_seeds(Config(w_sem=w))
        row = "".join(f"{r['captured'][n]:>11.3f}" for n in names)
        print(f"{w:>7.2f}{row}")

    print("\nNeedle recall (high-importance / low-attention tokens) at w_sem=0.6:")
    r = _avg_over_seeds(Config(w_sem=0.6))
    for n in names:
        print(f"  {n:<24}{r['needle_recall'][n]:.3f}")
    print(f"  (avg {r['avg_needles']:.0f} needle tokens / trial)")

    print("\n--- HONEST READOUT ---")
    print("• At w_sem=0 attention selection is optimal; semantic adds nothing (expected).")
    print("• As w_sem rises, semantic/SCC retain more true importance AND catch the needles")
    print("  attention misses — but this is BY CONSTRUCTION; it only proves the mechanism.")
    print("• SCC (blend) is the robust choice: never far below the better single signal.")
    print("• REAL-WORLD VALUE IS UNKNOWN: it hinges entirely on the real w_sem and on whether")
    print("  a model's coherence score actually predicts KV importance. Both require a GPU")
    print("  experiment on a real model. This script does NOT measure them and makes NO claim.")


if __name__ == "__main__":
    main()
