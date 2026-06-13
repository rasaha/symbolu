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
import statistics
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


def _bootstrap_partial(x: list[float], y: list[float], z: list[float],
                       n: int = 500, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap CI for partial_spearman(x, y | z) — so the >0.1 call carries
    uncertainty instead of resting on a single point estimate."""
    rng = random.Random(seed)
    m = len(x)
    if m < 8:
        return (float("nan"), float("nan"))
    vals = []
    for _ in range(n):
        idx = [rng.randrange(m) for _ in range(m)]
        vals.append(partial_spearman([x[i] for i in idx], [y[i] for i in idx], [z[i] for i in idx]))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


# --------------------------------------------------------------------------- #
# analyze() — turns (attention, coherence, true-importance) into stats +
# DIAGNOSTICS + a validity gate, so a degenerate run cannot yield a verdict.
# --------------------------------------------------------------------------- #
def analyze(attention: list[float], coherence: list[float], true: list[float],
            needle_budget_frac: float = 0.10) -> dict:
    n = len(true)
    rho_attn = spearman(attention, true)
    rho_coh = spearman(coherence, true)
    rho_partial = partial_spearman(coherence, true, attention)
    ci_lo, ci_hi = _bootstrap_partial(coherence, true, attention)
    rho_ac = spearman(attention, coherence)               # signal collinearity
    imp_sorted = sorted(true)
    imp_med = imp_sorted[n // 2] if n else 0.0
    imp_max = max(true) if n else 0.0
    frac_tiny = (sum(1 for t in true if t < 1e-4) / n) if n else 1.0
    attn_std = statistics.pstdev(attention) if n > 1 else 0.0
    coh_std = statistics.pstdev(coherence) if n > 1 else 0.0

    hi = imp_sorted[int(0.85 * n)] if n else 0.0
    lo_attn = sorted(attention)[int(0.50 * n)] if n else 0.0
    needles = [k for k in range(n) if true[k] >= hi and attention[k] <= lo_attn]
    budget = max(1, int(needle_budget_frac * n))

    def recall(scores):
        top = set(sorted(range(n), key=lambda k: scores[k], reverse=True)[:budget])
        return (sum(1 for k in needles if k in top) / len(needles)) if needles else float("nan")

    # validity gate — model-agnostic (does NOT assume attention predicts importance)
    reasons = []
    if imp_max < 1e-3:
        reasons.append("LOO importance ≈0 for every block — masking not applied, or context fully redundant")
    if frac_tiny > 0.95:
        reasons.append(f"{frac_tiny:.0%} of blocks have ~zero importance — degenerate ground truth")
    if abs(rho_ac) > 0.9:
        reasons.append(f"attention & coherence are collinear (ρ={rho_ac:+.2f}) — partial correlation unstable")
    if attn_std < 1e-9 or coh_std < 1e-9:
        reasons.append("a signal has ~no variance — cannot rank")

    return {
        "rho_attn": rho_attn, "rho_coh": rho_coh, "rho_partial_coh_given_attn": rho_partial,
        "rho_partial_ci": (ci_lo, ci_hi), "rho_attn_coh": rho_ac,
        "imp_med": imp_med, "imp_max": imp_max, "imp_frac_tiny": frac_tiny,
        "attn_std": attn_std, "coh_std": coh_std,
        "needle_recall_attn": recall(attention), "needle_recall_coh": recall(coherence),
        "n_needles": len(needles), "valid": len(reasons) == 0, "invalid_reasons": reasons,
    }


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
    true = [loo(b) for b in range(cfg.n_blocks)]   # full LOO (cheap synthetically; sampled on real models)
    return analyze(attention, coherence, true)


# ------------------------------ real-model path ---------------------------- #
_DEFAULT_TEXT = (
    "The history of computing spans mechanical calculators, vacuum tubes, transistors, "
    "and integrated circuits. Memory hierarchies trade capacity against latency. "
    "Long-context language models keep a key-value cache whose size grows with the "
    "sequence. Quantization reduces the bytes per element while protecting sensitive "
    "channels. Flash storage offers cheap capacity but limited write endurance. "
)


def run_real(
    model: str,
    *,
    text_file: str | None = None,
    prompt_len: int = 2048,
    block_size: int = 64,
    layer: int = -1,
    n_sample: int = 128,
    device: str = "cuda",
    seed: int = 0,
) -> dict:
    """GPU path: measure LOO KV-importance on a real model and compute Exp-A stats.

    ⚠️ WRITTEN TO THE HUGGINGFACE API BUT NOT EXECUTED HERE (no GPU in the dev box).
    Expect to adapt small details per model / attention backend on first run.

    Method (docs/SEMANTIC_TIERING_GPU_PROTOCOL.md §2–3):
      prefill the prompt (eager attn so attentions are returned) → per-block
      attention score (last query's attention mass over the block) and coherence
      score (mean value-vector cosine to the context centroid). For a sample of
      blocks, re-run the forward with that block masked in the attention mask and
      measure KL(full ‖ masked) as ground-truth importance. Then partial-correlate.
    """
    import torch  # noqa: F401
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from .coherence import score_torch

    rng = random.Random(seed)
    tok = AutoTokenizer.from_pretrained(model)
    # eager attention is required for output_attentions on most HF models
    lm = AutoModelForCausalLM.from_pretrained(
        model, torch_dtype="auto", attn_implementation="eager"
    ).to(device).eval()

    text = open(text_file).read() if text_file else _DEFAULT_TEXT
    ids = tok(text, return_tensors="pt").input_ids[0]
    while ids.numel() < prompt_len:  # repeat to reach target length
        ids = torch.cat([ids, ids], dim=0)
    ids = ids[:prompt_len].unsqueeze(0).to(device)
    L = ids.shape[1]
    pos = torch.arange(L, device=device).unsqueeze(0)

    with torch.no_grad():
        out = lm(input_ids=ids, attention_mask=torch.ones_like(ids), position_ids=pos,
                 output_attentions=True, use_cache=True)
    full_logits = out.logits[0, -1].float()
    p_full = torch.softmax(full_logits, dim=-1)

    blocks = [(lo, min(lo + block_size, L)) for lo in range(0, L, block_size)]
    nb = len(blocks)

    # attention score: last query's attention mass over each block (mean over heads)
    att = out.attentions[layer][0]                      # [heads, q_len, k_len]
    last_attn = att[:, -1, :].mean(0).float()           # [k_len]
    attention = [float(last_attn[lo:hi].sum()) for lo, hi in blocks]

    # coherence score: mean value-vector per block, cosine to context centroid.
    # transformers >= 4.36 returns a Cache object, not the legacy tuple — handle both.
    pkv = out.past_key_values
    if hasattr(pkv, "to_legacy_cache"):
        val = pkv.to_legacy_cache()[layer][1][0]        # [kv_heads, seq, head_dim]
    elif hasattr(pkv, "value_cache"):
        val = pkv.value_cache[layer][0]
    else:
        val = pkv[layer][1][0]
    block_mat = torch.stack([val[:, lo:hi, :].mean(dim=1).reshape(-1) for lo, hi in blocks])
    coherence = score_torch(block_mat.float(), mode="cos_value").tolist()

    # stratified block sample for the (expensive) LOO forwards
    idx = list(range(nb))
    if nb > n_sample:
        by_attn = sorted(idx, key=lambda i: attention[i])
        disagree = sorted(idx, key=lambda i: abs(_ranks(attention)[i] - _ranks(coherence)[i]),
                          reverse=True)
        keep = set(by_attn[:16] + by_attn[-16:] + disagree[:48])
        keep.update(rng.sample(idx, min(n_sample - len(keep), nb)))
        idx = sorted(keep)

    true = []
    with torch.no_grad():
        for b in idx:
            lo, hi = blocks[b]
            mask = torch.ones(L, device=device, dtype=torch.long)
            mask[lo:hi] = 0
            ob = lm(input_ids=ids, attention_mask=mask.unsqueeze(0), position_ids=pos)
            pb = torch.softmax(ob.logits[0, -1].float(), dim=-1)
            true.append(float((p_full * (p_full.clamp_min(1e-12) / pb.clamp_min(1e-12)).log()).sum()))

    a_s = [attention[b] for b in idx]
    c_s = [coherence[b] for b in idx]
    return {"model": model, "seq_len": L, "n_blocks": nb, "n_loo": len(idx), "layer": layer,
            **analyze(a_s, c_s, true)}


# ----------------------------------- CLI ----------------------------------- #
def _decision(d: dict) -> str:
    """Validity-gated, CI-based 3-way determination (Decision Rule A)."""
    if not d.get("valid", True):
        return "INCONCLUSIVE — RUN INVALID: " + "; ".join(d["invalid_reasons"])
    lo, hi = d.get("rho_partial_ci", (float("nan"), float("nan")))
    edge = d["needle_recall_coh"] > d["needle_recall_attn"] + 0.05
    if not math.isnan(lo) and lo > 0.1 and edge:
        return f"USEFUL — partial-corr CI [{lo:+.2f},{hi:+.2f}] > 0.1 and coherence catches the needles → proceed to Exp B"
    if not math.isnan(hi) and hi < 0.1:
        return f"NOT USEFUL — partial-corr CI [{lo:+.2f},{hi:+.2f}] < 0.1; attention suffices → drop"
    return f"INCONCLUSIVE — partial-corr CI [{lo:+.2f},{hi:+.2f}] straddles 0.1 → more prompts/samples or check signals"


def _print_expA(d: dict, header: str, footer: str) -> None:
    lo, hi = d.get("rho_partial_ci", (float("nan"), float("nan")))
    print(header + "\n")
    print(f"  Spearman(attention, importance)            = {d['rho_attn']:+.3f}")
    print(f"  Spearman(coherence, importance)            = {d['rho_coh']:+.3f}")
    print(f"  PARTIAL (coherence, importance | attn)     = {d['rho_partial_coh_given_attn']:+.3f}  CI[{lo:+.2f},{hi:+.2f}]  <- decisive")
    print(f"  needle recall  attention / coherence       = {d['needle_recall_attn']:.3f} / {d['needle_recall_coh']:.3f}"
          f"  ({d['n_needles']} needles)")
    print("  --- diagnostics (validity gate) ---")
    print(f"  attention–coherence collinearity ρ         = {d['rho_attn_coh']:+.3f}   (|ρ|>0.9 ⇒ partial unstable)")
    print(f"  LOO importance  median / max               = {d['imp_med']:.2e} / {d['imp_max']:.2e}"
          f"   ({d['imp_frac_tiny']:.0%} ~zero)")
    print(f"  signal variance  attn / coh                = {d['attn_std']:.3e} / {d['coh_std']:.3e}")
    print(f"  run valid?                                 = {d['valid']}"
          + ("" if d["valid"] else f"  ({'; '.join(d['invalid_reasons'])})"))
    print(f"\n  decision: {_decision(d)}")
    print(footer)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exp-A: LOO KV-importance signal predictivity")
    ap.add_argument("--synthetic", action="store_true", help="run the CPU synthetic model")
    ap.add_argument("--w-sem", type=float, default=0.5, help="(synthetic) semantic importance share")
    ap.add_argument("--n-blocks", type=int, default=400, help="(synthetic) number of blocks")
    ap.add_argument("--seed", type=int, default=0, help="(synthetic) RNG seed")
    # real-model (GPU) args
    ap.add_argument("--model", default=None, help="HF model id — real GPU path")
    ap.add_argument("--text-file", default=None, help="long-context prompt file (default: built-in)")
    ap.add_argument("--prompt-len", type=int, default=2048)
    ap.add_argument("--block-size", type=int, default=64)
    ap.add_argument("--layer", type=int, default=-1, help="layer index for attn/coherence scores")
    ap.add_argument("--n-sample", type=int, default=128, help="blocks to LOO-mask")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args(argv)

    if args.model:
        r = run_real(args.model, text_file=args.text_file, prompt_len=args.prompt_len,
                     block_size=args.block_size, layer=args.layer, n_sample=args.n_sample,
                     device=args.device)
        _print_expA(
            r,
            f"Exp-A (REAL: {r['model']}, seq_len={r['seq_len']}, layer={r['layer']}, "
            f"LOO {r['n_loo']}/{r['n_blocks']} blocks, {r['n_needles']} needles)",
            "\n  Measured on a real model. Repeat across ≥2 models + layers + prompts and apply "
            "Decision Rule A\n  (docs/SEMANTIC_TIERING_GPU_PROTOCOL.md §3) before any claim.",
        )
        return 0

    if not args.synthetic:
        ap.error("pass --synthetic (CPU) or --model <id> (GPU)")

    d = run_synthetic(SyntheticConfig(n_blocks=args.n_blocks, w_sem=args.w_sem, seed=args.seed))
    _print_expA(
        d,
        f"Exp-A (synthetic, w_sem={args.w_sem}, n_blocks={args.n_blocks}, seed={args.seed})",
        "\n  NOTE: synthetic — proves the harness + diagnostics + decision rule. Real w_sem is"
        "\n  unknown; run --model <id> on a GPU pod to measure it on a real model.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

