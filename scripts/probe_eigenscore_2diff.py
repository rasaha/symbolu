#!/usr/bin/env python
"""§13.16 experiment — Hidden-state EigenScore over positions.

Reference:
  Chen, Quan, Jia, Bao, Liu (2024). "INSIDE: LLMs' Internal States
  Retain the Power of Hallucination Detection." ICLR 2024.
  (EigenScore as the per-position scalar.)

  symbolu_robotics/bcvf_autonomous/DESIGN.md §6.1 / §6.7 — the
  autonomy-domain BCVF observable `S3_map_error_accel` peak that
  passed validation, motivating the 2nd-difference operator applied
  here.

Background:
  §13.14 implemented the LLM analogue of `S3_map_error_accel` over
  per-position semantic entropy of NLI-clustered truncations. The
  result was combined `BCVF_2DIFF_ANTI_FINDING` (TruthfulQA-MC AUC
  0.574 / HaluEval-QA AUC 0.363, signal *inverted* on HaluEval).
  §13.15 diagnosed three reasons the construction failed:
    (a) per-position entropy curves were monotonic, not smooth-with-
        rare-spikes — 2nd derivative measures local curvature, not
        fault onset.
    (b) trend direction flipped across benchmarks → observable
        dominated by NLI behavior on truncations of varying length,
        not the model's epistemic state.
    (c) the signal was text-level (decode → truncate → NLI →
        cluster: 4 lossy projections) rather than model-state-level.

  The §13.15 narrowing was: the result rejects BCVF over text-level
  semantic-entropy trajectories. It does NOT reject BCVF over
  model-internal continuous state trajectories.

  §13.16 tests the un-rejected construction. Per-position EigenScore
  S_t = (1/K) log det Σ_t over hidden states satisfies all three
  structural requirements that §13.14 violated:
    (a) continuous real-valued signal (not bounded by log K)
    (b) trend direction not driven by NLI artifacts
    (c) one projection (layer + position pick) instead of four

  The 2nd-difference operator is unchanged from §13.14; only the
  signal it operates on changes — from text-level cluster-count
  entropy to internal-state covariance log-det.

Method:
  1. Generate K=10 completions per question with output_hidden_states
     captured during generation.
  2. At each grid position t in {8, 12, 16, ..., 128} (31 positions),
     extract each sample's layer-L hidden state at the model step
     that produced its t-th generated token (capped at the sample's
     actual non-pad length). Stack into X_t in R^{K x H}.
  3. Per-position EigenScore (Chen 2024 K x K Gram form):
         X_t^c   = X_t - X_t.mean(axis=0, keepdims=True)
         Sigma_t = X_t^c @ X_t^c.T / H + alpha * I_K
         S_t     = (1/K) * log det Sigma_t
     with alpha = 1e-3 (Chen 2024 default; identical to §13.12).
  4. Centered second difference at each interior grid index:
         accel_i = S_{t_{i+1}} - 2*S_{t_i} + S_{t_{i-1}}
  5. Primary scalar (pinned for AUC + bands):
         bcvf_eig_2diff(q) = max_i |accel_i|
  6. Secondary diagnostic scalars reported but NOT used for band
     classification: mean|accel|, sum accel^2, peak position.
  7. Correctness label: Qwen greedy passes question-conditioned NLI
     against correct AND fails NLI against every distractor
     (identical to §13.10/§13.11/§13.12/§13.14 - direct AUC
     comparability).
  8. AUC computed on -bcvf_eig_2diff (higher acceleration → less
     stable evolving internal-state geometry → more likely wrong;
     same sign convention as §13.12 single-snapshot EigenScore).

Pre-committed success bands (§13.16, pinned in design doc BEFORE
implementation; same numerical partition as §13.11/§13.12/§13.13/
§13.14 since the §13.10 baseline of 0.661 is unchanged):

  - AUC >= 0.75 on both benchmarks -> HSEIG_2DIFF_STRONG.
    Gates the §13.9 VC-brief revision AND constitutes the first
    load-bearing positive evidence for BCVF-for-LLMs at any
    construction in this codebase. Authorizes a §13.17 result
    writeup positioning §13.16 as the first BCVF-faithful LLM
    result.
  - 0.70 <= AUC < 0.75 on both -> HSEIG_2DIFF_INTERNAL_STRONG.
    Strong for internal research; VC-brief still held.
    Diagnostic follow-ups: layer sweep (--layer), finer position
    grid (--position-stride 1 or 2), alpha sweep (--alpha).
  - 0.681 <= AUC < 0.70 on both -> HSEIG_2DIFF_MARGINAL_LIFT.
    Modest but real lift above §13.10 + 0.02. Document; do not
    authorize further single-axis probe progression.
  - 0.641 <= AUC <= 0.681 on both -> HSEIG_2DIFF_SATURATION.
    Within ±0.02 of §13.10's 0.661. Combined with §13.11/§13.12/
    §13.14 anti-findings, this would establish that EVERY
    literature-aligned single-axis probe — across sample-space,
    ensemble, internal-state, and temporal-evolution variants —
    saturates at the §13.10 ceiling on Qwen-7B with base-NLI at
    N=100. Conclusive evidence single-axis methods saturate.
  - AUC < 0.641 on any benchmark -> HSEIG_2DIFF_ANTI_FINDING.
    The hidden-state-internal variant of the BCVF 2nd-difference
    observable underperforms the §13.10 baseline. Would constitute
    a 4-of-4 anti-finding across literature-backed paths; pause
    LLM track. The autonomy-domain BCVF claim stands independently
    on §6.1 evidence.

Relationship to other §13 probes:
  - §13.10: pinned single-snapshot baseline (AUC 0.661 on both).
  - §13.12: single-snapshot EigenScore (same scalar at one position
    per question). §13.16 is §13.12 lifted to a position-indexed
    series with 2nd-difference operator on top.
  - §13.14: text-level 2nd-difference (rejected per §13.15).
    §13.16 keeps the position grid and 2nd-difference operator
    identical; replaces the text-level entropy signal with a
    continuous internal-state EigenScore signal.

Do NOT update AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md on the basis of
any result from this probe except HSEIG_2DIFF_STRONG on BOTH
benchmarks (per §13.9). Anything less is internal research
confidence only.

Usage:
    HF_HUB_DISABLE_XET=1 python scripts/probe_eigenscore_2diff.py \\
        --num-questions 100 \\
        --benchmark truthfulqa_mc \\
        --dump-json

Runtime ~3-5 min at N=100 on a 24+ GB GPU (faster than §13.14
because no per-position NLI clustering pass — only NLI calls are
the ~3 per question for the correctness label).
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
    # Per-sample non-pad length in generated tokens. Used both to
    # cap per-position hidden-state extraction (samples shorter than
    # a grid position fall back to their last available position)
    # and to surface short-generation pathologies in the JSON dump.
    sample_lengths: List[int]
    greedy: str
    # Pinned grid positions (in generated-token indices) where
    # EigenScore was computed.
    grid_positions: List[int]
    # Per-position EigenScore S_t. Same length as grid_positions.
    eigenscore_series: List[float]
    # Per-position centered 2nd differences accel_i = S_{i+1} -
    # 2*S_i + S_{i-1} for i in [1, len(eigenscore_series) - 2].
    # Length is len(eigenscore_series) - 2 (interior only).
    accelerations: List[float]
    # Primary scalar pinned for AUC + bands: max_i |accel_i|.
    primary_scalar: float
    # Diagnostic secondary scalars — pinned in dataclass so changing
    # the primary post-hoc requires a code edit (visible §0.8
    # violation), not a runtime override.
    mean_abs_accel: float
    sum_squared_accel: float
    peak_position_index: int  # index into accelerations of the peak
    greedy_matches_correct: bool
    label: int  # 1 = correct, 0 = wrong


# §13.16 pre-committed band boundaries. Identical numerical partition
# to §13.11/§13.12/§13.13/§13.14 because the §13.10 baseline of 0.661
# is unchanged across all five probes. Relabeled HSEIG_2DIFF_* so the
# per-revision lineage stays legible in console output, JSON dumps,
# and grep.
BASELINE_AUC = 0.661               # §13.10 single-model SE result.
SATURATION_DELTA = 0.02            # ±window around the baseline.
STRONG_THRESHOLD = 0.75            # §13.9 VC-gate bar.
INTERNAL_STRONG_THRESHOLD = 0.70   # Strong-for-internal; VC still held.
MARGINAL_LIFT_THRESHOLD = BASELINE_AUC + SATURATION_DELTA   # 0.681
SATURATION_LOWER = BASELINE_AUC - SATURATION_DELTA          # 0.641


def classify(auc: float) -> Tuple[str, str]:
    """Map an AUC to a §13.16 band label and per-run recommendation.

    Bands are partitioned so every float in [0, 1] falls into exactly
    one label. "On both benchmarks" determination is made externally
    by running this script twice (truthfulqa_mc + halueval_qa) and
    comparing the two per-run classifications under the §13.16
    worst-benchmark rule.

    Recommendations carry §13.16-specific framing because §13.16
    tests the construction §13.15's narrowing leaves explicitly open
    — its outcome bears directly on the BCVF-for-LLMs transfer claim
    at a model-internal continuous state representation.
    """
    if auc >= STRONG_THRESHOLD:
        return "HSEIG_2DIFF_STRONG", (
            "Strong pass. Gates the §13.9 VC-brief revision — but "
            "only if the OTHER benchmark also clears 0.75. ALSO "
            "constitutes the first load-bearing positive evidence "
            "for BCVF-for-LLMs at any construction in this codebase. "
            "§13.15's narrowing predicted exactly this outcome was "
            "still possible after the §13.14 text-level null. "
            "Authorizes §13.17 result writeup positioning §13.16 as "
            "the first BCVF-faithful LLM result."
        )
    if auc >= INTERNAL_STRONG_THRESHOLD:
        return "HSEIG_2DIFF_INTERNAL_STRONG", (
            "Strong for internal research. The hidden-state 2nd-"
            "difference observable produces signal but doesn't clear "
            "§13.9. Diagnostic follow-ups: (a) layer sweep "
            "(--layer), (b) finer position grid (--position-stride "
            "2 or 1), (c) alpha sweep (--alpha)."
        )
    if auc >= MARGINAL_LIFT_THRESHOLD:
        return "HSEIG_2DIFF_MARGINAL_LIFT", (
            "Real but modest lift above §13.10 + 0.02. Document; "
            "do NOT authorize further single-axis probe progression. "
            "The hidden-state 2nd-difference signal exists but is "
            "not strong enough to change the §13.9 external framing."
        )
    if auc >= SATURATION_LOWER:
        return "HSEIG_2DIFF_SATURATION", (
            "Within ±0.02 of §13.10's 0.661 baseline. The hidden-"
            "state 2nd-difference observable adds NOTHING measurable "
            "beyond static-snapshot semantic entropy. Combined with "
            "§13.11/§13.12/§13.14 anti-findings, this establishes "
            "that EVERY literature-aligned single-axis probe "
            "saturates at the §13.10 ceiling on this codebase's "
            "Qwen-7B + base-NLI configuration at N=100. Conclusive "
            "evidence single-axis methods saturate; further lift "
            "requires either model-scale upgrade (§13.8 item 4) or "
            "compound-revision construction with orthogonality "
            "tested first (§13.8 item 6)."
        )
    return "HSEIG_2DIFF_ANTI_FINDING", (
        "AUC below §13.10 − 0.02. The hidden-state 2nd-difference "
        "signal underperforms the static §13.10 baseline. 4-of-4 "
        "anti-finding across literature-backed paths "
        "(§13.11/§13.12/§13.14/§13.16). Pause LLM track. The "
        "autonomy-domain BCVF claim stands independently on §6.1 "
        "evidence and is unaffected by this null. Check for "
        "implementation bugs (per-position hidden-state extraction "
        "indexing, alpha numerics, accel sign convention) before "
        "treating as a genuine anti-finding."
    )


def build_nli_checker(nli_model, nli_tokenizer, device: str, batch_size: int = 32):
    """Return a function (premises, hypotheses) -> List[bool] for batched
    entailment checks. Identical to §13.10/§13.11/§13.12/§13.14 —
    ensures the correctness labels produced here are the same labels
    those scripts produce on the same inputs.

    NLI is used in this script ONLY for the correctness label (a few
    calls per question against the correct choice + distractors). It
    is not used for clustering — §13.16 operates on hidden-state
    geometry, not on text-level NLI clusters.
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


def label_correctness(
    greedy_gen: str, correct_choice: str, distractors: List[str],
    check_batch, question: str,
) -> bool:
    """Question-conditioned correctness label. Identical protocol to
    §13.10/§13.11/§13.12/§13.14. Holding this fixed across the §13
    ladder is what makes the AUC numbers directly comparable across
    all five probes.
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


def generate_samples_with_full_hidden_states(
    model, tokenizer, prompt: str, k: int, temperature: float,
    max_new_tokens: int, device: str, seed: int, layer_idx: int,
    grid_positions: List[int],
):
    """Sample `k` completions and extract layer-`layer_idx` hidden
    states at every grid position for every sample.

    Returns ``(decoded_samples, hidden_grid, sample_lengths)`` where:
      - decoded_samples : List[str], length k. Generation strings
        with prompt prefix stripped.
      - hidden_grid : np.ndarray of shape ``(len(grid_positions), k,
        H)``, float32. Per-position hidden states ready for the
        per-position EigenScore computation.
      - sample_lengths : List[int], length k. Per-sample non-pad
        token count.

    Implementation note — out.hidden_states is a tuple of length
    T_new (one entry per generation step). Entry t corresponds to
    the forward pass that produced the token at generated position
    t. Entry 0 has shape (k, prompt_len, H) — the prompt's full
    forward; entries 1..T_new-1 have shape (k, 1, H) — single-token
    forwards. The hidden state that "produced" the token at
    generated position t is at hidden_states[t][L][k, -1, :]
    (uniformly: -1 picks the only relevant position regardless of
    seq_len). This matches the §13.12 fix in commit a4753a1.

    For grid position t (in 1-indexed generated-token count, e.g.
    t=8 means "first 8 tokens"), the hidden state of interest is
    the one that produced the t-th token = generated index (t-1).
    Capped at the sample's actual non-pad length so we don't index
    past valid generation steps.
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
            output_hidden_states=True,
            return_dict_in_generate=True,
        )

    sequences = out.sequences  # (k, prompt_len + T_new)
    gen_segment = sequences[:, prompt_len:]                 # (k, T_new)

    # Per-sample non-pad length in generated tokens. A sample with
    # non-pad length L emitted L meaningful tokens before EOS/pad.
    is_non_pad = (gen_segment != pad_id)                    # (k, T_new)
    sample_lengths = is_non_pad.sum(dim=1).tolist()

    n_steps = len(out.hidden_states)  # equals T_new actually generated

    # Build the (P, k, H) tensor where P = len(grid_positions).
    # For each grid position t and sample k:
    #   effective_pos = min(t, sample_lengths[k]) - 1
    #     (0-indexed step that produced the t-th non-pad token, or
    #     the last available step if the sample is shorter than t)
    #   if effective_pos < 0: sample emitted 0 non-pad tokens →
    #     fall back to step 0's last position (prompt's last token,
    #     same fallback as §13.12).
    #   else: hidden state = hidden_states[effective_pos][L][k, -1, :]
    P = len(grid_positions)
    H = int(out.hidden_states[0][layer_idx].shape[-1])
    hidden_grid = np.zeros((P, k, H), dtype=np.float32)

    for p_idx, t in enumerate(grid_positions):
        for k_idx in range(k):
            effective_pos = min(t, sample_lengths[k_idx]) - 1
            if effective_pos < 0:
                # Sample emitted zero non-pad tokens — fall back to
                # prompt's last token at chosen layer.
                step_idx = 0
            else:
                # Cap step index at n_steps - 1 defensively in case
                # of rare alignment edge cases (should not occur
                # with the min(t, sample_lengths[k_idx]) cap above
                # because sample_lengths[k_idx] <= n_steps by
                # construction).
                step_idx = min(effective_pos, n_steps - 1)
            h = out.hidden_states[step_idx][layer_idx][k_idx, -1, :]
            hidden_grid[p_idx, k_idx, :] = (
                h.detach().to(torch.float32).cpu().numpy()
            )

    decoded_samples = [
        tokenizer.decode(g, skip_special_tokens=True).strip()
        for g in gen_segment
    ]
    return decoded_samples, hidden_grid, sample_lengths


def generate_greedy(
    model, tokenizer, prompt: str, max_new_tokens: int, device: str,
) -> str:
    """Deterministic T=0 completion. Used by the correctness labeler;
    no hidden-state capture (the label is computed against the
    decoded greedy text via NLI, identical to §13.10–§13.14)."""
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


def compute_eigenscore_at_position(
    X: np.ndarray, alpha: float,
) -> float:
    """Chen 2024 EigenScore at a single position.

    Given hidden-state matrix X of shape (K, H), compute:
        X_c     = X - X.mean(axis=0, keepdims=True)
        Sigma_K = (X_c @ X_c.T) / H + alpha * I_K
        S       = (1/K) * log det Sigma_K

    Uses np.linalg.slogdet for numerical stability. Sigma_K is
    positive-definite by construction with alpha > 0; defensively
    asserts sign > 0 (any negative sign would indicate NaN/Inf in
    X or alpha too small for the hidden-state norm scale).

    Identical formulation to §13.12's eigenscore() — only the
    calling context differs (per-position here, single-position
    there).
    """
    K, H = X.shape
    if K < 2:
        raise ValueError(f"EigenScore requires K >= 2 samples; got K={K}")
    X_c = X - X.mean(axis=0, keepdims=True)            # (K, H)
    Sigma_K = (X_c @ X_c.T) / float(H) + alpha * np.eye(K)  # (K, K)
    sign, logabsdet = np.linalg.slogdet(Sigma_K)
    if sign <= 0:
        raise RuntimeError(
            f"slogdet returned sign={sign} on regularized Gram matrix "
            f"with alpha={alpha} > 0. Check for NaN/Inf in hidden "
            f"states (alpha too small for this model's hidden-state "
            f"norm scale)."
        )
    return float(logabsdet / K)


def compute_eigenscore_series(
    hidden_grid: np.ndarray, alpha: float,
) -> List[float]:
    """Compute the per-position EigenScore series S_t for all grid
    positions.

    ``hidden_grid`` has shape (P, K, H) — per-position hidden-state
    matrices. Returns a list of P EigenScore values.

    This is the 1st-derivative-class signal that the 2nd-difference
    operator will be applied to. Without per-position hidden-state
    capture there is no "evolving internal-state geometry" analogue
    and the BCVF transfer claim cannot be tested at this level.
    """
    P = hidden_grid.shape[0]
    series: List[float] = []
    for p_idx in range(P):
        X = hidden_grid[p_idx]                              # (K, H)
        series.append(compute_eigenscore_at_position(X, alpha))
    return series


def compute_2nd_difference_scalars(
    eigenscore_series: List[float],
) -> Tuple[List[float], float, float, float, int]:
    """Centered 2nd differences of the per-position EigenScore series,
    with the four §13.16 scalars.

    Returns ``(accelerations, primary, mean_abs, sum_squared,
    peak_idx)``:
      - accelerations : list of accel_i = S_{i+1} − 2·S_i + S_{i−1}
        for interior i. Length = len(eigenscore_series) - 2.
      - primary : max_i |accel_i|. Pinned per §13.16 as the band-
        classification scalar.
      - mean_abs : mean_i |accel_i|. Diagnostic only.
      - sum_squared : Σ_i accel_i². Diagnostic only.
      - peak_idx : index of the peak. Diagnostic only.

    Same structure as §13.14's compute_2nd_difference_scalars; only
    the input series differs (EigenScore values, not entropies).
    """
    n = len(eigenscore_series)
    if n < 3:
        return [], 0.0, 0.0, 0.0, -1

    accelerations: List[float] = []
    for i in range(1, n - 1):
        accel = (
            eigenscore_series[i + 1]
            - 2.0 * eigenscore_series[i]
            + eigenscore_series[i - 1]
        )
        accelerations.append(accel)

    abs_accels = [abs(a) for a in accelerations]
    primary = max(abs_accels)
    mean_abs = float(np.mean(abs_accels))
    sum_squared = float(np.sum(np.array(accelerations) ** 2))
    peak_idx = int(np.argmax(abs_accels))
    return accelerations, primary, mean_abs, sum_squared, peak_idx


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Binary AUC via tie-aware rank sum. Identical to §13.10–§13.14."""
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
        help="Identical benchmark semantics to §13.10–§13.14 — only "
             "the per-question scalar differs (max|accel| over per-"
             "position EigenScore series instead of single-position "
             "EigenScore or per-position semantic entropy).",
    )
    parser.add_argument(
        "--include-context", action="store_true",
        help="halueval_qa only: prepend the 'knowledge' passage. "
             "Default False to mirror §13.10–§13.14 closed-book.",
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
        help="Target model. §13.16 pre-commitment pins this to "
             "Qwen2.5-7B-Instruct for direct §13.10/§13.12/§13.14 "
             "comparability; changing it is a §0.8 deviation.",
    )
    parser.add_argument(
        "--nli-model",
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        help="MNLI-trained classifier for the correctness label. "
             "Same default as §13.10/§13.11/§13.12/§13.14. NLI is "
             "NOT used for clustering in this script — only for the "
             "correctness label.",
    )
    parser.add_argument(
        "--layer", type=int, default=None,
        help="Hidden-state layer index. Default None → "
             "model.config.num_hidden_layers // 2 (= 14 for "
             "Qwen2.5-7B-Instruct, the §13.16-pinned middle layer; "
             "identical to §13.12). A non-default value is a §13.16 "
             "deviation flagged in the report.",
    )
    parser.add_argument(
        "--alpha", type=float, default=1e-3,
        help="EigenScore regularization. Default 1e-3 per Chen 2024 "
             "and §13.12/§13.16 pre-commitment.",
    )
    parser.add_argument(
        "--position-min", type=int, default=8,
        help="Minimum grid position (in generated-token count). "
             "§13.16 pins 8 to skip leading low-information tokens. "
             "A non-default value is a §13.16 deviation.",
    )
    parser.add_argument(
        "--position-stride", type=int, default=4,
        help="Spacing between grid positions. §13.16 pins 4 for "
             "compute tractability and direct comparability with "
             "§13.14's grid. A non-default value is a §13.16 "
             "deviation.",
    )
    parser.add_argument("--k-samples", type=int, default=10,
                        help="Samples per question. Pinned to 10 by "
                             "§13.16 for §13.10–§13.14 parity.")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument(
        "--max-new-tokens", type=int, default=128,
        help="§13.16 pins 128 (4× §13.10's 32; matches §13.14). "
             "Needed so the EigenScore series has enough sequence "
             "length to evolve a 2nd-difference signal.",
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
             "per-position EigenScore series and per-position 2nd "
             "differences. Required for post-hoc secondary-scalar "
             "audits if the primary scalar saturates.",
    )
    args = parser.parse_args()

    if args.k_samples < 2:
        parser.error(
            f"--k-samples must be >= 2 (EigenScore is undefined at "
            f"K=1); got {args.k_samples}."
        )
    if args.alpha <= 0:
        parser.error(f"--alpha must be > 0; got {args.alpha}.")
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

    grid_positions = list(range(
        args.position_min, args.max_new_tokens + 1, args.position_stride,
    ))
    if len(grid_positions) < 3:
        parser.error(
            f"Position grid produced only {len(grid_positions)} "
            f"positions (need >= 3 for any centered 2nd difference)."
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
    num_hidden_layers = int(model.config.num_hidden_layers)
    hidden_size = int(model.config.hidden_size)
    layer_idx = (
        args.layer if args.layer is not None
        else num_hidden_layers // 2
    )
    if not (0 <= layer_idx <= num_hidden_layers):
        parser.error(
            f"--layer {layer_idx} out of range [0, {num_hidden_layers}] "
            f"for {args.model}."
        )
    layer_is_default = (args.layer is None)
    print(
        f"  num_hidden_layers={num_hidden_layers}, "
        f"hidden_size={hidden_size}, using layer={layer_idx}"
        + ("" if layer_is_default
           else "  [§13.16 DEVIATION: non-default layer]"),
        flush=True,
    )
    print(
        f"Position grid: {len(grid_positions)} positions, "
        f"min={args.position_min}, stride={args.position_stride}, "
        f"max={args.max_new_tokens}"
        + ("" if grid_is_default
           else "  [§13.16 DEVIATION: non-default grid]"),
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

        # Generate K samples + capture per-position layer-L hidden
        # states across the entire grid in a single batched generate
        # call (output_hidden_states=True).
        decoded_samples, hidden_grid, sample_lengths = (
            generate_samples_with_full_hidden_states(
                model, tokenizer, prompt,
                k=args.k_samples, temperature=args.temperature,
                max_new_tokens=args.max_new_tokens, device=device,
                seed=args.seed + q_idx, layer_idx=layer_idx,
                grid_positions=grid_positions,
            )
        )

        # Per-position EigenScore series — the 1st-derivative signal
        # the BCVF 2nd-difference operates on. This is the core
        # piece §13.16 introduces over §13.12 (which computed
        # EigenScore at one position per question).
        eigenscore_series = compute_eigenscore_series(
            hidden_grid, alpha=args.alpha,
        )

        # 2nd-difference scalars (primary + three diagnostic
        # secondaries). Pinning happens here in code: the unpacking
        # enforces that the primary scalar is exactly max|accel|; any
        # post-hoc swap requires a code edit (visible §0.8 violation).
        accelerations, primary, mean_abs, sum_squared, peak_idx = (
            compute_2nd_difference_scalars(eigenscore_series)
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
            samples=decoded_samples,
            sample_lengths=sample_lengths,
            greedy=greedy,
            grid_positions=list(grid_positions),
            eigenscore_series=eigenscore_series,
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
            mean_S_end = float(np.mean([
                r.eigenscore_series[-1] for r in results
                if r.eigenscore_series
            ])) if results else 0.0
            print(
                f"  [{q_idx + 1}/{len(ds)}] elapsed={elapsed:.0f}s "
                f"eta={eta:.0f}s correct={n_correct}/{len(results)} "
                f"mean_primary={mean_primary:.4f} "
                f"mean_S_end={mean_S_end:.3f}",
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
    auc_sum_squared = roc_auc(
        -sum_squared_scalars, labels_np.astype(bool),
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

    # Sanity check value: mean S at the last grid position. This is
    # the §13.12-comparable single-snapshot EigenScore. If §13.16
    # produces wildly different mean_S_end vs §13.12's expectation,
    # something is wrong with the per-position extraction pipeline.
    mean_S_end = float(np.mean([
        r.eigenscore_series[-1] for r in results if r.eigenscore_series
    ])) if results else 0.0
    mean_S_start = float(np.mean([
        r.eigenscore_series[0] for r in results if r.eigenscore_series
    ])) if results else 0.0

    # --- Console report --- #
    print()
    print(f"{'metric':<48} {'value':>20}")
    print("-" * 71)
    print(f"{'N questions':<48} {len(results):>20}")
    print(f"{'Target model':<48} {args.model:>20}")
    print(f"{'NLI model (label only)':<48} {args.nli_model:>20}")
    print(f"{'num_hidden_layers':<48} {num_hidden_layers:>20}")
    print(f"{'hidden_size (H)':<48} {hidden_size:>20}")
    print(f"{'Layer used':<48} {layer_idx:>20}")
    print(f"{'Regularization alpha':<48} {args.alpha:>20.2e}")
    print(f"{'K samples':<48} {args.k_samples:>20}")
    print(f"{'max_new_tokens':<48} {args.max_new_tokens:>20}")
    print(f"{'Position grid (min, stride, count)':<48} "
          f"({args.position_min}, {args.position_stride}, "
          f"{len(grid_positions)})".rjust(20))
    print(f"{'Correct (greedy matches)':<48} {n_pos:>20}")
    print(f"{'Wrong':<48} {n_neg:>20}")
    print(f"{'Greedy accuracy':<48} {overall_correct_rate:>20.3f}")
    print(f"{'Mean S at first grid position':<48} {mean_S_start:>20.4f}")
    print(f"{'Mean S at last grid position (≈ §13.12)':<48} {mean_S_end:>20.4f}")
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
        f"probe_eigenscore_2diff_{args.benchmark}{args.suffix}.md"
    )
    deviation_notes: List[str] = []
    if not layer_is_default:
        deviation_notes.append(
            f"  ⚠ §13.16 DEVIATION: non-default layer "
            f"(pinned default = {num_hidden_layers // 2})"
        )
    if not grid_is_default:
        deviation_notes.append(
            f"  ⚠ §13.16 DEVIATION: non-default position grid "
            f"(pinned defaults: position_min=8, position_stride=4, "
            f"max_new_tokens=128)"
        )
    deviation_block = "\n".join(deviation_notes) + "\n" if deviation_notes else ""

    lines = [
        "# §13.16 Experiment — Hidden-State EigenScore Over Positions\n",
        "References: Chen, Quan, Jia, Bao, Liu (2024) ICLR — INSIDE/"
        "EigenScore (per-position scalar). `symbolu_robotics/"
        "bcvf_autonomous/DESIGN.md` §6.1 / §6.7 — autonomy-domain "
        "BCVF observable `S3_map_error_accel` peak motivating the "
        "2nd-difference operator. §13.15 — narrowing of the BCVF "
        "transfer claim that this probe tests.\n",
        "## Configuration\n",
        f"- **Target model:** `{args.model}`",
        f"- **NLI model (correctness label only):** `{args.nli_model}`",
        f"- **Hidden-state layer:** {layer_idx} of {num_hidden_layers} "
        f"({'default — model.config.num_hidden_layers // 2' if layer_is_default else 'non-default'})",
        f"- **Hidden dimension (H):** {hidden_size}",
        f"- **EigenScore α:** {args.alpha:.2e}",
        f"- **Position grid:** position_min={args.position_min}, "
        f"position_stride={args.position_stride}, "
        f"count={len(grid_positions)}",
        deviation_block.rstrip() if deviation_block else "",
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
        f"- **Seed:** {args.seed}\n",
        "## Result (primary scalar)\n",
        "| Metric | Value |",
        "|---|---|",
        f"| N questions | {len(results)} |",
        f"| Greedy accuracy (correct / N) | {n_pos}/{len(results)} = "
        f"{overall_correct_rate:.3f} |",
        f"| Mean S at first grid position (t={args.position_min}) | "
        f"{mean_S_start:.4f} |",
        f"| Mean S at last grid position (t={args.max_new_tokens}, "
        f"≈ §13.12 single-snapshot) | {mean_S_end:.4f} |",
        f"| Mean primary scalar `max_i \\|accel_i\\|` (all) | "
        f"{float(primary_scalars.mean()):.4f} |",
        f"| Mean primary scalar (correct) | {mean_correct:.4f} |",
        f"| Mean primary scalar (wrong) | {mean_wrong:.4f} |",
        f"| **AUC — primary (max\\|accel\\|)** | **{auc_primary:.3f}** |",
        f"| Δ vs §13.10 baseline (0.661) | "
        f"**{auc_primary - BASELINE_AUC:+.3f}** |",
        f"| **Classification** | **`{classification}`** |\n",
        "## Diagnostic secondary scalars (NOT used for classification)\n",
        "Pinned in §13.16 to support post-hoc audit. If the primary "
        "scalar lands at SATURATION but a secondary shows clear "
        "correct/wrong separation, that constitutes evidence the "
        "BCVF-shaped signal exists but the wrong aggregation was "
        "pinned — a fresh §0.8 re-commitment with a different "
        "primary scalar would be authorized. Changing the primary "
        "scalar without that re-commitment is a §0.8 violation.\n",
        "| Diagnostic scalar | AUC |",
        "|---|---|",
        f"| `mean_i \\|accel_i\\|` | {auc_mean_abs:.3f} |",
        f"| `Σ_i accel_i²` | {auc_sum_squared:.3f} |",
        "",
        "## §13.16 pre-committed bands\n",
        f"- `AUC ≥ {STRONG_THRESHOLD}` → **HSEIG_2DIFF_STRONG** — "
        "gates §13.9 VC-brief revision when cleared on BOTH "
        "benchmarks; first load-bearing positive evidence for "
        "BCVF-for-LLMs.",
        f"- `{INTERNAL_STRONG_THRESHOLD:.3f} ≤ AUC < "
        f"{STRONG_THRESHOLD:.3f}` → **HSEIG_2DIFF_INTERNAL_STRONG** "
        "— strong for internal research; VC-brief still held.",
        f"- `{MARGINAL_LIFT_THRESHOLD:.3f} ≤ AUC < "
        f"{INTERNAL_STRONG_THRESHOLD:.3f}` → "
        "**HSEIG_2DIFF_MARGINAL_LIFT** — modest but real lift above "
        "§13.10 + 0.02.",
        f"- `{SATURATION_LOWER:.3f} ≤ AUC ≤ "
        f"{MARGINAL_LIFT_THRESHOLD:.3f}` → "
        "**HSEIG_2DIFF_SATURATION** — within ±"
        f"{SATURATION_DELTA} of §13.10's {BASELINE_AUC} baseline; "
        "combined with §13.11/§13.12/§13.14 anti-findings, "
        "establishes single-axis saturation.",
        f"- `AUC < {SATURATION_LOWER:.3f}` → "
        "**HSEIG_2DIFF_ANTI_FINDING** — 4-of-4 anti-finding across "
        "literature-backed paths; pause LLM track.\n",
        "## Recommendation\n",
        recommendation + "\n",
        "## Interpretation guidance\n",
        "This probe implements the construction §13.15's narrowing "
        "leaves explicitly open: BCVF 2nd-difference operator "
        "applied to a continuous model-internal representation "
        "(per-position EigenScore over hidden-state geometry) "
        "rather than to a text-level NLI clustering proxy. The "
        "north-star phrasing from §13.15: \"the failure in §13.14 "
        "was not the 2nd-difference idea itself, but the choice of "
        "text-level semantic entropy as the evolving state "
        "variable. §13.16 therefore moves the BCVF operator onto a "
        "continuous model-internal representation.\"\n",
        "Distinguishing feature vs §13.10/§13.11/§13.12/§13.14: "
        "those probes are first-derivative-class single-snapshot "
        "measurements OR second-derivative-class measurements over "
        "text-level proxies. §13.16 is the only construction in "
        "the §13 ladder that combines (a) the BCVF 2nd-difference "
        "operator with (b) a continuous model-internal representation "
        "of the evolving state. A positive result here is "
        "qualitatively different from a positive on §13.10–§13.14.\n",
        "Critically: this script does NOT authorize any update to "
        "`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on its own. Per §13.9, "
        "the external framing revision requires "
        "`HSEIG_2DIFF_STRONG` (or any §13 probe's STRONG band) on "
        "BOTH benchmarks, which has not been observed across §13.10-"
        "§13.14. Furthermore, neither outcome of this probe "
        "retroactively affects the autonomy-domain BCVF result — "
        "§6.1's N=21 sign-test on `S3_map_error_accel` passed "
        "independently and stands.\n",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nMarkdown report: {md_path}")

    if args.dump_json:
        json_path = args.out_dir / (
            f"probe_eigenscore_2diff_{args.benchmark}{args.suffix}.json"
        )
        with json_path.open("w", encoding="utf-8") as f:
            json.dump({
                "config": {
                    "model": args.model,
                    "nli_model": args.nli_model,
                    "num_hidden_layers": num_hidden_layers,
                    "hidden_size": hidden_size,
                    "layer": layer_idx,
                    "layer_is_default": layer_is_default,
                    "alpha": args.alpha,
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
                    "mean_S_first_position": mean_S_start,
                    "mean_S_last_position": mean_S_end,
                    "mean_primary_scalar_all": float(
                        primary_scalars.mean()
                    ),
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
                        "eigenscore_series": r.eigenscore_series,
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
