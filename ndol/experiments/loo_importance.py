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
            topk_frac: float = 0.15, budget_frac: float = 0.15) -> dict:
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

    # PRIMARY metric (heavy-tail robust): recall of the truly-important block set.
    # KV importance for a single next-token is heavy-tailed (few blocks matter),
    # so Spearman over a sea of ~zeros is weak; "does the signal's top-budget
    # contain the truly-important blocks?" is the decision-relevant question.
    K = max(3, int(round(topk_frac * n)))
    important = set(sorted(range(n), key=lambda i: true[i], reverse=True)[:K])
    budget = max(3, int(round(budget_frac * n)))
    # blend on RANKS (attention & coherence are on different scales)
    ra, rc = _ranks(attention), _ranks(coherence)
    scc = [0.5 * ra[i] + 0.5 * rc[i] for i in range(n)]
    # INVERSE hypothesis: distinctiveness = low centroid similarity = -coherence
    distinct = [-c for c in coherence]
    scc_d = [0.5 * ra[i] + 0.5 * ((n - 1) - rc[i]) for i in range(n)]   # attn + distinctiveness ranks

    def recall(scores):
        top = set(sorted(range(n), key=lambda i: scores[i], reverse=True)[:budget])
        return len(top & important) / len(important) if important else float("nan")

    # how many blocks carry meaningful (>5% of max) importance — too few ⇒ not rankable
    n_meaningful = sum(1 for t in true if t > 0.05 * imp_max) if imp_max > 0 else 0

    # validity gate — recalibrated: heavy-tailed importance is NORMAL (it's why
    # read-skip works), NOT degenerate. Invalid only if masking did nothing, a
    # signal is flat, signals are collinear, or there are too few positives to rank.
    reasons = []
    if imp_max < 1e-3:
        reasons.append("LOO importance ≈0 for every block — masking not applied, or context fully redundant")
    if n_meaningful < 3:
        reasons.append(f"only {n_meaningful} block(s) carry meaningful importance — too few positives to rank "
                       "(use a needle/retrieval prompt or aggregate over more decode positions)")
    if abs(rho_ac) > 0.9:
        reasons.append(f"attention & coherence are collinear (ρ={rho_ac:+.2f}) — partial correlation unstable")
    if attn_std < 1e-9 or coh_std < 1e-9:
        reasons.append("a signal has ~no variance — cannot rank")

    return {
        "rho_attn": rho_attn, "rho_coh": rho_coh, "rho_partial_coh_given_attn": rho_partial,
        "rho_partial_ci": (ci_lo, ci_hi), "rho_attn_coh": rho_ac,
        "imp_med": imp_med, "imp_max": imp_max, "imp_frac_tiny": frac_tiny,
        "n_meaningful": n_meaningful, "heavy_tailed": frac_tiny > 0.9,
        "important_k": K, "budget": budget,
        "attn_std": attn_std, "coh_std": coh_std,
        "recall_attn": recall(attention), "recall_coh": recall(coherence), "recall_scc": recall(scc),
        "recall_distinct": recall(distinct), "recall_scc_distinct": recall(scc_d),
        # back-compat aliases (now = recall of important set)
        "needle_recall_attn": recall(attention), "needle_recall_coh": recall(coherence),
        "n_needles": len(important),
        "valid": len(reasons) == 0, "invalid_reasons": reasons,
    }


# alternative signals to attention, by name → recall key (for the determination)
_ALT_RECALLS = {
    "coherence": "recall_coh",
    "distinctiveness(-coh)": "recall_distinct",
    "scc(attn+coh)": "recall_scc",
    "scc(attn+distinct)": "recall_scc_distinct",
}


def best_alternative(d: dict) -> tuple[str, float]:
    """Best non-attention signal (coherence / distinctiveness / either blend) by recall."""
    return max(((name, d[key]) for name, key in _ALT_RECALLS.items()), key=lambda kv: kv[1])


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
def _diverse_filler(rng, n_sentences: int) -> str:
    """Non-repeating filler — each sentence carries unique tokens, so masking a
    block removes information not recoverable from elsewhere (unlike repeated
    text, which makes every block redundant → zero LOO importance)."""
    S = ["The committee", "A sensor array", "The field archive", "Our control model",
         "The cooling unit", "A courier drone", "The audit ledger", "The orbital probe"]
    V = ["recorded", "transmitted", "recalibrated", "rejected", "amplified", "buffered",
         "encrypted", "down-sampled"]
    O = ["a fragment", "the residual", "an anomaly", "the manifest", "a checksum",
         "the payload", "an estimate", "the gradient"]
    out = []
    for i in range(n_sentences):
        out.append(f"{rng.choice(S)} {rng.choice(V)} {rng.choice(O)} #{rng.randint(100, 999)} at stage {i}.")
    return " ".join(out)


def _build_prompt_ids(tok, task: str, prompt_len: int, seed: int = 0) -> list[int]:
    """Token ids for the real-model prompt. task='needle' (default) plants one
    unique fact early and ends with a query that REQUIRES it, so the needle block
    has high LOO importance and most filler blocks have low — giving the variance
    Exp-A needs (and a built-in test that masking actually changes the output)."""
    rng = random.Random(seed)
    if task != "needle":
        ids = tok(_diverse_filler(rng, max(1, prompt_len // 8))).input_ids
        while len(ids) < prompt_len:
            ids += tok(_diverse_filler(rng, 200)).input_ids
        return ids[:prompt_len]
    code = rng.randint(10000, 99999)
    n_ids = tok(f" Important fact to remember: the secret access code is {code}. ").input_ids
    q_ids = tok(" Question: what is the secret access code? Answer: the secret access code is").input_ids
    budget = max(0, prompt_len - len(n_ids) - len(q_ids))
    pre = tok(_diverse_filler(rng, max(1, budget // 8))).input_ids[: budget // 5]
    post = tok(_diverse_filler(rng, max(1, budget // 2))).input_ids[: budget - len(pre)]
    return pre + n_ids + post + q_ids   # query stays at the very end


def _cache_layer_values(pkv, layer: int):
    """Per-layer value tensor [batch, kv_heads, seq, head_dim] from whatever
    transformers Cache layout this version uses. The API has churned a lot."""
    # 1. newest layered API (transformers ≳4.54): pkv.layers[i].values / .value_states
    layers = getattr(pkv, "layers", None)
    if layers is not None:
        lyr = layers[layer]
        for attr in ("values", "value_states", "value"):
            v = getattr(lyr, attr, None)
            if v is not None and not callable(v):
                return v
    # 2. 4.36–4.53: parallel lists
    vc = getattr(pkv, "value_cache", None)
    if vc is not None:
        return vc[layer]
    # 3. legacy-cache conversion
    if hasattr(pkv, "to_legacy_cache"):
        leg = pkv.to_legacy_cache()
        if leg:
            return leg[layer][1]
    # 4. iterable of (key, value) per layer
    try:
        return list(pkv)[layer][1]
    except Exception:
        pass
    # 5. legacy tuple-of-tuples
    try:
        return pkv[layer][1]
    except Exception:
        pass
    attrs = sorted(a for a in dir(pkv) if not a.startswith("__"))
    raise RuntimeError(
        f"could not extract value cache from {type(pkv).__name__}; attributes = {attrs}"
    )


def run_real(
    model: str,
    *,
    task: str = "needle",
    text_file: str | None = None,
    prompt_len: int = 2048,
    block_size: int = 64,
    layers=(-1,),
    n_sample: int = 128,
    coh_mode: str = "cos_value",
    device: str = "cuda",
    seeds=(0,),
) -> dict:
    """GPU path: measure LOO KV-importance across a layers × seeds grid + aggregate.

    Per seed (prompt): prefill (eager attn) → MULTI-POSITION LOO importance
    (layer-agnostic, computed ONCE — the expensive part) → for each layer, cheaply
    re-score attention, coherence, and the inverse 'distinctiveness' against that
    importance. Aggregate across the grid. Run per --model for ≥2 models before a
    final close. (Written to the HF API; adapt small details per attention backend.)
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from .coherence import score_torch

    tok = AutoTokenizer.from_pretrained(model)
    lm = AutoModelForCausalLM.from_pretrained(
        model, torch_dtype="auto", attn_implementation="eager"
    ).to(device).eval()

    def _block_value_mat(out, layer, blocks):
        val = _cache_layer_values(out.past_key_values, layer)[0]   # [kv_heads, seq, head_dim]
        return torch.stack([val[:, lo:hi, :].mean(dim=1).reshape(-1) for lo, hi in blocks])

    configs = []
    for seed in seeds:
        rng = random.Random(seed)
        if text_file:
            prompt_ids = tok(open(text_file).read()).input_ids[:prompt_len]
        else:
            prompt_ids = _build_prompt_ids(tok, task, prompt_len, seed)
        ids = torch.tensor(prompt_ids, dtype=torch.long, device=device).unsqueeze(0)
        L = ids.shape[1]
        pos = torch.arange(L, device=device).unsqueeze(0)

        with torch.no_grad():
            out = lm(input_ids=ids, attention_mask=torch.ones_like(ids), position_ids=pos,
                     output_attentions=True, use_cache=True)

        n_eval = max(8, min(64, L // 4))
        eval_pos = list(range(L - n_eval, L))
        eval_t = torch.tensor(eval_pos, device=device)
        p_full = torch.softmax(out.logits[0, eval_pos].float(), dim=-1)
        blocks = [(lo, min(lo + block_size, L)) for lo in range(0, L, block_size)]
        nb = len(blocks)

        idx = list(range(nb))
        if nb > n_sample:
            rng.shuffle(idx)
            idx = sorted(idx[:n_sample])

        # LOO importance — layer-agnostic, computed ONCE per seed (the expensive part)
        true = []
        with torch.no_grad():
            for b in idx:
                lo, hi = blocks[b]
                mask = torch.ones(L, device=device, dtype=torch.long)
                mask[lo:hi] = 0
                ob = lm(input_ids=ids, attention_mask=mask.unsqueeze(0), position_ids=pos)
                pb = torch.softmax(ob.logits[0, eval_pos].float(), dim=-1)
                kl = (p_full * (p_full.clamp_min(1e-12) / pb.clamp_min(1e-12)).log()).sum(dim=-1)
                kl = kl * (eval_t >= (hi - 1)).float()   # causal: only positions that attend to b
                true.append(float(kl.sum()))

        # per layer: cheap re-scoring from the SAME prefill against the shared importance
        for layer in layers:
            att = out.attentions[layer][0]
            attn_rows = att[:, eval_pos, :].mean(0).float()
            attention = [float(attn_rows[:, lo:hi].sum(dim=1).mean()) for lo, hi in blocks]
            coherence = score_torch(_block_value_mat(out, layer, blocks).float(), mode=coh_mode).tolist()
            a_s = [attention[b] for b in idx]
            c_s = [coherence[b] for b in idx]
            configs.append({"seed": seed, "layer": layer, "seq_len": L, "n_blocks": nb,
                            "n_loo": len(idx), **analyze(a_s, c_s, true)})

        del out
        if str(device).startswith("cuda"):
            torch.cuda.empty_cache()

    return {"model": model, "coh_mode": coh_mode, "configs": configs,
            "aggregate": _aggregate(configs)}


def _aggregate(configs: list[dict]) -> dict:
    import statistics as st
    from collections import Counter
    valid = [c for c in configs if c["valid"]]
    out = {"n_valid": len(valid), "n_total": len(configs)}
    if not valid:
        out["determination"] = "INCONCLUSIVE — no valid configs (see per-config reasons)"
        return out
    best = [best_alternative(c) for c in valid]
    deltas = [b[1] - c["recall_attn"] for b, c in zip(best, valid)]
    out["mean_recall_attn"] = st.mean(c["recall_attn"] for c in valid)
    out["mean_recall_best_alt"] = st.mean(b[1] for b in best)
    out["mean_delta"] = st.mean(deltas)
    out["best_alt_winner"] = Counter(b[0] for b in best).most_common(1)[0][0]
    n_useful = sum(1 for d in deltas if d > 0.10)
    n_notuseful = sum(1 for d in deltas if d < -0.05)
    out["n_useful"], out["n_notuseful"] = n_useful, n_notuseful
    if out["mean_delta"] > 0.10 and n_useful >= 0.6 * len(valid):
        out["determination"] = (f"USEFUL — best alt '{out['best_alt_winner']}' beats attention by "
                                 f"Δrecall {out['mean_delta']:+.2f} in {n_useful}/{len(valid)} valid configs → proceed to Exp B")
    elif out["mean_delta"] < 0 and n_notuseful >= 0.6 * len(valid):
        out["determination"] = (f"NOT USEFUL — attention ≥ every alternative (recall "
                                 f"{out['mean_recall_attn']:.2f} vs best-alt {out['mean_recall_best_alt']:.2f}) "
                                 f"in {n_notuseful}/{len(valid)} valid configs → DROP")
    else:
        out["determination"] = (f"INCONCLUSIVE — mixed across configs (mean Δrecall {out['mean_delta']:+.2f}); "
                                 "need more seeds/layers/models")
    return out


# ----------------------------------- CLI ----------------------------------- #
def _decision(d: dict) -> str:
    """Validity-gated determination (Decision Rule A). Primary signal = recall of
    the truly-important block set (heavy-tail robust); partial correlation secondary."""
    if not d.get("valid", True):
        return "INCONCLUSIVE — RUN INVALID: " + "; ".join(d["invalid_reasons"])
    ra = d["recall_attn"]
    name, best_alt = best_alternative(d)
    lo, hi = d.get("rho_partial_ci", (float("nan"), float("nan")))
    if best_alt > ra + 0.10:
        return (f"USEFUL — '{name}' retains MORE important blocks "
                f"(recall {best_alt:.2f} vs attention {ra:.2f}) → proceed to Exp B")
    if best_alt < ra - 0.05:
        return (f"NOT USEFUL — attention retains more important blocks "
                f"(recall {ra:.2f} vs best-alt '{name}' {best_alt:.2f}) → attention suffices, drop")
    return (f"INCONCLUSIVE — attn {ra:.2f} vs best-alt '{name}' {best_alt:.2f}, "
            f"partial CI[{lo:+.2f},{hi:+.2f}] → need more positives/configs")


def _print_expA(d: dict, header: str, footer: str) -> None:
    lo, hi = d.get("rho_partial_ci", (float("nan"), float("nan")))
    print(header + "\n")
    print(f"  recall of important blocks (top-{d['important_k']}, budget {d['budget']})  <- PRIMARY")
    print(f"    attention            = {d['recall_attn']:.3f}")
    print(f"    coherence            = {d['recall_coh']:.3f}")
    print(f"    distinctiveness(-coh)= {d['recall_distinct']:.3f}   <- inverse hypothesis")
    print(f"    scc(attn+coh)        = {d['recall_scc']:.3f}")
    print(f"    scc(attn+distinct)   = {d['recall_scc_distinct']:.3f}")
    print(f"  Spearman attn / coh                        = {d['rho_attn']:+.3f} / {d['rho_coh']:+.3f}")
    print(f"  PARTIAL (coherence | attn)                 = {d['rho_partial_coh_given_attn']:+.3f}  CI[{lo:+.2f},{hi:+.2f}]")
    print("  --- diagnostics (validity gate) ---")
    print(f"  attention–coherence collinearity ρ         = {d['rho_attn_coh']:+.3f}   (|ρ|>0.9 ⇒ partial unstable)")
    print(f"  LOO importance  median / max               = {d['imp_med']:.2e} / {d['imp_max']:.2e}"
          f"   ({d['imp_frac_tiny']:.0%} ~zero, {d['n_meaningful']} meaningful, heavy_tailed={d['heavy_tailed']})")
    print(f"  run valid?                                 = {d['valid']}"
          + ("" if d["valid"] else f"  ({'; '.join(d['invalid_reasons'])})"))
    print(f"\n  decision: {_decision(d)}")
    print(footer)


def _print_grid(res: dict) -> None:
    print(f"Exp-A GRID — {res['model']}  (coh_mode={res['coh_mode']})\n")
    print(f"  {'seed':>4}{'layer':>6}{'ok':>3}{'attn':>7}{'coh':>7}{'dist':>7}{'sccD':>7}{'partial':>9}  note")
    for c in res["configs"]:
        note = "" if c["valid"] else "INVALID: " + c["invalid_reasons"][0][:40]
        print(f"  {c['seed']:>4}{c['layer']:>6}{('Y' if c['valid'] else '-'):>3}"
              f"{c['recall_attn']:>7.2f}{c['recall_coh']:>7.2f}{c['recall_distinct']:>7.2f}"
              f"{c['recall_scc_distinct']:>7.2f}{c['rho_partial_coh_given_attn']:>9.2f}  {note}")
    a = res["aggregate"]
    print(f"\n  valid configs: {a['n_valid']}/{a['n_total']}")
    if a["n_valid"]:
        print(f"  mean recall  attention={a['mean_recall_attn']:.3f}  best-alt={a['mean_recall_best_alt']:.3f}"
              f" ({a['best_alt_winner']})  meanΔ={a['mean_delta']:+.3f}")
    print(f"\n  DETERMINATION: {a['determination']}")
    print("\n  This is ONE model. Re-run per --model for ≥2 models, and check consistency,"
          "\n  before the final close (docs/SEMANTIC_TIERING_GPU_PROTOCOL.md §3).")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exp-A: LOO KV-importance signal predictivity")
    ap.add_argument("--synthetic", action="store_true", help="run the CPU synthetic model")
    ap.add_argument("--w-sem", type=float, default=0.5, help="(synthetic) semantic importance share")
    ap.add_argument("--n-blocks", type=int, default=400, help="(synthetic) number of blocks")
    ap.add_argument("--seed", type=int, default=0, help="(synthetic) RNG seed")
    # real-model (GPU) args
    ap.add_argument("--model", default=None, help="HF model id — real GPU path")
    ap.add_argument("--task", default="needle", choices=["needle", "text"],
                    help="needle = plant a fact + query that needs it (gives importance variance); "
                         "text = diverse filler")
    ap.add_argument("--text-file", default=None, help="real long-doc prompt (overrides --task)")
    ap.add_argument("--prompt-len", type=int, default=2048,
                    help="keep ≤~4096: output_attentions stores all-layer attn (O(L²)·layers); 8192 OOMs 80GB")
    ap.add_argument("--block-size", type=int, default=64)
    ap.add_argument("--layers", default="-1", help="comma list of layer indices, e.g. '0,15,-1'")
    ap.add_argument("--seeds", default="0", help="comma list of prompt seeds, e.g. '0,1,2' (≥2 prompts)")
    ap.add_argument("--coh-mode", default="cos_value", choices=["cos_value", "value_norm"],
                    help="coherence signal: cos_value (centroid cosine) or value_norm")
    ap.add_argument("--n-sample", type=int, default=128, help="blocks to LOO-mask per seed")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args(argv)

    if args.model:
        layers = [int(x) for x in str(args.layers).split(",")]
        seeds = [int(x) for x in str(args.seeds).split(",")]
        res = run_real(args.model, task=args.task, text_file=args.text_file, prompt_len=args.prompt_len,
                       block_size=args.block_size, layers=layers, n_sample=args.n_sample,
                       coh_mode=args.coh_mode, device=args.device, seeds=seeds)
        _print_grid(res)
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

