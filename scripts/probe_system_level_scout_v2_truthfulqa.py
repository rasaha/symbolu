#!/usr/bin/env python
"""§15.5 sibling producer — §14a.2 protocol applied to TruthfulQA-MC.

This script is a near-verbatim copy of
`scripts/probe_system_level_scout_v2.py` (the §14a.2 producer)
with three surgical changes per §15.5 Amendment 1:

  1. Dataset loading swapped from HaluEval-QA to TruthfulQA-MC
     (mirroring §13.11's `--benchmark truthfulqa_mc` loader).
  2. Per-question correctness labeling swapped from single-
     `hallucinated_answer` to multi-`distractors` (mirroring
     §13.11's `label_correctness` for TruthfulQA-MC's MC structure).
  3. Per-question dataclass field renamed accordingly
     (`hallucinated_answer: str` → `distractors: List[str]`)
     and JSON dump field updated.

All other §14a.2 pinned configuration is preserved verbatim:
M=3 cross-family sources, K=10 stochastic samples, T=1.0,
max_new_tokens=32, NLI model = DeBERTa-v3-base-mnli-fever-anli,
V1 softmin tau=0.5, V2 thresholded exclusion, NLI-clustered
weighted majority vote selector, identical sign-test and
classify() functions.

Output: docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json
(per §15.5 Chunk 5h's pinned output path).

§0.8 discipline: §14a.2's producer
`scripts/probe_system_level_scout_v2.py` is preserved
unchanged; this sibling exists to extend the §14a.2 protocol
to TruthfulQA-MC for §15.5 Stage A without modifying the
closed §14a.2 verdict-of-record's reproducibility chain.

§15.5 does NOT classify this script's output against §14a.2
bands. The output dump is consumed by §15.5 Phase 2
(`scripts/probe_hybrid_selective_abstention_truthfulqa.py`,
to be drafted) which classifies against §15.5's pinned
Delta_kappa cascade per §15.5 Chunk 5g.

ORIGINAL §14a.2 PRODUCER DOCSTRING FOLLOWS — unchanged from
`scripts/probe_system_level_scout_v2.py`:

§14a.2 experiment — System-level BCVF integration scout (selector-spec fix).

Reference:
  §14a / §14b — original system-level scout. Returned
  SCOUT_SATURATION per §14a's pre-committed bands. Post-§14b
  audit revealed structural issue: the §14a-pinned selector
  (weighted majority vote with string-identity grouping)
  degenerates at M=3 cross-family because Qwen, Llama, and
  Mistral emit stylistically different greedy strings even when
  they semantically agree. With 3 distinct strings, all majority
  votes become 3-way string ties broken by source-list order →
  always pick Qwen. Empirical confirmation in §14a JSON dump:
  acc(Baseline-A) = acc(Baseline-B) = 0.300 exactly across N=100.
  Baseline-B was effectively single-source-Qwen, not real
  ensembling. The system layer never had bandwidth to differentiate.

  §14a SCOUT_SATURATION verdict remains binding under §0.8 for
  the §14a-pinned configuration. §14a.2 fixes ONLY the selector
  spec; everything else inherits §14a verbatim.

  symbolu_robotics/bcvf_autonomous/DESIGN.md §6.1 / §6.7 —
  autonomy-domain validation that passed (sign-test p=0.0072 on
  N=21 with S3_map_error_accel) was a SYSTEM-LEVEL result: multi-
  source robotic system using BCVF-shaped routing produces sign-
  test-significant gains over baseline. NOT an isolated-observable
  result.

  §13's program (§13.10–§13.19) tested observables in isolation;
  closed at the single-axis level. §14a tested system-level with
  string-matched selector; closed at SCOUT_SATURATION but with
  the spec issue described above. §14a.2 is the methodologically
  correct re-test.

Method (changes from §14a in **bold**):
  1. Three sources: Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct,
     Mistral-7B-Instruct-v0.3 (all cached from §13.11). Unchanged.
  2. Per source per question: K=10 stochastic samples + 1 greedy
     answer. Compute per-source semantic entropy H_src(q) over
     question-conditioned NLI clusters of the K samples (§13.10
     method, identical scalar). Unchanged.
  3. Two consumer variants (both run, results compared):
     - V1 softmin trust: w_i ∝ exp(-d_i/τ), τ=0.5 pinned. Unchanged.
     - V2 thresholded exclusion: S = {i : d_i ≤ θ}, w_i = 1/|S|,
       θ = per-question median entropy. Unchanged.
  4. **NEW** Selector: NLI-clustered weighted majority vote.
     a. Cluster the M=3 source greedies via question-conditioned
        bidirectional NLI entailment (the §13.10
        cluster_by_entailment mechanism applied to candidate
        answers, not K stochastic samples).
     b. Aggregate weights within each cluster.
     c. Pick the cluster with maximum total weight (ties broken
        by lowest cluster index).
     d. Within the winning cluster, pick the source with the
        highest individual weight as the representative (ties
        broken by source-list order).
  5. **NEW** Baselines:
     A: single-source Qwen greedy (unchanged from §14a).
     B: NLI-clustered uniform majority vote of M source greedies
        (uses the new selector with weights w_i = 1/M). This
        replaces §14a's string-matched Baseline-B which was
        empirically degenerate.
  6. Per-question correctness label (each candidate answer):
     question-conditioned NLI must entail right_answer AND not
     entail hallucinated_answer. Unchanged.
  7. Per-variant accuracy = fraction of N=100 questions where
     the variant's selected answer is labeled correct.
  8. Δ_v = acc(v) - acc(Baseline-B_v2) for v in {V1, V2}.
     Note: Baseline-B here is the new NLI-clustered uniform
     majority, NOT §14a's degenerate string-matched Baseline-B.
  9. Sign-test for v vs Baseline-B_v2: per-question wins (v
     correct AND B_v2 wrong) vs losses (v wrong AND B_v2 correct);
     binomial test on win count vs total non-ties at α=0.05.

Pre-committed bands (§14a.2, pinned in design doc BEFORE
implementation; same numerical thresholds as §14a but applied to
Δ vs the new NLI-clustered Baseline-B):

  - STRONG: Δ_v ≥ +5pp for both V1 and V2 AND sign-test p<0.05
    for at least one. PROMOTE to full §14.
  - DIRECTIONAL: Δ_V2 ≥ +3pp AND Δ_V1 ≤ 0pp. PROMOTE to full §14
    with V1 deprioritized.
  - MARGINAL: Δ_v in (0, +3) for both. AUTHORIZE one more scout.
  - SATURATION: Δ_v in [-3, 0] for both. Combined with §14a's
    SCOUT_SATURATION + §13.19's 5-of-5 single-axis null, this is
    the methodologically clean closure of the LLM transfer line
    in this codebase.
  - REGRESSION: Δ_v < -3 for either V1 or V2. CLOSE LLM transfer
    line with strong evidence.

Do NOT update AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md on the basis of
any §14a.2 result — that requires STRONG band on BOTH benchmarks
at any §13 or §14 probe. §14a.2 is HaluEval-only by design.

Usage:
    HF_HUB_DISABLE_XET=1 python scripts/probe_system_level_scout_v2.py \\
        --num-questions 100 --dump-json

Runtime ~50–60 min on the 80 GB GPU (essentially identical to
§14a; the new NLI-cluster step on M=3 candidate answers per
question adds ~1 min vs §14a's selector cost).
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
    distractors: List[str]                  # §15.5: TruthfulQA-MC has multiple distractors
    sources: List[SourceResult]
    # NEW in §14a.2: NLI clustering of the M source greedies. Cluster
    # IDs are length-M, parallel to sources; same canonicalization as
    # §13.10 cluster_by_entailment (lowest source index wins canonical 0).
    answer_cluster_ids: List[int]
    n_answer_clusters: int                  # number of distinct clusters
    # Per-variant outputs (selectors NOW use NLI-clustered weighted
    # majority vote):
    v1_weights: List[float]                 # softmin weights, length M
    v1_cluster_weights: List[float]         # aggregated weight per cluster
    v1_winning_cluster: int                 # cluster ID of winning cluster
    v1_selected: str                        # representative answer string
    v1_correct: bool                        # NLI label on V1's pick
    v2_weights: List[float]                 # thresholded weights, length M
    v2_cluster_weights: List[float]
    v2_winning_cluster: int
    v2_selected: str
    v2_correct: bool
    v2_threshold: float                     # the per-question median used
    v2_n_survivors: int                     # |S| after thresholding
    # Baselines (Baseline-B NOW uses NLI-clustered uniform majority):
    baseline_a_correct: bool                # Qwen greedy correctness (unchanged)
    baseline_b_cluster_weights: List[float]
    baseline_b_winning_cluster: int
    baseline_b_selected: str                # NLI-clustered uniform majority winner
    baseline_b_correct: bool


# §14a.2 pinned constants. Same numerical thresholds as §14a (the
# metric is structurally the same; only Baseline-B's meaning changes).
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
            "Strong §14a.2 scout pass — PROMOTE TO FULL §14. Both V1 "
            "and V2 lift accuracy by ≥5pp over NLI-clustered uniform "
            "majority vote, with sign-test significance for at least "
            "one variant. The selector-spec fix vs §14a's degenerate "
            "string-matched selector reveals the system-level "
            "integration hypothesis IS supported on the most "
            "permissive §13 benchmark when properly evaluated. "
            "Authorizes drafting full §14 pre-commitment with both "
            "benchmarks (TruthfulQA-MC + HaluEval-QA), all four "
            "consumer variants, both selectors, and ablation runners."
        )
    # DIRECTIONAL: V2 ≥ +3pp AND V1 ≤ 0pp (ChatGPT's predicted pattern)
    if (delta_v2 >= DIRECTIONAL_V2_THRESHOLD
            and delta_v1 <= DIRECTIONAL_V1_CEILING):
        return "SCOUT_DIRECTIONAL", (
            "Directional §14a.2 scout pass — PROMOTE TO FULL §14 WITH "
            "V1 DEPRIORITIZED. ChatGPT's predicted pattern observed "
            "under the methodologically correct selector: softmin "
            "trust shaping (V1) does not lift while thresholded "
            "exclusion (V2) does. Authorizes full §14 with V1 "
            "dropped from the consumer variant pool, V2 promoted as "
            "primary, V3 (veto-only) and V4 (deadband) added as the "
            "remaining variants. The autonomy-domain softmin default "
            "appears inappropriate for LLM-domain ensembling at "
            "this configuration."
        )
    # REGRESSION: Δ < -3pp for either variant — close LLM track
    if (delta_v1 < REGRESSION_THRESHOLD
            or delta_v2 < REGRESSION_THRESHOLD):
        return "SCOUT_REGRESSION", (
            "§14a.2 scout regression — CLOSE LLM TRANSFER LINE with "
            "comprehensive evidence. System-level integration with "
            "the methodologically correct NLI-clustered selector "
            "actively HURTS accuracy vs NLI-clustered naive majority "
            "voting on the most permissive §13 benchmark. Combined "
            "with §13.19's 5-of-5 single-axis null AND §14a's "
            "string-matched-selector SCOUT_SATURATION, this is "
            "comprehensive evidence that BCVF-for-LLMs does not "
            "transfer at any tested experimental structure on this "
            "codebase, including the methodologically-corrected "
            "system-level configuration. The autonomy-domain BCVF "
            "claim stands independently on §6.1. No further LLM-"
            "domain probes authorized without a fundamental "
            "reframing (different model class, different benchmark "
            "family, or different formal structure entirely)."
        )
    # MARGINAL: 0 < Δ ≤ +3pp for both
    if (MARGINAL_LOWER < delta_v1 <= MARGINAL_UPPER
            and MARGINAL_LOWER < delta_v2 <= MARGINAL_UPPER):
        return "SCOUT_MARGINAL", (
            "§14a.2 scout marginal — UNDECIDED. Small lift over the "
            "NLI-clustered baseline but neither variant clears the "
            "+3pp DIRECTIONAL threshold or +5pp STRONG threshold. "
            "Authorize one more scout (V3 veto-only + V4 deadband "
            "consumer variants, OR Variant A entropy 2nd-difference "
            "per-source scalar) before deciding on full §14. Pre-"
            "commitment for the additional scout would be a fresh "
            "§0.8 commitment (§14a.3 or similar). Full §14 NOT "
            "authorized until either MARGINAL+ or STRONG is reached "
            "on a follow-up scout."
        )
    # SATURATION: Δ ∈ [-3, 0] for both
    return "SCOUT_SATURATION", (
        "§14a.2 scout saturation — DOCUMENT AS NULL, do NOT promote. "
        "The system layer adds nothing measurable on top of NLI-"
        "clustered uniform majority voting EVEN AFTER the §14a "
        "selector-spec fix. Combined with §14a's SCOUT_SATURATION "
        "(string-matched selector) and §13.19's 5-of-5 single-axis "
        "null, this is the methodologically clean closure §14a's "
        "structural issue made unavailable. The honest external "
        "framing: single-axis observables saturate (5-of-5 §13 "
        "null); system-level integration with string-matched "
        "selector saturates (§14a); system-level integration with "
        "NLI-clustered selector also saturates (§14a.2). The LLM "
        "transfer line is closed at all tested experimental "
        "structures. Do NOT update VC-facing material; the §13.9 "
        "hold remains in force and is strengthened. Full §14 NOT "
        "authorized without a fundamentally different signal class "
        "or scope."
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


def select_nli_clustered_majority_vote(
    answers: List[str], weights: np.ndarray, cluster_ids: List[int],
) -> Tuple[str, np.ndarray, int]:
    """§14a.2 NLI-clustered weighted majority vote selector.

    Replaces §14a's `select_weighted_majority_vote` (which grouped
    by string identity → degenerate at M=3 cross-family, see §14a.2
    pre-commitment for full rationale).

    Inputs:
      - answers : list of M candidate answer strings, parallel to
        `cluster_ids` (sources).
      - weights : np.ndarray of M floats, parallel to answers.
      - cluster_ids : list of M cluster assignments produced
        externally by `cluster_by_entailment` on the M candidate
        answers using question-conditioned bidirectional NLI.

    Algorithm (per §14a.2 spec):
      1. Aggregate weights within each cluster:
         W_k = Σ_{i ∈ cluster k} w_i.
      2. Pick winning cluster k* = argmax_k W_k. Ties broken by
         lowest cluster index (deterministic via cluster_ids
         canonicalization).
      3. Within winning cluster k*, pick representative source as
         the one with the highest individual weight. Ties broken
         by lowest source index (the natural argmax tiebreaker).
      4. Return (representative_answer, cluster_weights, k*).

    Returns:
      - representative answer string
      - per-cluster aggregated weights array (length = number of
        unique clusters; index k corresponds to cluster ID k after
        canonicalization)
      - winning cluster ID
    """
    M = len(answers)
    if M == 0:
        return "", np.zeros(0), -1
    n_clusters = max(cluster_ids) + 1 if cluster_ids else 0
    cluster_weights = np.zeros(n_clusters, dtype=np.float64)
    for i in range(M):
        cluster_weights[cluster_ids[i]] += float(weights[i])
    # Argmax with lowest-cluster-index tiebreaker. np.argmax returns
    # the lowest index among ties by default — matches the spec.
    winning_cluster = int(np.argmax(cluster_weights))
    # Within the winning cluster, pick the source with the highest
    # individual weight. Ties broken by lowest source index (np.argmax
    # default behavior on the masked weight vector).
    in_cluster_mask = np.array(
        [cid == winning_cluster for cid in cluster_ids], dtype=bool,
    )
    masked_weights = np.where(in_cluster_mask, weights, -np.inf)
    representative_idx = int(np.argmax(masked_weights))
    return answers[representative_idx], cluster_weights, winning_cluster


def label_answer_correctness(
    candidate_answer: str, right_answer: str, distractors: List[str],
    check_batch, question: str,
) -> bool:
    """Question-conditioned correctness label for a single candidate
    answer. §15.5 sibling: handles TruthfulQA-MC's multi-distractor
    structure (mirroring §13.11's `label_correctness`) — entails
    right_answer AND does NOT entail ANY distractor.

    Identical labeling protocol to §13.10 / §13.11 / §13.18 on
    TruthfulQA-MC. The only difference vs the §14a.2 single-
    distractor version is that we batch over all distractors and
    require none to be entailed.
    """
    premise = f"{question} {candidate_answer}"
    candidates = [right_answer] + list(distractors)
    hypotheses = [f"{question} {c}" for c in candidates]
    verdicts = check_batch([premise] * len(candidates), hypotheses)
    entails_right = verdicts[0]
    entails_any_distractor = any(verdicts[1:])
    return bool(entails_right and not entails_any_distractor)


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

    print("Loading TruthfulQA (multiple_choice, validation) ...", flush=True)
    ds = load_dataset(
        "truthful_qa", "multiple_choice", split="validation",
    )
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
        # §15.5: TruthfulQA-MC row parsing (mirroring §13.11 lines 652-660).
        # Replaces §14a.2's single-`hallucinated_answer` HaluEval row parser.
        q_text = row["question"]
        choices = list(row["mc1_targets"]["choices"])
        labels = list(row["mc1_targets"]["labels"])
        correct_index = int(labels.index(1))
        right_answer = choices[correct_index]
        distractors = [
            c for i, c in enumerate(choices) if i != correct_index
        ]
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
                greedy, right_answer, distractors,
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

        # NEW in §14a.2: cluster the M source greedies by question-
        # conditioned bidirectional NLI entailment. This is the same
        # cluster_by_entailment mechanism §13.10 uses for K=10
        # samples; here applied to the M=3 candidate answers. Result
        # is parallel to `greedies` and `source_results`. Cluster
        # IDs are canonicalized starting from 0 with lowest source
        # index winning canonical 0.
        answer_cluster_ids = cluster_by_entailment(
            greedies, check_batch, q_text,
        )
        n_answer_clusters = (
            max(answer_cluster_ids) + 1 if answer_cluster_ids else 0
        )

        # V1 — softmin trust shaping with NLI-clustered selector
        v1_weights = consumer_v1_softmin(entropies, tau=SOFTMIN_TAU)
        v1_selected, v1_cluster_weights, v1_winning_cluster = (
            select_nli_clustered_majority_vote(
                greedies, v1_weights, answer_cluster_ids,
            )
        )
        v1_correct = label_answer_correctness(
            v1_selected, right_answer, distractors,
            check_batch, q_text,
        )

        # V2 — thresholded exclusion + uniform survivors with
        # NLI-clustered selector
        v2_weights, v2_threshold, v2_n_survivors = (
            consumer_v2_thresholded(entropies)
        )
        v2_selected, v2_cluster_weights, v2_winning_cluster = (
            select_nli_clustered_majority_vote(
                greedies, v2_weights, answer_cluster_ids,
            )
        )
        v2_correct = label_answer_correctness(
            v2_selected, right_answer, distractors,
            check_batch, q_text,
        )

        # Baselines
        baseline_a_correct = source_results[
            args.qwen_baseline_idx
        ].greedy_correct
        # NEW in §14a.2: Baseline-B uses NLI-clustered uniform majority
        # (NOT the §14a string-matched version which was empirically
        # degenerate at M=3 cross-family). This is the §14a.2-pinned
        # comparison baseline.
        baseline_b_weights = np.ones(M, dtype=np.float64) / M
        (
            baseline_b_selected,
            baseline_b_cluster_weights,
            baseline_b_winning_cluster,
        ) = select_nli_clustered_majority_vote(
            greedies, baseline_b_weights, answer_cluster_ids,
        )
        baseline_b_correct = label_answer_correctness(
            baseline_b_selected, right_answer, distractors,
            check_batch, q_text,
        )

        results.append(QuestionResult(
            q_idx=q_idx, question=q_text,
            right_answer=right_answer,
            distractors=distractors,
            sources=source_results,
            answer_cluster_ids=answer_cluster_ids,
            n_answer_clusters=n_answer_clusters,
            v1_weights=v1_weights.tolist(),
            v1_cluster_weights=v1_cluster_weights.tolist(),
            v1_winning_cluster=v1_winning_cluster,
            v1_selected=v1_selected,
            v1_correct=v1_correct,
            v2_weights=v2_weights.tolist(),
            v2_cluster_weights=v2_cluster_weights.tolist(),
            v2_winning_cluster=v2_winning_cluster,
            v2_selected=v2_selected,
            v2_correct=v2_correct,
            v2_threshold=v2_threshold,
            v2_n_survivors=v2_n_survivors,
            baseline_a_correct=baseline_a_correct,
            baseline_b_cluster_weights=baseline_b_cluster_weights.tolist(),
            baseline_b_winning_cluster=baseline_b_winning_cluster,
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
        f"probe_system_level_scout_v2_truthfulqa_mc{args.suffix}.md"
    )
    deviation_note = (
        ""
        if sources_default
        else "  ⚠ §14a DEVIATION: non-default config\n"
    )
    lines = [
        "# §14a.2 Experiment — System-Level BCVF Scout with NLI-Clustered Selector (HaluEval-QA)\n",
        "References: §6.1 / §6.7 (autonomy-domain validation that "
        "passed as a system-level result). §13.10 (per-source "
        "semantic-entropy scalar). §14a / §14b (original scout, "
        "returned SCOUT_SATURATION; post-§14b audit revealed "
        "string-matched selector degenerate at M=3 cross-family). "
        "§14a.2 (this experiment — selector-spec fix only).\n",
        "## Configuration\n",
        f"- **Sources (M = {M}):** "
        + ", ".join(f"`{s}`" for s in args.sources),
        f"- **Per-source scalar:** semantic entropy (§13.10 method)",
        f"- **Per-source K samples:** {args.k_samples}",
        f"- **max_new_tokens:** {args.max_new_tokens}",
        f"- **Consumer V1:** softmin trust shaping, τ={SOFTMIN_TAU}",
        f"- **Consumer V2:** thresholded exclusion (per-question "
        f"median entropy), uniform survivors",
        f"- **Selector (NEW vs §14a):** NLI-clustered weighted "
        f"majority vote of source greedies",
        f"- **Benchmark:** TruthfulQA-MC validation split, N={n}",
        f"- **Baseline-A:** single-source Qwen greedy "
        f"(source idx {args.qwen_baseline_idx})",
        f"- **Baseline-B (NEW vs §14a):** NLI-clustered uniform "
        f"majority vote, M sources",
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
            f"probe_system_level_scout_v2_truthfulqa_mc{args.suffix}.json"
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
                        "distractors": r.distractors,
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
                        # NEW in §14a.2: NLI-clustering of M
                        # candidate answers + per-cluster aggregated
                        # weights for each variant.
                        "answer_cluster_ids": r.answer_cluster_ids,
                        "n_answer_clusters": r.n_answer_clusters,
                        "v1_weights": r.v1_weights,
                        "v1_cluster_weights": r.v1_cluster_weights,
                        "v1_winning_cluster": r.v1_winning_cluster,
                        "v1_selected": r.v1_selected,
                        "v1_correct": r.v1_correct,
                        "v2_weights": r.v2_weights,
                        "v2_cluster_weights": r.v2_cluster_weights,
                        "v2_winning_cluster": r.v2_winning_cluster,
                        "v2_selected": r.v2_selected,
                        "v2_correct": r.v2_correct,
                        "v2_threshold": r.v2_threshold,
                        "v2_n_survivors": r.v2_n_survivors,
                        "baseline_a_correct": r.baseline_a_correct,
                        "baseline_b_cluster_weights":
                            r.baseline_b_cluster_weights,
                        "baseline_b_winning_cluster":
                            r.baseline_b_winning_cluster,
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
