#!/usr/bin/env python
"""§15.11 Phase 2 — Layer-wise phase-coherence probe (final-resolution sprint).

Pure §0.8-binding implementation per the frozen §15.11 pre-
commitment. Tests whether truth signal is encoded in the
non-linear, multi-scale phase relationship across Qwen-7B's
29 per-layer last-token hidden states — a mechanism class
that §13.10 entropy and §15.10 supervised linear extraction
cannot capture by construction.

Reference: docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md §15.11
(commits 7c20d3b, ec6f667, f0a96a0, dab98cf, 7ba55ee, d59d4e7).

What this script DOES:
  * Loads correctness labels from the existing §13.10 dumps
    (per-question greedy_matches_correct booleans).
  * Optionally extracts ALL 29 layers' last-token hidden
    states from Qwen2.5-7B-Instruct over each question
    prompt `Q: {question}\\nA:` (or loads from a §15.11-
    specific cache if already extracted).
  * For each question, computes the 29x29 phase-coherence
    matrix C[i,j] = (1/W) * sum_k cos(phi_i[k] - phi_j[k])
    using rfft on each layer's last-token hidden state with
    W = 1791 frequency bins (DC and Nyquist excluded).
  * Aggregates each C matrix into a single scalar F per
    question via mean over the 406 upper-triangular off-
    diagonal entries.
  * Computes AUC(F vs correctness) per benchmark, ΔAUC vs
    §13.10 entropy baseline 0.661, and selective-prediction
    operating points.
  * Applies the §15.11 cascade: direction-gate then STRONG /
    PARTIAL / NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE.
  * Emits JSON + markdown artifacts with §15.7-pattern
    interpretation firewall enforced at write time.

What this script DOES NOT:
  * Re-classify any §13/§14/§15.x verdict-of-record. All
    bands remain binding regardless of §15.11 outputs.
  * Iterate on the formula, the FFT bin range, the layer
    subset, or the feature aggregation. All are pinned per
    the §15.11 pre-commitment; one shot.
  * Sign-flip if AUC < 0.5. The BCVF-faithful direction
    was the pre-committed hypothesis; failing it is a
    failure (NO_MATERIAL automatic), not a sign-flip
    opportunity.
  * Authorize Phase 3 (§15.12). Phase 3 requires its own
    §0.8 commitment.

Inputs (per §15.11):
    docs/experiments/probe_semantic_entropy.json
        (§13.10 TruthfulQA-MC dump; per-question correctness
        labels; first 100 questions used regardless of N status)
    docs/experiments/probe_semantic_entropy_halueval_qa.json
        (§13.10 HaluEval-QA dump; same usage)
    `Qwen/Qwen2.5-7B-Instruct` (cached HF model)
    HaluEval-QA + TruthfulQA-MC datasets (HuggingFace,
    fallback for question text if dump field absent)

Outputs (per §15.11):
    docs/experiments/hidden_states_all_layers_qwen_15_11.npz
        (cached extraction; (N, 29, 3584) per benchmark;
        allows skipping re-extraction)
    docs/experiments/probe_phase_coherence_15_11.json
        (machine-readable result, schema_version "15.11")
    docs/experiments/probe_phase_coherence_15_11.md
        (human-readable report, firewall-scanned at write time)

Usage:
    # Required pre-execution gate.
    python scripts/probe_phase_coherence_15_11.py --self-test

    # Full pipeline (extract + coherence + report).
    python scripts/probe_phase_coherence_15_11.py

    # Extract only (GPU phase; produces .npz cache).
    python scripts/probe_phase_coherence_15_11.py --extract-only

    # Probe only (CPU phase; uses .npz cache).
    python scripts/probe_phase_coherence_15_11.py --probe-only
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

# Suppress sklearn FutureWarning for the `penalty` kwarg (mirrors §15.10).
# §15.11 only uses sklearn for roc_auc_score (no LogisticRegression), so
# this filter is precautionary.
warnings.filterwarnings(
    "ignore",
    message=r".*'penalty'.*",
    category=FutureWarning,
)

# ===========================================================================
# §15.11 PINNED CONSTANTS — DO NOT CHANGE during implementation.
# Any change requires a fresh §0.8 amendment to §15.11.
# ===========================================================================

SCHEMA_VERSION = "15.11"

# Target model (pinned per §15.11 spec; matches §15.10).
QWEN_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

# Benchmarks (pinned).
BENCHMARKS: tuple[str, ...] = ("halueval_qa", "truthfulqa_mc")

# Pinned size per benchmark.
PINNED_N = 100

# §13.10 dumps — used ONLY for correctness labels, first 100 records.
INPUT_S13_10_HALUEVAL = "docs/experiments/probe_semantic_entropy_halueval_qa.json"
INPUT_S13_10_TRUTHFULQA = "docs/experiments/probe_semantic_entropy.json"

# Pinned §13.10 baseline AUCs (per §13.10 verdict-of-record at N=100).
BASELINE_AUC_PER_BENCHMARK: dict[str, float] = {
    "halueval_qa": 0.661,
    "truthfulqa_mc": 0.661,
}
ENTROPY_BASELINE_AUC = 0.661

# §15.10 supervised AUCs (disclosure only; not in cascade).
SUPERVISED_AUC_PER_BENCHMARK_PHASE_1: dict[str, float] = {
    "halueval_qa": 0.6685714285714286,
    "truthfulqa_mc": 0.6224,
}

# Pinned base rates pi (per §13.10 prose; Qwen-greedy accuracy).
PINNED_PI: dict[str, float] = {
    "halueval_qa": 0.300,
    "truthfulqa_mc": 0.250,
}

# Pinned alpha targets per benchmark (matches §15.10).
ALPHA_TARGETS_PER_BENCHMARK: dict[str, tuple[float, ...]] = {
    "halueval_qa": (0.40, 0.50, 0.75),
    "truthfulqa_mc": (0.35, 0.50, 0.75),
}
ALPHA_PRIMARY = 0.50
N_MIN = 10  # selective-prediction floor (matches §15.10)
SEED_ENTROPY = 15  # for any rng calls; no CV in §15.11

# Cascade thresholds per §15.11 (pinned exhaustive partition;
# numerically identical to §15.10).
STRONG_AUC_THRESHOLD = 0.75
STRONG_DELTA_AUC_THRESHOLD = 0.05
PARTIAL_AUC_THRESHOLD = 0.66
DIRECTION_GATE_THRESHOLD = 0.5  # strict (AUC < 0.5 fails)

# Hidden-state extraction config (pinned).
PROMPT_FORMAT = "Q: {question}\nA:"
HIDDEN_DIM = 3584
N_LAYERS = 29  # 1 embedding output + 28 transformer-layer outputs
EXTRACT_DTYPE_INFERENCE = "float16"  # match Qwen2.5-7B's native fp16
EXTRACT_DTYPE_CACHE = "float32"  # cast for portability

# Phase-coherence config (pinned).
FFT_N = HIDDEN_DIM  # 3584
N_FREQ_BINS_TOTAL = FFT_N // 2 + 1  # 1793 (rfft length)
W = 1791  # frequency bins used (exclude DC at k=0 and Nyquist at k=1792)
BIN_RANGE_USED = (1, 1792)  # inclusive lo, exclusive hi → bins 1..1791
WINDOWING = "rectangular (none)"
DETRENDING = "none"
FEATURE_AGGREGATION = "mean over upper-triangular off-diagonal of 29x29 C (406 entries)"
DIRECTION_CONVENTION = "higher F predicts correct (BCVF-faithful)"
N_OFF_DIAG_ENTRIES = (N_LAYERS * (N_LAYERS - 1)) // 2  # 406

# Cache + output paths (pinned).
HIDDEN_STATES_CACHE_PATH = "docs/experiments/hidden_states_all_layers_qwen_15_11.npz"
OUTPUT_JSON_PATH = "docs/experiments/probe_phase_coherence_15_11.json"
OUTPUT_MD_PATH = "docs/experiments/probe_phase_coherence_15_11.md"

# §13.10 dump field names (per §15.1 Amendment 1 pinned schema).
FIELD_QID = "q_idx"
FIELD_CORRECT = "greedy_matches_correct"
FIELD_QUESTION = "question"

# §15.7-style Class-3 forbidden-statement patterns. Inherits §15.10/§15.7
# set (16 patterns) plus §15.11-specific (10 patterns) per design-doc
# Chunk 5 — total 26 patterns.
CLASS_3_FORBIDDEN_PATTERNS: list[str] = [
    # Inherited from §15.10 / §15.7.
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
    # §15.11-specific (10).
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
]

# Self-test boundary cases for the cascade classifier (per §15.11 design-doc
# Chunk 4). Each entry: (auc_h, auc_t, dauc_h, dauc_t, expected_label).
SELF_TEST_CASCADE_CASES: list[tuple[float, float, float, float, str]] = [
    # 1. STRONG clean.
    (0.80, 0.78, +0.139, +0.119, "STRONG_SIGNAL_IN_PHASE_COHERENCE"),
    # 2. STRONG boundary inclusive (both AUC=0.75; both ΔAUC≥0.05).
    (0.75, 0.75, +0.089, +0.089, "STRONG_SIGNAL_IN_PHASE_COHERENCE"),
    # 3. PARTIAL via auc_h just below STRONG.
    (0.74, 0.78, +0.079, +0.119, "PARTIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 4. PARTIAL via one benchmark passes both PARTIAL conditions.
    (0.70, 0.62, +0.039, -0.041, "PARTIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 5. PARTIAL boundary: auc_h = 0.66 inclusive.
    (0.66, 0.55, +0.001, -0.111, "PARTIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 6. NO_MATERIAL: both AUC < 0.66; both ΔAUC < 0.
    (0.65, 0.65, -0.011, -0.011, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 7. NO_MATERIAL: exact baseline both; ΔAUC = 0 (not > 0).
    (0.661, 0.661, 0.0, 0.0, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 8. NO_MATERIAL via direction gate (auc_h < 0.5).
    (0.49, 0.78, -0.171, +0.119, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 9. NO_MATERIAL via direction gate (both < 0.5).
    (0.45, 0.40, -0.211, -0.261, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 10. PARTIAL via direction gate inclusive (auc_h = 0.5; passes gate).
    (0.50, 0.78, -0.161, +0.119, "PARTIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 11. NO_MATERIAL via direction gate strict (auc_h = 0.499).
    (0.499, 0.80, -0.162, +0.139, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 12. NO_MATERIAL: direction holds but both fail PARTIAL conditions.
    (0.55, 0.55, -0.111, -0.111, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
]


# ===========================================================================
# Dataclasses — immutable records.
# ===========================================================================


@dataclass(frozen=True)
class BenchmarkLabels:
    """Per-question correctness labels + question text loaded from §13.10 dump."""

    benchmark: str
    q_ids: tuple[int, ...]
    questions: tuple[str, ...]
    correctness: tuple[bool, ...]


@dataclass(frozen=True)
class HiddenStateExtraction:
    """All-29-layer last-token hidden states aligned with labels."""

    benchmark: str
    q_ids: np.ndarray  # int, shape (N,)
    hidden_states: np.ndarray  # float, shape (N, n_layers, d)
    correctness: np.ndarray  # bool, shape (N,)
    n_layers: int
    d: int


@dataclass(frozen=True)
class CoherenceMatrixSummary:
    """Sanity statistics over the 406 upper-triangular off-diagonal C entries."""

    off_diag_min: float
    off_diag_mean: float
    off_diag_max: float
    off_diag_std: float
    n_off_diag_entries: int


@dataclass(frozen=True)
class PhaseCoherenceResult:
    """Per-benchmark phase-coherence probe result."""

    benchmark: str
    n_questions: int
    n_correct: int
    n_wrong: int
    pi_observed: float
    auc_phase: float
    auc_baseline: float  # 0.661
    dauc_phase: float  # auc_phase - auc_baseline
    auc_supervised_phase_1: float  # disclosure only
    dauc_phase_vs_supervised: float  # disclosure only
    direction_held: bool  # auc_phase >= 0.5
    f_per_question: tuple[float, ...]
    coherence_matrix_summary: CoherenceMatrixSummary
    operating_points: tuple[dict, ...]
    kappa_at_alpha_primary: float
    tau_star_at_alpha_primary: float


@dataclass(frozen=True)
class CascadeVerdict:
    """Final §15.11 cascade outcome."""

    label: str  # STRONG_/PARTIAL_/NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE
    auc_halueval: float
    auc_truthfulqa: float
    dauc_halueval: float
    dauc_truthfulqa: float
    direction_held_halueval: bool
    direction_held_truthfulqa: bool
    rationale: str


@dataclass(frozen=True)
class PhaseAuditOutputs:
    """Top-level §15.11 outputs for both benchmarks."""

    schema_version: str
    halueval_result: PhaseCoherenceResult
    truthfulqa_result: PhaseCoherenceResult
    cascade_verdict: CascadeVerdict
    n_layers_used: int
    hidden_dim: int
    qwen_model_id: str
