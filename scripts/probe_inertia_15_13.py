#!/usr/bin/env python
"""§15.13 Phase 4 — Continuation-inertia probe (multi-turn state dynamics).

Pure §0.8-binding implementation per the sealed §15.13 design
spec at `docs/design/15_13_R_INERTIA_DESIGN_SPEC.md`. Tests
whether the LM's residual alignment toward a prior answer
trajectory R_A — relative to a new question Q_B — predicts
whether the model will fail to pivot to Q_B.

§15.13 is a fresh top-level §0.X commitment, NOT an amendment
to any prior section. It does NOT modify any §13/§14/§15.x
verdict-of-record (including §15.10 PARTIAL_SIGNAL_IN_Z, §15.11
NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE, §15.12 closure outcome,
§13.9 hold, or §6.1 N=21 autonomy result). All upstream
verdicts remain binding.

Mechanism class: continuation inertia (H3 only). Tested in
isolation. No combination with H1 (state coherence) or H2
(intent competition); those remain in the open-but-untested
column for future top-level §0.X work.

Pinned formula (§15.13 §0.8-binding):

    R_inertia = cos(s_t, r_A) − cos(s_t, q_B)

with the BCVF-faithful direction convention:

    Lower R_inertia predicts CORRECT response to Q_B.
    Test statistic: AUC(−R_inertia, y).

R_sim comparator baseline:

    R_sim = cos(q_A, q_B)

The cascade requires R_inertia to beat BOTH chance (0.5) AND
R_sim's AUC by the cascade margin to clear STRONG / PARTIAL
bands (strict-comparator requirement, not chance-vs-zero).

What this script DOES:
  * Loads correctness labels from the existing §13.10 dump
    (TruthfulQA-MC; first 100 q_idx records).
  * Constructs 100 deterministic stimulus pairs by the pinned
    rule (Q_A_idx, Q_B_idx) = (i, (i + 50) mod 100).
  * Per stimulus, runs three Qwen2.5-7B-Instruct forward
    passes (Pass 1: generate R_A + extract q_A, r_A; Pass 2:
    multi-turn forward + generate Q_B response + extract s_t;
    Pass 3: standalone Q_B forward + extract q_B).
  * Splices Pass 1's decoded R_A text verbatim into Pass 2 to
    guarantee byte-identical R_A across passes (Risk 3
    mitigation per spec).
  * Scores the Q_B response with §13.10-style NLI (DeBERTa-
    v3-base-mnli-fever-anli) against the gold answer.
  * Computes R_inertia and R_sim per stimulus; aggregates
    auc_inertia = AUC(−R_inertia, y) and auc_sim =
    AUC(−R_sim, y) over all 100.
  * Applies the §15.13 cascade (direction gate → STRONG via
    AUC≥0.75 + ΔAUC≥+0.05 vs both chance and sim → PARTIAL
    via AUC≥0.66 + ΔAUC>0 vs both → NO_MATERIAL).
  * Emits JSON + markdown artifacts with a 44-pattern §15.7-
    pattern interpretation firewall enforced at write time.

What this script DOES NOT:
  * Re-classify any §13/§14/§15.x verdict-of-record.
  * Test H1 (state coherence) or H2 (intent competition).
  * Combine signals (no R_total).
  * Sign-flip if AUC(−R_inertia, y) < 0.5. The BCVF-faithful
    direction was the pre-committed hypothesis; failing it
    is a hypothesis failure (NO_MATERIAL via direction gate),
    not a sign-flip opportunity.
  * Bootstrap CIs in v1; mirrors §15.10 / §15.11.
  * Test on HaluEval in v1 (TruthfulQA-MC only). HaluEval is a
    v2 follow-up only if v1 shows signal.
  * Authorize Phase 5+ or further §15.x work.

Inputs (per spec §15.13):
    docs/experiments/probe_semantic_entropy.json
        (§13.10 TruthfulQA-MC dump; q_idx + correctness labels;
        first 100 records used for q_idx alignment)
    `Qwen/Qwen2.5-7B-Instruct` (cached HF model)
    TruthfulQA-MC dataset (HuggingFace; question text +
    mc1_targets gold-answer choice via q_idx alignment)
    `cross-encoder/nli-deberta-v3-base` (HF NLI model loaded
    via the §13.10 scoring helper for the y label)

Outputs:
    docs/experiments/inertia_15_13_extractions.npz
        (cached extraction; per-stimulus q_a/r_a/s_t/q_b
        hidden states + decoded text + y; allows --probe-only)
    docs/experiments/probe_inertia_15_13.json
        (machine-readable result, schema_version "15.13")
    docs/experiments/probe_inertia_15_13.md
        (human-readable report, firewall-scanned at write
        time; 8 sections per spec)

Usage:
    # Required pre-execution gate.
    python scripts/probe_inertia_15_13.py --self-test

    # Full pipeline (extract + probe + report).
    python scripts/probe_inertia_15_13.py

    # Extract only (GPU phase; produces .npz cache).
    python scripts/probe_inertia_15_13.py --extract-only

    # Probe only (CPU phase; uses .npz cache).
    python scripts/probe_inertia_15_13.py --probe-only

Exit codes:
    0  success
    2  CLI / argument error (handled by argparse)
    3  SELF_TEST_FAILED
    4  INTERPRETATION_VIOLATION
    5  SCHEMA_MISMATCH (label dump or cache)
    6  EXTRACTION_FAILED (torch / transformers stack)
    7  PROBE_FAILED (sklearn / NaN in features)
    8  NLI_SCORING_FAILED (DeBERTa scoring stack failure)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

# Suppress sklearn FutureWarning for the `penalty` kwarg (mirrors §15.10/§15.11).
# §15.13 only uses sklearn for roc_auc_score; this filter is precautionary.
warnings.filterwarnings(
    "ignore",
    message=r".*'penalty'.*",
    category=FutureWarning,
)


# ===========================================================================
# §15.13 PINNED CONSTANTS — DO NOT CHANGE during implementation.
# Any change requires a fresh §0.8 amendment to the §15.13 spec at
# docs/design/15_13_R_INERTIA_DESIGN_SPEC.md.
# ===========================================================================

SCHEMA_VERSION = "15.13"

# Target model (pinned per §15.13 spec; matches §15.10 / §15.11).
QWEN_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

# Single benchmark for v1 (pinned). HaluEval is a v2 follow-up only if v1
# shows signal; v2 requires its own §0.8.
BENCHMARK = "truthfulqa_mc"

# Pinned stimulus count.
PINNED_N = 100

# Pinned pairing rule offset: (Q_A_idx, Q_B_idx) = (i, (i + PAIRING_OFFSET)
# mod PINNED_N) for i in 0..PINNED_N-1. Each question appears once as Q_A
# and once as Q_B; same-family pairing eliminates benchmark-family
# asymmetry as a confound.
PAIRING_OFFSET = 50
PAIRING_RULE_DESCRIPTION = (
    "(Q_A_idx, Q_B_idx) = (i, (i + 50) mod 100) for i in 0..99"
)

# §13.10 dump — used ONLY for q_idx alignment + correctness cross-check;
# correctness label y is recomputed via NLI on the Q_B response per spec.
INPUT_S13_10_TRUTHFULQA = "docs/experiments/probe_semantic_entropy.json"

# §13.10 dump field names (per §15.1 Amendment 1 pinned schema).
FIELD_QID = "q_idx"
FIELD_CORRECT = "greedy_matches_correct"
FIELD_QUESTION = "question"
# Optional gold-answer field name in the §13.10 dump (per §13.10 producer).
# If absent, fall back to HF dataset's mc1_targets.
FIELD_CORRECT_CHOICE = "correct_choice"

# Pinned cross-phase disclosure values (verdicts-of-record from prior
# §15.x phases; carried forward for the cross-phase-comparison section
# of the markdown report and the JSON's cross_phase_disclosure block).
PHASE_1_VERDICT = "PARTIAL_SIGNAL_IN_Z"
PHASE_2_VERDICT = "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"
PHASE_3_STATUS = "sealed (closure outcome pending implementation)"

# Pinned alpha targets per spec §15.13 (selective-prediction operating
# points; disclosure only — do NOT enter cascade decision).
ALPHA_TARGETS: tuple[float, ...] = (0.35, 0.50, 0.75)
ALPHA_PRIMARY = 0.50
N_MIN = 10  # selective-prediction floor (matches §15.10/§15.11)
SEED_ENTROPY = 15  # for any rng calls; no CV in §15.13

# Cascade thresholds per §15.13 spec (numerically identical to §15.10/§15.11
# for cross-phase comparability).
STRONG_AUC_THRESHOLD = 0.75            # inclusive
STRONG_DELTA_AUC_THRESHOLD = 0.05      # inclusive (vs both chance and R_sim)
PARTIAL_AUC_THRESHOLD = 0.66           # inclusive
DIRECTION_GATE_THRESHOLD = 0.5         # strict (auc_inertia < 0.5 fails)
CHANCE_BASELINE_AUC = 0.5

# Hidden-state extraction config (pinned per spec §15.13 Choice 4 + Choice 5).
HIDDEN_DIM = 3584
LAYER_IDX = -1                         # final layer only; no multi-layer agg
EXTRACT_DTYPE_INFERENCE = "float16"    # match Qwen2.5-7B's native fp16
EXTRACT_DTYPE_CACHE = "float32"        # cast for portability

# Generation config (pinned per spec §15.13).
MAX_NEW_TOKENS = 64
DECODE_TEMPERATURE = 0.0               # greedy

# Pinned representation-extraction descriptors (used in JSON
# extraction_config + markdown pinned-config block).
R_A_POOLING_DESCRIPTION = "mean_over_decoded_assistant_tokens"
S_T_EXTRACTION_DESCRIPTION = (
    "last_token_pre_decode_at_second_assistant_tag"
)
Q_B_EXTRACTION_DESCRIPTION = (
    "last_token_pre_decode_standalone_with_chat_template"
)
Q_A_EXTRACTION_DESCRIPTION = (
    "last_token_pre_decode_at_first_assistant_tag"
)
DIRECTION_CONVENTION = (
    "lower R_inertia predicts correct (BCVF-faithful); "
    "test statistic AUC(-R_inertia, y)"
)

# Cache + output paths (pinned per spec §15.13 §0.8-binding artifacts list).
EXTRACTIONS_CACHE_PATH = "docs/experiments/inertia_15_13_extractions.npz"
OUTPUT_JSON_PATH = "docs/experiments/probe_inertia_15_13.json"
OUTPUT_MD_PATH = "docs/experiments/probe_inertia_15_13.md"


# ===========================================================================
# §15.13 Class-3 forbidden-statement patterns (44 total).
#
# Inheritance per spec §15.13 firewall section:
#   * Inherited from §15.10 / §15.7 (16 patterns).
#   * Inherited from §15.11           (10 patterns).
#   * Inherited from §15.12           (10 patterns).
#   * §15.13-specific                  (8 patterns).
#
# Match policy (per spec): case-insensitive substring for non-§ patterns;
# literal (case-sensitive) for §-anchored patterns to preserve precise
# §-numbering. Detection → exit code 4 (INTERPRETATION_VIOLATION) without
# writing.
# ===========================================================================

CLASS_3_FORBIDDEN_PATTERNS: list[str] = [
    # ----- Inherited from §15.10 / §15.7 (16). -----
    "verdict was wrong",
    "verdict is wrong",
    "should be re-classified",
    "should be reclassified",
    "is invalid because",
    "§13.9 should be relaxed",
    "§13.9 hold should be",
    "§13.9 hold can be",
    "§15.8 authorized",
    "§15.8 is authorized",
    "§6.1 is strengthened",
    "autonomy result is strengthened",
    "actually STRONG",
    "should be classified as STRONG",
    "actually PARTIAL despite",
    "STRONG despite the cascade",
    # ----- Inherited from §15.11 (10). -----
    "actually STRONG_SIGNAL_IN_PHASE_COHERENCE despite",
    "should be STRONG_SIGNAL_IN_PHASE_COHERENCE",
    "actually PARTIAL_SIGNAL_IN_PHASE_COHERENCE despite",
    "should be classified as PARTIAL_SIGNAL_IN_PHASE_COHERENCE",
    "the wrong-direction failure should be flipped",
    "the direction gate should be relaxed",
    "the BCVF-faithful direction was wrong",
    "§15.10 PARTIAL is overturned",
    "§15.10 verdict is overturned",
    "§13.10 baseline should be replaced",
    # ----- Inherited from §15.12 (10). -----
    "§15.10 PARTIAL was wrong",
    "§15.10 PARTIAL should be relaxed",
    "§15.11 NO_MATERIAL should be relaxed",
    "§15.11 direction gate should be relaxed",
    "the bootstrap test was inappropriate",
    "the bootstrap test should be replaced",
    "§15.12 closure should be reopened",
    "§15.12 should authorize REOPEN",
    "§6.1 N=21 sign test was wrong",
    "the autonomy result is invalidated",
    # ----- §15.13-specific (8). -----
    "actually STRONG_SIGNAL_IN_INERTIA despite",
    "should be STRONG_SIGNAL_IN_INERTIA",
    "actually PARTIAL_SIGNAL_IN_INERTIA despite",
    "should be classified as PARTIAL_SIGNAL_IN_INERTIA",
    "the R_sim comparator should be ignored",
    "the same-family pairing was a mistake",
    "the pooling over R_A tokens was wrong",
    "the chance baseline alone is sufficient",
]

# Sanity invariant (also asserted by the self-test gate at runtime).
assert len(CLASS_3_FORBIDDEN_PATTERNS) == 44, (
    f"§15.13 spec pins 44 firewall patterns; got "
    f"{len(CLASS_3_FORBIDDEN_PATTERNS)}."
)


# ===========================================================================
# Dataclasses — immutable records.
#
# Six records per spec §15.13 Chunk I-1:
#   * StimulusPair         — (q_a_idx, q_b_idx) + question text + gold text.
#   * StimulusExtraction   — three hidden states + decoded text + y label.
#   * StimulusFeatures     — derived cosines + R_inertia + R_sim + y.
#   * InertiaProbeResult   — aggregate AUCs + selective-prediction ops.
#   * InertiaCascadeVerdict — cascade label + rationale + numbers.
#   * InertiaAuditOutputs  — top-level packaged result for JSON/MD writers.
# ===========================================================================


@dataclass(frozen=True)
class StimulusPair:
    """One (Q_A, Q_B) stimulus per the pinned pairing rule.

    Constructed in `construct_stimulus_pairs` from §13.10-aligned q_idx
    values + question text + gold answer choice. `pair_idx` is the
    enumeration index `i` in 0..PINNED_N-1 (the same i that produced
    `(q_a_idx, q_b_idx) = (i, (i + PAIRING_OFFSET) mod PINNED_N)`).
    """

    pair_idx: int
    q_a_idx: int
    q_b_idx: int
    q_a_text: str
    q_b_text: str
    q_b_correct_choice: str
    s13_10_correct_q_a: bool  # disclosure-only sanity
    s13_10_correct_q_b: bool  # disclosure-only sanity


@dataclass(frozen=True)
class StimulusExtraction:
    """Per-stimulus 3-pass extraction result.

    All hidden states stored fp32 (cast from inference fp16) for cache
    portability. Vectors are layer −1, hidden_dim 3584. Text fields are
    the verbatim greedy-decoded outputs of Pass 1 (R_A) and Pass 2 (Q_B
    response) — Pass 1's r_a_text is spliced into Pass 2's prompt
    construction (Risk 3 mitigation per spec).
    """

    pair_idx: int
    q_a_idx: int
    q_b_idx: int
    q_a_repr: np.ndarray            # float32, shape (HIDDEN_DIM,)
    r_a_repr: np.ndarray            # float32, shape (HIDDEN_DIM,)
    s_t: np.ndarray                 # float32, shape (HIDDEN_DIM,)
    q_b_repr: np.ndarray            # float32, shape (HIDDEN_DIM,)
    r_a_text: str                   # decoded Pass 1 assistant tokens
    q_b_response_text: str          # decoded Pass 2 assistant tokens
    n_r_a_tokens: int               # |T_A|; tracked for Risk 6 disclosure
    n_q_b_response_tokens: int      # for parity with R_A disclosure
    y: bool                         # NLI entailment(q_b_response, gold) ∈ {0,1}


@dataclass(frozen=True)
class StimulusFeatures:
    """Per-stimulus derived scalars used by the §15.13 cascade.

    All cosines computed in fp64 from fp32 cache values (no clipping
    required since inputs are real-valued LM hidden states; no FFT).
    """

    pair_idx: int
    q_a_idx: int
    q_b_idx: int
    cos_st_ra: float                # cos(s_t, r_a_repr)
    cos_st_qb: float                # cos(s_t, q_b_repr)
    cos_qa_qb: float                # cos(q_a_repr, q_b_repr) = R_sim
    r_inertia: float                # cos_st_ra - cos_st_qb
    r_sim: float                    # = cos_qa_qb (alias for clarity)
    y: bool


@dataclass(frozen=True)
class InertiaProbeResult:
    """Aggregate-level §15.13 probe result over all PINNED_N stimuli."""

    benchmark: str
    n_stimuli: int
    n_correct: int
    n_wrong: int
    auc_inertia: float              # AUC(-R_inertia, y); higher = better
    auc_sim: float                  # AUC(-R_sim,     y); higher = better
    dauc_inertia_vs_chance: float   # auc_inertia - 0.5
    dauc_inertia_vs_sim: float      # auc_inertia - auc_sim
    direction_held: bool            # auc_inertia >= 0.5
    r_inertia_per_stimulus: tuple[float, ...]
    r_sim_per_stimulus: tuple[float, ...]
    y_per_stimulus: tuple[bool, ...]
    operating_points: tuple[dict, ...]
    kappa_at_alpha_primary: float
    tau_star_at_alpha_primary: float
    n_r_a_tokens_per_stimulus: tuple[int, ...] = field(default_factory=tuple)
    n_q_b_response_tokens_per_stimulus: tuple[int, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class InertiaCascadeVerdict:
    """Final §15.13 cascade outcome.

    Fields mirror the spec §15.13 cascade_verdict JSON block. Numbers are
    plain floats so they serialize cleanly via json.dump(... sort_keys=True).
    """

    label: str                      # STRONG_/PARTIAL_/NO_MATERIAL_SIGNAL_IN_INERTIA
    auc_inertia: float
    auc_sim: float
    dauc_vs_chance: float
    dauc_vs_sim: float
    direction_held: bool
    rationale: str


@dataclass(frozen=True)
class InertiaAuditOutputs:
    """Top-level §15.13 packaged outputs for JSON + markdown writers."""

    schema_version: str
    benchmark: str
    qwen_model_id: str
    probe_result: InertiaProbeResult
    cascade_verdict: InertiaCascadeVerdict
    n_stimuli: int


# ===========================================================================
# Self-test boundary cases for the §15.13 cascade classifier (12 cases).
#
# Each entry: (auc_inertia, auc_sim, expected_label). PINNED per spec
# §15.13 "Pinned self-test boundary cases" table. The implementation
# script must pass all 12 at the self-test gate before any data inspection.
#
# Coverage rationale (from spec):
#   * Cases 1–3:  STRONG band entries (clean; AUC=0.75 + ΔAUC=0.05 inclusive
#                 boundary; well-separated from sim).
#   * Cases 4–6:  PARTIAL band entries (AUC just-below-STRONG; ΔAUC sim
#                 just-below-STRONG; AUC=0.66 boundary inclusive).
#   * Cases 7–9:  NO_MATERIAL via cascade-condition failure (AUC<0.66; ΔAUC
#                 sim=0 strictly; ΔAUC sim<0).
#   * Cases 10–12: NO_MATERIAL via direction-gate failure (inclusive at 0.5;
#                 strict below 0.5; both wrong-direction).
#
# Note on case 10: auc_inertia=0.50 PASSES the direction gate (gate is
# `auc_inertia < 0.5` strict, so 0.5 is admitted). It then fails STRONG
# (AUC<0.75) and PARTIAL (AUC<0.66), landing NO_MATERIAL by Step 4 default.
# ===========================================================================

SELF_TEST_CASCADE_CASES: list[tuple[float, float, str]] = [
    # 1. STRONG clean (clears all 3 conditions).
    (0.80, 0.65, "STRONG_SIGNAL_IN_INERTIA"),
    # 2. STRONG boundary at AUC=0.75 + ΔAUC sim=0.05 inclusive.
    (0.75, 0.70, "STRONG_SIGNAL_IN_INERTIA"),
    # 3. STRONG well above sim.
    (0.78, 0.20, "STRONG_SIGNAL_IN_INERTIA"),
    # 4. PARTIAL via AUC just below 0.75; ΔAUC sim=0.09>0.
    (0.74, 0.65, "PARTIAL_SIGNAL_IN_INERTIA"),
    # 5. PARTIAL via ΔAUC sim=0.04<0.05 but >0.
    (0.78, 0.74, "PARTIAL_SIGNAL_IN_INERTIA"),
    # 6. PARTIAL boundary at AUC=0.66 inclusive; ΔAUC sim=0.01.
    (0.66, 0.65, "PARTIAL_SIGNAL_IN_INERTIA"),
    # 7. NO_MATERIAL: AUC < 0.66.
    (0.65, 0.50, "NO_MATERIAL_SIGNAL_IN_INERTIA"),
    # 8. NO_MATERIAL: ΔAUC sim = 0 (not > 0).
    (0.70, 0.70, "NO_MATERIAL_SIGNAL_IN_INERTIA"),
    # 9. NO_MATERIAL: ΔAUC sim < 0 (R_inertia worse than sim).
    (0.70, 0.72, "NO_MATERIAL_SIGNAL_IN_INERTIA"),
    # 10. NO_MATERIAL: direction gate inclusive at 0.5; AUC<0.66.
    (0.50, 0.30, "NO_MATERIAL_SIGNAL_IN_INERTIA"),
    # 11. NO_MATERIAL: direction gate strict (auc_inertia<0.5).
    (0.49, 0.65, "NO_MATERIAL_SIGNAL_IN_INERTIA"),
    # 12. NO_MATERIAL: direction gate (both wrong-direction).
    (0.40, 0.40, "NO_MATERIAL_SIGNAL_IN_INERTIA"),
]

# Sanity invariant (also asserted by the self-test gate at runtime).
assert len(SELF_TEST_CASCADE_CASES) == 12, (
    f"§15.13 spec pins 12 self-test cascade cases; got "
    f"{len(SELF_TEST_CASCADE_CASES)}."
)
