#!/usr/bin/env python
"""§13.18 experiment — Single-trajectory forced-allocation-gap probe.

Reference:
  Project_documentation/autonomous_robotics/symbolu_robotics/bcvf_autonomous/DESIGN.md §6.1 / §6.7 — autonomy-
  domain BCVF observable `S3_map_error_accel` peak that passed
  validation, motivating the 2nd-difference operator applied here.

  ChatGPT mechanism analysis (referenced in §13.17 / §13.18):
  hallucinations enter at the moment Softmax forces probability
  allocation despite low absolute logit magnitude. Cross-entropy
  training forbids expressing absolute ignorance; autoregression
  locks the forced guess into context for subsequent tokens.

Background:
  §13.10 (single-model SE), §13.11 (cross-family), §13.12
  (EigenScore single-snapshot), §13.14 (BCVF text-level 2nd-diff),
  §13.16 (BCVF hidden-state 2nd-diff) all measured BETWEEN-SAMPLE
  variance — decoding stochasticity introduced by the temperature
  parameter. None of these probes measured the actual hallucination
  signature, which (per the mechanism above) lives in single-
  trajectory logit geometry, not K-sample geometry.

  §13.17 narrowed the BCVF-for-LLMs transfer claim to:
  *BCVF's 2nd-difference operator does not produce a fault-onset-
  shaped signal at any K-sample-divergence-based observable tested
  in this codebase. Signal classes that do not depend on K-sample
  divergence are not foreclosed.*

  §13.18 tests the un-rejected signal class — single-trajectory
  forced-allocation-gap. The hypothesis is that a token where the
  model knows the answer produces high confidence-magnitude M_t
  and low entropy H_t (low forced-allocation gap g_t), while a
  token where the model is forced to guess produces low M_t and
  high H_t (high g_t). Forced moments should be sparse and local
  — exactly the smooth-with-rare-spikes shape BCVF's 2nd-difference
  operator exploits.

Method:
  1. Generate a SINGLE GREEDY completion per question (T=0,
     deterministic, K=1 effectively) at max_new_tokens=128 with
     output_scores=True so per-token logits are captured during
     the generation pass.
  2. At each grid position t in [position_min, T_actual] (stride 1,
     every token; position_min=4 to skip leading-token artifacts):
     - confidence magnitude M_t = max_j z_t[j] − mean_j z_t[j]
     - post-softmax entropy H_t = -Σ p_t log p_t
  3. Z-normalize both quantities across the trajectory:
         M̃_t = (M_t − mean) / std
         H̃_t = (H_t − mean) / std
     (per-question normalization, not global).
  4. Forced-allocation gap (α = 1.0 pinned):
         g_t = H̃_t − α · M̃_t
  5. Centered 2nd difference (interior positions only):
         accel_t = g_{t+1} − 2·g_t + g_{t-1}
  6. Primary scalar (pinned for AUC + bands):
         forced_alloc_2diff(q) = max_t |accel_t|
  7. Diagnostic secondary scalars (REPORTED but NOT in band
     classification, pinned in dataclass to make post-hoc swap a
     visible §0.8 violation):
       - mean_t |accel_t|
       - sum_t accel_t²
       - peak position t*
       - Variant-A entropy-only diagnostic: max_t |a^H_t| where
         a^H_t = H_{t+1} − 2·H_t + H_{t-1} (no z-norm, no M_t term)
  8. Correctness label: Qwen greedy passes question-conditioned
     NLI against correct AND fails NLI against every distractor
     (identical to §13.10–§13.16 for direct AUC comparability).
  9. AUC computed on -forced_alloc_2diff (higher acceleration →
     forced-guess moment → more likely wrong).

Pre-committed success bands (§13.18, pinned in design doc BEFORE
implementation; same numerical partition as §13.11–§13.16 since the
§13.10 baseline of 0.661 is unchanged):

  - AUC >= 0.75 on both benchmarks -> FORCED_ALLOC_2DIFF_STRONG.
    Gates §13.9 VC + first load-bearing positive evidence for
    BCVF-for-LLMs at any single-axis construction in this codebase.
  - 0.70 <= AUC < 0.75 on both -> FORCED_ALLOC_2DIFF_INTERNAL_STRONG.
    Strong for internal research; VC-brief still held.
  - 0.681 <= AUC < 0.70 on both -> FORCED_ALLOC_2DIFF_MARGINAL_LIFT.
    Modest but real lift above §13.10 + 0.02.
  - 0.641 <= AUC <= 0.681 on both -> FORCED_ALLOC_2DIFF_SATURATION.
    Within ±0.02 of §13.10. Combined with §13.11/§13.12/§13.14/
    §13.16 anti-findings, this is 5-of-5 single-axis null.
  - AUC < 0.641 on any benchmark -> FORCED_ALLOC_2DIFF_ANTI_FINDING.
    5-of-5 anti across literature-backed paths; pause LLM track.

Relationship to §13.10–§13.16:
  Different hypothesis class (single-trajectory) than the four
  K-sample-divergence-based probes in §13.10–§13.16. Does NOT
  violate the §13.17 single-axis program closure (which was
  specifically scoped to K-sample-divergence-based observables).
  Same target model, benchmarks, max_new_tokens=128, and
  correctness labeling as §13.14 / §13.16 for direct AUC
  comparability across the §13 ladder.

Do NOT update AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md on the basis of
any result from this probe except FORCED_ALLOC_2DIFF_STRONG on
BOTH benchmarks (per §13.9). Anything less is internal research
confidence only.

Usage:
    HF_HUB_DISABLE_XET=1 python scripts/probe_forced_alloc_2diff.py \\
        --num-questions 100 \\
        --benchmark truthfulqa_mc \\
        --dump-json

Runtime ~2–4 min at N=100 on a 24+ GB GPU — the cheapest §13 probe
to date (no per-position NLI clustering, no per-position EigenScore
extraction; just per-token scalar arithmetic on captured logits).
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
    greedy: str
    # Number of generated non-pad tokens in the greedy trajectory.
    n_generated_tokens: int
    # Position grid (in 1-indexed generated-token positions). Equal
    # length to the per-position scalar arrays below.
    grid_positions: List[int]
    # Per-position raw scalars (pre-normalization), captured for
    # post-hoc audit.
    confidence_magnitude_series: List[float]   # M_t
    entropy_series: List[float]                # H_t
    # Per-position normalized scalars and the forced-allocation gap.
    confidence_magnitude_z_series: List[float]  # M̃_t
    entropy_z_series: List[float]               # H̃_t
    gap_series: List[float]                     # g_t
    # Per-position centered 2nd differences accel_t = g_{t+1} −
    # 2·g_t + g_{t-1} for t in [1, len(gap_series) - 2].
    accelerations: List[float]
    # Primary scalar pinned for AUC + bands.
    primary_scalar: float                       # max_t |accel_t|
    # Pinned diagnostic secondary scalars — surfaced in JSON for
    # post-hoc audit but NOT used for band classification. Pinning
    # in dataclass means changing the primary post-hoc requires a
    # code edit (visible §0.8 violation).
    mean_abs_accel: float
    sum_squared_accel: float
    peak_position_index: int
    # Variant-A entropy-only diagnostic (no z-normalization, no M_t
    # term). Tests whether the M_t component contributes any signal
    # beyond raw entropy alone.
    entropy_2diff_max_abs: float
    greedy_matches_correct: bool
    label: int  # 1 = correct, 0 = wrong


# §13.18 pre-committed band boundaries. Identical numerical partition
# to §13.11/§13.12/§13.13/§13.14/§13.16 because the §13.10 baseline
# of 0.661 is unchanged. Relabeled FORCED_ALLOC_2DIFF_* so the per-
# revision lineage stays legible in console output, JSON dumps, and
# grep.
BASELINE_AUC = 0.661
SATURATION_DELTA = 0.02
STRONG_THRESHOLD = 0.75
INTERNAL_STRONG_THRESHOLD = 0.70
MARGINAL_LIFT_THRESHOLD = BASELINE_AUC + SATURATION_DELTA   # 0.681
SATURATION_LOWER = BASELINE_AUC - SATURATION_DELTA          # 0.641


def classify(auc: float) -> Tuple[str, str]:
    """Map an AUC to a §13.18 band label and per-run recommendation."""
    if auc >= STRONG_THRESHOLD:
        return "FORCED_ALLOC_2DIFF_STRONG", (
            "Strong pass. Gates the §13.9 VC-brief revision — but "
            "only if the OTHER benchmark also clears 0.75. ALSO "
            "constitutes the first load-bearing positive evidence "
            "for BCVF-for-LLMs at any single-axis construction in "
            "this codebase. §13.18 was designed to satisfy the five "
            "structural requirements §13.14/§13.16 violated; a "
            "STRONG result here confirms the mechanism analysis "
            "(forced-allocation gap as the LLM-domain analogue of "
            "S3_map_error_accel) was correct."
        )
    if auc >= INTERNAL_STRONG_THRESHOLD:
        return "FORCED_ALLOC_2DIFF_INTERNAL_STRONG", (
            "Strong for internal research. The forced-allocation-gap "
            "2nd-difference observable produces signal but doesn't "
            "clear §13.9. Diagnostic follow-ups: (a) alpha sweep "
            "(--alpha), (b) Variant C logit-lens curvature, (c) "
            "longer trajectories (--max-new-tokens 256), (d) per-"
            "question-vs-global z-normalization comparison."
        )
    if auc >= MARGINAL_LIFT_THRESHOLD:
        return "FORCED_ALLOC_2DIFF_MARGINAL_LIFT", (
            "Real but modest lift above §13.10 + 0.02. Document; "
            "do NOT authorize further single-axis probe progression."
        )
    if auc >= SATURATION_LOWER:
        return "FORCED_ALLOC_2DIFF_SATURATION", (
            "Within ±0.02 of §13.10's 0.661 baseline. Combined with "
            "§13.11/§13.12/§13.14/§13.16 anti-findings, this is the "
            "5-of-5 single-axis null. The forced-allocation-gap "
            "construction adds nothing measurable beyond the §13.10 "
            "ceiling. Single-axis methods are conclusively saturated "
            "on this codebase's Qwen-7B + base-NLI configuration. "
            "Further lift requires either system-level integration "
            "(§14 outlined in §13.8) or model-scale upgrade."
        )
    return "FORCED_ALLOC_2DIFF_ANTI_FINDING", (
        "AUC below §13.10 − 0.02. The forced-allocation-gap signal "
        "underperforms the static §13.10 baseline. 5-of-5 anti "
        "across literature-backed paths "
        "(§13.11/§13.12/§13.14/§13.16/§13.18). Pause LLM track at "
        "the single-axis level. The autonomy-domain BCVF claim "
        "stands independently on §6.1 evidence and is unaffected. "
        "Check for implementation bugs (logit capture indexing, "
        "z-normalization sign, accel sign convention) before "
        "treating as a genuine anti-finding."
    )


def build_nli_checker(nli_model, nli_tokenizer, device: str, batch_size: int = 32):
    """Return a function (premises, hypotheses) -> List[bool] for batched
    entailment checks. Identical to §13.10/§13.11/§13.12/§13.14/§13.16
    — used here ONLY for the correctness label, ~3 calls per question
    against (correct + distractors). Not used for clustering."""
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


def label_correctness(
    greedy_gen: str, correct_choice: str, distractors: List[str],
    check_batch, question: str,
) -> bool:
    """Question-conditioned correctness label. Identical protocol to
    §13.10/§13.11/§13.12/§13.14/§13.16. Holding this fixed across
    the §13 ladder is what makes the AUC numbers directly
    comparable across all six probes."""
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


def generate_greedy_with_logits(
    model, tokenizer, prompt: str, max_new_tokens: int, device: str,
):
    """Generate a single greedy completion (T=0, deterministic) and
    return the full per-token logit trajectory.

    Returns ``(decoded_text, generated_token_ids, logit_trajectory,
    n_generated_non_pad)`` where:
      - decoded_text : str. Greedy generation with prompt prefix
        stripped.
      - generated_token_ids : np.ndarray of shape (T_new,) int64.
      - logit_trajectory : np.ndarray of shape (T_new, V) float32.
        Per-token raw logits before softmax. Captured via
        out.scores from the generate() call (these ARE pre-softmax
        scores when do_sample=False; transformers populates them
        as the post-warper logits which equal pre-softmax for
        greedy decoding without temperature/top-k/top-p warpers).
      - n_generated_non_pad : int. Number of tokens before EOS/pad.

    Implementation note: greedy decoding uses do_sample=False, no
    temperature. transformers's `out.scores` returns one tensor
    per generation step, each of shape (batch=1, vocab_size). For
    greedy, these are the raw logits used to argmax the next token.
    """
    import torch

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
            do_sample=False,
            max_new_tokens=max_new_tokens,
            pad_token_id=pad_id,
            output_scores=True,
            return_dict_in_generate=True,
        )

    sequences = out.sequences            # (1, prompt_len + T_new)
    gen_segment = sequences[0, prompt_len:]   # (T_new,)
    n_generated_non_pad = int((gen_segment != pad_id).sum().item())

    # out.scores is a tuple of length T_new. Each entry has shape
    # (1, V) — the score distribution that produced that step's
    # token. Stack into (T_new, V).
    score_stack = torch.stack([s[0] for s in out.scores], dim=0)
    logit_trajectory = score_stack.detach().to(torch.float32).cpu().numpy()
    generated_token_ids = gen_segment.detach().cpu().numpy().astype(np.int64)
    decoded_text = tokenizer.decode(
        gen_segment, skip_special_tokens=True,
    ).strip()

    return (
        decoded_text, generated_token_ids, logit_trajectory,
        n_generated_non_pad,
    )


def compute_per_token_quantities(
    logit_trajectory: np.ndarray, n_non_pad: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute per-position confidence magnitude M_t and post-softmax
    entropy H_t for the first n_non_pad positions of the trajectory.

    ``logit_trajectory`` has shape (T_new, V). Only the first
    ``n_non_pad`` rows are used (post-EOS/pad rows have undefined
    semantics for the forced-allocation construction).

    Returns ``(M, H)`` each of shape (n_non_pad,).
        M_t = max_j z_t[j] − mean_j z_t[j]
        H_t = -Σ_j p_t[j] log p_t[j]  where p_t = softmax(z_t)

    Numerical notes: softmax is computed via the standard
    log-sum-exp trick (subtract max logit before exponentiating)
    to avoid overflow for high-magnitude logits.
    """
    if n_non_pad <= 0:
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64)

    Z = logit_trajectory[:n_non_pad].astype(np.float64)  # (T, V)
    # Confidence magnitude: max minus mean per row.
    z_max = Z.max(axis=1)                  # (T,)
    z_mean = Z.mean(axis=1)                # (T,)
    M = z_max - z_mean                     # (T,)

    # Stable softmax + entropy.
    Z_shifted = Z - z_max[:, None]         # (T, V); max row is 0
    exp_Z = np.exp(Z_shifted)              # (T, V)
    sum_exp = exp_Z.sum(axis=1)            # (T,)
    log_sum_exp = np.log(sum_exp) + z_max  # (T,)  — log Z (partition fn)
    # H = log Z − E_p[z]. Equivalent and stable.
    # E_p[z] = Σ p_t[j] z_t[j] = (1/sum_exp) · Σ exp(z − z_max) · z
    # Compute directly as Σ p log p with stabilized p.
    p = exp_Z / sum_exp[:, None]            # (T, V)
    # Avoid log(0) at very confident positions: clamp p before log.
    # Any p < 1e-30 contributes ~0 to the entropy sum anyway.
    p_safe = np.clip(p, 1e-30, 1.0)
    H = -np.sum(p * np.log(p_safe), axis=1)  # (T,)
    return M, H


def z_normalize(x: np.ndarray) -> np.ndarray:
    """Per-trajectory z-normalization. Returns zeros if std < 1e-12
    (degenerate constant series — happens for max_new_tokens=1 or
    pathological short generations). The fallback prevents division
    by zero without injecting NaN into downstream math; constant
    series have no meaningful 2nd derivative anyway."""
    if x.size == 0:
        return x.copy()
    mu = float(x.mean())
    sigma = float(x.std())
    if sigma < 1e-12:
        return np.zeros_like(x)
    return (x - mu) / sigma


def compute_2nd_difference_scalars(
    series: np.ndarray,
) -> Tuple[List[float], float, float, float, int]:
    """Centered 2nd differences of a 1-D series and the four §13.18
    scalars.

    Returns ``(accelerations, primary, mean_abs, sum_squared,
    peak_idx)``:
      - accelerations : list of accel_i = s_{i+1} − 2·s_i + s_{i−1}
        for interior i. Length = len(series) - 2.
      - primary : max_i |accel_i|. Pinned per §13.18 as the band-
        classification scalar.
      - mean_abs : mean_i |accel_i|. Diagnostic only.
      - sum_squared : Σ_i accel_i². Diagnostic only.
      - peak_idx : index of the peak (within the accelerations
        array, NOT within the original series).

    Same structure as §13.14 / §13.16's compute_2nd_difference_scalars;
    only the input series differs.
    """
    n = len(series)
    if n < 3:
        return [], 0.0, 0.0, 0.0, -1
    accelerations: List[float] = []
    for i in range(1, n - 1):
        accel = float(series[i + 1] - 2.0 * series[i] + series[i - 1])
        accelerations.append(accel)
    abs_accels = [abs(a) for a in accelerations]
    primary = max(abs_accels)
    mean_abs = float(np.mean(abs_accels))
    sum_squared = float(np.sum(np.array(accelerations) ** 2))
    peak_idx = int(np.argmax(abs_accels))
    return accelerations, primary, mean_abs, sum_squared, peak_idx


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Binary AUC via tie-aware rank sum. Identical to §13.10–§13.16."""
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
        help="Identical benchmark semantics to §13.10–§13.16 — only "
             "the per-question scalar differs (max_t |accel(g_t)| "
             "over the forced-allocation gap series instead of K-"
             "sample variance or per-position EigenScore).",
    )
    parser.add_argument(
        "--include-context", action="store_true",
        help="halueval_qa only: prepend the 'knowledge' passage. "
             "Default False to mirror §13.10–§13.16 closed-book.",
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
        help="Target model. §13.18 pre-commitment pins this to "
             "Qwen2.5-7B-Instruct for direct §13.10–§13.16 "
             "comparability; changing it is a §0.8 deviation.",
    )
    parser.add_argument(
        "--nli-model",
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        help="MNLI classifier for the correctness label only. "
             "Same default as §13.10–§13.16. NLI is NOT used for "
             "any per-position computation in this script.",
    )
    parser.add_argument(
        "--alpha", type=float, default=1.0,
        help="Forced-allocation gap weighting: g_t = H̃_t − α·M̃_t. "
             "§13.18 pins 1.0 (equal weighting after z-norm). "
             "Non-default flagged as §13.18 deviation in report.",
    )
    parser.add_argument(
        "--position-min", type=int, default=4,
        help="Minimum grid position (1-indexed generated-token "
             "count). §13.18 pins 4 to skip leading-token prompt-"
             "conditioning artifacts. Lower than §13.14/§13.16's 8 "
             "because there is no NLI-on-truncations noise concern "
             "at single-trajectory logit level. Non-default flagged "
             "as §13.18 deviation.",
    )
    parser.add_argument(
        "--position-stride", type=int, default=1,
        help="Grid stride. §13.18 pins 1 (every token; finest "
             "resolution for catching sparse forced-allocation "
             "moments). Single-trajectory observables don't have "
             "the per-position computational cost K-sample probes "
             "did, so finer stride is affordable. Non-default "
             "flagged as §13.18 deviation.",
    )
    parser.add_argument(
        "--max-new-tokens", type=int, default=128,
        help="§13.18 pins 128 (matches §13.14/§13.16). Greedy "
             "trajectory length cap.",
    )
    parser.add_argument("--seed", type=int, default=1,
                        help="Greedy is deterministic so seed is "
                             "primarily for tie-breaking in upstream "
                             "code; preserved for parity.")
    parser.add_argument(
        "--out-dir", type=pathlib.Path,
        default=_REPO_ROOT / "docs" / "experiments",
    )
    parser.add_argument("--suffix", type=str, default="")
    parser.add_argument(
        "--dump-json", action="store_true",
        help="Also write a per-question JSON dump including the "
             "full per-position M_t, H_t, g_t series and the "
             "accelerations. Required for post-hoc audit if the "
             "primary scalar saturates.",
    )
    args = parser.parse_args()

    if args.position_min < 1:
        parser.error(
            f"--position-min must be >= 1; got {args.position_min}."
        )
    if args.position_stride < 1:
        parser.error(
            f"--position-stride must be >= 1; got "
            f"{args.position_stride}."
        )
    if args.position_min > args.max_new_tokens:
        parser.error(
            f"--position-min ({args.position_min}) cannot exceed "
            f"--max-new-tokens ({args.max_new_tokens})."
        )

    grid_is_default = (
        args.position_min == 4
        and args.position_stride == 1
        and args.max_new_tokens == 128
        and args.alpha == 1.0
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
    vocab_size = int(model.config.vocab_size)
    print(
        f"  vocab_size={vocab_size}, alpha={args.alpha}"
        + ("" if grid_is_default
           else "  [§13.18 DEVIATION: non-default grid/alpha]"),
        flush=True,
    )

    print(f"Loading NLI model: {args.nli_model}", flush=True)
    nli_tokenizer = AutoTokenizer.from_pretrained(args.nli_model)
    nli_dtype = torch.float16 if device == "cuda" else torch.float32
    nli_model = AutoModelForSequenceClassification.from_pretrained(
        args.nli_model, torch_dtype=nli_dtype,
    ).to(device)
    nli_model.eval()
    check_batch = build_nli_checker(nli_model, nli_tokenizer, device)

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

        # Single greedy generation with full per-token logit capture.
        # No K-sample sampling — §13.18 hypothesis is single-
        # trajectory by design.
        (
            greedy_text, generated_token_ids, logit_trajectory,
            n_non_pad,
        ) = generate_greedy_with_logits(
            model, tokenizer, prompt,
            max_new_tokens=args.max_new_tokens, device=device,
        )

        # Per-token confidence magnitude M_t and entropy H_t for
        # the non-pad portion of the trajectory.
        M_full, H_full = compute_per_token_quantities(
            logit_trajectory, n_non_pad,
        )

        # Apply position grid: index from position_min (1-indexed)
        # to n_non_pad inclusive, with the configured stride. Use
        # 0-indexed internally (subtract 1 from grid positions when
        # slicing into M_full / H_full).
        grid_positions: List[int] = []
        for p in range(args.position_min, n_non_pad + 1, args.position_stride):
            grid_positions.append(p)
        if len(grid_positions) < 3:
            # Trajectory too short for any centered 2nd difference.
            # Record the result with empty scalars; will not contribute
            # signal but won't crash the run.
            results.append(QuestionResult(
                q_idx=q_idx, question=q_text, prompt=prompt,
                correct_choice=correct_choice, distractors=distractors,
                greedy=greedy_text,
                n_generated_tokens=n_non_pad,
                grid_positions=grid_positions,
                confidence_magnitude_series=[],
                entropy_series=[],
                confidence_magnitude_z_series=[],
                entropy_z_series=[],
                gap_series=[],
                accelerations=[],
                primary_scalar=0.0,
                mean_abs_accel=0.0, sum_squared_accel=0.0,
                peak_position_index=-1,
                entropy_2diff_max_abs=0.0,
                greedy_matches_correct=False,
                label=0,
            ))
            # Still need a label for this question. Compute it.
            is_correct = label_correctness(
                greedy_text, correct_choice, distractors,
                check_batch, q_text,
            )
            results[-1].greedy_matches_correct = is_correct
            results[-1].label = 1 if is_correct else 0
            continue

        # Slice M and H to the grid positions (1-indexed → 0-indexed).
        grid_idx = np.array(
            [p - 1 for p in grid_positions], dtype=np.int64,
        )
        M_grid = M_full[grid_idx]
        H_grid = H_full[grid_idx]

        # Per-trajectory z-normalization.
        M_z = z_normalize(M_grid)
        H_z = z_normalize(H_grid)

        # Forced-allocation gap (pinned α weighting).
        gap = H_z - args.alpha * M_z

        # Centered 2nd difference + four scalars on g_t.
        accelerations, primary, mean_abs, sum_squared, peak_idx = (
            compute_2nd_difference_scalars(gap)
        )

        # Variant-A entropy-only diagnostic: 2nd difference of H_t
        # directly (no z-normalization, no M_t term). Tests whether
        # the M_t component contributes anything beyond raw entropy.
        _, entropy_primary, _, _, _ = compute_2nd_difference_scalars(
            H_grid,
        )

        # Correctness label.
        is_correct = label_correctness(
            greedy_text, correct_choice, distractors,
            check_batch, q_text,
        )

        results.append(QuestionResult(
            q_idx=q_idx, question=q_text, prompt=prompt,
            correct_choice=correct_choice, distractors=distractors,
            greedy=greedy_text,
            n_generated_tokens=n_non_pad,
            grid_positions=grid_positions,
            confidence_magnitude_series=M_grid.tolist(),
            entropy_series=H_grid.tolist(),
            confidence_magnitude_z_series=M_z.tolist(),
            entropy_z_series=H_z.tolist(),
            gap_series=gap.tolist(),
            accelerations=accelerations,
            primary_scalar=primary,
            mean_abs_accel=mean_abs,
            sum_squared_accel=sum_squared,
            peak_position_index=peak_idx,
            entropy_2diff_max_abs=entropy_primary,
            greedy_matches_correct=is_correct,
            label=1 if is_correct else 0,
        ))

        if (q_idx + 1) % 5 == 0 or q_idx + 1 == len(ds):
            elapsed = time.perf_counter() - t_start
            eta = elapsed / (q_idx + 1) * (len(ds) - q_idx - 1)
            n_correct = sum(r.label for r in results)
            mean_primary = float(np.mean(
                [r.primary_scalar for r in results]
            ))
            mean_n_tok = float(np.mean(
                [r.n_generated_tokens for r in results]
            ))
            print(
                f"  [{q_idx + 1}/{len(ds)}] elapsed={elapsed:.0f}s "
                f"eta={eta:.0f}s correct={n_correct}/{len(results)} "
                f"mean_primary={mean_primary:.4f} "
                f"mean_n_tok={mean_n_tok:.1f}",
                flush=True,
            )

    # --- AUC on the pinned PRIMARY scalar --- #
    primary_scalars = np.array(
        [r.primary_scalar for r in results], dtype=np.float64,
    )
    labels_np = np.array([r.label for r in results], dtype=np.float64)
    auc_primary = roc_auc(-primary_scalars, labels_np.astype(bool))
    classification, recommendation = classify(auc_primary)

    # --- Diagnostic AUCs (reported but NOT used for band class.) --- #
    mean_abs_scalars = np.array(
        [r.mean_abs_accel for r in results], dtype=np.float64,
    )
    sum_sq_scalars = np.array(
        [r.sum_squared_accel for r in results], dtype=np.float64,
    )
    entropy_only_scalars = np.array(
        [r.entropy_2diff_max_abs for r in results], dtype=np.float64,
    )
    auc_mean_abs = roc_auc(-mean_abs_scalars, labels_np.astype(bool))
    auc_sum_sq = roc_auc(-sum_sq_scalars, labels_np.astype(bool))
    auc_entropy_only = roc_auc(
        -entropy_only_scalars, labels_np.astype(bool),
    )

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

    # Trajectory length statistics (single-trajectory probes are
    # sensitive to short generations because the position grid
    # then has fewer measurements).
    n_tokens_arr = np.array(
        [r.n_generated_tokens for r in results], dtype=np.int64,
    )
    mean_n_tokens = float(n_tokens_arr.mean()) if len(n_tokens_arr) else 0.0
    median_n_tokens = (
        float(np.median(n_tokens_arr)) if len(n_tokens_arr) else 0.0
    )
    n_short_trajectories = int(
        (n_tokens_arr < args.position_min + 2).sum()
    )

    # --- Console report --- #
    print()
    print(f"{'metric':<48} {'value':>20}")
    print("-" * 71)
    print(f"{'N questions':<48} {len(results):>20}")
    print(f"{'Target model':<48} {args.model:>20}")
    print(f"{'NLI model (label only)':<48} {args.nli_model:>20}")
    print(f"{'vocab_size':<48} {vocab_size:>20}")
    print(f"{'Alpha (forced-allocation gap weight)':<48} "
          f"{args.alpha:>20.3f}")
    print(f"{'Position grid (min, stride)':<48} "
          f"({args.position_min}, {args.position_stride})".rjust(20))
    print(f"{'max_new_tokens':<48} {args.max_new_tokens:>20}")
    print(f"{'Mean greedy length (non-pad tokens)':<48} "
          f"{mean_n_tokens:>20.1f}")
    print(f"{'Median greedy length':<48} {median_n_tokens:>20.1f}")
    print(f"{'Trajectories too short for 2nd diff':<48} "
          f"{n_short_trajectories:>20}")
    print(f"{'Correct (greedy matches)':<48} {n_pos:>20}")
    print(f"{'Wrong':<48} {n_neg:>20}")
    print(f"{'Greedy accuracy':<48} {overall_correct_rate:>20.3f}")
    print(f"{'Mean primary scalar (max|accel(g)|, all)':<48} "
          f"{float(primary_scalars.mean()):>20.4f}")
    print(f"{'Mean primary scalar (correct)':<48} "
          f"{mean_correct:>20.4f}")
    print(f"{'Mean primary scalar (wrong)':<48} "
          f"{mean_wrong:>20.4f}")
    print(f"{'AUC — primary (max|accel(g)|)':<48} "
          f"{auc_primary:>20.3f}")
    print(f"{'AUC — diagnostic mean|accel(g)|':<48} "
          f"{auc_mean_abs:>20.3f}")
    print(f"{'AUC — diagnostic Σ accel(g)²':<48} "
          f"{auc_sum_sq:>20.3f}")
    print(f"{'AUC — Variant A entropy-only max|accel(H)|':<48} "
          f"{auc_entropy_only:>20.3f}")
    print(f"{'vs §13.10 baseline (0.661)':<48} "
          f"{auc_primary - BASELINE_AUC:>+20.3f}")
    print(f"{'Classification (primary scalar)':<48} "
          f"{classification:>20}")
    print()
    print(f"Recommendation: {recommendation}")

    # --- Markdown report --- #
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / (
        f"probe_forced_alloc_2diff_{args.benchmark}{args.suffix}.md"
    )
    deviation_block = (
        ""
        if grid_is_default
        else (
            f"  ⚠ §13.18 DEVIATION: non-default grid/alpha "
            f"(pinned defaults: position_min=4, position_stride=1, "
            f"max_new_tokens=128, alpha=1.0)\n"
        )
    )
    lines = [
        "# §13.18 Experiment — Single-Trajectory Forced-Allocation-Gap Probe\n",
        "References: ChatGPT mechanism analysis (Softmax flattens "
        "absolute logit magnitude → forced allocation despite low "
        "support → autoregressive amplification). "
        "`Project_documentation/autonomous_robotics/symbolu_robotics/bcvf_autonomous/DESIGN.md` §6.1 / §6.7 — "
        "autonomy-domain `S3_map_error_accel` peak motivating the "
        "2nd-difference operator. §13.17 — narrowing of the BCVF "
        "transfer claim that this probe tests at the un-rejected "
        "single-trajectory observable class.\n",
        "## Configuration\n",
        f"- **Target model:** `{args.model}`",
        f"- **NLI model (correctness label only):** `{args.nli_model}`",
        f"- **vocab_size (V):** {vocab_size}",
        f"- **Alpha (forced-allocation gap weight):** {args.alpha:.3f}",
        f"- **Position grid:** position_min={args.position_min}, "
        f"position_stride={args.position_stride}, "
        f"max_new_tokens={args.max_new_tokens}",
        deviation_block.rstrip() if deviation_block else "",
        f"- **Generation:** single greedy completion per question "
        f"(K=1, T=0, deterministic)",
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
        f"- **Seed:** {args.seed}\n",
        "## Result (primary scalar)\n",
        "| Metric | Value |",
        "|---|---|",
        f"| N questions | {len(results)} |",
        f"| Greedy accuracy (correct / N) | {n_pos}/{len(results)} = "
        f"{overall_correct_rate:.3f} |",
        f"| Mean greedy length (non-pad tokens) | "
        f"{mean_n_tokens:.1f} |",
        f"| Median greedy length | {median_n_tokens:.1f} |",
        f"| Trajectories too short for any 2nd diff | "
        f"{n_short_trajectories} |",
        f"| Mean primary scalar `max_t \\|accel(g_t)\\|` (all) | "
        f"{float(primary_scalars.mean()):.4f} |",
        f"| Mean primary scalar (correct) | {mean_correct:.4f} |",
        f"| Mean primary scalar (wrong) | {mean_wrong:.4f} |",
        f"| **AUC — primary (max\\|accel(g)\\|)** | **{auc_primary:.3f}** |",
        f"| Δ vs §13.10 baseline (0.661) | "
        f"**{auc_primary - BASELINE_AUC:+.3f}** |",
        f"| **Classification** | **`{classification}`** |\n",
        "## Diagnostic secondary scalars (NOT used for classification)\n",
        "Pinned in §13.18 to support post-hoc audit. If primary "
        "saturates but a secondary shows clear correct/wrong "
        "separation, that constitutes evidence for either: (a) the "
        "wrong aggregation was pinned (max vs mean vs energy), or "
        "(b) the M_t component is helping or hurting beyond raw "
        "entropy. Either case authorizes a fresh §0.8 re-commitment "
        "with a different primary; changing it without re-commitment "
        "is a §0.8 violation.\n",
        "| Diagnostic scalar | AUC |",
        "|---|---|",
        f"| `mean_t \\|accel(g_t)\\|` | {auc_mean_abs:.3f} |",
        f"| `Σ_t accel(g_t)²` | {auc_sum_sq:.3f} |",
        f"| **Variant A** — `max_t \\|accel(H_t)\\|` (entropy only, "
        f"no z-norm, no M term) | **{auc_entropy_only:.3f}** |",
        "",
        "## §13.18 pre-committed bands\n",
        f"- `AUC ≥ {STRONG_THRESHOLD}` → **FORCED_ALLOC_2DIFF_STRONG** "
        "— gates §13.9 VC + first load-bearing positive evidence "
        "for BCVF-for-LLMs at any single-axis construction.",
        f"- `{INTERNAL_STRONG_THRESHOLD:.3f} ≤ AUC < "
        f"{STRONG_THRESHOLD:.3f}` → "
        "**FORCED_ALLOC_2DIFF_INTERNAL_STRONG** — strong for internal "
        "research; VC held.",
        f"- `{MARGINAL_LIFT_THRESHOLD:.3f} ≤ AUC < "
        f"{INTERNAL_STRONG_THRESHOLD:.3f}` → "
        "**FORCED_ALLOC_2DIFF_MARGINAL_LIFT** — modest lift above "
        "§13.10 + 0.02.",
        f"- `{SATURATION_LOWER:.3f} ≤ AUC ≤ "
        f"{MARGINAL_LIFT_THRESHOLD:.3f}` → "
        "**FORCED_ALLOC_2DIFF_SATURATION** — within ±"
        f"{SATURATION_DELTA} of §13.10 baseline; 5-of-5 single-axis "
        "null when combined with §13.11/§13.12/§13.14/§13.16.",
        f"- `AUC < {SATURATION_LOWER:.3f}` → "
        "**FORCED_ALLOC_2DIFF_ANTI_FINDING** — 5-of-5 anti across "
        "literature-backed paths; pause LLM track.\n",
        "## Recommendation\n",
        recommendation + "\n",
        "## Interpretation guidance\n",
        "This probe tests the un-rejected signal class identified in "
        "§13.17's narrowing: BCVF 2nd-difference operator applied "
        "across token positions WITHIN a single greedy trajectory, "
        "on the forced-allocation gap "
        "$g_t = \\tilde{H}_t - \\alpha \\cdot \\tilde{M}_t$. The "
        "construction was designed to satisfy the five structural "
        "requirements §13.14/§13.16 violated: continuous real-"
        "valued, direct from model internals (raw logits), plausibly "
        "smooth-with-rare-spikes (forced-allocation moments are "
        "sparse and local by mechanism), independent of K-sample "
        "divergence, and captures the autoregressive-hallucination "
        "mechanism (Softmax-forces-allocation-despite-low-magnitude).\n",
        "Distinguishing feature vs §13.10–§13.16: those probes "
        "measured between-sample variance (decoding stochasticity); "
        "§13.18 measures within-trajectory logit geometry. A "
        "positive result here would validate the mechanism analysis; "
        "a saturation/anti would tighten the §13.17 narrowing to "
        "exclude single-trajectory forced-allocation-gap observables "
        "as well, leaving system-level integration (§14 outlined in "
        "§13.8) and model-scale upgrade as the only remaining "
        "literature-backed paths.\n",
        "Critically: this script does NOT authorize any update to "
        "`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on its own. Per §13.9, "
        "the external framing revision requires "
        "`FORCED_ALLOC_2DIFF_STRONG` (or any §13 probe's STRONG band) "
        "on BOTH benchmarks — not yet observed across §13.10–§13.16. "
        "Furthermore, neither outcome retroactively affects the "
        "autonomy-domain BCVF result — §6.1 stands independently.\n",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nMarkdown report: {md_path}")

    if args.dump_json:
        json_path = args.out_dir / (
            f"probe_forced_alloc_2diff_{args.benchmark}{args.suffix}.json"
        )
        with json_path.open("w", encoding="utf-8") as f:
            json.dump({
                "config": {
                    "model": args.model,
                    "nli_model": args.nli_model,
                    "vocab_size": vocab_size,
                    "alpha": args.alpha,
                    "benchmark": args.benchmark,
                    "include_context": bool(args.include_context),
                    "num_questions": args.num_questions,
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
                    "mean_n_generated_tokens": mean_n_tokens,
                    "median_n_generated_tokens": median_n_tokens,
                    "n_short_trajectories": n_short_trajectories,
                    "mean_primary_scalar_all": float(
                        primary_scalars.mean()
                    ),
                    "mean_primary_scalar_correct": mean_correct,
                    "mean_primary_scalar_wrong": mean_wrong,
                    "auc_primary": auc_primary,
                    "auc_diagnostic_mean_abs": auc_mean_abs,
                    "auc_diagnostic_sum_squared": auc_sum_sq,
                    "auc_variant_a_entropy_only": auc_entropy_only,
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
                        "n_generated_tokens": r.n_generated_tokens,
                        "grid_positions": r.grid_positions,
                        "confidence_magnitude_series":
                            r.confidence_magnitude_series,
                        "entropy_series": r.entropy_series,
                        "confidence_magnitude_z_series":
                            r.confidence_magnitude_z_series,
                        "entropy_z_series": r.entropy_z_series,
                        "gap_series": r.gap_series,
                        "accelerations": r.accelerations,
                        "primary_scalar": r.primary_scalar,
                        "mean_abs_accel": r.mean_abs_accel,
                        "sum_squared_accel": r.sum_squared_accel,
                        "peak_position_index": r.peak_position_index,
                        "entropy_2diff_max_abs": r.entropy_2diff_max_abs,
                        "greedy_matches_correct": r.greedy_matches_correct,
                    }
                    for r in results
                ],
            }, f, indent=2)
        print(f"Per-question JSON dump: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
