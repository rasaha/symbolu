#!/usr/bin/env python
"""§13.14 experiment — BCVF-faithful 2nd-difference observable.

Background:
  §13.10 (single-model semantic entropy), §13.11 (cross-family
  ensemble), §13.12 (EigenScore over hidden states), and §13.13
  (continuous semantic entropy) are all single-snapshot agent-only
  measurements. Each samples K completions and computes ONE scalar
  per question. None of them is shaped like the autonomy-domain
  BCVF observable `S3_map_error_accel` that passed §6.1 / §6.7 —
  the second derivative of the divergence between the agent's
  internal map and ground truth, evaluated as the agent moves
  through its environment over time.

  This script implements the LLM analogue of that observable. The
  token sequence is the LLM's analogue of "robot moving through
  environment over time": the question is presented at t=0 and
  the model must construct an answer over t=1..T. Per-position
  semantic entropy across K samples is the LLM analogue of "agent's
  evolving world model". The 2nd difference of per-position entropy
  across the sequence is the LLM analogue of `S3_map_error_accel` —
  the acceleration of the model's evolving uncertainty as it
  constructs an answer.

  This is the first probe in the §13 ladder that is shaped like the
  autonomy-domain BCVF observable that actually passed validation.
  §13.10-§13.13 audit literature methods; §13.14 tests whether the
  BCVF formalism itself transfers. A positive result here would be
  the first novel construction in this codebase that is BCVF-shaped
  rather than literature-shaped; a negative result would constitute
  the first direct evidence that the BCVF formalism does not transfer
  to LLMs at this analogue.

  Importantly, neither outcome retroactively affects the autonomy-
  domain BCVF result. §6.1's N=21 sign-test on `S3_map_error_accel`
  passed independently and stands; §13.14's outcome bears only on
  the LLM-domain transfer claim.

Method:
  1. For each question, sample K=10 completions at T=1.0,
     max_new_tokens=128 (4× §13.10's 32; needed for the 2nd-
     difference signal to evolve over enough sequence length).
  2. At each pinned grid position
     t in {position_min, position_min + position_stride, ...,
           max_new_tokens}
     truncate the K samples to t generated tokens, decode each
     truncation to text, cluster the K truncated strings by
     question-conditioned bidirectional NLI entailment, and compute
     Shannon entropy H_t (nats) over the cluster-size distribution.
  3. Compute the per-position 2nd difference at each interior i:
         accel_i = H_{t_{i+1}} - 2·H_{t_i} + H_{t_{i-1}}
  4. Primary scalar (pinned for AUC + bands):
         bcvf_2diff(q) = max_i |accel_i|
     Mirrors `S3_map_error_accel` peak in the robotics domain —
     the largest moment of "uncertainty acceleration" during
     answer construction.
  5. Correctness label: Qwen greedy passes question-conditioned NLI
     against correct AND fails NLI against every distractor
     (identical to §13.10-§13.13 for direct AUC comparability).
  6. AUC computed on -bcvf_2diff(q) (higher acceleration → less
     stable evolving uncertainty → more likely wrong, negate for
     "higher = more truth-predictive" convention).

Pre-committed success bands (§13.14, pinned in design doc BEFORE
implementation; same numerical partition as §13.11-§13.13 since the
§13.10 baseline of 0.661 is unchanged):

  - AUC >= 0.75 on both benchmarks -> BCVF_2DIFF_STRONG.
    Gates the §13.9 VC-brief revision AND constitutes load-bearing
    evidence for the BCVF-for-LLMs transfer claim — distinct stake
    from any §13.10-§13.13 STRONG outcome because §13.14 is the
    first BCVF-shaped probe in the ladder.
  - 0.70 <= AUC < 0.75 on both -> BCVF_2DIFF_INTERNAL_STRONG.
    Strong for internal research; VC-brief still held.
  - 0.681 <= AUC < 0.70 on both -> BCVF_2DIFF_MARGINAL_LIFT.
    Modest but real lift above §13.10 + 0.02.
  - 0.641 <= AUC <= 0.681 on both -> BCVF_2DIFF_SATURATION.
    Within ±0.02 of §13.10 baseline. SUBSTANTIVE INTERNAL FINDING:
    the BCVF 2nd-difference observable adds nothing measurable
    beyond static-snapshot SE on the LLM domain. Narrows the
    BCVF-for-LLMs honest scope to "BCVF concepts inspired the §13
    metric exploration but the native BCVF observable does not
    improve on the literature's first-derivative methods on this
    codebase."
  - AUC < 0.641 on any benchmark -> BCVF_2DIFF_ANTI_FINDING.
    The 2nd-difference signal is *worse than* the static §13.10
    baseline. BCVF-for-LLMs as a hallucination detector is not
    supported by direct measurement on this codebase. The autonomy-
    domain BCVF claim stands independently on §6.1 evidence.

Relationship to other §13 probes:
  This is a NEW probe per §13.14. It does NOT replace any §13.10-
  §13.13 script (those results are pinned). Same target model,
  same benchmarks, same K=10, same correctness label as those
  probes — for direct AUC comparability across the five-probe
  ladder. The only differences are: (a) max_new_tokens=128 instead
  of 32 (needed for sequence-length signal), and (b) per-position
  clustering at a stride-4 grid instead of a single end-of-sequence
  clustering. The scalar is structurally different (2nd difference
  of position-indexed entropy series instead of single entropy
  value).

Do NOT update AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md on the basis of
any result from this probe except BCVF_2DIFF_STRONG on BOTH
benchmarks (per §13.9). Anything less is internal research
confidence only.

Usage:
    HF_HUB_DISABLE_XET=1 python scripts/probe_bcvf_2diff.py \\
        --num-questions 100 \\
        --benchmark truthfulqa_mc \\
        --dump-json

Runtime ~8-12 min at N=100 on a 24+ GB GPU (per-position clustering
at ~31 grid positions × ~90 NLI pairs/position = ~2,800 NLI calls
per question, batched).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass
class QuestionResult:
    q_idx: int
    question: str
    prompt: str
    correct_choice: str
    distractors: List[str]
    samples: List[str]
    # Per-sample non-pad length in generated tokens. Diagnostic for
    # spotting truncation pathologies (e.g., all samples short, so
    # later grid positions all use the same full sample text).
    sample_lengths: List[int]
    greedy: str
    # The pinned grid positions (in generated-token indices) where
    # entropy was measured. Stored per-question because edge cases
    # (sample shorter than position) can produce duplicates.
    grid_positions: List[int]
    # Shannon entropy (nats) at each grid position. Same length as
    # grid_positions.
    entropy_series: List[float]
    # Per-position centered 2nd differences accel_i = H_{i+1} −
    # 2·H_i + H_{i-1} for i in [1, len(entropy_series) - 2]. Length
    # is len(entropy_series) - 2 (interior positions only).
    accelerations: List[float]
    # Primary scalar pinned for AUC + bands: max_i |accel_i|.
    primary_scalar: float
    # Diagnostic secondary scalars — reported in JSON dump but NOT
    # in the band classification. Pinning them here means changing
    # the primary scalar after the run is detectable as a §0.8
    # violation.
    mean_abs_accel: float
    sum_squared_accel: float
    peak_position_index: int  # index into accelerations of the peak
    greedy_matches_correct: bool
    label: int  # 1 = correct, 0 = wrong


# §13.14 pre-committed band boundaries. Identical numerical partition
# to §13.11 / §13.12 / §13.13 because the §13.10 baseline of 0.661 is
# unchanged across all five probes. Relabeled BCVF_2DIFF_* so the
# per-revision lineage stays legible in console output, JSON dumps,
# and grep.
BASELINE_AUC = 0.661               # §13.10 single-model SE result.
SATURATION_DELTA = 0.02            # ±window around the baseline.
STRONG_THRESHOLD = 0.75            # §13.9 VC-gate bar.
INTERNAL_STRONG_THRESHOLD = 0.70   # Strong-for-internal; VC still held.
MARGINAL_LIFT_THRESHOLD = BASELINE_AUC + SATURATION_DELTA   # 0.681
SATURATION_LOWER = BASELINE_AUC - SATURATION_DELTA          # 0.641


def classify(auc: float) -> Tuple[str, str]:
    """Map an AUC to a §13.14 band label and per-run recommendation.

    Bands are partitioned so every float in [0, 1] falls into exactly
    one label. "On both benchmarks" determination is made externally
    by running this script twice (truthfulqa_mc + halueval_qa) and
    comparing the two per-run classifications under the §13.14 worst-
    benchmark rule.

    Recommendations carry §13.14-specific framing (vs §13.11 / §13.12
    / §13.13's recommendations) because §13.14's outcome bears
    directly on the BCVF-for-LLMs transfer claim, not just on a
    literature method's benchmark performance.
    """
    if auc >= STRONG_THRESHOLD:
        return "BCVF_2DIFF_STRONG", (
            "Strong pass. Gates the §13.9 VC-brief revision — but "
            "only if the OTHER benchmark also clears 0.75. ALSO "
            "constitutes load-bearing evidence for the BCVF-for-LLMs "
            "transfer claim: this is the first probe in the §13 "
            "ladder shaped like the autonomy-domain `S3_map_error_"
            "accel` observable that passed §6.1, and a STRONG result "
            "here is qualitatively different from a STRONG on §13.10-"
            "§13.13 (which only audit literature methods). Authorizes "
            "a §13.15 result writeup positioning §13.14 as the first "
            "BCVF-faithful LLM result in this codebase."
        )
    if auc >= INTERNAL_STRONG_THRESHOLD:
        return "BCVF_2DIFF_INTERNAL_STRONG", (
            "Strong for internal research. The 2nd-difference "
            "observable produces signal but doesn't clear §13.9. "
            "Diagnostic follow-ups: (a) NLI upgrade to DeBERTa-v3-"
            "large (--nli-model), (b) finer position grid "
            "(--position-stride 2 or 1), (c) target-model upscale "
            "to Qwen2.5-32B."
        )
    if auc >= MARGINAL_LIFT_THRESHOLD:
        return "BCVF_2DIFF_MARGINAL_LIFT", (
            "Real but modest lift above §13.10 + 0.02. Document; "
            "do NOT authorize further single-axis probe progression. "
            "The BCVF-shaped signal exists but is not strong enough "
            "to change the §13.9 external framing."
        )
    if auc >= SATURATION_LOWER:
        return "BCVF_2DIFF_SATURATION", (
            "Within ±0.02 of §13.10's 0.661 baseline. The BCVF 2nd-"
            "difference observable adds NOTHING MEASURABLE beyond "
            "static-snapshot semantic entropy on the LLM domain. "
            "SUBSTANTIVE INTERNAL FINDING: narrows the BCVF-for-LLMs "
            "honest scope. The native BCVF observable that powered "
            "§6.1 in robotics does not produce a comparable signal "
            "lift on this codebase's LLM benchmarks. Diagnostic "
            "options before treating as final: secondary-scalar "
            "audit (mean|accel|, Σaccel² in the JSON dump), wider "
            "position grid (stride=1), longer max_new_tokens=256."
        )
    return "BCVF_2DIFF_ANTI_FINDING", (
        "AUC below §13.10 − 0.02. The 2nd-difference signal is "
        "WORSE than the static §13.10 baseline. BCVF-for-LLMs as a "
        "hallucination detector is NOT SUPPORTED by direct "
        "measurement on this codebase. Pause LLM track. The "
        "autonomy-domain BCVF claim stands independently on §6.1 "
        "evidence and is unaffected by this null. Check for "
        "implementation bugs (position-truncation logic, NLI noise "
        "on partial sentences, accel sign convention) before "
        "treating as a genuine anti-finding."
    )


def build_nli_checker(nli_model, nli_tokenizer, device: str, batch_size: int = 32):
    """Return a function (premises, hypotheses) -> List[bool] for batched
    entailment checks. Identical to §13.10 / §13.11 / §13.12 / §13.13 —
    ensures the cluster assignments and correctness labels produced
    here are the same labels those scripts produce on the same inputs.
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


def cluster_truncated_at_position(
    truncated_samples: List[str], check_batch, question: str,
) -> List[int]:
    """Union-find clustering at a single grid position.

    Mechanically identical to §13.10's `cluster_by_entailment` — only
    the input strings differ (these are partial-generation truncations
    rather than full-generation strings). Question-conditioning is
    preserved (the question is prepended to each truncation before
    NLI) because partial generations are even more reliant on
    question context than full ones — without the question prefix,
    short truncations like "It was" or "Paris is" produce systematic
    over-clustering or under-clustering.

    All K × (K - 1) directional NLI pairs at this position are
    submitted as a single batch via `check_batch`. For K=10 that's
    90 pairs per position — batched by `check_batch` at batch_size=32
    into ~3 forward passes per position.
    """
    n = len(truncated_samples)
    if n == 0:
        return []
    contextualized = [f"{question} {s}" for s in truncated_samples]

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
    """Shannon entropy (nats) over cluster-size distribution.
    Identical formula to §13.10 / §13.11. Returns 0.0 for empty
    input or single cluster (all samples agree)."""
    from collections import Counter

    n = len(cluster_ids)
    if n == 0:
        return 0.0
    sizes = Counter(cluster_ids).values()
    p = np.array([s / n for s in sizes], dtype=np.float64)
    return float(-np.sum(p * np.log(p)))


def label_correctness(
    greedy_gen: str, correct_choice: str, distractors: List[str],
    check_batch, question: str,
) -> bool:
    """Question-conditioned correctness label. Identical protocol to
    §13.10 / §13.11 / §13.12 / §13.13. Holding this fixed across the
    §13 ladder is what makes the AUC numbers directly comparable
    across all five probes.
    """
    premise = f"{question} {greedy_gen}"
    candidates = [correct_choice] + list(distractors)
    contextualized_candidates = [f"{question} {c}" for c in candidates]
    verdicts = check_batch(
        [premise] * len(candidates),
        contextualized_candidates,
    )
    entails_correct = verdicts[0]
    entails_any_distractor = any(verdicts[1:])
    return bool(entails_correct and not entails_any_distractor)


def generate_samples_with_token_ids(
    model, tokenizer, prompt: str, k: int, temperature: float,
    max_new_tokens: int, device: str, seed: int,
):
    """Sample `k` completions and return BOTH decoded text and the
    raw generated-token-id tensor needed for per-position truncation.

    Returns ``(decoded_full, gen_token_ids, sample_lengths)`` where:
      - decoded_full : List[str], length k. Full generation strings
        with prompt prefix stripped.
      - gen_token_ids : np.ndarray of shape (k, T_new), int64.
        The generated tokens for each sample, with pad tokens
        included for samples that hit EOS before T_new.
      - sample_lengths : List[int], length k. Per-sample non-pad
        token count (used to detect when truncation at position t
        would exceed a sample's actual length).

    The token-id array is the input to per-position truncation: at
    grid position `t`, sample k's truncated text is
    ``tokenizer.decode(gen_token_ids[k, :min(t, sample_lengths[k])],
    skip_special_tokens=True)``.
    """
    import torch

    torch.manual_seed(seed)
    enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
    input_ids = enc.input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)
    prompt_len = int(input_ids.shape[1])

    pad_id = tokenizer.pad_token_id
    if pad_id is None:
        pad_id = tokenizer.eos_token_id

    with torch.inference_mode():
        out = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            do_sample=True,
            temperature=temperature,
            num_return_sequences=k,
            max_new_tokens=max_new_tokens,
            pad_token_id=pad_id,
        )
    sequences = out  # (k, prompt_len + T_new)
    gen_segment = sequences[:, prompt_len:]  # (k, T_new)
    gen_token_ids = gen_segment.detach().cpu().numpy().astype(np.int64)

    # Per-sample non-pad length: count tokens until first pad.
    is_non_pad = (gen_segment != pad_id)              # (k, T_new), bool
    sample_lengths = is_non_pad.sum(dim=1).tolist()

    decoded_full = [
        tokenizer.decode(g, skip_special_tokens=True).strip()
        for g in gen_segment
    ]
    return decoded_full, gen_token_ids, sample_lengths


def generate_greedy(
    model, tokenizer, prompt: str, max_new_tokens: int, device: str,
) -> str:
    """Deterministic T=0 completion. Used by the correctness labeler."""
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


def decode_truncated_samples(
    tokenizer, gen_token_ids: np.ndarray,
    sample_lengths: List[int], position: int,
) -> List[str]:
    """At grid position `t = position`, return the K samples truncated
    to t generated tokens (capped at each sample's actual non-pad
    length so we don't decode pad tokens into the cluster input).

    Samples shorter than `position` use their full content. This is
    a deliberate design choice: if sample k generated only 5 tokens
    before EOS and we are computing entropy at position t=12, sample
    k's "truncation at 12" is its full 5-token string. Skipping the
    sample would change K and break the clustering size; truncating
    to 12 (which would include pad tokens) would inject NLI noise.
    Using the actual length is the cleanest middle path.
    """
    k = gen_token_ids.shape[0]
    out: List[str] = []
    for k_idx in range(k):
        effective_len = min(position, sample_lengths[k_idx])
        if effective_len <= 0:
            # Sample emitted zero non-pad tokens (rare; immediate
            # EOS). Use empty string — NLI on empty premise will
            # produce neutral verdicts and the sample will likely
            # form its own cluster.
            out.append("")
            continue
        ids = gen_token_ids[k_idx, :effective_len]
        out.append(
            tokenizer.decode(ids, skip_special_tokens=True).strip()
        )
    return out


def compute_per_position_entropy_series(
    tokenizer, gen_token_ids: np.ndarray, sample_lengths: List[int],
    grid_positions: List[int], check_batch, question: str,
) -> List[float]:
    """For each grid position t in `grid_positions`, decode the K
    samples truncated to length t, cluster them by question-
    conditioned bidirectional NLI entailment, and compute Shannon
    entropy. Returns the entropy series H_{t_0}, H_{t_1}, ...
    aligned with `grid_positions`.

    This function is the core BCVF-shaped piece — it produces the
    1st-derivative-class signal (per-position entropy as a function
    of sequence index) that the 2nd-difference scalar is computed
    from. Without per-position clustering there is no "evolving
    world model" analogue and the BCVF transfer claim cannot be
    tested.
    """
    series: List[float] = []
    for t in grid_positions:
        truncated = decode_truncated_samples(
            tokenizer, gen_token_ids, sample_lengths, t,
        )
        cluster_ids = cluster_truncated_at_position(
            truncated, check_batch, question,
        )
        series.append(shannon_entropy_nats(cluster_ids))
    return series


def compute_2nd_difference_scalars(
    entropy_series: List[float],
) -> Tuple[List[float], float, float, float, int]:
    """Given per-position entropy series, compute the centered 2nd
    differences and the four §13.14 scalars.

    Returns ``(accelerations, primary, mean_abs, sum_squared,
    peak_idx)``:
      - accelerations : List[float], length len(entropy_series) - 2.
        accel_i = H_{i+1} - 2·H_i + H_{i-1} for interior i.
      - primary : float = max_i |accel_i|. Pinned per §13.14 as
        the band-classification scalar.
      - mean_abs : float = mean_i |accel_i|. Diagnostic only.
      - sum_squared : float = Σ_i accel_i². Diagnostic only.
      - peak_idx : int = index into accelerations of the peak.
        Diagnostic only.

    Edge case: if `entropy_series` has fewer than 3 points (which
    can happen only if the position grid was misconfigured to
    produce <3 positions — defensively handled), all scalars are
    0 and peak_idx = -1. Real runs at the §13.14-pinned defaults
    produce ~31 grid positions, so this case is purely defensive.
    """
    n = len(entropy_series)
    if n < 3:
        return [], 0.0, 0.0, 0.0, -1

    accelerations: List[float] = []
    for i in range(1, n - 1):
        accel = entropy_series[i + 1] - 2.0 * entropy_series[i] + entropy_series[i - 1]
        accelerations.append(accel)

    abs_accels = [abs(a) for a in accelerations]
    primary = max(abs_accels)
    mean_abs = float(np.mean(abs_accels))
    sum_squared = float(np.sum(np.array(accelerations) ** 2))
    peak_idx = int(np.argmax(abs_accels))
    return accelerations, primary, mean_abs, sum_squared, peak_idx


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Binary AUC via tie-aware rank sum. Matches §13.10 / §13.11 /
    §13.12 / §13.13. Reproduced here so this script has no internal
    project imports."""
    labels = labels.astype(bool)
    n_pos = int(labels.sum())
    n_neg = int(labels.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    rank_sum_pos = float(ranks[labels].sum())
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-questions", type=int, default=100)
    parser.add_argument(
        "--benchmark", choices=("truthfulqa_mc", "halueval_qa"),
        default="truthfulqa_mc",
        help="Identical benchmark semantics to §13.10–§13.13 — only "
             "the per-question scalar differs (max|accel| over per-"
             "position semantic entropy series instead of single "
             "end-of-sequence entropy or hidden-state covariance).",
    )
    parser.add_argument(
        "--include-context", action="store_true",
        help="halueval_qa only: prepend the 'knowledge' passage. "
             "Default False to mirror §13.10–§13.13 closed-book.",
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
        help="Target model. §13.14 pre-commitment pins this to "
             "Qwen2.5-7B-Instruct for direct §13.10 baseline "
             "comparability; changing it is a §0.8 deviation.",
    )
    parser.add_argument(
        "--nli-model",
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        help="MNLI-trained classifier for clustering AND correctness "
             "labeling. §13.14 v1 pins DeBERTa-v3-base for parity "
             "with §13.10 / §13.11 / §13.12. The §13.13-pinned "
             "DeBERTa-v3-large is the §13.14-v2 follow-up if v1 "
             "lands at SATURATION or below.",
    )
    parser.add_argument(
        "--position-min", type=int, default=8,
        help="Minimum grid position (in generated-token indices). "
             "§13.14 pins 8 to skip leading low-information tokens "
             "where NLI clustering is noisiest. A non-default value "
             "is a §13.14 deviation flagged in the report.",
    )
    parser.add_argument(
        "--position-stride", type=int, default=4,
        help="Spacing between grid positions (in generated tokens). "
             "§13.14 pins 4 for compute tractability. stride=1 is "
             "gold-standard 2nd-difference approximation but ~4× "
             "more expensive. A non-default value is a §13.14 "
             "deviation flagged in the report.",
    )
    parser.add_argument("--k-samples", type=int, default=10,
                        help="Samples per question. Pinned to 10 by "
                             "§13.14 for §13.10–§13.13 parity.")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument(
        "--max-new-tokens", type=int, default=128,
        help="§13.14 pins 128 (4× §13.10's 32). Needed so the 2nd-"
             "difference signal has enough sequence length to "
             "evolve. Lower values would compress the position grid "
             "and dilute the BCVF-shaped signal.",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--out-dir", type=pathlib.Path,
        default=_REPO_ROOT / "docs" / "experiments",
    )
    parser.add_argument("--suffix", type=str, default="")
    parser.add_argument(
        "--dump-json", action="store_true",
        help="Also write a per-question JSON dump including the full "
             "per-position entropy series and per-position 2nd "
             "differences. Required for post-hoc secondary-scalar "
             "audits if the primary scalar saturates.",
    )
    args = parser.parse_args()

    if args.k_samples < 2:
        parser.error(
            f"--k-samples must be >= 2 (clustering is undefined at K=1); "
            f"got {args.k_samples}."
        )
    if args.position_min < 1:
        parser.error(
            f"--position-min must be >= 1; got {args.position_min}."
        )
    if args.position_stride < 1:
        parser.error(
            f"--position-stride must be >= 1; got {args.position_stride}."
        )
    if args.position_min > args.max_new_tokens:
        parser.error(
            f"--position-min ({args.position_min}) cannot exceed "
            f"--max-new-tokens ({args.max_new_tokens})."
        )

    # Build the §13.14-pinned position grid. With defaults
    # (position_min=8, position_stride=4, max_new_tokens=128) this
    # produces 31 grid positions: 8, 12, 16, ..., 128.
    grid_positions = list(range(
        args.position_min, args.max_new_tokens + 1, args.position_stride,
    ))
    if len(grid_positions) < 3:
        parser.error(
            f"Position grid produced only {len(grid_positions)} positions "
            f"(need >= 3 for a 2nd difference). Check --position-min, "
            f"--position-stride, --max-new-tokens settings."
        )

    grid_is_default = (
        args.position_min == 8
        and args.position_stride == 4
        and args.max_new_tokens == 128
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

    print(f"Loading target model: {args.model}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.float16,
    ).to(device)
    model.eval()

    print(f"Loading NLI model: {args.nli_model}", flush=True)
    nli_tokenizer = AutoTokenizer.from_pretrained(args.nli_model)
    nli_dtype = torch.float16 if device == "cuda" else torch.float32
    nli_model = AutoModelForSequenceClassification.from_pretrained(
        args.nli_model, torch_dtype=nli_dtype,
    ).to(device)
    nli_model.eval()
    check_batch = build_nli_checker(nli_model, nli_tokenizer, device)

    print(
        f"Position grid: {len(grid_positions)} positions, "
        f"min={args.position_min}, stride={args.position_stride}, "
        f"max={args.max_new_tokens}"
        + ("" if grid_is_default else "  [§13.14 DEVIATION: non-default grid]"),
        flush=True,
    )

    if args.benchmark == "truthfulqa_mc":
        print("Loading TruthfulQA (multiple_choice, validation) ...", flush=True)
        ds = load_dataset(
            "truthful_qa", "multiple_choice", split="validation",
        )
    elif args.benchmark == "halueval_qa":
        print("Loading HaluEval (qa, data) ...", flush=True)
        ds = load_dataset("pminervini/HaluEval", "qa", split="data")
    else:
        raise ValueError(f"unsupported benchmark: {args.benchmark}")
    ds = ds.select(range(min(args.num_questions, len(ds))))

    results: List[QuestionResult] = []
    t_start = time.perf_counter()

    for q_idx, row in enumerate(ds):
        if args.benchmark == "truthfulqa_mc":
            q_text = row["question"]
            choices = list(row["mc1_targets"]["choices"])
            labels = list(row["mc1_targets"]["labels"])
            correct_index = int(labels.index(1))
            correct_choice = choices[correct_index]
            distractors = [
                c for i, c in enumerate(choices) if i != correct_index
            ]
            prompt = f"Q: {q_text}\nA:"
        else:  # halueval_qa
            q_text = row["question"]
            correct_choice = row["right_answer"]
            distractors = [row["hallucinated_answer"]]
            if args.include_context and row.get("knowledge"):
                prompt = f"{row['knowledge']}\n\nQ: {q_text}\nA:"
            else:
                prompt = f"Q: {q_text}\nA:"

        # Generate K samples (decoded text + raw token ids for
        # per-position truncation later).
        decoded_full, gen_token_ids, sample_lengths = (
            generate_samples_with_token_ids(
                model, tokenizer, prompt,
                k=args.k_samples, temperature=args.temperature,
                max_new_tokens=args.max_new_tokens, device=device,
                seed=args.seed + q_idx,
            )
        )

        # Per-position semantic entropy series — the 1st-derivative
        # signal that the BCVF 2nd difference will be computed from.
        entropy_series = compute_per_position_entropy_series(
            tokenizer, gen_token_ids, sample_lengths,
            grid_positions, check_batch, q_text,
        )

        # 2nd-difference scalars: pinned primary + diagnostic
        # secondaries. The unpacking enforces that these are stored
        # exactly as computed; any post-hoc swap of the primary scalar
        # would require re-running this function and is therefore
        # detectable as a §0.8 violation.
        accelerations, primary, mean_abs, sum_squared, peak_idx = (
            compute_2nd_difference_scalars(entropy_series)
        )

        # Greedy + correctness label.
        greedy = generate_greedy(
            model, tokenizer, prompt,
            max_new_tokens=args.max_new_tokens, device=device,
        )
        is_correct = label_correctness(
            greedy, correct_choice, distractors, check_batch, q_text,
        )

        results.append(QuestionResult(
            q_idx=q_idx, question=q_text, prompt=prompt,
            correct_choice=correct_choice, distractors=distractors,
            samples=decoded_full,
            sample_lengths=sample_lengths,
            greedy=greedy,
            grid_positions=list(grid_positions),
            entropy_series=entropy_series,
            accelerations=accelerations,
            primary_scalar=primary,
            mean_abs_accel=mean_abs,
            sum_squared_accel=sum_squared,
            peak_position_index=peak_idx,
            greedy_matches_correct=is_correct,
            label=1 if is_correct else 0,
        ))

        if (q_idx + 1) % 5 == 0 or q_idx + 1 == len(ds):
            elapsed = time.perf_counter() - t_start
            eta = elapsed / (q_idx + 1) * (len(ds) - q_idx - 1)
            n_correct = sum(r.label for r in results)
            mean_primary = float(
                np.mean([r.primary_scalar for r in results])
            )
            mean_entropy_end = float(np.mean([
                r.entropy_series[-1] for r in results
                if r.entropy_series
            ])) if results else 0.0
            print(
                f"  [{q_idx + 1}/{len(ds)}] elapsed={elapsed:.0f}s "
                f"eta={eta:.0f}s correct={n_correct}/{len(results)} "
                f"mean_primary={mean_primary:.4f} "
                f"mean_H_end={mean_entropy_end:.3f}",
                flush=True,
            )

    # --- AUC on the pinned PRIMARY scalar --- #
    primary_scalars = np.array(
        [r.primary_scalar for r in results], dtype=np.float64,
    )
    labels_np = np.array([r.label for r in results], dtype=np.float64)
    auc_primary = roc_auc(-primary_scalars, labels_np.astype(bool))
    classification, recommendation = classify(auc_primary)

    # --- Diagnostic AUCs on the secondary scalars (reported but NOT
    # used for band classification — pinning prevents post-hoc swap).
    mean_abs_scalars = np.array(
        [r.mean_abs_accel for r in results], dtype=np.float64,
    )
    sum_squared_scalars = np.array(
        [r.sum_squared_accel for r in results], dtype=np.float64,
    )
    auc_mean_abs = roc_auc(-mean_abs_scalars, labels_np.astype(bool))
    auc_sum_squared = roc_auc(-sum_squared_scalars, labels_np.astype(bool))

    # Summary stats on the primary scalar.
    mean_correct = (
        float(primary_scalars[labels_np == 1.0].mean())
        if (labels_np == 1.0).any() else 0.0
    )
    mean_wrong = (
        float(primary_scalars[labels_np == 0.0].mean())
        if (labels_np == 0.0).any() else 0.0
    )
    n_pos = int(labels_np.sum())
    n_neg = int(labels_np.size - n_pos)
    overall_correct_rate = n_pos / len(results) if results else 0.0

    # Mean per-position entropy at the LAST grid position — this is
    # the §13.10-comparable static-snapshot entropy value, useful for
    # checking that our per-position pipeline reproduces §13.10's
    # mean entropy (~1.5–2.5 nats range expected) at the final
    # position.
    mean_H_end = float(np.mean([
        r.entropy_series[-1] for r in results if r.entropy_series
    ])) if results else 0.0
    # Mean entropy at the FIRST grid position — useful for checking
    # the position_min=8 noise-floor assumption (early positions
    # should have low cross-sample diversity if "The"/"A" tokens
    # dominate, OR high diversity if NLI is being misled — either
    # way it's diagnostic).
    mean_H_start = float(np.mean([
        r.entropy_series[0] for r in results if r.entropy_series
    ])) if results else 0.0

    # --- Console report --- #
    print()
    print(f"{'metric':<48} {'value':>20}")
    print("-" * 71)
    print(f"{'N questions':<48} {len(results):>20}")
    print(f"{'Target model':<48} {args.model:>20}")
    print(f"{'NLI model':<48} {args.nli_model:>20}")
    print(f"{'K samples':<48} {args.k_samples:>20}")
    print(f"{'max_new_tokens':<48} {args.max_new_tokens:>20}")
    print(f"{'Position grid (min, stride, count)':<48} "
          f"({args.position_min}, {args.position_stride}, "
          f"{len(grid_positions)})".rjust(20))
    print(f"{'Correct (greedy matches)':<48} {n_pos:>20}")
    print(f"{'Wrong':<48} {n_neg:>20}")
    print(f"{'Greedy accuracy':<48} {overall_correct_rate:>20.3f}")
    print(f"{'Mean H at first grid position':<48} {mean_H_start:>20.4f}")
    print(f"{'Mean H at last grid position (≈§13.10)':<48} {mean_H_end:>20.4f}")
    print(f"{'Mean primary scalar (max|accel|, all)':<48} "
          f"{float(primary_scalars.mean()):>20.4f}")
    print(f"{'Mean primary scalar (correct)':<48} {mean_correct:>20.4f}")
    print(f"{'Mean primary scalar (wrong)':<48} {mean_wrong:>20.4f}")
    print(f"{'AUC — primary (max|accel|)':<48} {auc_primary:>20.3f}")
    print(f"{'AUC — diagnostic mean|accel|':<48} {auc_mean_abs:>20.3f}")
    print(f"{'AUC — diagnostic Σ accel²':<48} {auc_sum_squared:>20.3f}")
    print(f"{'vs §13.10 baseline (0.661)':<48} "
          f"{auc_primary - BASELINE_AUC:>+20.3f}")
    print(f"{'Classification (primary scalar)':<48} {classification:>20}")
    print()
    print(f"Recommendation: {recommendation}")

    # --- Markdown report --- #
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / (
        f"probe_bcvf_2diff_{args.benchmark}{args.suffix}.md"
    )
    deviation_note = (
        ""
        if grid_is_default
        else (
            f"  ⚠ §13.14 DEVIATION: non-default position grid "
            f"(pinned defaults: position_min=8, position_stride=4, "
            f"max_new_tokens=128)\n"
        )
    )
    lines = [
        "# §13.14 Experiment — BCVF-Faithful 2nd-Difference Observable\n",
        "Reference: BCVF autonomy-domain validation, "
        "`symbolu_robotics/bcvf_autonomous/DESIGN.md` §6.1 / §6.7 — "
        "`S3_map_error_accel` peak as the validated 2nd-derivative "
        "observable in the robotics domain. §13.14 is the LLM "
        "analogue: 2nd difference of per-position semantic entropy "
        "across the token sequence within a single generation.\n",
        "## Configuration\n",
        f"- **Target model:** `{args.model}`",
        f"- **NLI model (clustering + correctness label):** `{args.nli_model}`",
        f"- **Benchmark:** `{args.benchmark}`",
        (
            "- **Dataset:** `truthful_qa / multiple_choice / validation`"
            if args.benchmark == "truthfulqa_mc"
            else (
                "- **Dataset:** `pminervini/HaluEval / qa / data` "
                f"(include_context={args.include_context})"
            )
        ),
        f"- **N questions:** {len(results)}",
        f"- **Samples per question (K):** {args.k_samples}",
        f"- **Sampling temperature:** {args.temperature}",
        f"- **max_new_tokens:** {args.max_new_tokens}",
        f"- **Position grid:** position_min={args.position_min}, "
        f"position_stride={args.position_stride}, "
        f"count={len(grid_positions)}",
        deviation_note,
        f"- **Seed:** {args.seed}\n",
        "## Result (primary scalar)\n",
        "| Metric | Value |",
        "|---|---|",
        f"| N questions | {len(results)} |",
        f"| Greedy accuracy (correct / N) | {n_pos}/{len(results)} = "
        f"{overall_correct_rate:.3f} |",
        f"| Mean H at first grid position (t={args.position_min}) | "
        f"{mean_H_start:.4f} |",
        f"| Mean H at last grid position (t={args.max_new_tokens}, "
        f"≈ §13.10 single-snapshot) | {mean_H_end:.4f} |",
        f"| Mean primary scalar `max_i \\|accel_i\\|` (all) | "
        f"{float(primary_scalars.mean()):.4f} |",
        f"| Mean primary scalar (correct) | {mean_correct:.4f} |",
        f"| Mean primary scalar (wrong) | {mean_wrong:.4f} |",
        f"| **AUC — primary (max\\|accel\\|)** | **{auc_primary:.3f}** |",
        f"| Δ vs §13.10 baseline (0.661) | "
        f"**{auc_primary - BASELINE_AUC:+.3f}** |",
        f"| **Classification** | **`{classification}`** |\n",
        "## Diagnostic secondary scalars (NOT used for classification)\n",
        "These exist purely to support post-hoc interpretation. If "
        "the primary scalar lands at SATURATION but a secondary "
        "shows clear correct/wrong separation, that constitutes "
        "evidence the BCVF-shaped signal exists but the wrong "
        "aggregation was pinned — a fresh §0.8 re-commitment with "
        "a different primary scalar would be authorized. Changing "
        "the primary scalar without that re-commitment is a §0.8 "
        "violation.\n",
        "| Diagnostic scalar | AUC |",
        "|---|---|",
        f"| `mean_i \\|accel_i\\|` | {auc_mean_abs:.3f} |",
        f"| `Σ_i accel_i²` | {auc_sum_squared:.3f} |",
        "",
        "## §13.14 pre-committed bands\n",
        f"- `AUC ≥ {STRONG_THRESHOLD}` → **BCVF_2DIFF_STRONG** — "
        "gates §13.9 VC-brief revision when cleared on BOTH "
        "benchmarks; load-bearing evidence for BCVF-for-LLMs claim.",
        f"- `{INTERNAL_STRONG_THRESHOLD:.3f} ≤ AUC < "
        f"{STRONG_THRESHOLD:.3f}` → **BCVF_2DIFF_INTERNAL_STRONG** — "
        "strong for internal research; VC-brief still held.",
        f"- `{MARGINAL_LIFT_THRESHOLD:.3f} ≤ AUC < "
        f"{INTERNAL_STRONG_THRESHOLD:.3f}` → **BCVF_2DIFF_MARGINAL_LIFT** "
        "— modest but real lift above §13.10 + 0.02.",
        f"- `{SATURATION_LOWER:.3f} ≤ AUC ≤ "
        f"{MARGINAL_LIFT_THRESHOLD:.3f}` → **BCVF_2DIFF_SATURATION** "
        f"— within ±{SATURATION_DELTA} of §13.10's {BASELINE_AUC} "
        "baseline; substantive internal finding (narrows BCVF-for-"
        "LLMs scope).",
        f"- `AUC < {SATURATION_LOWER:.3f}` → **BCVF_2DIFF_ANTI_FINDING** "
        "— BCVF-for-LLMs as hallucination detector not supported by "
        "direct measurement on this codebase.\n",
        "## Recommendation\n",
        recommendation + "\n",
        "## Interpretation guidance\n",
        "This probe implements the LLM analogue of `S3_map_error_"
        "accel` from the robotics-domain BCVF validation: 2nd "
        "difference of per-position semantic entropy across the "
        "token sequence within a single generation. The token "
        "sequence is the LLM's analogue of \"robot moving through "
        "environment over time\". Per-position semantic entropy "
        "across K samples is the analogue of \"agent's evolving "
        "world model\". The 2nd difference is the analogue of \"is "
        "that evolution accelerating into divergence\" — directly "
        "mirroring the robotics-domain `S3_map_error_accel` peak "
        "that passed §6.1.\n",
        "Distinguishing feature vs §13.10 / §13.11 / §13.12 / "
        "§13.13: those probes are first-derivative-class single-"
        "snapshot measurements that score one scalar per question. "
        "§13.14 introduces the temporal-evolution structure BCVF "
        "actually uses, by reading token position within a single "
        "generation as the temporal axis. A positive result here is "
        "qualitatively different from a positive on §13.10–§13.13: "
        "it tests the BCVF formalism's transfer to LLMs, not just "
        "a literature method's benchmark performance.\n",
        "Critically: this script does NOT authorize any update to "
        "`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on its own. Per §13.9, "
        "the external framing revision requires "
        "`BCVF_2DIFF_STRONG` (or any §13 probe's STRONG band) on "
        "BOTH benchmarks. Furthermore, neither outcome of this "
        "probe retroactively affects the autonomy-domain BCVF "
        "result — §6.1's N=21 sign-test on `S3_map_error_accel` "
        "passed independently and stands.\n",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nMarkdown report: {md_path}")

    if args.dump_json:
        json_path = args.out_dir / (
            f"probe_bcvf_2diff_{args.benchmark}{args.suffix}.json"
        )
        with json_path.open("w", encoding="utf-8") as f:
            json.dump({
                "config": {
                    "model": args.model,
                    "nli_model": args.nli_model,
                    "benchmark": args.benchmark,
                    "include_context": bool(args.include_context),
                    "num_questions": args.num_questions,
                    "k_samples": args.k_samples,
                    "temperature": args.temperature,
                    "max_new_tokens": args.max_new_tokens,
                    "position_min": args.position_min,
                    "position_stride": args.position_stride,
                    "grid_is_default": grid_is_default,
                    "seed": args.seed,
                },
                "summary": {
                    "n": len(results),
                    "n_correct": n_pos,
                    "n_wrong": n_neg,
                    "greedy_accuracy": overall_correct_rate,
                    "mean_H_first_position": mean_H_start,
                    "mean_H_last_position": mean_H_end,
                    "mean_primary_scalar_all": float(primary_scalars.mean()),
                    "mean_primary_scalar_correct": mean_correct,
                    "mean_primary_scalar_wrong": mean_wrong,
                    "auc_primary": auc_primary,
                    "auc_diagnostic_mean_abs": auc_mean_abs,
                    "auc_diagnostic_sum_squared": auc_sum_squared,
                    "baseline_auc_s13_10": BASELINE_AUC,
                    "auc_delta_vs_baseline": auc_primary - BASELINE_AUC,
                    "classification": classification,
                },
                "questions": [
                    {
                        "q_idx": r.q_idx,
                        "question": r.question,
                        "prompt": r.prompt,
                        "correct_choice": r.correct_choice,
                        "distractors": r.distractors,
                        "greedy": r.greedy,
                        "samples": r.samples,
                        "sample_lengths": r.sample_lengths,
                        "grid_positions": r.grid_positions,
                        "entropy_series": r.entropy_series,
                        "accelerations": r.accelerations,
                        "primary_scalar": r.primary_scalar,
                        "mean_abs_accel": r.mean_abs_accel,
                        "sum_squared_accel": r.sum_squared_accel,
                        "peak_position_index": r.peak_position_index,
                        "greedy_matches_correct": r.greedy_matches_correct,
                    }
                    for r in results
                ],
            }, f, indent=2)
        print(f"Per-question JSON dump: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
