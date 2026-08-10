#!/usr/bin/env python
"""§14a experiment — System-level BCVF integration scout.

Reference:
  Project_documentation/autonomous_robotics/symbolu_robotics/bcvf_autonomous/DESIGN.md §6.1 / §6.7 — autonomy-
  domain validation that passed (sign-test p=0.0072 on N=21 with
  S3_map_error_accel) was a SYSTEM-LEVEL result: multi-source robotic
  system using BCVF-shaped routing produces sign-test-significant
  gains over baseline. NOT an isolated-observable result.

  §13's program (§13.10–§13.19) tested observables in isolation —
  per-question scalar vs ground-truth correctness via AUC. Five
  hypothesis classes were exhausted; none lifted §13.10's marginal
  baseline on the combined-classification rule. §13.19 closed the
  §13 single-axis program.

  §14 tests the un-tested experimental structure: not "does
  scalar X correlate with truth at the per-question level," but
  "does multi-source LLM Q&A using BCVF-shaped routing produce
  measurable accuracy lift over naive aggregation?"

  §14a is the bounded scout that gates the multi-week investment
  of full §14 behind a cheap pre-committed test on the most
  permissive §13 benchmark (HaluEval-QA).

Method:
  1. Three sources: Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct,
     Mistral-7B-Instruct-v0.3 (all cached from §13.11).
  2. Per source per question: K=10 stochastic samples + 1 greedy
     answer. Compute per-source semantic entropy H_src(q) over
     question-conditioned NLI clusters of the K samples (§13.10
     method, identical scalar).
  3. Two consumer variants (both run, results compared):
     - V1 softmin trust: w_i ∝ exp(-d_i/τ), τ=0.5 pinned
     - V2 thresholded exclusion: S = {i : d_i ≤ θ}, w_i = 1/|S|,
       θ = per-question median entropy. If |S|<1 fall back to
       all sources with uniform weights (1/M).
  4. Selector: weighted majority vote on the 3 source greedies.
     Each candidate answer's score is sum of weights of sources
     emitting it. Argmax wins; ties broken by source-list order.
  5. Two baselines:
     A: single-source Qwen greedy (no system, no ensembling).
     B: uniform majority vote of 3 source greedies (no BCVF).
  6. Per-question correctness label (each candidate answer):
     question-conditioned NLI must entail the right answer AND
     not entail the hallucinated answer (identical to §13.10–
     §13.18; HaluEval has exactly one right_answer + one
     hallucinated_answer per row).
  7. Per-variant accuracy = fraction of N=100 questions where
     the variant's selected answer is labeled correct.
  8. Δ_v = acc(v) - acc(Baseline-B) for v in {V1, V2}.
  9. Sign-test for v vs Baseline-B: per-question wins
     (v correct AND B wrong) vs losses (v wrong AND B correct);
     binomial test on win count vs total non-ties at α=0.05.

Pre-committed bands (§14a, pinned in design doc BEFORE
implementation; see §14a for full text):

  - STRONG: Δ_v ≥ +5pp for both V1 and V2 AND sign-test p<0.05
    for at least one. PROMOTE to full §14.
  - DIRECTIONAL: Δ_V2 ≥ +3pp AND Δ_V1 ≤ 0pp. PROMOTE to full §14
    with V1 deprioritized (ChatGPT's predicted pattern: softmin
    harmful, threshold helpful).
  - MARGINAL: Δ_v in (0, +3) for both. AUTHORIZE one more scout
    (V3/V4 or different per-source scalar).
  - SATURATION: Δ_v in [-3, 0] for both. Document as null;
    do NOT promote.
  - REGRESSION: Δ_v < -3 for either V1 or V2. CLOSE LLM transfer
    line with strong evidence.

Do NOT update AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md on the basis of
any §14a result — that requires STRONG band on BOTH benchmarks
at any §13 or §14 probe. §14a is HaluEval-only by design.

Usage:
    HF_HUB_DISABLE_XET=1 python scripts/probe_system_level_scout.py \\
        --num-questions 100 --dump-json

Runtime ~50–60 min on the 80 GB GPU (3-source K=10 sampling +
3-source greedy + per-source NLI clustering + per-question NLI
labeling + sign-test).
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass
class SourceResult:
    """Per-source state captured per question."""
    source_idx: int
    source_name: str
    samples: List[str]                      # K decoded stochastic samples
    cluster_ids: List[int]                  # union-find result
    semantic_entropy: float                 # H_src(q), the BCVF scalar
    greedy: str                             # source's greedy answer
    greedy_correct: bool                    # NLI label on greedy answer


@dataclass
class QuestionResult:
    q_idx: int
    question: str
    right_answer: str
    hallucinated_answer: str
    sources: List[SourceResult]
    # Per-variant outputs:
    v1_weights: List[float]                 # softmin weights, length M
    v1_selected: str                        # weighted-majority winner
    v1_correct: bool                        # NLI label on V1's pick
    v2_weights: List[float]                 # thresholded weights, length M
    v2_selected: str
    v2_correct: bool
    v2_threshold: float                     # the per-question median used
    v2_n_survivors: int                     # |S| after thresholding
    # Baselines:
    baseline_a_correct: bool                # Qwen greedy correctness
    baseline_b_selected: str                # uniform majority winner
    baseline_b_correct: bool


# §14a pinned constants. Different bands from §13 because the metric
# is accuracy delta in percentage points, not AUC.
SOFTMIN_TAU = 0.5                           # V1 softmin temperature
SIGN_TEST_ALPHA = 0.05                       # binomial test alpha
STRONG_DELTA_THRESHOLD = 5.0                # ≥5pp lift for STRONG
DIRECTIONAL_V2_THRESHOLD = 3.0               # ≥3pp lift on V2 for DIRECTIONAL
DIRECTIONAL_V1_CEILING = 0.0                 # V1 ≤ 0pp for DIRECTIONAL
MARGINAL_LOWER = 0.0
MARGINAL_UPPER = 3.0
SATURATION_LOWER = -3.0
SATURATION_UPPER = 0.0
REGRESSION_THRESHOLD = -3.0


def classify(
    delta_v1: float, delta_v2: float,
    sign_test_p_v1: float, sign_test_p_v2: float,
) -> Tuple[str, str]:
    """Map (Δ_V1, Δ_V2, sign-test p-values) to a §14a band label and
    per-run recommendation. Pre-committed bands per §14a; cannot be
    redefined post-hoc.

    Both deltas are in percentage points (e.g., +5.0 means accuracy
    rose by 5 percentage points vs Baseline-B). Sign-test p-values
    are for the per-question wins-vs-losses comparison vs Baseline-B.
    """
    # STRONG: both ≥ +5pp AND sign-test p < 0.05 for at least one
    if (delta_v1 >= STRONG_DELTA_THRESHOLD
            and delta_v2 >= STRONG_DELTA_THRESHOLD
            and (sign_test_p_v1 < SIGN_TEST_ALPHA
                 or sign_test_p_v2 < SIGN_TEST_ALPHA)):
        return "SCOUT_STRONG", (
            "Strong scout pass — PROMOTE TO FULL §14. Both V1 and V2 "
            "lift accuracy by ≥5pp over uniform majority vote, with "
            "sign-test significance for at least one variant. "
            "Authorizes drafting full §14 pre-commitment with both "
            "benchmarks (TruthfulQA-MC + HaluEval-QA), all four "
            "consumer variants, both selectors, and ablation "
            "runners. The system-level integration hypothesis is "
            "supported on the most permissive §13 benchmark and "
            "merits the multi-week full investment."
        )
    # DIRECTIONAL: V2 ≥ +3pp AND V1 ≤ 0pp (ChatGPT's predicted pattern)
    if (delta_v2 >= DIRECTIONAL_V2_THRESHOLD
            and delta_v1 <= DIRECTIONAL_V1_CEILING):
        return "SCOUT_DIRECTIONAL", (
            "Directional scout pass — PROMOTE TO FULL §14 WITH V1 "
            "DEPRIORITIZED. ChatGPT's predicted pattern observed: "
            "softmin trust shaping (V1) does not lift while "
            "thresholded exclusion (V2) does. Authorizes full §14 "
            "with V1 dropped from the consumer variant pool, V2 "
            "promoted as primary, V3 (veto-only) and V4 (deadband) "
            "added as the remaining variants. The autonomy-domain "
            "softmin default appears to be inappropriate for LLM-"
            "domain ensembling at this configuration."
        )
    # REGRESSION: Δ < -3pp for either variant — close LLM track
    if (delta_v1 < REGRESSION_THRESHOLD
            or delta_v2 < REGRESSION_THRESHOLD):
        return "SCOUT_REGRESSION", (
            "Scout regression — CLOSE LLM TRANSFER LINE with strong "
            "evidence. System-level integration actively HURTS "
            "accuracy on the most permissive §13 benchmark vs naive "
            "majority voting. Combined with §13.19's 5-of-5 single-"
            "axis null, this is comprehensive evidence that BCVF-"
            "for-LLMs does not transfer at any tested experimental "
            "structure on this codebase. The autonomy-domain BCVF "
            "claim stands independently on §6.1. No further LLM-"
            "domain probes authorized in this codebase without a "
            "fundamental reframing (different model class, "
            "different benchmark family, or different formal "
            "structure entirely)."
        )
    # MARGINAL: 0 < Δ ≤ +3pp for both
    if (MARGINAL_LOWER < delta_v1 <= MARGINAL_UPPER
            and MARGINAL_LOWER < delta_v2 <= MARGINAL_UPPER):
        return "SCOUT_MARGINAL", (
            "Marginal scout — UNDECIDED. Small lift over baseline "
            "but neither variant clears the +3pp DIRECTIONAL "
            "threshold or +5pp STRONG threshold. Authorize one more "
            "scout (V3 veto-only + V4 deadband consumer variants, "
            "OR Variant A entropy 2nd-difference per-source scalar) "
            "before deciding on full §14. Pre-commitment for the "
            "additional scout would be a fresh §0.8 commitment "
            "(§14a.2 or similar). Full §14 NOT authorized until "
            "either MARGINAL or STRONG is reached on a follow-up "
            "scout."
        )
    # SATURATION: Δ ∈ [-3, 0] for both
    return "SCOUT_SATURATION", (
        "Scout saturation — DOCUMENT AS NULL, do NOT promote. The "
        "system layer adds nothing measurable on top of naive 3-"
        "source majority voting. Combined with §13.19's 5-of-5 "
        "single-axis null, the honest external framing becomes: "
        "single-axis observables saturate AND system-level "
        "integration on the most permissive benchmark also "
        "saturates. The LLM transfer line is closed at all tested "
        "experimental structures. Do NOT update VC-facing "
        "material; the §13.9 hold remains in force and is "
        "strengthened. Full §14 NOT authorized without a "
        "fundamentally different signal class or scope."
    )


def build_nli_checker(nli_model, nli_tokenizer, device: str, batch_size: int = 32):
    """Return a function (premises, hypotheses) -> List[bool] for batched
    entailment checks. Identical to §13.10–§13.18.

    Used in this script for two purposes (both batched):
    1. Per-source semantic-entropy clustering: K(K-1)=90 directional
       NLI pairs per source per question.
    2. Per-question correctness label: for each candidate answer,
       check (entails right_answer) AND NOT (entails hallucinated).
    """
    import torch

    ent_idx = None
    if hasattr(nli_model.config, "label2id"):
        for k, v in nli_model.config.label2id.items():
            if "entail" in k.lower():
                ent_idx = int(v)
                break
    if ent_idx is None:
        ent_idx = 0

    @torch.inference_mode()
    def check_batch(premises: List[str], hypotheses: List[str]) -> List[bool]:
        assert len(premises) == len(hypotheses)
        if not premises:
            return []
        verdicts: List[bool] = []
        for start in range(0, len(premises), batch_size):
            end = min(start + batch_size, len(premises))
            enc = nli_tokenizer(
                premises[start:end], hypotheses[start:end],
                return_tensors="pt", truncation=True, max_length=512,
                padding=True,
            ).to(device)
            logits = nli_model(**enc).logits
            preds = torch.argmax(logits, dim=-1).tolist()
            verdicts.extend(int(p) == ent_idx for p in preds)
        return verdicts

    return check_batch


def cluster_by_entailment(
    samples: List[str], check_batch, question: str,
) -> List[int]:
    """Question-conditioned bidirectional NLI clustering via union-find.
    Identical to §13.10's `cluster_by_entailment` — same scalar means
    direct comparability with §13.10's per-source AUC of 0.661 on
    Qwen-only HaluEval.

    Returns a list of cluster IDs (canonicalized starting from 0)
    parallel to the input samples list.
    """
    n = len(samples)
    if n == 0:
        return []
    contextualized = [f"{question} {s}" for s in samples]

    pairs: List[Tuple[int, int]] = []
    premises: List[str] = []
    hypotheses: List[str] = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            pairs.append((i, j))
            premises.append(contextualized[i])
            hypotheses.append(contextualized[j])

    verdicts = check_batch(premises, hypotheses)
    entail = {pair: v for pair, v in zip(pairs, verdicts)}

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if entail.get((i, j)) and entail.get((j, i)):
                union(i, j)

    roots = [find(i) for i in range(n)]
    canon = {r: idx for idx, r in enumerate(sorted(set(roots)))}
    return [canon[r] for r in roots]


def shannon_entropy_nats(cluster_ids: List[int]) -> float:
    """Shannon entropy (nats) over cluster-size distribution. Same as
    §13.10's per-question scalar."""
    n = len(cluster_ids)
    if n == 0:
        return 0.0
    sizes = Counter(cluster_ids).values()
    p = np.array([s / n for s in sizes], dtype=np.float64)
    return float(-np.sum(p * np.log(p)))


def generate_samples(
    model, tokenizer, prompt: str, k: int, temperature: float,
    max_new_tokens: int, device: str, seed: int,
) -> List[str]:
    """Sample `k` completions from (model, tokenizer). Same protocol
    as §13.10 / §13.11. Returns decoded strings stripped of the
    prompt prefix."""
    import torch

    torch.manual_seed(seed)
    enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
    input_ids = enc.input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)
    prompt_len = input_ids.shape[1]

    with torch.inference_mode():
        out = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            do_sample=True,
            temperature=temperature,
            num_return_sequences=k,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    gens = out[:, prompt_len:]
    return [
        tokenizer.decode(g, skip_special_tokens=True).strip()
        for g in gens
    ]


def generate_greedy(
    model, tokenizer, prompt: str, max_new_tokens: int, device: str,
) -> str:
    """Deterministic T=0 completion. Used for each source's candidate
    answer that feeds into the consumer + selector."""
    import torch

    enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
    input_ids = enc.input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)
    prompt_len = input_ids.shape[1]

    with torch.inference_mode():
        out = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            do_sample=False,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    gen = out[0, prompt_len:]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def consumer_v1_softmin(
    entropies: np.ndarray, tau: float = SOFTMIN_TAU,
) -> np.ndarray:
    """V1 — Softmin trust shaping (autonomy-domain default; ChatGPT
    flagged as harmful). Higher entropy → lower weight, sharply.

        w_i ∝ exp(-d_i / tau),  d_i = entropies[i],  tau pinned

    Numerically stable via exp(-d/tau) shifted by max — same trick
    as standard softmax stability. Returns weights summing to 1.
    """
    d_over_tau = entropies / float(tau)
    # Negate and stabilize: w ∝ exp(-d/tau) = exp(-d/tau - max(-d/tau))
    shifted = -d_over_tau
    shifted = shifted - shifted.max()
    exp_shifted = np.exp(shifted)
    return exp_shifted / exp_shifted.sum()


def consumer_v2_thresholded(
    entropies: np.ndarray,
) -> Tuple[np.ndarray, float, int]:
    """V2 — Thresholded exclusion + uniform survivors (ChatGPT
    recommendation). Threshold = per-question median.

        S = {i : d_i ≤ median(d)},  w_i = 1 / |S|  for i in S, else 0

    If |S| < 1 (degenerate; all entropies above median, which can
    happen with ties at the median), fall back to all sources with
    uniform weights (1/M).

    Returns (weights, threshold_used, n_survivors).
    """
    M = len(entropies)
    threshold = float(np.median(entropies))
    survivor_mask = (entropies <= threshold)
    n_survivors = int(survivor_mask.sum())
    if n_survivors < 1:
        # Degenerate case — fall back to uniform across all sources.
        weights = np.ones(M, dtype=np.float64) / M
        return weights, threshold, M
    weights = np.where(survivor_mask, 1.0 / n_survivors, 0.0)
    return weights, threshold, n_survivors


def select_weighted_majority_vote(
    answers: List[str], weights: np.ndarray,
) -> str:
    """Weighted majority vote selector. For each unique candidate
    answer, sum the weights of sources that emitted it; argmax wins.
    Ties broken deterministically by first-emission order in the
    source list (i.e., earlier source wins).
    """
    if len(answers) == 0:
        return ""
    score: Dict[str, float] = {}
    first_pos: Dict[str, int] = {}
    for idx, (a, w) in enumerate(zip(answers, weights)):
        score[a] = score.get(a, 0.0) + float(w)
        if a not in first_pos:
            first_pos[a] = idx
    # argmax by (score, -first_pos) — higher score first, then earlier
    # source first as tiebreaker.
    best = max(
        score.keys(),
        key=lambda a: (score[a], -first_pos[a]),
    )
    return best


def label_answer_correctness(
    candidate_answer: str, right_answer: str, hallucinated_answer: str,
    check_batch, question: str,
) -> bool:
    """Question-conditioned correctness label for a single candidate
    answer. Same protocol as §13.10–§13.18 — entails right AND does
    NOT entail hallucinated.
    """
    premise = f"{question} {candidate_answer}"
    hypotheses = [
        f"{question} {right_answer}",
        f"{question} {hallucinated_answer}",
    ]
    verdicts = check_batch([premise, premise], hypotheses)
    return bool(verdicts[0] and not verdicts[1])


def sign_test_pvalue(wins: int, losses: int) -> float:
    """Two-sided binomial sign-test p-value for wins vs losses. Ties
    are excluded from both counts (caller's responsibility). Returns
    1.0 if total non-ties is 0.

    Uses `math.comb` and an explicit binomial sum for portability —
    no scipy dependency. For modest N this is fast enough.
    """
    n = wins + losses
    if n == 0:
        return 1.0
    # Two-sided: p = 2 * P(X ≥ max(wins, losses)) under H0: p=0.5
    k = max(wins, losses)
    # Sum of binomial probabilities from k to n
    log_half = math.log(0.5)
    # Compute P(X ≥ k) under Bin(n, 0.5)
    log_pmf = [
        math.log(math.comb(n, i)) + n * log_half
        for i in range(k, n + 1)
    ]
    # Stable log-sum-exp
    max_log = max(log_pmf)
    p_one_sided = math.exp(max_log) * sum(
        math.exp(lp - max_log) for lp in log_pmf
    )
    p_two_sided = min(1.0, 2.0 * p_one_sided)
    return p_two_sided


DEFAULT_SOURCES = ",".join([
    "Qwen/Qwen2.5-7B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
])


def parse_sources_flag(raw: str) -> List[str]:
    names = [s.strip() for s in raw.split(",")]
    if any(not n for n in names):
        raise argparse.ArgumentTypeError(
            f"--sources contains an empty entry: {raw!r}"
        )
    if len(names) < 2:
        raise argparse.ArgumentTypeError(
            f"--sources must list >= 2 model IDs (got {len(names)})."
        )
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-questions", type=int, default=100)
    parser.add_argument(
        "--sources", type=parse_sources_flag, default=DEFAULT_SOURCES,
        help="Comma-separated list of HF model IDs. §14a pins the "
             "cross-family triple (Qwen + Llama + Mistral); a "
             "non-default value is a §14a deviation.",
    )
    parser.add_argument(
        "--qwen-baseline-idx", type=int, default=0,
        help="Index of the Qwen source in --sources for Baseline-A "
             "(single-source-Qwen-greedy comparison). Default 0 "
             "matches the pinned source order.",
    )
    parser.add_argument(
        "--nli-model",
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        help="MNLI classifier for per-source semantic-entropy "
             "clustering AND per-question correctness labeling.",
    )
    parser.add_argument(
        "--k-samples", type=int, default=10,
        help="K samples per source per question for semantic entropy "
             "(pinned to 10 per §13.10 / §13.11 protocol).",
    )
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument(
        "--max-new-tokens", type=int, default=32,
        help="§14a pins 32 (matches §13.10 / §13.11 — NOT the §13.14/"
             "§13.16/§13.18 value of 128). Per-source semantic entropy "
             "is the §13.10 scalar; using §13.10's max_new_tokens=32 "
             "preserves direct AUC comparability.",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--out-dir", type=pathlib.Path,
        default=_REPO_ROOT / "docs" / "experiments",
    )
    parser.add_argument("--suffix", type=str, default="")
    parser.add_argument(
        "--dump-json", action="store_true",
        help="Also write a per-question JSON dump including per-source "
             "samples + entropy, per-variant weights/selected/correct, "
             "and baseline outputs for post-hoc audit.",
    )
    args = parser.parse_args()

    if not (0 <= args.qwen_baseline_idx < len(args.sources)):
        parser.error(
            f"--qwen-baseline-idx {args.qwen_baseline_idx} out of "
            f"range for {len(args.sources)} sources."
        )

    sources_default = (
        args.sources == [
            "Qwen/Qwen2.5-7B-Instruct",
            "meta-llama/Llama-3.1-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3",
        ]
        and args.qwen_baseline_idx == 0
        and args.k_samples == 10
        and args.max_new_tokens == 32
    )

    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForCausalLM, AutoModelForSequenceClassification,
        AutoTokenizer,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}", flush=True)
    if device == "cuda":
        total_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"  GPU total memory: {total_gb:.1f} GB", flush=True)

    M = len(args.sources)
    tokenizers: List = []
    models: List = []
    for name in args.sources:
        print(f"Loading source: {name}", flush=True)
        tok = AutoTokenizer.from_pretrained(name)
        mdl = AutoModelForCausalLM.from_pretrained(
            name, torch_dtype=torch.float16,
        ).to(device)
        mdl.eval()
        tokenizers.append(tok)
        models.append(mdl)
        if device == "cuda":
            alloc = torch.cuda.memory_allocated() / (1024**3)
            print(f"  VRAM after load: {alloc:.1f} GB", flush=True)

    print(f"Loading NLI model: {args.nli_model}", flush=True)
    nli_tokenizer = AutoTokenizer.from_pretrained(args.nli_model)
    nli_dtype = torch.float16 if device == "cuda" else torch.float32
    nli_model = AutoModelForSequenceClassification.from_pretrained(
        args.nli_model, torch_dtype=nli_dtype,
    ).to(device)
    nli_model.eval()
    check_batch = build_nli_checker(nli_model, nli_tokenizer, device)

    print("Loading HaluEval (qa, data) ...", flush=True)
    ds = load_dataset("pminervini/HaluEval", "qa", split="data")
    ds = ds.select(range(min(args.num_questions, len(ds))))

    print(
        f"Sources: {M}, K={args.k_samples}, "
        f"max_new_tokens={args.max_new_tokens}, "
        f"softmin τ={SOFTMIN_TAU}, "
        f"baseline-A source idx={args.qwen_baseline_idx}"
        + ("" if sources_default
           else "  [§14a DEVIATION: non-default config]"),
        flush=True,
    )

    results: List[QuestionResult] = []
    t_start = time.perf_counter()

    for q_idx, row in enumerate(ds):
        q_text = row["question"]
        right_answer = row["right_answer"]
        hallucinated_answer = row["hallucinated_answer"]
        prompt = f"Q: {q_text}\nA:"

        # Per-source: K samples + greedy + semantic entropy + greedy
        # correctness label.
        source_results: List[SourceResult] = []
        for s_idx, (tok, mdl) in enumerate(zip(tokenizers, models)):
            samples = generate_samples(
                mdl, tok, prompt,
                k=args.k_samples, temperature=args.temperature,
                max_new_tokens=args.max_new_tokens, device=device,
                seed=args.seed + q_idx * M + s_idx,
            )
            cluster_ids = cluster_by_entailment(
                samples, check_batch, q_text,
            )
            entropy = shannon_entropy_nats(cluster_ids)
            greedy = generate_greedy(
                mdl, tok, prompt,
                max_new_tokens=args.max_new_tokens, device=device,
            )
            greedy_correct = label_answer_correctness(
                greedy, right_answer, hallucinated_answer,
                check_batch, q_text,
            )
            source_results.append(SourceResult(
                source_idx=s_idx,
                source_name=args.sources[s_idx],
                samples=samples,
                cluster_ids=cluster_ids,
                semantic_entropy=entropy,
                greedy=greedy,
                greedy_correct=greedy_correct,
            ))

        entropies = np.array(
            [sr.semantic_entropy for sr in source_results],
            dtype=np.float64,
        )
        greedies = [sr.greedy for sr in source_results]

        # V1 — softmin trust shaping
        v1_weights = consumer_v1_softmin(entropies, tau=SOFTMIN_TAU)
        v1_selected = select_weighted_majority_vote(greedies, v1_weights)
        v1_correct = label_answer_correctness(
            v1_selected, right_answer, hallucinated_answer,
            check_batch, q_text,
        )

        # V2 — thresholded exclusion + uniform survivors
        v2_weights, v2_threshold, v2_n_survivors = (
            consumer_v2_thresholded(entropies)
        )
        v2_selected = select_weighted_majority_vote(greedies, v2_weights)
        v2_correct = label_answer_correctness(
            v2_selected, right_answer, hallucinated_answer,
            check_batch, q_text,
        )

        # Baselines
        baseline_a_correct = source_results[
            args.qwen_baseline_idx
        ].greedy_correct
        baseline_b_weights = np.ones(M, dtype=np.float64) / M
        baseline_b_selected = select_weighted_majority_vote(
            greedies, baseline_b_weights,
        )
        baseline_b_correct = label_answer_correctness(
            baseline_b_selected, right_answer, hallucinated_answer,
            check_batch, q_text,
        )

        results.append(QuestionResult(
            q_idx=q_idx, question=q_text,
            right_answer=right_answer,
            hallucinated_answer=hallucinated_answer,
            sources=source_results,
            v1_weights=v1_weights.tolist(),
            v1_selected=v1_selected,
            v1_correct=v1_correct,
            v2_weights=v2_weights.tolist(),
            v2_selected=v2_selected,
            v2_correct=v2_correct,
            v2_threshold=v2_threshold,
            v2_n_survivors=v2_n_survivors,
            baseline_a_correct=baseline_a_correct,
            baseline_b_selected=baseline_b_selected,
            baseline_b_correct=baseline_b_correct,
        ))

        if (q_idx + 1) % 5 == 0 or q_idx + 1 == len(ds):
            elapsed = time.perf_counter() - t_start
            eta = elapsed / (q_idx + 1) * (len(ds) - q_idx - 1)
            n_v1 = sum(r.v1_correct for r in results)
            n_v2 = sum(r.v2_correct for r in results)
            n_a = sum(r.baseline_a_correct for r in results)
            n_b = sum(r.baseline_b_correct for r in results)
            print(
                f"  [{q_idx + 1}/{len(ds)}] elapsed={elapsed:.0f}s "
                f"eta={eta:.0f}s  V1={n_v1}  V2={n_v2}  "
                f"BaseA={n_a}  BaseB={n_b}",
                flush=True,
            )

    # --- Per-variant accuracy --- #
    n = len(results)
    acc_v1 = sum(r.v1_correct for r in results) / n
    acc_v2 = sum(r.v2_correct for r in results) / n
    acc_base_a = sum(r.baseline_a_correct for r in results) / n
    acc_base_b = sum(r.baseline_b_correct for r in results) / n

    # Δ vs Baseline-B (primary comparison) in percentage points.
    delta_v1 = (acc_v1 - acc_base_b) * 100.0
    delta_v2 = (acc_v2 - acc_base_b) * 100.0
    # Δ vs Baseline-A (secondary comparison).
    delta_v1_vs_a = (acc_v1 - acc_base_a) * 100.0
    delta_v2_vs_a = (acc_v2 - acc_base_a) * 100.0

    # Sign-test vs Baseline-B (per-question wins/losses).
    def wins_losses(get_v_correct):
        wins = 0
        losses = 0
        for r in results:
            v_ok = get_v_correct(r)
            b_ok = r.baseline_b_correct
            if v_ok and not b_ok:
                wins += 1
            elif (not v_ok) and b_ok:
                losses += 1
        return wins, losses

    v1_wins, v1_losses = wins_losses(lambda r: r.v1_correct)
    v2_wins, v2_losses = wins_losses(lambda r: r.v2_correct)
    p_v1 = sign_test_pvalue(v1_wins, v1_losses)
    p_v2 = sign_test_pvalue(v2_wins, v2_losses)

    classification, recommendation = classify(
        delta_v1, delta_v2, p_v1, p_v2,
    )

    # --- Console report --- #
    print()
    print(f"{'metric':<48} {'value':>20}")
    print("-" * 71)
    print(f"{'N questions':<48} {n:>20}")
    print(f"{'Sources (M)':<48} {M:>20}")
    print(f"{'K samples per source':<48} {args.k_samples:>20}")
    print(f"{'Softmin τ (V1)':<48} {SOFTMIN_TAU:>20.3f}")
    print()
    print(f"{'Accuracy — Baseline-A (Qwen single-greedy)':<48} "
          f"{acc_base_a:>20.3f}")
    print(f"{'Accuracy — Baseline-B (uniform majority vote)':<48} "
          f"{acc_base_b:>20.3f}")
    print(f"{'Accuracy — V1 (softmin trust)':<48} "
          f"{acc_v1:>20.3f}")
    print(f"{'Accuracy — V2 (thresholded exclusion)':<48} "
          f"{acc_v2:>20.3f}")
    print()
    print(f"{'Δ V1 vs Baseline-B (pp, PRIMARY)':<48} "
          f"{delta_v1:>+20.2f}")
    print(f"{'Δ V2 vs Baseline-B (pp, PRIMARY)':<48} "
          f"{delta_v2:>+20.2f}")
    print(f"{'Δ V1 vs Baseline-A (pp, secondary)':<48} "
          f"{delta_v1_vs_a:>+20.2f}")
    print(f"{'Δ V2 vs Baseline-A (pp, secondary)':<48} "
          f"{delta_v2_vs_a:>+20.2f}")
    print()
    print(f"{'Sign-test V1 vs B: wins/losses':<48} "
          f"{v1_wins}/{v1_losses}".rjust(20))
    print(f"{'Sign-test V1 vs B: p-value':<48} "
          f"{p_v1:>20.4f}")
    print(f"{'Sign-test V2 vs B: wins/losses':<48} "
          f"{v2_wins}/{v2_losses}".rjust(20))
    print(f"{'Sign-test V2 vs B: p-value':<48} "
          f"{p_v2:>20.4f}")
    print()
    print(f"{'Classification':<48} {classification:>20}")
    print()
    print(f"Recommendation: {recommendation}")

    # --- Markdown report --- #
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / (
        f"probe_system_level_scout_halueval_qa{args.suffix}.md"
    )
    deviation_note = (
        ""
        if sources_default
        else "  ⚠ §14a DEVIATION: non-default config\n"
    )
    lines = [
        "# §14a Experiment — System-Level BCVF Integration Scout (HaluEval-QA)\n",
        "References: §6.1 / §6.7 (autonomy-domain validation that "
        "passed as a system-level result, not isolated observable). "
        "§13.10 (per-source semantic-entropy scalar — pinned for "
        "this scout). §13.19 (closure of the §13 single-axis "
        "program; §14a tests the next experimental structure).\n",
        "## Configuration\n",
        f"- **Sources (M = {M}):** "
        + ", ".join(f"`{s}`" for s in args.sources),
        f"- **Per-source scalar:** semantic entropy (§13.10 method)",
        f"- **Per-source K samples:** {args.k_samples}",
        f"- **max_new_tokens:** {args.max_new_tokens}",
        f"- **Consumer V1:** softmin trust shaping, τ={SOFTMIN_TAU}",
        f"- **Consumer V2:** thresholded exclusion (per-question "
        f"median entropy), uniform survivors",
        f"- **Selector:** weighted majority vote of source greedies",
        f"- **Benchmark:** HaluEval-QA `data` split, N={n}",
        f"- **Baseline-A:** single-source Qwen greedy "
        f"(source idx {args.qwen_baseline_idx})",
        f"- **Baseline-B:** uniform majority vote, M sources",
        f"- **NLI model:** `{args.nli_model}`",
        deviation_note.rstrip() if deviation_note else "",
        f"- **Seed:** {args.seed}\n",
        "## Result (primary comparison: V1/V2 vs Baseline-B)\n",
        "| Variant | Accuracy | Δ vs Baseline-B (pp) | Sign-test wins/losses | Sign-test p |",
        "|---|---|---|---|---|",
        f"| Baseline-A (Qwen single-greedy) | {acc_base_a:.3f} | "
        f"— | — | — |",
        f"| Baseline-B (uniform majority) | {acc_base_b:.3f} | "
        f"0.00 (reference) | — | — |",
        f"| **V1 (softmin trust, τ={SOFTMIN_TAU})** | "
        f"{acc_v1:.3f} | **{delta_v1:+.2f}** | "
        f"{v1_wins}/{v1_losses} | {p_v1:.4f} |",
        f"| **V2 (thresholded exclusion + uniform survivors)** | "
        f"{acc_v2:.3f} | **{delta_v2:+.2f}** | "
        f"{v2_wins}/{v2_losses} | {p_v2:.4f} |\n",
        "## Secondary: V1/V2 vs Baseline-A (single-source Qwen)\n",
        "| Variant | Δ vs Baseline-A (pp) |",
        "|---|---|",
        f"| V1 vs Baseline-A | {delta_v1_vs_a:+.2f} |",
        f"| V2 vs Baseline-A | {delta_v2_vs_a:+.2f} |\n",
        "## §14a pre-committed bands\n",
        f"- **STRONG (PROMOTE TO FULL §14):** Δ_v ≥ +5pp for both "
        f"V1 and V2 AND sign-test p<{SIGN_TEST_ALPHA} for at least "
        f"one variant.",
        f"- **DIRECTIONAL (PROMOTE TO FULL §14, V1 deprioritized):** "
        f"Δ_V2 ≥ +3pp AND Δ_V1 ≤ 0pp.",
        f"- **MARGINAL (one more scout authorized):** "
        f"Δ_v in (0, +3) for both.",
        f"- **SATURATION (no promotion; document as null):** "
        f"Δ_v in [-3, 0] for both.",
        f"- **REGRESSION (close LLM transfer line):** Δ_v < -3 "
        f"for either V1 or V2.\n",
        f"## Classification\n",
        f"**`{classification}`**\n",
        "## Recommendation\n",
        recommendation + "\n",
        "## Interpretation guidance\n",
        "§14a tests whether multi-source LLM Q&A using BCVF-shaped "
        "routing produces measurable accuracy lift over naive "
        "majority-voting on the most permissive §13 benchmark. The "
        "primary comparison is V1/V2 vs Baseline-B (uniform "
        "majority vote): does BCVF-shaped weighting add anything "
        "over naive 3-source ensembling? Secondary comparison is "
        "V1/V2 vs Baseline-A (single-source Qwen): does the system "
        "add anything over the strongest single source?\n",
        "If §14a STRONG or DIRECTIONAL, full §14 is authorized: "
        "extend to TruthfulQA-MC, add V3 (veto-only) and V4 "
        "(deadband) consumer variants, add highest-weight-source "
        "selector, run sign-tests at higher N. If §14a SATURATION "
        "or REGRESSION, full §14 is NOT authorized; the LLM "
        "transfer line is closed at this experimental structure "
        "in addition to §13.19's single-axis closure.\n",
        "Per §13.9, no `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` "
        "update is authorized by §14a alone — that requires "
        "STRONG band on BOTH benchmarks at any §13 or §14 probe, "
        "and §14a is HaluEval-only by design. Neither outcome "
        "retroactively affects the autonomy-domain BCVF result; "
        "§6.1 stands independently.\n",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nMarkdown report: {md_path}")

    if args.dump_json:
        json_path = args.out_dir / (
            f"probe_system_level_scout_halueval_qa{args.suffix}.json"
        )
        with json_path.open("w", encoding="utf-8") as f:
            json.dump({
                "config": {
                    "sources": list(args.sources),
                    "qwen_baseline_idx": args.qwen_baseline_idx,
                    "nli_model": args.nli_model,
                    "k_samples": args.k_samples,
                    "temperature": args.temperature,
                    "max_new_tokens": args.max_new_tokens,
                    "softmin_tau": SOFTMIN_TAU,
                    "sign_test_alpha": SIGN_TEST_ALPHA,
                    "sources_default": sources_default,
                    "seed": args.seed,
                },
                "summary": {
                    "n": n,
                    "acc_baseline_a": acc_base_a,
                    "acc_baseline_b": acc_base_b,
                    "acc_v1": acc_v1,
                    "acc_v2": acc_v2,
                    "delta_v1_vs_b_pp": delta_v1,
                    "delta_v2_vs_b_pp": delta_v2,
                    "delta_v1_vs_a_pp": delta_v1_vs_a,
                    "delta_v2_vs_a_pp": delta_v2_vs_a,
                    "v1_sign_test_wins": v1_wins,
                    "v1_sign_test_losses": v1_losses,
                    "v1_sign_test_p": p_v1,
                    "v2_sign_test_wins": v2_wins,
                    "v2_sign_test_losses": v2_losses,
                    "v2_sign_test_p": p_v2,
                    "classification": classification,
                },
                "questions": [
                    {
                        "q_idx": r.q_idx,
                        "question": r.question,
                        "right_answer": r.right_answer,
                        "hallucinated_answer": r.hallucinated_answer,
                        "sources": [
                            {
                                "source_idx": s.source_idx,
                                "source_name": s.source_name,
                                "samples": s.samples,
                                "cluster_ids": s.cluster_ids,
                                "semantic_entropy": s.semantic_entropy,
                                "greedy": s.greedy,
                                "greedy_correct": s.greedy_correct,
                            }
                            for s in r.sources
                        ],
                        "v1_weights": r.v1_weights,
                        "v1_selected": r.v1_selected,
                        "v1_correct": r.v1_correct,
                        "v2_weights": r.v2_weights,
                        "v2_selected": r.v2_selected,
                        "v2_correct": r.v2_correct,
                        "v2_threshold": r.v2_threshold,
                        "v2_n_survivors": r.v2_n_survivors,
                        "baseline_a_correct": r.baseline_a_correct,
                        "baseline_b_selected": r.baseline_b_selected,
                        "baseline_b_correct": r.baseline_b_correct,
                    }
                    for r in results
                ],
            }, f, indent=2)
        print(f"Per-question JSON dump: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
