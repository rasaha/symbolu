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
# Optional distractors field name in the §13.10 dump. Required by §13.10
# label_correctness (the NLI scoring helper); falls back to HF mc1_targets.
FIELD_DISTRACTORS = "distractors"

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
    q_b_distractors: tuple[str, ...]   # required by §13.10 label_correctness
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


# ===========================================================================
# §15.13 Chunk I-2 — schema validators, label/question/gold loader,
# stimulus-pair construction, lazy torch+transformers import, three-pass
# extraction (Pass 1 generate R_A + extract q_A,r_A; Pass 2 multi-turn
# forward + extract s_t + decode Q_B response + NLI score y; Pass 3
# standalone Q_B forward + extract q_B), .npz cache I/O.
#
# Mirrors §15.10/§15.11 schema-validation tightenings F1 (question
# optional + HF fallback) and F2 (duplicate-q_idx check). Extraction
# differs from §15.11 in that it gathers four hidden-state vectors per
# stimulus (q_A, r_A, s_t, q_B) at LAYER_IDX = -1 only, plus generates
# Q_B's response and runs §13.10-style NLI for the y label.
# ===========================================================================


class SchemaMismatchError(RuntimeError):
    """Raised when a §13.10 dump or §15.13 cache fails schema validation."""


def _validate_s13_10_dump(payload: object, source_path: str) -> list[dict]:
    """Validate top-level shape of a §13.10 dump and return per-question records.

    Required fields per record: q_idx (int) + greedy_matches_correct (bool).
    Optional fields: 'question' (str) and 'correct_choice' (str). If absent
    on any record, load_truthfulqa_labels falls back to the HuggingFace
    dataset by q_idx alignment.

    Duplicate q_idx triggers SCHEMA_MISMATCH (matches §15.7/§15.10/§15.11
    hardening; ascending alignment would be ambiguous).
    """
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key in ("per_question", "records", "questions"):
            if key in payload and isinstance(payload[key], list):
                records = payload[key]
                break
        else:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} top-level dict has no "
                f"'per_question'/'records'/'questions' list."
            )
    else:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: {source_path} top-level is "
            f"{type(payload).__name__}, expected list or dict."
        )

    if len(records) < PINNED_N:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: {source_path} has {len(records)} records, "
            f"need at least {PINNED_N}."
        )

    seen_qids: set[int] = set()
    for i, rec in enumerate(records[:PINNED_N]):
        if not isinstance(rec, dict):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} is "
                f"{type(rec).__name__}, expected dict."
            )
        for required in (FIELD_QID, FIELD_CORRECT):
            if required not in rec:
                raise SchemaMismatchError(
                    f"SCHEMA_MISMATCH: {source_path} record {i} missing "
                    f"required field '{required}'."
                )
        if not isinstance(rec[FIELD_QID], int):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_QID}' is {type(rec[FIELD_QID]).__name__}, "
                f"expected int."
            )
        if not isinstance(rec[FIELD_CORRECT], bool):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_CORRECT}' is "
                f"{type(rec[FIELD_CORRECT]).__name__}, expected bool."
            )
        if FIELD_QUESTION in rec and not isinstance(rec[FIELD_QUESTION], str):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_QUESTION}' is "
                f"{type(rec[FIELD_QUESTION]).__name__}, expected str."
            )
        if FIELD_CORRECT_CHOICE in rec and not isinstance(
            rec[FIELD_CORRECT_CHOICE], str
        ):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_CORRECT_CHOICE}' is "
                f"{type(rec[FIELD_CORRECT_CHOICE]).__name__}, expected str."
            )
        if FIELD_DISTRACTORS in rec:
            distractors = rec[FIELD_DISTRACTORS]
            if not isinstance(distractors, list) or not all(
                isinstance(d, str) for d in distractors
            ):
                raise SchemaMismatchError(
                    f"SCHEMA_MISMATCH: {source_path} record {i} field "
                    f"'{FIELD_DISTRACTORS}' must be a list[str]; got "
                    f"{type(distractors).__name__}."
                )
        qid = int(rec[FIELD_QID])
        if qid in seen_qids:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} duplicate "
                f"q_idx={qid}; ascending alignment would be ambiguous."
            )
        seen_qids.add(qid)
    return records


def _load_questions_and_gold_from_hf_dataset(
    q_ids: tuple[int, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Load TruthfulQA-MC question text + gold mc1 choice + distractors by
    q_idx alignment.

    Mirrors §13.10 producer's enumerate-after-select indexing
    (`scripts/probe_semantic_entropy.py`): q_idx corresponds to row index
    in the validation split.

    Returns (questions, gold_choices, distractors) tuples aligned with
    `q_ids`. Gold choice is `mc1_targets["choices"][i]` where
    `i = labels.index(1)`. Distractors are all OTHER mc1 choices (i.e.,
    those with label 0), matching §13.10's `label_correctness`
    distractor list semantics.
    """
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise ImportError(
            "§15.13 question/gold-text fallback requires the `datasets` "
            "library. Either ensure §13.10 dump records contain "
            f"'{FIELD_QUESTION}', '{FIELD_CORRECT_CHOICE}', and "
            f"'{FIELD_DISTRACTORS}', or install `datasets` on the runpod."
        ) from exc

    ds = load_dataset(
        "truthful_qa", "multiple_choice", split="validation"
    )
    n_max = max(q_ids) + 1 if q_ids else 0
    if len(ds) < n_max:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: HF TruthfulQA-MC validation has only "
            f"{len(ds)} rows; need at least {n_max} for q_idx alignment."
        )
    ds = ds.select(range(n_max))
    questions: list[str] = []
    gold_choices: list[str] = []
    distractors_per: list[tuple[str, ...]] = []
    for q_id in q_ids:
        row = ds[int(q_id)]
        questions.append(str(row["question"]))
        mc1 = row.get("mc1_targets") or {}
        choices = mc1.get("choices") or []
        labels = mc1.get("labels") or []
        if len(choices) != len(labels) or 1 not in labels:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: HF TruthfulQA-MC q_idx={q_id} has no "
                f"single mc1 correct label; choices={len(choices)}, "
                f"labels={labels!r}."
            )
        gold_idx = labels.index(1)
        gold_choices.append(str(choices[gold_idx]))
        distractors_per.append(
            tuple(str(c) for c, lb in zip(choices, labels) if lb == 0)
        )
    return tuple(questions), tuple(gold_choices), tuple(distractors_per)


def load_truthfulqa_labels() -> tuple[
    tuple[int, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[tuple[str, ...], ...],
    tuple[bool, ...],
]:
    """Load first PINNED_N records from the §13.10 TruthfulQA-MC dump.

    Returns (q_ids, questions, gold_choices, distractors_per, s13_10_
    correctness) tuples, each of length PINNED_N, aligned by record
    order in the dump.

    Question text, gold choice, and distractors come from the dump
    fields if all records have them; missing fields fall back to the
    HuggingFace TruthfulQA-MC validation split by q_idx alignment. A
    single HF load covers all missing fields when needed.

    The s13_10_correctness booleans are carried forward as disclosure-
    only sanity values; the actual y label used by the cascade is
    recomputed per spec via §13.10-style NLI on the Q_B response in
    Pass 2 (premise = Q_B + response; hypotheses = Q_B + correct,
    Q_B + each distractor).
    """
    dump_path = Path(INPUT_S13_10_TRUTHFULQA)
    if not dump_path.exists():
        raise FileNotFoundError(
            f"§13.10 TruthfulQA-MC dump not found: {dump_path}. "
            f"Required for §15.13 q_idx alignment."
        )
    with dump_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    records = _validate_s13_10_dump(payload, str(dump_path))
    head = records[:PINNED_N]
    q_ids = tuple(int(r[FIELD_QID]) for r in head)
    correctness = tuple(bool(r[FIELD_CORRECT]) for r in head)

    has_dump_questions = all(
        FIELD_QUESTION in r
        and isinstance(r[FIELD_QUESTION], str)
        and r[FIELD_QUESTION]
        for r in head
    )
    has_dump_gold = all(
        FIELD_CORRECT_CHOICE in r
        and isinstance(r[FIELD_CORRECT_CHOICE], str)
        and r[FIELD_CORRECT_CHOICE]
        for r in head
    )
    has_dump_distractors = all(
        FIELD_DISTRACTORS in r
        and isinstance(r[FIELD_DISTRACTORS], list)
        and all(isinstance(d, str) for d in r[FIELD_DISTRACTORS])
        for r in head
    )

    if has_dump_questions and has_dump_gold and has_dump_distractors:
        questions = tuple(str(r[FIELD_QUESTION]) for r in head)
        gold_choices = tuple(str(r[FIELD_CORRECT_CHOICE]) for r in head)
        distractors_per = tuple(
            tuple(str(d) for d in r[FIELD_DISTRACTORS]) for r in head
        )
    else:
        missing = []
        if not has_dump_questions:
            missing.append(f"'{FIELD_QUESTION}'")
        if not has_dump_gold:
            missing.append(f"'{FIELD_CORRECT_CHOICE}'")
        if not has_dump_distractors:
            missing.append(f"'{FIELD_DISTRACTORS}'")
        print(
            f"  truthfulqa_mc: dump lacks {', '.join(missing)} on at least "
            f"one record; loading from HuggingFace dataset by q_idx.",
            flush=True,
        )
        hf_questions, hf_gold, hf_distractors = (
            _load_questions_and_gold_from_hf_dataset(q_ids)
        )
        questions = (
            tuple(str(r[FIELD_QUESTION]) for r in head)
            if has_dump_questions
            else hf_questions
        )
        gold_choices = (
            tuple(str(r[FIELD_CORRECT_CHOICE]) for r in head)
            if has_dump_gold
            else hf_gold
        )
        distractors_per = (
            tuple(
                tuple(str(d) for d in r[FIELD_DISTRACTORS]) for r in head
            )
            if has_dump_distractors
            else hf_distractors
        )

    return q_ids, questions, gold_choices, distractors_per, correctness


def construct_stimulus_pairs(
    q_ids: tuple[int, ...],
    questions: tuple[str, ...],
    gold_choices: tuple[str, ...],
    distractors_per: tuple[tuple[str, ...], ...],
    s13_10_correctness: tuple[bool, ...],
) -> tuple[StimulusPair, ...]:
    """Build PINNED_N stimulus pairs by the pinned pairing rule.

    For i in 0..PINNED_N-1:
        pair_idx = i
        q_a_position = i
        q_b_position = (i + PAIRING_OFFSET) mod PINNED_N

    `q_a_position` and `q_b_position` index into the input arrays
    (which are already aligned with §13.10 dump record order).
    `q_a_idx` and `q_b_idx` on the resulting StimulusPair are the
    underlying §13.10 q_idx values at those positions.

    Properties (per spec):
        * PINNED_N unique pairs.
        * Each input position appears exactly once as Q_A and once as Q_B.
        * The +PAIRING_OFFSET offset randomizes topical adjacency without
          requiring a random seed.
    """
    if (
        len(q_ids) != PINNED_N
        or len(questions) != PINNED_N
        or len(gold_choices) != PINNED_N
        or len(distractors_per) != PINNED_N
        or len(s13_10_correctness) != PINNED_N
    ):
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: construct_stimulus_pairs expected "
            f"PINNED_N={PINNED_N} on all five input tuples; got "
            f"q_ids={len(q_ids)}, questions={len(questions)}, "
            f"gold_choices={len(gold_choices)}, "
            f"distractors_per={len(distractors_per)}, "
            f"s13_10_correctness={len(s13_10_correctness)}."
        )
    pairs: list[StimulusPair] = []
    for i in range(PINNED_N):
        a = i
        b = (i + PAIRING_OFFSET) % PINNED_N
        pairs.append(
            StimulusPair(
                pair_idx=i,
                q_a_idx=int(q_ids[a]),
                q_b_idx=int(q_ids[b]),
                q_a_text=str(questions[a]),
                q_b_text=str(questions[b]),
                q_b_correct_choice=str(gold_choices[b]),
                q_b_distractors=tuple(str(d) for d in distractors_per[b]),
                s13_10_correct_q_a=bool(s13_10_correctness[a]),
                s13_10_correct_q_b=bool(s13_10_correctness[b]),
            )
        )
    return tuple(pairs)


# ---------------------------------------------------------------------------
# Lazy imports for the GPU-side stack (torch + transformers; §13.10 NLI
# helper). Kept lazy so --self-test and --probe-only can run on CPU without
# requiring the heavy stack to be present.
# ---------------------------------------------------------------------------


def _lazy_import_torch_and_transformers():
    """Lazy import of torch + transformers; raises with a clear message."""
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "§15.13 hidden-state extraction requires torch + transformers. "
            "Install on the runpod GPU node before --extract-only or default."
        ) from exc
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    return torch, AutoModelForCausalLM, AutoTokenizer


def _lazy_import_nli_helper():
    """Lazy import of `build_nli_checker` + `label_correctness` from
    §13.10's `scripts/probe_semantic_entropy.py`.

    Per spec Risk 1: reuse the §13.10 scoring helper directly rather than
    reimplementing — same behavior as the original phase, including its
    known limitations (cross-phase comparability of the y label).
    """
    try:
        from transformers import (  # noqa: F401
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )
    except ImportError as exc:
        raise ImportError(
            "§15.13 NLI scoring requires transformers (for the §13.10 "
            "DeBERTa NLI scorer). Install on the runpod GPU node."
        ) from exc

    # Add repo-root to sys.path so the §13.10 module can be imported by
    # name even when this script is invoked via `python scripts/...`.
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from scripts.probe_semantic_entropy import (
            build_nli_checker,
            label_correctness,
        )
    except ImportError as exc:
        raise ImportError(
            "§15.13 expected to import build_nli_checker + label_correctness "
            "from scripts/probe_semantic_entropy.py (the §13.10 producer). "
            "Verify the repo layout."
        ) from exc

    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )

    return (
        build_nli_checker,
        label_correctness,
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )


# NLI model id pinned per §13.10; reused for §15.13 y label scoring per
# spec Risk 1 mitigation.
NLI_MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


# ---------------------------------------------------------------------------
# Three-pass extraction helpers.
#
# Pass 1: chat-template prompt over Q_A → greedy decode 64 tokens.
#         Extracts q_a_repr (last-token, layer −1, pre-decode) and
#         r_a_repr (mean over generated assistant token positions).
#
# Pass 2: chat-template multi-turn prompt over Q_A + verbatim Pass-1
#         r_a_text + Q_B → greedy decode 64 tokens.
#         Extracts s_t (last-token, layer −1, at the second [ASSISTANT]
#         tag position pre-decode) and decodes q_b_response_text.
#
# Pass 3: chat-template prompt over Q_B alone (standalone, no decode).
#         Extracts q_b_repr (last-token, layer −1).
#
# Splicing Pass-1's verbatim r_a_text into Pass-2's prompt guarantees
# byte-identical R_A across passes (Risk 3 mitigation per spec).
# ---------------------------------------------------------------------------


def _build_chat_prompt_q_only_ids(tokenizer, q_text: str, *, device):
    """Tokenize chat-template prompt for [SYS][USER]q_text[ASSISTANT]_."""
    msgs = [{"role": "user", "content": q_text}]
    input_ids = tokenizer.apply_chat_template(
        msgs,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to(device)
    return input_ids


def _build_chat_prompt_multiturn_ids(
    tokenizer, q_a_text: str, r_a_text: str, q_b_text: str, *, device
):
    """Tokenize multi-turn chat prompt with Q_A → R_A → Q_B → assistant tag.

    Pass 1's decoded r_a_text is spliced verbatim (Risk 3 mitigation).
    """
    msgs = [
        {"role": "user", "content": q_a_text},
        {"role": "assistant", "content": r_a_text},
        {"role": "user", "content": q_b_text},
    ]
    input_ids = tokenizer.apply_chat_template(
        msgs,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to(device)
    return input_ids


def _resolve_chat_end_token_ids(tokenizer) -> set[int]:
    """Return the set of token ids that mark end-of-assistant-turn for
    Qwen's chat template.

    Includes the tokenizer's eos_token_id and the Qwen `<|im_end|>` id
    when it is distinct. Used to truncate the generated portion before
    the chat-end marker so r_a_repr pools only over actual generated
    content (Risk 6 mitigation).
    """
    end_ids: set[int] = set()
    if tokenizer.eos_token_id is not None:
        end_ids.add(int(tokenizer.eos_token_id))
    try:
        im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
        if (
            isinstance(im_end_id, int)
            and im_end_id >= 0
            and im_end_id != tokenizer.unk_token_id
        ):
            end_ids.add(int(im_end_id))
    except Exception:
        pass
    return end_ids


def _greedy_decode_and_collect(
    model,
    tokenizer,
    prompt_input_ids,
    *,
    device,
    max_new_tokens: int,
):
    """Greedy-decode `max_new_tokens` from the prompt, then forward over
    the (truncated) prompt+generated sequence with output_hidden_states.

    Returns:
        prompt_repr   : np.ndarray fp32 (HIDDEN_DIM,) — last-layer hidden
                        state at the last prompt-token position (the
                        "ready-to-answer" anchor).
        generated_repr: np.ndarray fp32 (HIDDEN_DIM,) — mean over
                        last-layer hidden states at the generated token
                        positions.
        generated_text: str — decoded generated tokens (truncated at
                        first chat-end / eos token; skip_special_tokens).
        n_generated   : int — |T_A|; count of non-end generated tokens
                        used for pooling.
    """
    import torch

    prompt_len = int(prompt_input_ids.shape[1])
    pad_id = tokenizer.pad_token_id
    if pad_id is None:
        pad_id = tokenizer.eos_token_id
    with torch.inference_mode():
        gen_out = model.generate(
            input_ids=prompt_input_ids,
            attention_mask=torch.ones_like(prompt_input_ids),
            max_new_tokens=max_new_tokens,
            do_sample=False,
            num_beams=1,
            pad_token_id=pad_id,
        )
        full_ids = gen_out  # (1, prompt_len + n_gen_raw)
        if full_ids.shape[0] != 1:
            raise RuntimeError(
                f"EXTRACTION_FAILED: greedy generate returned batch dim "
                f"{full_ids.shape[0]}, expected 1."
            )
        gen_ids = full_ids[0, prompt_len:].tolist()
        end_ids = _resolve_chat_end_token_ids(tokenizer)
        n_generated = len(gen_ids)
        for i, tid in enumerate(gen_ids):
            if int(tid) in end_ids:
                n_generated = i
                break
        if n_generated == 0:
            raise RuntimeError(
                "EXTRACTION_FAILED: greedy decode produced 0 non-end "
                "tokens before chat-end marker; cannot pool generated_repr."
            )
        truncated_ids = full_ids[:, : prompt_len + n_generated]
        generated_text = tokenizer.decode(
            truncated_ids[0, prompt_len:], skip_special_tokens=True
        )

        out = model(
            input_ids=truncated_ids,
            attention_mask=torch.ones_like(truncated_ids),
            output_hidden_states=True,
        )
        hs_last = out.hidden_states[LAYER_IDX]  # (1, L, HIDDEN_DIM)
        if hs_last.shape != (1, prompt_len + n_generated, HIDDEN_DIM):
            raise RuntimeError(
                f"EXTRACTION_FAILED: layer{LAYER_IDX} hidden state shape "
                f"{tuple(hs_last.shape)} != expected "
                f"(1, {prompt_len + n_generated}, {HIDDEN_DIM})."
            )
        prompt_repr = (
            hs_last[0, prompt_len - 1, :].detach().to("cpu").float().numpy()
        )
        gen_block = hs_last[0, prompt_len : prompt_len + n_generated, :]
        generated_repr = (
            gen_block.mean(dim=0).detach().to("cpu").float().numpy()
        )

    return (
        prompt_repr.astype(np.float32),
        generated_repr.astype(np.float32),
        str(generated_text),
        int(n_generated),
    )


def _forward_only_last_token_repr(
    model, tokenizer, prompt_input_ids, *, device
):
    """Forward pass over prompt only (no decoding); return the last-token
    last-layer hidden state as fp32 np.ndarray (HIDDEN_DIM,).
    """
    import torch

    with torch.inference_mode():
        out = model(
            input_ids=prompt_input_ids,
            attention_mask=torch.ones_like(prompt_input_ids),
            output_hidden_states=True,
        )
    hs_last = out.hidden_states[LAYER_IDX]
    if hs_last.shape[-1] != HIDDEN_DIM:
        raise RuntimeError(
            f"EXTRACTION_FAILED: layer{LAYER_IDX} hidden state hidden_dim "
            f"{hs_last.shape[-1]} != expected {HIDDEN_DIM}."
        )
    last_repr = hs_last[0, -1, :].detach().to("cpu").float().numpy()
    return last_repr.astype(np.float32)


def extract_stimulus_three_passes(
    pair: StimulusPair,
    *,
    model,
    tokenizer,
    nli_check_batch,
    label_correctness_fn,
    device: str,
) -> StimulusExtraction:
    """Run the three pinned forward passes for one stimulus.

    Pass 1: Q_A-only chat prompt → greedy decode (≤MAX_NEW_TOKENS) →
            extracts q_a_repr (prompt-end last-token) and r_a_repr (mean
            over generated assistant token positions); records r_a_text.
    Pass 2: multi-turn chat prompt with Pass-1's verbatim r_a_text
            spliced in → greedy decode (≤MAX_NEW_TOKENS) → extracts s_t
            (prompt-end last-token at the second [ASSISTANT] tag) and
            records q_b_response_text.
    Pass 3: Q_B-only chat prompt → forward only (no decode) → extracts
            q_b_repr (prompt-end last-token).

    NLI scoring (y label): premise = `q_b_text + " " + q_b_response_text`;
    hypotheses = `q_b_text + " " + each candidate (gold + distractors)`.
    y = entails(gold) AND NOT entails(any distractor) — exactly §13.10's
    `label_correctness` semantics.
    """
    # Pass 1.
    p1_ids = _build_chat_prompt_q_only_ids(
        tokenizer, pair.q_a_text, device=device
    )
    q_a_repr, r_a_repr, r_a_text, n_r_a_tokens = _greedy_decode_and_collect(
        model, tokenizer, p1_ids, device=device, max_new_tokens=MAX_NEW_TOKENS
    )

    # Pass 2 — splice Pass 1's verbatim r_a_text into the multi-turn prompt
    # (Risk 3 mitigation: byte-identical R_A across passes).
    p2_ids = _build_chat_prompt_multiturn_ids(
        tokenizer,
        pair.q_a_text,
        r_a_text,
        pair.q_b_text,
        device=device,
    )
    s_t, _q_b_resp_traj_unused, q_b_response_text, n_q_b_response_tokens = (
        _greedy_decode_and_collect(
            model,
            tokenizer,
            p2_ids,
            device=device,
            max_new_tokens=MAX_NEW_TOKENS,
        )
    )

    # Pass 3 — standalone Q_B (no decoding).
    p3_ids = _build_chat_prompt_q_only_ids(
        tokenizer, pair.q_b_text, device=device
    )
    q_b_repr = _forward_only_last_token_repr(
        model, tokenizer, p3_ids, device=device
    )

    # NLI scoring of the Q_B response (y label) — §13.10-style.
    y_bool = bool(
        label_correctness_fn(
            q_b_response_text,
            pair.q_b_correct_choice,
            list(pair.q_b_distractors),
            nli_check_batch,
            pair.q_b_text,
        )
    )

    # Shape sanity (defensive — the per-helper checks should have
    # already failed earlier if these don't hold).
    for name, vec in (
        ("q_a_repr", q_a_repr),
        ("r_a_repr", r_a_repr),
        ("s_t", s_t),
        ("q_b_repr", q_b_repr),
    ):
        if vec.shape != (HIDDEN_DIM,):
            raise RuntimeError(
                f"EXTRACTION_FAILED: pair {pair.pair_idx} {name} shape "
                f"{vec.shape}, expected ({HIDDEN_DIM},)."
            )
        if vec.dtype != np.float32:
            raise RuntimeError(
                f"EXTRACTION_FAILED: pair {pair.pair_idx} {name} dtype "
                f"{vec.dtype}, expected float32."
            )

    return StimulusExtraction(
        pair_idx=int(pair.pair_idx),
        q_a_idx=int(pair.q_a_idx),
        q_b_idx=int(pair.q_b_idx),
        q_a_repr=q_a_repr,
        r_a_repr=r_a_repr,
        s_t=s_t,
        q_b_repr=q_b_repr,
        r_a_text=str(r_a_text),
        q_b_response_text=str(q_b_response_text),
        n_r_a_tokens=int(n_r_a_tokens),
        n_q_b_response_tokens=int(n_q_b_response_tokens),
        y=y_bool,
    )


# ---------------------------------------------------------------------------
# .npz cache I/O.
#
# Schema (PINNED per spec output schema):
#   pair_idx          int64,   shape (PINNED_N,)
#   q_a_idx           int64,   shape (PINNED_N,)
#   q_b_idx           int64,   shape (PINNED_N,)
#   q_a_repr          float32, shape (PINNED_N, HIDDEN_DIM)
#   r_a_repr          float32, shape (PINNED_N, HIDDEN_DIM)
#   s_t               float32, shape (PINNED_N, HIDDEN_DIM)
#   q_b_repr          float32, shape (PINNED_N, HIDDEN_DIM)
#   y                 bool,    shape (PINNED_N,)
#   r_a_text          object,  shape (PINNED_N,)
#   q_b_response_text object,  shape (PINNED_N,)
#   n_r_a_tokens          int64, shape (PINNED_N,)  # disclosure-only
#   n_q_b_response_tokens int64, shape (PINNED_N,)  # disclosure-only
#
# Approximate size: 4 × 100 × 3584 × 4 bytes ≈ 5.6 MB + text overhead.
# ---------------------------------------------------------------------------

_CACHE_HIDDEN_KEYS = ("q_a_repr", "r_a_repr", "s_t", "q_b_repr")
_CACHE_TEXT_KEYS = ("r_a_text", "q_b_response_text")
_CACHE_INT_KEYS = (
    "pair_idx",
    "q_a_idx",
    "q_b_idx",
    "n_r_a_tokens",
    "n_q_b_response_tokens",
)
_CACHE_BOOL_KEYS = ("y",)


def save_extractions_cache(
    extractions: tuple[StimulusExtraction, ...], path: str
) -> None:
    """Persist per-stimulus extractions to a single .npz file (spec schema)."""
    if len(extractions) != PINNED_N:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: expected {PINNED_N} extractions, got "
            f"{len(extractions)} for cache write."
        )

    pair_idx = np.asarray([e.pair_idx for e in extractions], dtype=np.int64)
    q_a_idx = np.asarray([e.q_a_idx for e in extractions], dtype=np.int64)
    q_b_idx = np.asarray([e.q_b_idx for e in extractions], dtype=np.int64)
    q_a_repr = np.stack([e.q_a_repr for e in extractions], axis=0).astype(
        np.float32
    )
    r_a_repr = np.stack([e.r_a_repr for e in extractions], axis=0).astype(
        np.float32
    )
    s_t = np.stack([e.s_t for e in extractions], axis=0).astype(np.float32)
    q_b_repr = np.stack([e.q_b_repr for e in extractions], axis=0).astype(
        np.float32
    )
    y = np.asarray([e.y for e in extractions], dtype=np.bool_)
    r_a_text = np.asarray(
        [e.r_a_text for e in extractions], dtype=object
    )
    q_b_response_text = np.asarray(
        [e.q_b_response_text for e in extractions], dtype=object
    )
    n_r_a_tokens = np.asarray(
        [e.n_r_a_tokens for e in extractions], dtype=np.int64
    )
    n_q_b_response_tokens = np.asarray(
        [e.n_q_b_response_tokens for e in extractions], dtype=np.int64
    )

    expected_hidden_shape = (PINNED_N, HIDDEN_DIM)
    for name, arr in (
        ("q_a_repr", q_a_repr),
        ("r_a_repr", r_a_repr),
        ("s_t", s_t),
        ("q_b_repr", q_b_repr),
    ):
        if arr.shape != expected_hidden_shape:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache write {name} shape {arr.shape}, "
                f"expected {expected_hidden_shape}."
            )

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        pair_idx=pair_idx,
        q_a_idx=q_a_idx,
        q_b_idx=q_b_idx,
        q_a_repr=q_a_repr,
        r_a_repr=r_a_repr,
        s_t=s_t,
        q_b_repr=q_b_repr,
        y=y,
        r_a_text=r_a_text,
        q_b_response_text=q_b_response_text,
        n_r_a_tokens=n_r_a_tokens,
        n_q_b_response_tokens=n_q_b_response_tokens,
    )


def load_extractions_cache(path: str) -> tuple[StimulusExtraction, ...]:
    """Load per-stimulus extractions from an .npz file written by
    save_extractions_cache. Validates pinned shapes / dtypes / counts."""
    cache_path = Path(path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"§15.13 extractions cache not found: {cache_path}. "
            f"Run --extract-only first or default to populate."
        )
    npz = np.load(cache_path, allow_pickle=True)
    required = (
        _CACHE_HIDDEN_KEYS
        + _CACHE_TEXT_KEYS
        + _CACHE_INT_KEYS
        + _CACHE_BOOL_KEYS
    )
    for key in required:
        if key not in npz.files:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} missing key {key!r}."
            )

    expected_hidden_shape = (PINNED_N, HIDDEN_DIM)
    for key in _CACHE_HIDDEN_KEYS:
        arr = npz[key]
        if arr.shape != expected_hidden_shape:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} {key} shape "
                f"{arr.shape}, expected {expected_hidden_shape}."
            )
        if arr.dtype != np.float32:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} {key} dtype "
                f"{arr.dtype}, expected float32."
            )

    for key in _CACHE_INT_KEYS:
        arr = npz[key]
        if arr.shape != (PINNED_N,):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} {key} shape "
                f"{arr.shape}, expected ({PINNED_N},)."
            )
    if npz["y"].shape != (PINNED_N,):
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: cache {cache_path} 'y' shape "
            f"{npz['y'].shape}, expected ({PINNED_N},)."
        )
    for key in _CACHE_TEXT_KEYS:
        arr = npz[key]
        if arr.shape != (PINNED_N,):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} {key} shape "
                f"{arr.shape}, expected ({PINNED_N},)."
            )

    extractions: list[StimulusExtraction] = []
    for i in range(PINNED_N):
        extractions.append(
            StimulusExtraction(
                pair_idx=int(npz["pair_idx"][i]),
                q_a_idx=int(npz["q_a_idx"][i]),
                q_b_idx=int(npz["q_b_idx"][i]),
                q_a_repr=np.asarray(npz["q_a_repr"][i], dtype=np.float32),
                r_a_repr=np.asarray(npz["r_a_repr"][i], dtype=np.float32),
                s_t=np.asarray(npz["s_t"][i], dtype=np.float32),
                q_b_repr=np.asarray(npz["q_b_repr"][i], dtype=np.float32),
                r_a_text=str(npz["r_a_text"][i]),
                q_b_response_text=str(npz["q_b_response_text"][i]),
                n_r_a_tokens=int(npz["n_r_a_tokens"][i]),
                n_q_b_response_tokens=int(npz["n_q_b_response_tokens"][i]),
                y=bool(npz["y"][i]),
            )
        )
    return tuple(extractions)


# ===========================================================================
# §15.13 Chunk I-3 — derived features (R_inertia, R_sim, cosines), selective-
# prediction κ@α at the pinned alphas (disclosure-only), aggregate probe run
# (run_inertia_probe), and the §15.13 cascade classifier with direction gate
# + dual-comparator (chance + R_sim) STRONG/PARTIAL bands.
#
# Formula recap (PINNED):
#     R_inertia = cos(s_t, r_a) - cos(s_t, q_b)        # primary signal
#     R_sim     = cos(q_a, q_b)                        # comparator
#     auc_inertia = AUC(-R_inertia, y)
#     auc_sim     = AUC(-R_sim,     y)
# Higher AUC → better signal in the BCVF-faithful direction
# (lower R_* predicts correct).
#
# Cosines computed in fp64 from fp32 cache values. No clipping required
# since inputs are real-valued LM hidden states (no FFT).
# ===========================================================================


def _cosine_fp64(a: np.ndarray, b: np.ndarray) -> float:
    """Numerically-stable cosine similarity between two 1-D vectors.

    Casts to fp64 before computing dot/norm to limit accumulation error
    on 3584-dim residual-stream vectors. Returns NaN if either norm is
    zero (caller should treat that as PROBE_FAILED — pinned hidden states
    should never be exactly zero).
    """
    if a.shape != b.shape:
        raise ValueError(
            f"_cosine_fp64 shape mismatch: {a.shape} vs {b.shape}"
        )
    if a.ndim != 1:
        raise ValueError(
            f"_cosine_fp64 expected 1-D vectors; got {a.ndim}-D"
        )
    a64 = a.astype(np.float64, copy=False)
    b64 = b.astype(np.float64, copy=False)
    na = float(np.linalg.norm(a64))
    nb = float(np.linalg.norm(b64))
    if na == 0.0 or nb == 0.0:
        return float("nan")
    return float(np.dot(a64, b64) / (na * nb))


def compute_features_per_stimulus(
    extraction: StimulusExtraction,
) -> StimulusFeatures:
    """Derive the §15.13 per-stimulus scalars.

    cos_st_ra = cos(s_t, r_a_repr)           # alignment with prior answer
    cos_st_qb = cos(s_t, q_b_repr)           # alignment with new question
    cos_qa_qb = cos(q_a_repr, q_b_repr)      # baseline question-similarity
    R_inertia = cos_st_ra - cos_st_qb        # primary signal
    R_sim     = cos_qa_qb                    # comparator baseline
    """
    cos_st_ra = _cosine_fp64(extraction.s_t, extraction.r_a_repr)
    cos_st_qb = _cosine_fp64(extraction.s_t, extraction.q_b_repr)
    cos_qa_qb = _cosine_fp64(extraction.q_a_repr, extraction.q_b_repr)
    if not all(math.isfinite(v) for v in (cos_st_ra, cos_st_qb, cos_qa_qb)):
        raise RuntimeError(
            f"PROBE_FAILED: pair {extraction.pair_idx} produced non-finite "
            f"cosine "
            f"(cos_st_ra={cos_st_ra}, cos_st_qb={cos_st_qb}, "
            f"cos_qa_qb={cos_qa_qb}); a hidden state may be the zero vector."
        )
    r_inertia = cos_st_ra - cos_st_qb
    return StimulusFeatures(
        pair_idx=int(extraction.pair_idx),
        q_a_idx=int(extraction.q_a_idx),
        q_b_idx=int(extraction.q_b_idx),
        cos_st_ra=float(cos_st_ra),
        cos_st_qb=float(cos_st_qb),
        cos_qa_qb=float(cos_qa_qb),
        r_inertia=float(r_inertia),
        r_sim=float(cos_qa_qb),
        y=bool(extraction.y),
    )


def compute_features_all(
    extractions: tuple[StimulusExtraction, ...],
) -> tuple[StimulusFeatures, ...]:
    """Vectorize compute_features_per_stimulus over all PINNED_N stimuli."""
    if len(extractions) != PINNED_N:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: compute_features_all expected {PINNED_N} "
            f"extractions; got {len(extractions)}."
        )
    return tuple(compute_features_per_stimulus(e) for e in extractions)


# ---------------------------------------------------------------------------
# Lazy sklearn import + selective-prediction κ@α (mirrors §15.11). Operating
# points are reported in the JSON / MD output for transparency but do NOT
# enter the cascade decision per spec.
# ---------------------------------------------------------------------------


def _lazy_import_sklearn():
    """Lazy import of `roc_auc_score` from sklearn."""
    try:
        from sklearn.metrics import roc_auc_score  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "§15.13 inertia probe requires scikit-learn for "
            "roc_auc_score. Install before --probe-only or default."
        ) from exc
    from sklearn.metrics import roc_auc_score

    return roc_auc_score


def _selective_kappa_at_alpha(
    score: np.ndarray, y: np.ndarray, alpha: float
) -> tuple[float, float, dict]:
    """κ@α: maximum coverage achieved at threshold τ* with conditional
    accuracy ≥ α and at least N_MIN admitted.

    score is the abstention score; admit iff score >= τ. Per §15.13 spec
    the score for selective prediction is `-R_inertia` (higher = more
    confident the model will be correct). `y` is the boolean correctness
    label cast to int.

    Returns (best_kappa, tau_star, operating_point_dict). The dict matches
    the §15.10 / §15.11 selective-prediction operating-point schema and
    is what gets serialized into the JSON output.
    """
    n = int(len(score))
    if n != int(len(y)):
        raise ValueError("score and y length mismatch")
    thresholds = sorted(
        set([float(score.min() - 1.0)] + [float(v) for v in score])
    )
    operating_point: dict = {
        "alpha": float(alpha),
        "tau_star": float("nan"),
        "kappa_at_alpha": 0.0,
        "coverage_at_tau_star": 0.0,
        "conditional_accuracy_at_tau_star": float("nan"),
        "n_admitted_at_tau_star": 0,
        "eligible": False,
    }
    best_kappa = 0.0
    for tau in thresholds:
        admitted = score >= tau
        n_adm = int(admitted.sum())
        if n_adm < N_MIN:
            continue
        cond_acc = float(y[admitted].mean())
        if cond_acc < alpha:
            continue
        coverage = n_adm / n
        if coverage > best_kappa:
            best_kappa = coverage
            operating_point.update(
                tau_star=float(tau),
                kappa_at_alpha=float(coverage),
                coverage_at_tau_star=float(coverage),
                conditional_accuracy_at_tau_star=float(cond_acc),
                n_admitted_at_tau_star=int(n_adm),
                eligible=True,
            )
    return best_kappa, operating_point["tau_star"], operating_point


# ---------------------------------------------------------------------------
# Aggregate-level §15.13 probe run.
# ---------------------------------------------------------------------------


def run_inertia_probe(
    extractions: tuple[StimulusExtraction, ...],
    features: Optional[tuple[StimulusFeatures, ...]] = None,
) -> InertiaProbeResult:
    """Compute per-stimulus features (if not provided), aggregate AUCs vs
    chance and vs R_sim, and selective-prediction operating points.

    Aggregate computations (per spec):
        auc_inertia = roc_auc_score(y, -R_inertia_array)
        auc_sim     = roc_auc_score(y, -R_sim_array)
        dauc_vs_chance = auc_inertia - 0.5
        dauc_vs_sim    = auc_inertia - auc_sim
        direction_held = (auc_inertia >= 0.5)

    The negation in `roc_auc_score(y, -R_*)` reflects the BCVF-faithful
    direction convention: lower R_* predicts correct, so the score for
    AUC must be flipped sign. After negation: higher score → predicts
    correct.

    Selective-prediction operating points are computed at the pinned
    alphas (0.35, 0.50, 0.75) using `-R_inertia` as the abstention score.
    These are disclosure-only — they do NOT enter the cascade decision.
    """
    roc_auc_score = _lazy_import_sklearn()

    if features is None:
        features = compute_features_all(extractions)
    if len(features) != PINNED_N:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: run_inertia_probe expected {PINNED_N} "
            f"features; got {len(features)}."
        )

    r_inertia = np.asarray(
        [f.r_inertia for f in features], dtype=np.float64
    )
    r_sim = np.asarray([f.r_sim for f in features], dtype=np.float64)
    y_arr = np.asarray([f.y for f in features], dtype=np.int64)
    if not np.all(np.isfinite(r_inertia)) or not np.all(np.isfinite(r_sim)):
        raise RuntimeError(
            "PROBE_FAILED: non-finite R_inertia or R_sim entry; "
            "investigate before running cascade."
        )

    n_stimuli = int(y_arr.shape[0])
    n_correct = int(y_arr.sum())
    n_wrong = int(n_stimuli - n_correct)
    if n_correct == 0 or n_wrong == 0:
        raise RuntimeError(
            f"PROBE_FAILED: degenerate label distribution "
            f"(n_correct={n_correct}, n_wrong={n_wrong}); AUC undefined."
        )

    auc_inertia = float(roc_auc_score(y_arr, -r_inertia))
    auc_sim = float(roc_auc_score(y_arr, -r_sim))
    dauc_vs_chance = float(auc_inertia - CHANCE_BASELINE_AUC)
    dauc_vs_sim = float(auc_inertia - auc_sim)
    direction_held = bool(auc_inertia >= DIRECTION_GATE_THRESHOLD)

    # Selective-prediction κ@α at the pinned alphas (disclosure only).
    score_for_kappa = -r_inertia
    operating_points: list[dict] = []
    primary_kappa = 0.0
    primary_tau = float("nan")
    for alpha in ALPHA_TARGETS:
        kappa, tau, op = _selective_kappa_at_alpha(
            score_for_kappa, y_arr, float(alpha)
        )
        operating_points.append(op)
        if math.isclose(alpha, ALPHA_PRIMARY, abs_tol=1e-9):
            primary_kappa = kappa
            primary_tau = tau

    if not any(
        math.isclose(op["alpha"], ALPHA_PRIMARY, abs_tol=1e-9)
        for op in operating_points
    ):
        kappa, tau, op = _selective_kappa_at_alpha(
            score_for_kappa, y_arr, float(ALPHA_PRIMARY)
        )
        operating_points.append(op)
        primary_kappa = kappa
        primary_tau = tau

    return InertiaProbeResult(
        benchmark=BENCHMARK,
        n_stimuli=n_stimuli,
        n_correct=n_correct,
        n_wrong=n_wrong,
        auc_inertia=auc_inertia,
        auc_sim=auc_sim,
        dauc_inertia_vs_chance=dauc_vs_chance,
        dauc_inertia_vs_sim=dauc_vs_sim,
        direction_held=direction_held,
        r_inertia_per_stimulus=tuple(float(v) for v in r_inertia),
        r_sim_per_stimulus=tuple(float(v) for v in r_sim),
        y_per_stimulus=tuple(bool(v) for v in y_arr),
        operating_points=tuple(operating_points),
        kappa_at_alpha_primary=float(primary_kappa),
        tau_star_at_alpha_primary=float(primary_tau),
        n_r_a_tokens_per_stimulus=tuple(
            int(e.n_r_a_tokens) for e in extractions
        ),
        n_q_b_response_tokens_per_stimulus=tuple(
            int(e.n_q_b_response_tokens) for e in extractions
        ),
    )


# ---------------------------------------------------------------------------
# §15.13 cascade classifier. Three steps in mechanical order
# (PINNED per spec §15.13 cascade structure):
#
#   Step 1 — Direction gate (PINNED):
#     If auc_inertia < 0.5 → NO_MATERIAL_SIGNAL_IN_INERTIA. Skip rest.
#     (BCVF-faithful direction failure; no sign-flip rescue.)
#
#   Step 2 — STRONG check:
#     If auc_inertia ≥ 0.75 AND
#        (auc_inertia − 0.5) ≥ 0.05 AND
#        (auc_inertia − auc_sim) ≥ 0.05
#     → STRONG_SIGNAL_IN_INERTIA.
#
#   Step 3 — PARTIAL check:
#     If not STRONG, AND
#        auc_inertia ≥ 0.66 AND
#        (auc_inertia − 0.5) > 0 AND
#        (auc_inertia − auc_sim) > 0
#     → PARTIAL_SIGNAL_IN_INERTIA.
#
#   Step 4 — Default:
#     Otherwise → NO_MATERIAL_SIGNAL_IN_INERTIA.
#
# The dual-comparator requirement (chance + R_sim) is the strict version
# enforced per spec — R_inertia must beat the topic-similarity baseline,
# not merely chance.
# ---------------------------------------------------------------------------


def classify_cascade_inertia(
    auc_inertia: float, auc_sim: float
) -> InertiaCascadeVerdict:
    """Apply the §15.13 3-step cascade. Inputs are AUC(-R_*, y) values."""
    auc_inertia = float(auc_inertia)
    auc_sim = float(auc_sim)
    dauc_vs_chance = auc_inertia - CHANCE_BASELINE_AUC
    dauc_vs_sim = auc_inertia - auc_sim
    direction_held = bool(auc_inertia >= DIRECTION_GATE_THRESHOLD)

    # Step 1 — Direction gate.
    if not direction_held:
        rationale = (
            f"NO_MATERIAL (direction gate): wrong-direction failure. "
            f"BCVF-faithful direction (lower R_inertia predicts correct) "
            f"did not hold (auc_inertia = {auc_inertia:.3f} < "
            f"{DIRECTION_GATE_THRESHOLD}). No sign-flip rescue per §0.8."
        )
        return InertiaCascadeVerdict(
            label="NO_MATERIAL_SIGNAL_IN_INERTIA",
            auc_inertia=auc_inertia,
            auc_sim=auc_sim,
            dauc_vs_chance=float(dauc_vs_chance),
            dauc_vs_sim=float(dauc_vs_sim),
            direction_held=direction_held,
            rationale=rationale,
        )

    # Step 2 — STRONG check (dual comparator inclusive).
    is_strong = (
        auc_inertia >= STRONG_AUC_THRESHOLD
        and dauc_vs_chance >= STRONG_DELTA_AUC_THRESHOLD
        and dauc_vs_sim >= STRONG_DELTA_AUC_THRESHOLD
    )
    if is_strong:
        rationale = (
            f"STRONG: auc_inertia = {auc_inertia:.3f} ≥ "
            f"{STRONG_AUC_THRESHOLD}; ΔAUC vs chance = "
            f"{dauc_vs_chance:+.3f} ≥ +{STRONG_DELTA_AUC_THRESHOLD}; "
            f"ΔAUC vs R_sim = {dauc_vs_sim:+.3f} ≥ "
            f"+{STRONG_DELTA_AUC_THRESHOLD} (auc_sim = {auc_sim:.3f})."
        )
        return InertiaCascadeVerdict(
            label="STRONG_SIGNAL_IN_INERTIA",
            auc_inertia=auc_inertia,
            auc_sim=auc_sim,
            dauc_vs_chance=float(dauc_vs_chance),
            dauc_vs_sim=float(dauc_vs_sim),
            direction_held=direction_held,
            rationale=rationale,
        )

    # Step 3 — PARTIAL check (dual comparator strictly positive).
    is_partial = (
        auc_inertia >= PARTIAL_AUC_THRESHOLD
        and dauc_vs_chance > 0.0
        and dauc_vs_sim > 0.0
    )
    if is_partial:
        rationale = (
            f"PARTIAL: not STRONG; auc_inertia = {auc_inertia:.3f} ≥ "
            f"{PARTIAL_AUC_THRESHOLD}; ΔAUC vs chance = "
            f"{dauc_vs_chance:+.3f} > 0; ΔAUC vs R_sim = "
            f"{dauc_vs_sim:+.3f} > 0 (auc_sim = {auc_sim:.3f})."
        )
        return InertiaCascadeVerdict(
            label="PARTIAL_SIGNAL_IN_INERTIA",
            auc_inertia=auc_inertia,
            auc_sim=auc_sim,
            dauc_vs_chance=float(dauc_vs_chance),
            dauc_vs_sim=float(dauc_vs_sim),
            direction_held=direction_held,
            rationale=rationale,
        )

    # Step 4 — Default.
    rationale = (
        f"NO_MATERIAL: direction held (auc_inertia = {auc_inertia:.3f} ≥ "
        f"{DIRECTION_GATE_THRESHOLD}), but neither STRONG nor PARTIAL "
        f"conditions met. ΔAUC vs chance = {dauc_vs_chance:+.3f}; "
        f"ΔAUC vs R_sim = {dauc_vs_sim:+.3f} (auc_sim = {auc_sim:.3f})."
    )
    return InertiaCascadeVerdict(
        label="NO_MATERIAL_SIGNAL_IN_INERTIA",
        auc_inertia=auc_inertia,
        auc_sim=auc_sim,
        dauc_vs_chance=float(dauc_vs_chance),
        dauc_vs_sim=float(dauc_vs_sim),
        direction_held=direction_held,
        rationale=rationale,
    )


# ===========================================================================
# §15.13 Chunk I-4a — interpretation firewall.
#
# Match policy (PINNED per spec §15.13 Class-3 firewall section):
#   * Non-§ patterns: case-insensitive substring match.
#   * §-anchored patterns (start with "§"): literal (case-sensitive)
#     substring match — preserves precise §-numbering.
#
# Detection on rendered markdown → exit code 4 (INTERPRETATION_VIOLATION)
# without writing the file.
# ===========================================================================


def scan_for_forbidden_patterns(text: str) -> list[str]:
    """Return Class-3 forbidden patterns found in `text`.

    Case-insensitive for non-§ patterns; literal (case-sensitive) for
    §-anchored patterns to preserve precise §-numbering.
    """
    found: list[str] = []
    lowered = text.lower()
    for pattern in CLASS_3_FORBIDDEN_PATTERNS:
        if pattern.startswith("§"):
            if pattern in text:
                found.append(pattern)
        else:
            if pattern.lower() in lowered:
                found.append(pattern)
    return found


def enforce_firewall_or_exit(text: str, output_path: str) -> None:
    """Scan `text`; if any Class-3 forbidden patterns are found, print
    INTERPRETATION_VIOLATION and exit 4 without writing.

    Per spec §15.13 §0.8-binding firewall behavior: the cascade verdict
    is binding regardless of post-hoc interpretation. Override-language
    in the rendered markdown is refused.
    """
    violations = scan_for_forbidden_patterns(text)
    if violations:
        print(
            f"INTERPRETATION_VIOLATION: refused to write {output_path}.",
            flush=True,
        )
        print("  detected Class-3 forbidden statement(s):", flush=True)
        for v in violations:
            print(f"    - {v!r}", flush=True)
        print(
            "  rewrite the offending sentence(s) to remove the override "
            "language; the §15.13 cascade verdict is binding.",
            flush=True,
        )
        sys.exit(4)


# ===========================================================================
# §15.13 Chunk I-4b — self-test gate.
#
# Three required sub-tests (per spec §15.13 Chunk plan I-4b):
#   1. 12 cascade boundary cases against classify_cascade_inertia.
#   2. Cosine invariants on synthetic data (identity, symmetry,
#      anti-parallel, orthogonality).
#   3. Firewall coverage (44 positive + clean §15.13-style negative).
#
# Any failure exits 3 (SELF_TEST_FAILED). Required pre-execution gate:
# the runpod must run `--self-test` and see exit code 0 before
# `--extract-only` or default full pipeline per §15.13 §0.8 discipline.
# ===========================================================================


def _self_test_cascade() -> list[str]:
    """Run all SELF_TEST_CASCADE_CASES; return list of failure messages."""
    failures: list[str] = []
    for i, (auc_inertia, auc_sim, expected) in enumerate(
        SELF_TEST_CASCADE_CASES
    ):
        verdict = classify_cascade_inertia(auc_inertia, auc_sim)
        if verdict.label != expected:
            failures.append(
                f"  case {i + 1}: AUC=({auc_inertia:.3f}, {auc_sim:.3f}) → "
                f"got {verdict.label!r}, expected {expected!r}"
            )
    return failures


def _self_test_cosine_invariants() -> list[str]:
    """Synthetic cosine invariants exercised through `_cosine_fp64`.

    1. Identity: cos(v, v) = 1 for non-zero v.
    2. Anti-parallel: cos(v, -v) = -1.
    3. Orthogonal: cos(e_i, e_j) = 0 for i != j on the standard basis.
    4. Symmetry: cos(a, b) == cos(b, a) numerically.

    These exercise the same code path used to compute cos_st_ra,
    cos_st_qb, and cos_qa_qb on real LM hidden states. Tolerance is
    1e-9 to match §15.11's strictness on a similar surface.
    """
    failures: list[str] = []
    rng = np.random.default_rng(SEED_ENTROPY)

    # 1. Identity.
    v = rng.normal(0.0, 1.0, HIDDEN_DIM).astype(np.float32)
    if v.dot(v) <= 0.0:
        failures.append("  identity: synthetic vector has zero norm")
    c_ii = _cosine_fp64(v, v)
    if not (abs(c_ii - 1.0) <= 1e-9):
        failures.append(
            f"  identity: cos(v, v) = {c_ii} (expected 1; tol 1e-9)"
        )

    # 2. Anti-parallel.
    c_anti = _cosine_fp64(v, -v)
    if not (abs(c_anti + 1.0) <= 1e-9):
        failures.append(
            f"  anti-parallel: cos(v, -v) = {c_anti} (expected -1; tol 1e-9)"
        )

    # 3. Orthogonality (standard-basis vectors).
    e_i = np.zeros(HIDDEN_DIM, dtype=np.float32)
    e_j = np.zeros(HIDDEN_DIM, dtype=np.float32)
    e_i[7] = 1.0
    e_j[42] = 1.0
    c_orth = _cosine_fp64(e_i, e_j)
    if not (abs(c_orth) <= 1e-12):
        failures.append(
            f"  orthogonal: cos(e_7, e_42) = {c_orth} (expected 0; tol 1e-12)"
        )

    # 4. Symmetry.
    a = rng.normal(0.0, 1.0, HIDDEN_DIM).astype(np.float32)
    b = rng.normal(0.0, 1.0, HIDDEN_DIM).astype(np.float32)
    c_ab = _cosine_fp64(a, b)
    c_ba = _cosine_fp64(b, a)
    if not (abs(c_ab - c_ba) <= 1e-12):
        failures.append(
            f"  symmetry: cos(a, b) = {c_ab} vs cos(b, a) = {c_ba} "
            f"(expected equal; tol 1e-12)"
        )
    # Bonus: random pair should land within [-1, 1] up to fp epsilon.
    if not (-1.0 - 1e-9 <= c_ab <= 1.0 + 1e-9):
        failures.append(
            f"  range: cos(a, b) = {c_ab} outside [-1, 1] (random pair)"
        )

    return failures


def _self_test_firewall() -> list[str]:
    """Verify firewall flags all 44 Class-3 patterns + clean text passes.

    Positive: each pattern triggers detection when embedded in plain text.
    Negative: a clean §15.13-style report (cascade prose + preserved-
    verdict cross-phase references + pinned-formula expression) passes
    without false positives.
    """
    failures: list[str] = []
    if len(CLASS_3_FORBIDDEN_PATTERNS) != 44:
        failures.append(
            f"  pattern count: got {len(CLASS_3_FORBIDDEN_PATTERNS)}, "
            f"expected 44 (spec §15.13 §0.8-binding)"
        )
    for pattern in CLASS_3_FORBIDDEN_PATTERNS:
        sample = f"Some innocuous text. {pattern} more text."
        if not scan_for_forbidden_patterns(sample):
            failures.append(
                f"  firewall failed to detect pattern: {pattern!r}"
            )
    clean = (
        "The §15.13 cascade verdict is NO_MATERIAL_SIGNAL_IN_INERTIA "
        "by mechanical readout: auc_inertia ≈ 0.51, auc_sim ≈ 0.52, "
        "ΔAUC vs chance = +0.01, ΔAUC vs R_sim = -0.01; direction held. "
        "§15.10 PARTIAL_SIGNAL_IN_Z preserved. §15.11 "
        "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE preserved. §15.12 closure "
        "preserved. §13.9 hold remains binding. §6.1 N=21 autonomy "
        "result preserved. Pinned formula: R_inertia = cos(s_t, r_A) - "
        "cos(s_t, q_B); BCVF-faithful direction (lower R_inertia "
        "predicts correct). Same-family pairing is the spec's pinned "
        "rule. The R_sim comparator entered the cascade as required."
    )
    spurious = scan_for_forbidden_patterns(clean)
    if spurious:
        failures.append(
            f"  firewall false-positive on clean §15.13-style text: "
            f"{spurious!r}"
        )
    return failures


def run_self_test() -> int:
    """Execute the §15.13 self-test gate; return 0 on success, 3 on failure.

    Required pre-execution gate per spec: the runpod must run
    `--self-test` and see exit 0 before `--extract-only` or default
    full pipeline.
    """
    print("§15.13 self-test gate", flush=True)
    print(f"  schema_version: {SCHEMA_VERSION}", flush=True)
    print(f"  benchmark: {BENCHMARK}", flush=True)
    print(f"  pinned_N: {PINNED_N}", flush=True)
    print(f"  pairing rule: {PAIRING_RULE_DESCRIPTION}", flush=True)
    print(
        f"  cascade thresholds: STRONG_AUC≥{STRONG_AUC_THRESHOLD}, "
        f"STRONG_dAUC≥+{STRONG_DELTA_AUC_THRESHOLD}, "
        f"PARTIAL_AUC≥{PARTIAL_AUC_THRESHOLD}, "
        f"DIRECTION_GATE={DIRECTION_GATE_THRESHOLD}",
        flush=True,
    )
    print(f"  hidden_dim: {HIDDEN_DIM}, layer_idx: {LAYER_IDX}", flush=True)
    print(f"  direction convention: {DIRECTION_CONVENTION}", flush=True)

    all_failures: list[str] = []

    print("  [1/3] cascade boundary cases (12)...", flush=True)
    cascade_fail = _self_test_cascade()
    if cascade_fail:
        all_failures.append("CASCADE FAILURES:")
        all_failures.extend(cascade_fail)
    else:
        print(
            f"    OK: {len(SELF_TEST_CASCADE_CASES)} boundary cases pass.",
            flush=True,
        )

    print("  [2/3] cosine invariants on synthetic data...", flush=True)
    cosine_fail = _self_test_cosine_invariants()
    if cosine_fail:
        all_failures.append("COSINE FAILURES:")
        all_failures.extend(cosine_fail)
    else:
        print(
            "    OK: identity → 1, anti-parallel → -1, orthogonal → 0, "
            "symmetry holds.",
            flush=True,
        )

    print(
        f"  [3/3] interpretation firewall ({len(CLASS_3_FORBIDDEN_PATTERNS)} "
        f"patterns)...",
        flush=True,
    )
    firewall_fail = _self_test_firewall()
    if firewall_fail:
        all_failures.append("FIREWALL FAILURES:")
        all_failures.extend(firewall_fail)
    else:
        print(
            f"    OK: firewall flags all {len(CLASS_3_FORBIDDEN_PATTERNS)} "
            f"Class-3 patterns; clean §15.13 text passes.",
            flush=True,
        )

    if all_failures:
        print("\nSELF_TEST_FAILED:", flush=True)
        for line in all_failures:
            print(line, flush=True)
        return 3
    print("\nSELF_TEST_PASSED — proceed.", flush=True)
    return 0


# ===========================================================================
# §15.13 Chunk I-4c — JSON output writer.
#
# Top-level keys PINNED per spec output schema (alphabetical for
# sort_keys=True parity with §15.10 / §15.11 / §15.12):
#   benchmark, cascade_thresholds, cascade_verdict,
#   cross_phase_disclosure, extraction_config, n_stimuli, pairing_rule,
#   phase_4_eligible_outcomes, probe_result, qwen_model_id,
#   schema_version.
#
# No additional keys; no key removal. schema_version = "15.13".
# ===========================================================================


def _cascade_verdict_to_dict(cv: InertiaCascadeVerdict) -> dict:
    return {
        "label": cv.label,
        "auc_inertia": float(cv.auc_inertia),
        "auc_sim": float(cv.auc_sim),
        "dauc_vs_chance": float(cv.dauc_vs_chance),
        "dauc_vs_sim": float(cv.dauc_vs_sim),
        "direction_held": bool(cv.direction_held),
        "rationale": str(cv.rationale),
    }


def _probe_result_to_dict(pr: InertiaProbeResult) -> dict:
    """Serialize InertiaProbeResult to the spec-pinned JSON shape.

    Top-level probe_result fields per spec:
      n_stimuli, n_correct, n_wrong,
      auc_inertia, auc_sim,
      dauc_inertia_vs_chance, dauc_inertia_vs_sim,
      direction_held,
      r_inertia_per_stimulus, r_sim_per_stimulus, y_per_stimulus,
      selective_prediction_operating_points,
      kappa_at_alpha_primary, tau_star_at_alpha_primary, alpha_primary.
    """
    return {
        "n_stimuli": int(pr.n_stimuli),
        "n_correct": int(pr.n_correct),
        "n_wrong": int(pr.n_wrong),
        "auc_inertia": float(pr.auc_inertia),
        "auc_sim": float(pr.auc_sim),
        "dauc_inertia_vs_chance": float(pr.dauc_inertia_vs_chance),
        "dauc_inertia_vs_sim": float(pr.dauc_inertia_vs_sim),
        "direction_held": bool(pr.direction_held),
        "r_inertia_per_stimulus": [float(v) for v in pr.r_inertia_per_stimulus],
        "r_sim_per_stimulus": [float(v) for v in pr.r_sim_per_stimulus],
        "y_per_stimulus": [bool(v) for v in pr.y_per_stimulus],
        "selective_prediction_operating_points": [
            {
                "alpha": float(op["alpha"]),
                "tau_star": float(op["tau_star"]),
                "kappa_at_alpha": float(op["kappa_at_alpha"]),
                "coverage_at_tau_star": float(op["coverage_at_tau_star"]),
                "conditional_accuracy_at_tau_star": float(
                    op["conditional_accuracy_at_tau_star"]
                )
                if not math.isnan(
                    op.get("conditional_accuracy_at_tau_star", float("nan"))
                )
                else None,
                "n_admitted_at_tau_star": int(op["n_admitted_at_tau_star"]),
                "eligible": bool(op["eligible"]),
            }
            for op in pr.operating_points
        ],
        "kappa_at_alpha_primary": float(pr.kappa_at_alpha_primary),
        "tau_star_at_alpha_primary": (
            float(pr.tau_star_at_alpha_primary)
            if not math.isnan(pr.tau_star_at_alpha_primary)
            else None
        ),
        "alpha_primary": float(ALPHA_PRIMARY),
        "n_r_a_tokens_per_stimulus": [
            int(v) for v in pr.n_r_a_tokens_per_stimulus
        ],
        "n_q_b_response_tokens_per_stimulus": [
            int(v) for v in pr.n_q_b_response_tokens_per_stimulus
        ],
    }


def _build_json_payload(outputs: InertiaAuditOutputs) -> dict:
    """Construct the §15.13 JSON payload with the spec-pinned top-level keys.

    The keyset is exactly:
      benchmark, cascade_thresholds, cascade_verdict,
      cross_phase_disclosure, extraction_config, n_stimuli,
      pairing_rule, phase_4_eligible_outcomes, probe_result,
      qwen_model_id, schema_version.
    """
    return {
        "benchmark": str(outputs.benchmark),
        "cascade_thresholds": {
            "strong_auc": float(STRONG_AUC_THRESHOLD),
            "strong_delta_auc": float(STRONG_DELTA_AUC_THRESHOLD),
            "partial_auc": float(PARTIAL_AUC_THRESHOLD),
            "direction_gate_threshold": float(DIRECTION_GATE_THRESHOLD),
            "chance_baseline_auc": float(CHANCE_BASELINE_AUC),
        },
        "cascade_verdict": _cascade_verdict_to_dict(outputs.cascade_verdict),
        "cross_phase_disclosure": {
            "phase_1_§15_10_verdict": PHASE_1_VERDICT,
            "phase_2_§15_11_verdict": PHASE_2_VERDICT,
            "phase_3_§15_12_status": PHASE_3_STATUS,
            "this_phase_modifies": "none",
        },
        "extraction_config": {
            "layer_idx": int(LAYER_IDX),
            "hidden_dim": int(HIDDEN_DIM),
            "max_new_tokens": int(MAX_NEW_TOKENS),
            "decode_temperature": float(DECODE_TEMPERATURE),
            "r_a_pooling": R_A_POOLING_DESCRIPTION,
            "s_t_extraction": S_T_EXTRACTION_DESCRIPTION,
            "q_b_extraction": Q_B_EXTRACTION_DESCRIPTION,
            "q_a_extraction": Q_A_EXTRACTION_DESCRIPTION,
            "direction_convention": DIRECTION_CONVENTION,
            "nli_model_id": NLI_MODEL_ID,
        },
        "n_stimuli": int(outputs.n_stimuli),
        "pairing_rule": PAIRING_RULE_DESCRIPTION,
        "phase_4_eligible_outcomes": [
            "STRONG_SIGNAL_IN_INERTIA",
            "PARTIAL_SIGNAL_IN_INERTIA",
            "NO_MATERIAL_SIGNAL_IN_INERTIA",
        ],
        "probe_result": _probe_result_to_dict(outputs.probe_result),
        "qwen_model_id": str(outputs.qwen_model_id),
        "schema_version": str(outputs.schema_version),
    }


def write_json_output(outputs: InertiaAuditOutputs, path: str) -> None:
    """Serialize InertiaAuditOutputs to JSON (schema_version "15.13").

    Uses sort_keys=True for deterministic top-level alphabetical ordering
    (parity with §15.10 / §15.11 / §15.12 outputs). indent=2.
    """
    payload = _build_json_payload(outputs)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


# ===========================================================================
# §15.13 Chunk I-4d — markdown rendering + firewall-scanned writer.
#
# 8-section structure pinned per spec output schema markdown bullet:
#   1. Header + schema/model/extraction config one-liner.
#   2. Cascade verdict (label, rationale, AUC table with chance + sim).
#   3. Probe details (n, AUC, ΔAUC vs both baselines, direction-held,
#      R_inertia distribution summary).
#   4. Selective-prediction operating points table (disclosure only).
#   5. Pinned configuration block (formula, pairing rule, extraction
#      protocol, cascade thresholds, direction convention).
#   6. Caveats (§0.8-disclosed; carries forward §15.10/§15.11 caveats by
#      §-reference; §15.13-specific caveats listed inline).
#   7. Cross-phase comparison (Phase 1/2/3/4 status; disclosure only).
#   8. Audit-trail integrity (§0.8-binding; §13/§14/§15.x verdicts
#      preserved; firewall-scanned).
#
# Firewall is enforced before write (Chunk I-4a's enforce_firewall_or_exit).
# ===========================================================================


def _r_inertia_summary(values: tuple[float, ...]) -> dict:
    """Min/median/mean/std/max of the per-stimulus R_inertia distribution.

    Reported in section 3 for transparency. Pure numpy; no leak into
    cascade decision.
    """
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": int(arr.size),
        "min": float(arr.min()) if arr.size else float("nan"),
        "max": float(arr.max()) if arr.size else float("nan"),
        "mean": float(arr.mean()) if arr.size else float("nan"),
        "median": float(np.median(arr)) if arr.size else float("nan"),
        "std": (
            float(arr.std(ddof=1)) if arr.size > 1 else 0.0
        ),
    }


def _format_operating_points_table(ops: tuple[dict, ...]) -> str:
    """Markdown table of κ@α operating points (disclosure only)."""
    lines = [
        "| α | τ* | κ@α | coverage | cond. acc. | n_admitted | eligible |",
        "|---|----|-----|----------|------------|------------|----------|",
    ]
    for op in ops:
        tau_str = (
            f"{op['tau_star']:.4f}"
            if not math.isnan(op.get("tau_star", float("nan")))
            else "—"
        )
        cond_str = (
            f"{op['conditional_accuracy_at_tau_star']:.3f}"
            if not math.isnan(
                op.get("conditional_accuracy_at_tau_star", float("nan"))
            )
            else "—"
        )
        lines.append(
            f"| {op['alpha']:.2f} | {tau_str} | {op['kappa_at_alpha']:.3f} | "
            f"{op['coverage_at_tau_star']:.3f} | {cond_str} | "
            f"{op['n_admitted_at_tau_star']} | "
            f"{'yes' if op['eligible'] else 'no'} |"
        )
    return "\n".join(lines)


def render_markdown_report(outputs: InertiaAuditOutputs) -> str:
    """Render the §15.13 markdown report.

    Output is firewall-scanned by `write_markdown_output` before write;
    any Class-3 forbidden statement triggers exit code 4
    (INTERPRETATION_VIOLATION) without writing.
    """
    cv = outputs.cascade_verdict
    pr = outputs.probe_result
    summary = _r_inertia_summary(pr.r_inertia_per_stimulus)
    sim_summary = _r_inertia_summary(pr.r_sim_per_stimulus)

    n_r_a_min = (
        min(pr.n_r_a_tokens_per_stimulus)
        if pr.n_r_a_tokens_per_stimulus
        else 0
    )
    n_r_a_max = (
        max(pr.n_r_a_tokens_per_stimulus)
        if pr.n_r_a_tokens_per_stimulus
        else 0
    )
    n_r_a_mean = (
        sum(pr.n_r_a_tokens_per_stimulus)
        / max(1, len(pr.n_r_a_tokens_per_stimulus))
    )

    lines: list[str] = []

    # ---- Section 1: header ---------------------------------------------
    lines.append(
        "# §15.13 Phase 4 — Continuation-inertia probe (result)\n"
    )
    lines.append(
        f"_Schema version: `{outputs.schema_version}`._  \n"
        f"_Model: `{outputs.qwen_model_id}`; "
        f"benchmark: `{outputs.benchmark}`; "
        f"layer used: {LAYER_IDX} (final); hidden dim: `{HIDDEN_DIM}`; "
        f"max_new_tokens: {MAX_NEW_TOKENS} (greedy); "
        f"NLI scorer: `{NLI_MODEL_ID}`._\n"
    )

    # ---- Section 2: cascade verdict ------------------------------------
    lines.append("## Cascade verdict (mechanical readout)\n")
    lines.append(f"**Label:** `{cv.label}`\n")
    lines.append(f"**Rationale:** {cv.rationale}\n")
    lines.append(
        "| metric | value |\n"
        "|---|---|\n"
        f"| auc_inertia (AUC(−R_inertia, y)) | {cv.auc_inertia:.4f} |\n"
        f"| auc_sim    (AUC(−R_sim,     y)) | {cv.auc_sim:.4f} |\n"
        f"| ΔAUC vs chance (0.5) | {cv.dauc_vs_chance:+.4f} |\n"
        f"| ΔAUC vs R_sim         | {cv.dauc_vs_sim:+.4f} |\n"
        f"| direction held (auc_inertia ≥ 0.5) | "
        f"**{'yes' if cv.direction_held else 'no'}** |\n"
    )

    # ---- Section 3: probe details --------------------------------------
    lines.append("## Probe details\n")
    lines.append(
        f"- N stimuli: {pr.n_stimuli} "
        f"(correct: {pr.n_correct}, wrong: {pr.n_wrong}; "
        f"observed accuracy = {pr.n_correct / max(1, pr.n_stimuli):.3f})\n"
        f"- auc_inertia = **{pr.auc_inertia:.4f}** "
        f"(ΔAUC vs chance: {pr.dauc_inertia_vs_chance:+.4f}; "
        f"ΔAUC vs R_sim: {pr.dauc_inertia_vs_sim:+.4f})\n"
        f"- auc_sim     = {pr.auc_sim:.4f} (R_sim comparator baseline)\n"
        f"- direction held (auc_inertia ≥ {DIRECTION_GATE_THRESHOLD}): "
        f"**{'yes' if pr.direction_held else 'no'}**\n"
        "- R_inertia distribution (per-stimulus, fp64):\n"
        f"  - min:    {summary['min']:+.4f}\n"
        f"  - median: {summary['median']:+.4f}\n"
        f"  - mean:   {summary['mean']:+.4f}\n"
        f"  - std:    {summary['std']:.4f}\n"
        f"  - max:    {summary['max']:+.4f}\n"
        "- R_sim distribution (per-stimulus, fp64):\n"
        f"  - min:    {sim_summary['min']:+.4f}\n"
        f"  - median: {sim_summary['median']:+.4f}\n"
        f"  - mean:   {sim_summary['mean']:+.4f}\n"
        f"  - std:    {sim_summary['std']:.4f}\n"
        f"  - max:    {sim_summary['max']:+.4f}\n"
        f"- |T_A| (decoded R_A token count) per stimulus: "
        f"min {n_r_a_min}, mean {n_r_a_mean:.1f}, max {n_r_a_max} "
        f"(MAX_NEW_TOKENS = {MAX_NEW_TOKENS}; Risk-6 disclosure)\n"
    )

    # ---- Section 4: selective-prediction operating points --------------
    lines.append("## Selective-prediction operating points (disclosure only)\n")
    lines.append(
        "These κ@α operating points report what the −R_inertia abstention "
        "score achieves at the pinned alphas (0.35, 0.50, 0.75) under the "
        f"N_MIN={N_MIN} eligibility floor. They are reported for "
        "transparency and do NOT enter the §15.13 cascade decision.\n"
    )
    lines.append(_format_operating_points_table(pr.operating_points))
    lines.append("")
    primary_tau_str = (
        f"{pr.tau_star_at_alpha_primary:.4f}"
        if not math.isnan(pr.tau_star_at_alpha_primary)
        else "—"
    )
    lines.append(
        f"At α_primary = {ALPHA_PRIMARY:.2f}: κ@α = "
        f"{pr.kappa_at_alpha_primary:.3f}; τ* = {primary_tau_str}.\n"
    )

    # ---- Section 5: pinned configuration -------------------------------
    lines.append("## Pinned configuration (§15.13 §0.8-binding)\n")
    lines.append(
        f"- **Model:** `{outputs.qwen_model_id}`; layer `{LAYER_IDX}` "
        f"(final layer only); hidden dim `{HIDDEN_DIM}`.\n"
        f"- **Benchmark:** `{outputs.benchmark}` (single benchmark for "
        "v1; HaluEval is a v2 follow-up only if v1 shows signal).\n"
        f"- **Pairing rule:** `{PAIRING_RULE_DESCRIPTION}` "
        f"({PINNED_N} unique pairs; each question appears once as Q_A "
        "and once as Q_B).\n"
        "- **Pinned formula:** `R_inertia = cos(s_t, r_A) − cos(s_t, q_B)`.\n"
        "- **Comparator baseline:** `R_sim = cos(q_A, q_B)`.\n"
        f"- **Direction convention:** {DIRECTION_CONVENTION}.\n"
        f"- **Decoding:** greedy (temperature {DECODE_TEMPERATURE}); "
        f"`max_new_tokens = {MAX_NEW_TOKENS}`.\n"
        "- **Per-stimulus extraction protocol (3 forward passes):**\n"
        "  - Pass 1: `[SYS][USER]Q_A[ASSISTANT]_` → greedy decode → "
        "extract `q_A` (last-token, layer −1, pre-decode) + `r_A` "
        "(mean over decoded assistant token positions, layer −1).\n"
        "  - Pass 2: `[SYS][USER]Q_A[ASSISTANT]r_A_text[USER]Q_B"
        "[ASSISTANT]_` → greedy decode → extract `s_t` (last-token, "
        "layer −1, pre-decode at second `[ASSISTANT]` tag); decode "
        "Q_B response for NLI label scoring.\n"
        "  - Pass 3: `[SYS][USER]Q_B[ASSISTANT]_` → forward only → "
        "extract `q_B` (last-token, layer −1).\n"
        "  - Pass 1's verbatim `r_a_text` is spliced into Pass 2's "
        "prompt (Risk-3 mitigation: byte-identical R_A across passes).\n"
        f"- **NLI scoring (y label):** `{NLI_MODEL_ID}` via the §13.10 "
        "`label_correctness` helper (premise = Q_B + response; "
        "hypotheses = Q_B + each candidate; "
        "y = entails(gold) AND NOT entails(any distractor)).\n"
        f"- **Cascade thresholds:** STRONG AUC ≥ {STRONG_AUC_THRESHOLD} "
        f"AND ΔAUC ≥ +{STRONG_DELTA_AUC_THRESHOLD} vs BOTH chance and "
        f"R_sim; PARTIAL AUC ≥ {PARTIAL_AUC_THRESHOLD} AND ΔAUC > 0 vs "
        "BOTH; otherwise NO_MATERIAL. Direction gate: "
        f"auc_inertia < {DIRECTION_GATE_THRESHOLD} → NO_MATERIAL "
        "automatic.\n"
        f"- **Selective-prediction:** alphas {ALPHA_TARGETS}; "
        f"primary alpha = {ALPHA_PRIMARY}; floor N_MIN = {N_MIN}; "
        "disclosure only — does NOT enter cascade.\n"
    )

    # ---- Section 6: caveats --------------------------------------------
    lines.append("## Caveats (§0.8-disclosed)\n")
    lines.append(
        "- **One mechanism within the multi-turn class.** §15.13 tests "
        "ONE instantiation of continuation inertia: the pinned R_inertia "
        "formula at layer −1, on TruthfulQA-MC, with the +50 same-family "
        "pairing rule. A null result rules out THIS instantiation; H1 "
        "(state coherence) and H2 (intent competition) remain in the "
        "open-but-untested column for future top-level §0.X work.\n"
        "- **Direction is pinned BCVF-faithful (lower R_inertia predicts "
        "correct).** A failure of the direction gate is a hypothesis "
        "failure (NO_MATERIAL automatic), not a sign-flip opportunity. "
        "Mirrors §15.11's enforcement.\n"
        "- **R_sim controls for topical-overlap confound.** R_inertia "
        "must beat R_sim by the cascade margin to clear STRONG/PARTIAL; "
        "if same-family pairing is too topically clustered to separate "
        "inertia from topic similarity, the dual-comparator cascade "
        "lands NO_MATERIAL.\n"
        f"- **N = {PINNED_N} stimuli.** AUC standard error at AUC ≈ 0.66 "
        "with N=100 is ~0.05–0.06; cascade bands at 0.66 and 0.75 are "
        "hit/miss-able by sampling noise. Mirrors §15.10/§15.11 power "
        "constraint.\n"
        "- **Single model size: Qwen2.5-7B-Instruct.** Does not speak "
        "to scaling at 13B / 32B / 70B.\n"
        "- **Greedy refusals.** Hedged or refusal Q_B responses score "
        "as non-entailment under §13.10 NLI semantics. If the model "
        "refuses more on Q_B questions where it is stuck on R_A, that "
        "is treated as genuine signal, not noise (Risk 2 disclosure).\n"
        "- **|T_A| variability.** Pass 1 may emit an end token before "
        f"MAX_NEW_TOKENS = {MAX_NEW_TOKENS}; r_A pooling averages only "
        "over actually-generated non-end token positions (Risk 6 "
        "disclosure). The |T_A| distribution is reported in section 3.\n"
        "- **NLI cost.** DeBERTa-v3-base-mnli-fever-anli is loaded for "
        "y label scoring; ~5 GB peak memory + ~2 min wall time at N=100 "
        "(Risk 8 disclosure).\n"
        "- **No bootstrap CIs in v1.** Mirrors §15.10/§15.11; v1 reports "
        "point estimates against pinned bands.\n"
        f"- **Inherited from §15.10:** prompt-format vs §13.10 labelling "
        f"regime (pinned chat-template `{outputs.qwen_model_id}` "
        "regardless of §13.10's `Q: ... A:` raw-text labelling); "
        "question-text source (dump field if present, else HF dataset "
        "by `q_idx`).\n"
        "- **Inherited from §15.11:** sklearn `penalty` FutureWarning "
        "filter installed precautionarily even though §15.13 uses only "
        "`roc_auc_score`.\n"
    )

    # ---- Section 7: cross-phase comparison -----------------------------
    lines.append("## Cross-phase comparison (disclosure only)\n")
    lines.append(
        "| phase | mechanism class | verdict | this row modifies |\n"
        "|---|---|---|---|\n"
        "| §15.10 (Phase 1) | supervised linear (single-turn) | "
        f"`{PHASE_1_VERDICT}` | no |\n"
        "| §15.11 (Phase 2) | layer-wise phase coherence (single-turn) | "
        f"`{PHASE_2_VERDICT}` | no |\n"
        "| §15.12 (Phase 3) | synthesis + closure | "
        f"{PHASE_3_STATUS} | no |\n"
        "| §15.13 (Phase 4) | continuation inertia (multi-turn) | "
        f"`{cv.label}` | n/a (this row is the result) |\n"
    )
    lines.append(
        "This subsection is disclosure only and does not enter any "
        "phase's cascade decision. Each phase's verdict is an "
        "independent §0.8-binding mechanical readout; §15.13 does not "
        "reopen any prior phase.\n"
    )

    # ---- Section 8: audit-trail integrity ------------------------------
    lines.append("## Audit-trail integrity\n")
    lines.append(
        "This result is a mechanical readout of the §15.13 cascade "
        "applied to per-stimulus R_inertia + R_sim cosines computed "
        "from Qwen-7B's last-layer hidden states across the three "
        "pinned forward passes. Per §0.8 discipline, the cascade label "
        "is binding regardless of any post-hoc interpretation.\n\n"
        "§15.13 does not modify any §13/§14/§15.x verdict-of-record. "
        "The §13.9 hold remains binding. The §6.1 N=21 autonomy result "
        "is preserved. §15.10 PARTIAL_SIGNAL_IN_Z is preserved. §15.11 "
        "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE is preserved. §15.12 "
        "closure is preserved. §15.13 is a fresh top-level §0.X testing "
        "a different mechanism class (multi-turn continuation inertia); "
        "its outcome is independent of the four single-turn canonical "
        "mechanism classes covered by §15.10 / §15.11 / §15.12.\n\n"
        "The interpretation firewall scanned this document for "
        f"{len(CLASS_3_FORBIDDEN_PATTERNS)} Class-3 forbidden statements "
        "before write. Detection would have triggered "
        "INTERPRETATION_VIOLATION (exit 4) without writing. The cascade "
        "verdict above is the binding §15.13 readout.\n"
    )

    return "\n".join(lines)


def write_markdown_output(outputs: InertiaAuditOutputs, path: str) -> None:
    """Render markdown, run interpretation firewall, then write."""
    text = render_markdown_report(outputs)
    enforce_firewall_or_exit(text, path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(text)
