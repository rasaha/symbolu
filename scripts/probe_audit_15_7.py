#!/usr/bin/env python
"""§15.7 — Diagnostic post-processing audit on existing dumps (no new compute).

Pure post-processing diagnostic implementation per the frozen
§15.7 pre-commitment (Chunks 7a-7h).

Reference: Project_documentation/repository/docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md §15.7.

What this script DOES:
  Reads four on-disk artifacts (§14a.2 dumps for both benchmarks,
  §15.2 verdict-of-record, §13.10 dumps) and computes:
    - Class-conditional CDFs F_1(tau), F_0(tau).
    - Separation diagnostic Delta(tau) = F_1 - F_0.
    - Likelihood-ratio rho(tau) = F_1/F_0.
    - Base-rate-adjusted threshold rho*(alpha, pi) and pass/fail
      against rho(tau*) at each pinned alpha target.
    - Precision and coverage curves p(tau), c(tau).
    - Step-size audit (number of distinct r values, jump sizes,
      operating-point collapse).
    - Stage A / B / Composition decomposition with three failure
      modes (A-DEGENERATE, B-INSUFFICIENT, C-MISMATCHED, MIXED).
    - §15.6 sampling-noise hypothesis test (KS two-sample +
      distance metrics) classifying as HYPOTHESIS_SUPPORTED,
      HYPOTHESIS_REFUTED, or HYPOTHESIS_PARTIAL.
    - Diagnostic decision-tree classification per benchmark.
    - Interpretation-firewall-enforced markdown narrative using
      one of four pinned templates per (benchmark, verdict) pair.

What this script DOES NOT do:
  - Re-classify any §13/§14/§15.x verdict-of-record. All bands
    pinned in prior §0.8 chapters remain binding regardless of
    §15.7 outputs.
  - Modify any input artifact.
  - Run any new generation, NLI, GPU compute, or network access.
  - Authorize §15.8 follow-up.
  - Relax §13.9 VC-brief hold.
  - Strengthen §6.1 autonomy claim.

The interpretation firewall (Chunk 7f) is enforced at write time:
emitted markdown is checked for Class-3 forbidden statements
(verdict overrides, band reassignments, §13.9 relaxation, etc.);
detection triggers INTERPRETATION_VIOLATION and aborts before
any artifact is written.

Inputs (per §15.7 Chunk 7b):
    docs/experiments/probe_system_level_scout_v2_halueval_qa.json
    docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json
    docs/experiments/probe_selective_abstention.json
    docs/experiments/probe_semantic_entropy.json
    docs/experiments/probe_semantic_entropy_halueval_qa.json

Outputs (per §15.7 Chunk 7g):
    docs/experiments/probe_audit_15_7.json
    docs/experiments/probe_audit_15_7.md

Usage:
    # Required pre-execution gate.
    python scripts/probe_audit_15_7.py --self-test

    # Real-data audit (auto-runs --self-test first; aborts on failure).
    python scripts/probe_audit_15_7.py

    # Real-data audit skipping self-test gate (debug only).
    python scripts/probe_audit_15_7.py --no-self-test

§15.1 / §15.3 / §15.5 metric primitives are COPIED, not imported,
to preserve those scripts' reproducibility chains (per §15.5
Chunk 5h discipline applied recursively to §15.7).

scipy.stats.ks_2samp is used if available; if not, a numpy-only
two-sample KS implementation is used (documented inline). Both
produce identical KS statistics within float-precision; only
the p-value approximation differs slightly between the scipy
asymptotic form and the numpy fallback.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from scipy.stats import ks_2samp as _scipy_ks_2samp
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False
    _scipy_ks_2samp = None

# ===========================================================================
# §15.7 PINNED CONSTANTS — DO NOT CHANGE during implementation.
# Any change requires a fresh §0.8 amendment to §15.7.
# ===========================================================================

SCHEMA_VERSION = "15.7-diagnostic"

# Chunk 7e — sampling-noise hypothesis test thresholds.
KS_PVALUE_THRESHOLD = 0.05
DISTANCE_THRESHOLD_NATS = 0.10
DISTANCE_THRESHOLD_PARTIAL_UPPER = 0.20

# Chunk 7c (inherited from §15.1 / §15.3 / §15.5) — minimum-answered floor.
N_MIN = 10

# Chunk 7c — pinned target accuracies per benchmark.
ALPHA_TARGETS_PER_BENCHMARK: dict[str, tuple[float, ...]] = {
    "halueval_qa": (0.40, 0.50, 0.75),
    "truthfulqa_mc": (0.35, 0.50, 0.75),
}
ALPHA_PRIMARY = 0.50

# Chunk 7c — pinned base rates pi per configuration (drives rho*).
# Computed from §13.10 prose / §14c verdict-of-record / §15.6 Chunk 6c.
PINNED_PI: dict[str, dict[str, float]] = {
    # benchmark → configuration → pi
    "halueval_qa": {
        "hybrid_v1": 0.330,         # §14c V1 acc on HaluEval
        "single_source_qwen": 0.300,  # §13.10 Qwen greedy
    },
    "truthfulqa_mc": {
        "hybrid_v1": 0.250,         # §15.6 V1 acc on TruthfulQA-MC
        "single_source_qwen": 0.250,  # §13.10 Qwen greedy
    },
}

# Chunk 7d — Stage A / B / Composition decision-tree thresholds.
STAGE_A_DEGENERATE_DELTA_THRESHOLD = 0.01     # |Delta_A| < this → Stage A failure
STAGE_A_DEGENERATE_DSET_FRACTION = 0.05        # |D|/N < this → Stage A small divergence
COMPOSITION_CORR_GAP_THRESHOLD = 0.30          # |corr(D-bar) - corr(D)| > this → C-MISMATCHED

# Chunk 7b — pinned input paths (relative to repo root).
INPUT_HALUEVAL_DUMP = "docs/experiments/probe_system_level_scout_v2_halueval_qa.json"
INPUT_TRUTHFULQA_DUMP = "docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json"
INPUT_S15_2_ARTIFACT = "docs/experiments/probe_selective_abstention.json"
INPUT_S13_10_TRUTHFULQA = "docs/experiments/probe_semantic_entropy.json"
INPUT_S13_10_HALUEVAL = "docs/experiments/probe_semantic_entropy_halueval_qa.json"

# Chunk 7g — pinned output paths.
OUTPUT_JSON_PATH = "docs/experiments/probe_audit_15_7.json"
OUTPUT_MD_PATH = "docs/experiments/probe_audit_15_7.md"

# Chunk 7b — pinned field expectations.
FIELD_QUESTIONS = "questions"
FIELD_QUESTION_ID = "q_idx"
FIELD_SOURCES = "sources"
FIELD_SOURCE_ENTROPY = "semantic_entropy"
FIELD_SOURCE_NAME = "source_name"
FIELD_ANSWER_CLUSTER_IDS = "answer_cluster_ids"
FIELD_V1_WEIGHTS = "v1_weights"
FIELD_V1_WINNING_CLUSTER = "v1_winning_cluster"
FIELD_V1_CORRECT = "v1_correct"
FIELD_BASELINE_A_CORRECT = "baseline_a_correct"

FIELD_S13_10_ENTROPY = "semantic_entropy"
FIELD_S13_10_CORRECT = "greedy_matches_correct"
FIELD_S13_10_QID = "q_idx"

FIELD_S15_2_SCHEMA_VERSION = "schema_version"
EXPECTED_S15_2_SCHEMA_VERSION = "15.1"
FIELD_S15_2_BENCHMARKS = "benchmarks"
FIELD_S15_2_KAPPA = "kappa"

# Chunk 7f — Class-3 forbidden-statement substrings.
# The interpretation firewall scans markdown output for these BEFORE writing.
# Match is case-insensitive substring match.
CLASS_3_FORBIDDEN_PATTERNS: list[str] = [
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
]

# Chunk 7d / 7e — self-test boundary cases for both classifiers.

# Stage-A/B/Composition decision-tree self-test cases.
# Each case: (decomposition_inputs_dict, expected_class_label).
SELF_TEST_DECISION_TREE_CASES: list[tuple[dict, str]] = [
    # A-DEGENERATE: V1 picked Qwen on all, Delta_A ~ 0.
    (
        {
            "delta_a": 0.000,
            "d_set_fraction": 0.00,
            "rho_at_tau_star_meets_target": True,  # not relevant
            "corr_dbar": 0.30,
            "corr_d": 0.30,
        },
        "A-DEGENERATE",
    ),
    # B-INSUFFICIENT: Stage A produces some lift, but rho<rho* near operating point.
    (
        {
            "delta_a": 0.05,
            "d_set_fraction": 0.10,
            "rho_at_tau_star_meets_target": False,
            "corr_dbar": 0.30,
            "corr_d": 0.30,
        },
        "B-INSUFFICIENT",
    ),
    # C-MISMATCHED: rho meets target overall, but corr drops on V1-divergent set.
    (
        {
            "delta_a": 0.05,
            "d_set_fraction": 0.10,
            "rho_at_tau_star_meets_target": True,
            "corr_dbar": 0.50,
            "corr_d": 0.10,
        },
        "C-MISMATCHED",
    ),
    # MIXED: multiple criteria fire.
    (
        {
            "delta_a": 0.000,
            "d_set_fraction": 0.00,
            "rho_at_tau_star_meets_target": False,
            "corr_dbar": 0.50,
            "corr_d": 0.10,
        },
        "MIXED",
    ),
]

# Sampling-noise hypothesis classifier self-test cases.
# Each case: (ks_pvalue, mean_diff, stdev_diff, expected_label).
SELF_TEST_SAMPLING_NOISE_CASES: list[tuple[float, float, float, str]] = [
    (0.50, 0.05, 0.05, "HYPOTHESIS_SUPPORTED"),
    (0.001, 0.30, 0.30, "HYPOTHESIS_REFUTED"),
    (0.50, 0.15, 0.05, "HYPOTHESIS_PARTIAL"),
    (0.50, 0.05, 0.15, "HYPOTHESIS_PARTIAL"),
    (0.001, 0.05, 0.05, "HYPOTHESIS_REFUTED"),  # p fails alone
    (0.50, 0.25, 0.05, "HYPOTHESIS_REFUTED"),   # mean_diff > 0.20 (above PARTIAL upper)
]


# ===========================================================================
# Dataclasses — immutable record types for clarity.
# ===========================================================================


@dataclass(frozen=True)
class HybridDumpRecord:
    """Per-question record extracted from a §14a.2-class dump."""

    q_idx: int
    winning_source_name: str
    winning_source_idx: int
    selected_answer_correct: bool
    baseline_a_correct: bool
    risk_score: float                        # H_src of winning source
    per_source_entropies: tuple[float, ...]  # length M=3
    per_source_names: tuple[str, ...]


@dataclass(frozen=True)
class S13_10DumpRecord:
    """Per-question record from a §13.10 dump (Qwen greedy + entropy)."""

    q_idx: int
    semantic_entropy: float
    greedy_matches_correct: bool


@dataclass(frozen=True)
class CurveAuditResult:
    """Per-benchmark output of the diagnostic curve computation."""

    benchmark: str
    n_questions: int
    n_correct: int
    n_wrong: int
    pi_observed: float
    grid: list[float]
    f1_curve: list[float]
    f0_curve: list[float]
    delta_curve: list[float]
    rho_curve: list[float]
    p_curve: list[float]
    c_curve: list[float]
    rho_star_per_alpha: dict[float, float]
    operating_points: list[dict]  # one per alpha target
    n_distinct_r: int
    jump_sizes: list[float]
    operating_point_collapse: list[tuple[float, float, bool]]


@dataclass(frozen=True)
class StageABCDecomposition:
    """Per-benchmark Stage A / B / Composition decomposition outputs."""

    benchmark: str
    v1_selection_histogram: dict[str, int]
    d_set_size: int
    d_set_fraction: float
    delta_a: float
    pi_s: float
    pi_a: float
    delta_d_subset: float
    rho_at_tau_star_meets_target: bool
    rho_summary_at_alpha2: dict[str, float]
    corr_pearson_overall: float
    corr_spearman_overall: float
    corr_pearson_dbar: float
    corr_pearson_d: float
    corr_pearson_gap: float
    classification: str  # A-DEGENERATE / B-INSUFFICIENT / C-MISMATCHED / MIXED


@dataclass(frozen=True)
class SamplingNoiseTestResult:
    """§15.6 sampling-noise hypothesis test result on TruthfulQA-MC."""

    benchmark: str
    n_15_5_phase_1: int
    n_13_10_reference: int
    n_13_10_overwritten: bool
    ks_statistic: float
    ks_pvalue: float
    mean_diff_nats: float
    stdev_diff_nats: float
    classification: str  # HYPOTHESIS_SUPPORTED / REFUTED / PARTIAL
    classification_rationale: str


@dataclass(frozen=True)
class AuditOutputs:
    """Top-level §15.7 outputs across both benchmarks."""

    schema_version: str
    halueval_curves: CurveAuditResult
    truthfulqa_curves: CurveAuditResult
    halueval_decomposition: StageABCDecomposition
    truthfulqa_decomposition: StageABCDecomposition
    sampling_noise_test: SamplingNoiseTestResult
    s15_2_baselines: dict[str, float]
    s13_10_n200_status: dict[str, bool]


# ===========================================================================
# Components 1-4: schema validators + four dump loaders.
# Per §15.7 Chunk 7b. Fail-fast on any missing/malformed field.
# ===========================================================================


def _abort_schema(message: str) -> None:
    """Print SCHEMA_MISMATCH and exit with code 2 (matches §15.5/§15.3)."""
    print(f"SCHEMA_MISMATCH: {message}", file=sys.stderr)
    print(
        "  (per §15.7 Chunk 7b, the four input artifacts are pinned; "
        "no fallback path is consulted.)",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _load_json(path: Path) -> object:
    """Read+parse JSON or fail-fast SCHEMA_MISMATCH."""
    if not path.exists():
        _abort_schema(f"input artifact not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        _abort_schema(f"{path} is not valid JSON: {e}")
        return None  # unreachable; placates type-checkers


def load_hybrid_dump(path: Path, benchmark: str) -> list[HybridDumpRecord]:
    """Component 2 — load §14a.2-class dump.

    Validates against Chunk 7b's pinned per-question fields:
      q_idx, sources[i].semantic_entropy, sources[i].source_name,
      answer_cluster_ids, v1_weights, v1_winning_cluster, v1_correct,
      baseline_a_correct.

    Extracts winning_source via cluster + v1_weights argmax (mirrors
    §15.3 / §15.5 Phase 2 Stage A handoff extraction).

    Returns list of HybridDumpRecord; aborts SCHEMA_MISMATCH on any
    missing/malformed field.
    """
    payload = _load_json(path)
    if not isinstance(payload, dict) or FIELD_QUESTIONS not in payload:
        _abort_schema(f"{path}: top-level missing '{FIELD_QUESTIONS}'")
    questions = payload[FIELD_QUESTIONS]
    if not isinstance(questions, list):
        _abort_schema(f"{path}.{FIELD_QUESTIONS} not a list")

    required_per_q = (
        FIELD_QUESTION_ID,
        FIELD_SOURCES,
        FIELD_ANSWER_CLUSTER_IDS,
        FIELD_V1_WEIGHTS,
        FIELD_V1_WINNING_CLUSTER,
        FIELD_V1_CORRECT,
        FIELD_BASELINE_A_CORRECT,
    )

    records: list[HybridDumpRecord] = []
    seen_ids: set[int] = set()
    for i, rec in enumerate(questions):
        if not isinstance(rec, dict):
            _abort_schema(f"{path}.questions[{i}] not a JSON object")
        for f in required_per_q:
            if f not in rec:
                _abort_schema(
                    f"{path}.questions[{i}] missing required field '{f}'"
                )
        sources = rec[FIELD_SOURCES]
        if not isinstance(sources, list) or len(sources) < 1:
            _abort_schema(
                f"{path}.questions[{i}].sources must be a non-empty list"
            )
        for j, src in enumerate(sources):
            if (
                not isinstance(src, dict)
                or FIELD_SOURCE_ENTROPY not in src
                or FIELD_SOURCE_NAME not in src
            ):
                _abort_schema(
                    f"{path}.questions[{i}].sources[{j}] missing "
                    f"'{FIELD_SOURCE_ENTROPY}' or '{FIELD_SOURCE_NAME}'"
                )

        # Extract winning source per cluster + v1_weights argmax.
        cluster_ids = rec[FIELD_ANSWER_CLUSTER_IDS]
        v1_weights = rec[FIELD_V1_WEIGHTS]
        winning_cluster = rec[FIELD_V1_WINNING_CLUSTER]
        if len(cluster_ids) != len(sources) or len(v1_weights) != len(sources):
            _abort_schema(
                f"{path}.questions[{i}] cluster_ids / v1_weights length "
                f"mismatch with sources"
            )
        candidates = [
            j for j in range(len(sources))
            if cluster_ids[j] == winning_cluster
        ]
        if not candidates:
            _abort_schema(
                f"{path}.questions[{i}] winning_cluster {winning_cluster} "
                f"has no member sources"
            )
        winner_idx = max(candidates, key=lambda j: (v1_weights[j], -j))

        q_id = int(rec[FIELD_QUESTION_ID])
        if q_id in seen_ids:
            _abort_schema(f"{path}.questions[{i}] duplicate q_idx {q_id}")
        seen_ids.add(q_id)

        per_source_entropies = tuple(
            float(s[FIELD_SOURCE_ENTROPY]) for s in sources
        )
        per_source_names = tuple(
            str(s[FIELD_SOURCE_NAME]) for s in sources
        )

        records.append(HybridDumpRecord(
            q_idx=q_id,
            winning_source_name=per_source_names[winner_idx],
            winning_source_idx=winner_idx,
            selected_answer_correct=bool(rec[FIELD_V1_CORRECT]),
            baseline_a_correct=bool(rec[FIELD_BASELINE_A_CORRECT]),
            risk_score=per_source_entropies[winner_idx],
            per_source_entropies=per_source_entropies,
            per_source_names=per_source_names,
        ))

    if not records:
        _abort_schema(f"{path}: no question records loaded")
    return records


def load_s13_10_dump(path: Path) -> list[S13_10DumpRecord]:
    """Component 3 — load §13.10 dump (Qwen K=10 entropy + correctness).

    Used ONLY for distributional comparison (Chunk 7e sampling-noise
    test), per the §15.7 Chunk 7b §0.8 caveat. Does NOT re-derive the
    §15.2 verdict-of-record.

    Validates against the §15.1 Amendment 1 pinned field list:
      q_idx, semantic_entropy, greedy_matches_correct.

    Note: dumps on disk are now N=200 per §13.20 / §15.2 Postscript.
    The N status is recorded by caller, not by this loader.
    """
    payload = _load_json(path)
    if not isinstance(payload, list):
        _abort_schema(f"{path}: top-level must be a JSON list")

    required = (FIELD_S13_10_QID, FIELD_S13_10_ENTROPY, FIELD_S13_10_CORRECT)
    records: list[S13_10DumpRecord] = []
    seen_ids: set[int] = set()
    for i, rec in enumerate(payload):
        if not isinstance(rec, dict):
            _abort_schema(f"{path}[{i}] not a JSON object")
        for f in required:
            if f not in rec:
                _abort_schema(
                    f"{path}[{i}] missing required field '{f}' "
                    f"(per §15.1 Amendment 1 pinned schema)"
                )
        q_id = int(rec[FIELD_S13_10_QID])
        if q_id in seen_ids:
            _abort_schema(f"{path}[{i}] duplicate q_idx {q_id}")
        seen_ids.add(q_id)
        records.append(S13_10DumpRecord(
            q_idx=q_id,
            semantic_entropy=float(rec[FIELD_S13_10_ENTROPY]),
            greedy_matches_correct=bool(rec[FIELD_S13_10_CORRECT]),
        ))
    return records


def load_s15_2_baselines(path: Path) -> dict[str, float]:
    """Component 4 — load §15.2 verdict-of-record kappa baselines.

    Validates schema_version == "15.1" AND extracts
    benchmarks.{truthfulqa_mc, halueval_qa}.kappa.

    Returns {"truthfulqa_mc": kappa, "halueval_qa": kappa}.
    """
    payload = _load_json(path)
    if not isinstance(payload, dict):
        _abort_schema(f"{path}: top-level must be a JSON object")
    schema_version = payload.get(FIELD_S15_2_SCHEMA_VERSION)
    if schema_version != EXPECTED_S15_2_SCHEMA_VERSION:
        _abort_schema(
            f"{path}: schema_version is {schema_version!r}, expected "
            f"{EXPECTED_S15_2_SCHEMA_VERSION!r} (§15.2 verdict-of-record)"
        )
    benchmarks = payload.get(FIELD_S15_2_BENCHMARKS)
    if not isinstance(benchmarks, dict):
        _abort_schema(
            f"{path}.{FIELD_S15_2_BENCHMARKS} must be a JSON object"
        )

    out: dict[str, float] = {}
    for bench in ("truthfulqa_mc", "halueval_qa"):
        if bench not in benchmarks:
            _abort_schema(
                f"{path}.{FIELD_S15_2_BENCHMARKS}.{bench} missing"
            )
        bench_block = benchmarks[bench]
        if not isinstance(bench_block, dict) or FIELD_S15_2_KAPPA not in bench_block:
            _abort_schema(
                f"{path}.{FIELD_S15_2_BENCHMARKS}.{bench}.{FIELD_S15_2_KAPPA} missing"
            )
        out[bench] = float(bench_block[FIELD_S15_2_KAPPA])
    return out


def detect_n200_status(s13_10_records: list[S13_10DumpRecord]) -> bool:
    """Detect whether a §13.10 dump is the post-§13.20 N=200 version.

    Returns True if N >= 150 (a permissive threshold that flags either
    N=200 or any future overwrite); False otherwise. Only used for
    the §15.7 Chunk 7b §0.8 caveat note in the result section.
    """
    return len(s13_10_records) >= 150


# ===========================================================================
# Component 5: diagnostic curves per §15.7 Chunk 7c.
# F_1, F_0, Delta, rho, p, c over the empirical threshold grid;
# rho* base-rate-adjusted thresholds; step-size audit;
# operating-point collapse audit.
# ===========================================================================


def _rho_star(alpha: float, pi: float) -> float:
    """Base-rate-adjusted likelihood-ratio threshold for selective
    prediction precision (§15.7 Chunk 7c, Eq. derived).

    Pr(Y=1 | R<tau) >= alpha iff F_1/F_0 >= alpha(1-pi)/((1-alpha)pi).
    Returns +inf if pi == 0 (degenerate; no correct answers exist).
    """
    if pi <= 0.0 or alpha >= 1.0:
        return float("inf")
    if alpha <= 0.0:
        return 0.0
    return (alpha * (1.0 - pi)) / ((1.0 - alpha) * pi)


def _empirical_threshold_grid(risk_scores: np.ndarray) -> np.ndarray:
    """Sorted unique risk-score values plus -inf and +inf.

    Identical primitive to §15.1 / §15.3 / §15.5 Chunk 2c sweep grid.
    """
    uniques = np.unique(risk_scores.astype(float))
    return np.concatenate(([-np.inf], uniques, [np.inf]))


def _class_conditional_cdfs(
    risk_scores: np.ndarray,
    correctness: np.ndarray,
    grid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute F_1(tau) and F_0(tau) at each grid point.

    F_y(tau) = Pr(R < tau | Y = y), strict inequality consistent with
    the §15.x ANSWER if R<tau policy.
    """
    correct_scores = risk_scores[correctness]
    wrong_scores = risk_scores[~correctness]
    n_correct = len(correct_scores)
    n_wrong = len(wrong_scores)

    f1 = np.zeros_like(grid, dtype=np.float64)
    f0 = np.zeros_like(grid, dtype=np.float64)
    for i, tau in enumerate(grid):
        if n_correct > 0:
            f1[i] = float(np.sum(correct_scores < tau)) / n_correct
        if n_wrong > 0:
            f0[i] = float(np.sum(wrong_scores < tau)) / n_wrong
    return f1, f0


def _coverage_and_precision(
    risk_scores: np.ndarray,
    correctness: np.ndarray,
    grid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """c(tau) = Pr(R < tau); p(tau) = Pr(Y=1 | R < tau), NaN if empty."""
    n = len(risk_scores)
    cov = np.zeros_like(grid, dtype=np.float64)
    prec = np.full_like(grid, np.nan, dtype=np.float64)
    for i, tau in enumerate(grid):
        mask = risk_scores < tau
        n_answered = int(np.sum(mask))
        cov[i] = n_answered / n
        if n_answered > 0:
            prec[i] = float(np.sum(correctness[mask])) / n_answered
    return cov, prec


def _step_size_audit(
    risk_scores: np.ndarray, grid: np.ndarray, c_curve: np.ndarray
) -> tuple[int, list[float]]:
    """Number of distinct r values + adjacent-grid coverage jump sizes.

    Per §15.7 Chunk 7c (F): tests the §15.6 Chunk 6b "stepped curve"
    finding empirically.
    """
    n_distinct = int(len(np.unique(risk_scores)))
    jumps = [
        float(c_curve[i + 1] - c_curve[i])
        for i in range(len(c_curve) - 1)
    ]
    return n_distinct, jumps


def _operating_point_for_alpha(
    grid: np.ndarray,
    p_curve: np.ndarray,
    c_curve: np.ndarray,
    f1_curve: np.ndarray,
    f0_curve: np.ndarray,
    alpha: float,
    n_questions: int,
    n_min: int,
) -> dict:
    """Compute cov@alpha, tau_star, rho(tau_star), and meets-rho* flag."""
    best_cov = 0.0
    best_tau = float("inf")
    best_rho = float("nan")
    best_idx = -1
    for i, tau in enumerate(grid):
        cov = float(c_curve[i])
        n_answered = int(round(cov * n_questions))
        if n_answered < n_min:
            continue
        prec = float(p_curve[i])
        if prec != prec:  # NaN
            continue
        if not (prec >= alpha):
            continue
        if cov > best_cov:
            best_cov = cov
            best_tau = float(tau)
            best_idx = i
            f0_here = float(f0_curve[i])
            if f0_here > 0.0:
                best_rho = float(f1_curve[i] / f0_here)
            else:
                best_rho = float("inf")
    return {
        "alpha": alpha,
        "cov_at_alpha": best_cov,
        "tau_star": best_tau,
        "rho_at_tau_star": best_rho,
        "found": best_idx >= 0,
    }


def compute_curve_audit(
    benchmark: str,
    risk_scores: np.ndarray,
    correctness: np.ndarray,
    pi_observed: float,
) -> CurveAuditResult:
    """Component 5 orchestrator — compute all diagnostic curves for one
    benchmark per §15.7 Chunk 7c spec.
    """
    n = len(risk_scores)
    n_correct = int(np.sum(correctness))
    n_wrong = n - n_correct

    grid = _empirical_threshold_grid(risk_scores)
    f1, f0 = _class_conditional_cdfs(risk_scores, correctness, grid)
    delta = f1 - f0
    rho = np.where(f0 > 0.0, f1 / np.where(f0 > 0.0, f0, 1.0), np.inf)
    cov, prec = _coverage_and_precision(risk_scores, correctness, grid)

    n_distinct, jumps = _step_size_audit(risk_scores, grid, cov)

    alpha_targets = ALPHA_TARGETS_PER_BENCHMARK[benchmark]
    rho_star_per_alpha = {a: _rho_star(a, pi_observed) for a in alpha_targets}
    operating_points = []
    for alpha in alpha_targets:
        op = _operating_point_for_alpha(
            grid, prec, cov, f1, f0, alpha, n, N_MIN
        )
        op["rho_star"] = rho_star_per_alpha[alpha]
        op["meets_rho_star"] = (
            op["found"]
            and not math.isnan(op["rho_at_tau_star"])
            and op["rho_at_tau_star"] >= rho_star_per_alpha[alpha]
        )
        operating_points.append(op)

    # Operating-point collapse audit: which adjacent alphas resolve to
    # the same tau*?
    collapse: list[tuple[float, float, bool]] = []
    for i in range(len(alpha_targets) - 1):
        a1 = alpha_targets[i]
        a2 = alpha_targets[i + 1]
        op1 = operating_points[i]
        op2 = operating_points[i + 1]
        same = (
            op1["found"] and op2["found"]
            and abs(op1["tau_star"] - op2["tau_star"]) < 1e-12
        )
        collapse.append((float(a1), float(a2), bool(same)))

    return CurveAuditResult(
        benchmark=benchmark,
        n_questions=n,
        n_correct=n_correct,
        n_wrong=n_wrong,
        pi_observed=pi_observed,
        grid=[float(x) for x in grid.tolist()],
        f1_curve=[float(x) for x in f1.tolist()],
        f0_curve=[float(x) for x in f0.tolist()],
        delta_curve=[float(x) for x in delta.tolist()],
        rho_curve=[float(x) for x in rho.tolist()],
        p_curve=[float(x) for x in prec.tolist()],
        c_curve=[float(x) for x in cov.tolist()],
        rho_star_per_alpha=rho_star_per_alpha,
        operating_points=operating_points,
        n_distinct_r=n_distinct,
        jump_sizes=jumps,
        operating_point_collapse=collapse,
    )


# ===========================================================================
# Components 6-7: Stage A / Stage B / Composition decomposition.
# Per §15.7 Chunk 7d. Three failure modes; pinned decision-tree
# classifier with four outcomes (A-DEGENERATE / B-INSUFFICIENT /
# C-MISMATCHED / MIXED).
# ===========================================================================


def _spearman_rank_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation, numpy-only (no scipy needed).

    Equivalent to Pearson on rank-transformed inputs. Returns NaN if
    either array has zero variance after ranking (constant).
    """
    if len(x) < 2:
        return float("nan")
    rx = np.argsort(np.argsort(x)).astype(np.float64)
    ry = np.argsort(np.argsort(y)).astype(np.float64)
    if np.std(rx) == 0.0 or np.std(ry) == 0.0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def _pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation, NaN if either input is constant."""
    if len(x) < 2 or np.std(x) == 0.0 or np.std(y) == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _v1_selection_histogram(records: list[HybridDumpRecord]) -> dict[str, int]:
    """Count of questions where V1 picked each source name."""
    counts: dict[str, int] = {}
    for r in records:
        counts[r.winning_source_name] = counts.get(r.winning_source_name, 0) + 1
    return counts


def _classify_decision_tree(inputs: dict) -> str:
    """Component 7 — pinned diagnostic decision-tree classifier.

    Per §15.7 Chunk 7d. Four outcomes:
      - A-DEGENERATE: |Delta_A| < threshold AND d_set_fraction < threshold.
      - B-INSUFFICIENT: rho < rho* near operating point AND not A-DEGENERATE.
      - C-MISMATCHED: |corr(D-bar) - corr(D)| > gap threshold AND not A.
      - MIXED: A AND (B OR C) — two or more modes co-fire; OR none of A/B/C
        fire but the inputs are anomalous; OR A-DEGENERATE plus C-MISMATCHED
        on the small remaining D set.

    Decision rule: classify as A-DEGENERATE first (most parsimonious),
    then check additive composition with B / C as MIXED if those also
    indicate failure.
    """
    delta_a = inputs["delta_a"]
    d_frac = inputs["d_set_fraction"]
    rho_meets = inputs["rho_at_tau_star_meets_target"]
    corr_dbar = inputs["corr_dbar"]
    corr_d = inputs["corr_d"]

    is_a = (
        abs(delta_a) < STAGE_A_DEGENERATE_DELTA_THRESHOLD
        and d_frac < STAGE_A_DEGENERATE_DSET_FRACTION
    )
    is_b = not rho_meets
    # C-MISMATCHED only meaningful when D is non-trivial.
    if d_frac >= STAGE_A_DEGENERATE_DSET_FRACTION:
        corr_gap = abs(corr_dbar - corr_d)
        is_c = corr_gap > COMPOSITION_CORR_GAP_THRESHOLD
    else:
        # D set too small to evaluate composition reliably; do not fire C.
        is_c = False

    # Combine.
    if is_a and (is_b or is_c):
        return "MIXED"
    if is_a:
        return "A-DEGENERATE"
    if is_b and is_c:
        return "MIXED"
    if is_b:
        return "B-INSUFFICIENT"
    if is_c:
        return "C-MISMATCHED"
    # None of the failure modes fire — the data isn't anomalous in any
    # of the three pinned ways. Classify as MIXED to flag for inspection.
    return "MIXED"


def compute_decomposition(
    benchmark: str,
    records: list[HybridDumpRecord],
    curves: CurveAuditResult,
) -> StageABCDecomposition:
    """Component 6 orchestrator — compute Stage A / B / Composition
    decomposition for one benchmark per §15.7 Chunk 7d spec.
    """
    n = len(records)

    # V1 selection identity.
    v1_hist = _v1_selection_histogram(records)

    # Identify Qwen — we use the convention that the source whose name
    # contains 'Qwen' (case-insensitive) is Baseline-A's source. This
    # mirrors §14a.2's qwen_baseline_idx default.
    def _is_qwen(name: str) -> bool:
        return "qwen" in name.lower()

    d_set = [r for r in records if not _is_qwen(r.winning_source_name)]
    dbar_set = [r for r in records if _is_qwen(r.winning_source_name)]
    d_size = len(d_set)
    d_frac = d_size / n if n > 0 else 0.0

    # Stage A net lift: pi_S - pi_A (computed over all questions).
    pi_s = float(np.mean([r.selected_answer_correct for r in records]))
    pi_a = float(np.mean([r.baseline_a_correct for r in records]))
    delta_a = pi_s - pi_a

    # Stage A divergent-subset correctness delta.
    if d_size > 0:
        delta_d_subset = (
            float(np.mean([r.selected_answer_correct for r in d_set]))
            - float(np.mean([r.baseline_a_correct for r in d_set]))
        )
    else:
        delta_d_subset = 0.0

    # Stage B local condition test at alpha_2 = 0.50.
    op_alpha2 = next(
        (op for op in curves.operating_points
         if abs(op["alpha"] - ALPHA_PRIMARY) < 1e-9),
        None,
    )
    if op_alpha2 is not None:
        rho_meets = bool(op_alpha2["meets_rho_star"])
        rho_summary = {
            "alpha_2": ALPHA_PRIMARY,
            "tau_star": op_alpha2["tau_star"],
            "rho_at_tau_star": op_alpha2["rho_at_tau_star"],
            "rho_star": op_alpha2["rho_star"],
            "meets_rho_star": float(rho_meets),
        }
    else:
        rho_meets = False
        rho_summary = {
            "alpha_2": ALPHA_PRIMARY,
            "tau_star": float("inf"),
            "rho_at_tau_star": float("nan"),
            "rho_star": _rho_star(ALPHA_PRIMARY, pi_s),
            "meets_rho_star": 0.0,
        }

    # Composition: per-question correlation of R_S with (1 - Y_S),
    # split by D-bar (Qwen-picked) vs D (non-Qwen-picked).
    risk_all = np.array([r.risk_score for r in records], dtype=np.float64)
    wrong_y_all = 1.0 - np.array(
        [r.selected_answer_correct for r in records], dtype=np.float64
    )
    corr_pearson_overall = _pearson_corr(risk_all, wrong_y_all)
    corr_spearman_overall = _spearman_rank_corr(risk_all, wrong_y_all)

    if dbar_set:
        risk_dbar = np.array([r.risk_score for r in dbar_set], dtype=np.float64)
        wrong_dbar = 1.0 - np.array(
            [r.selected_answer_correct for r in dbar_set], dtype=np.float64
        )
        corr_pearson_dbar = _pearson_corr(risk_dbar, wrong_dbar)
    else:
        corr_pearson_dbar = float("nan")

    if d_set:
        risk_d = np.array([r.risk_score for r in d_set], dtype=np.float64)
        wrong_d = 1.0 - np.array(
            [r.selected_answer_correct for r in d_set], dtype=np.float64
        )
        corr_pearson_d = _pearson_corr(risk_d, wrong_d)
    else:
        corr_pearson_d = float("nan")

    # Composition gap: NaN-safe substitution for classifier inputs.
    cdbar = corr_pearson_dbar if not math.isnan(corr_pearson_dbar) else 0.0
    cd = corr_pearson_d if not math.isnan(corr_pearson_d) else cdbar
    corr_gap = float(cdbar - cd)

    classification = _classify_decision_tree({
        "delta_a": delta_a,
        "d_set_fraction": d_frac,
        "rho_at_tau_star_meets_target": rho_meets,
        "corr_dbar": cdbar,
        "corr_d": cd,
    })

    return StageABCDecomposition(
        benchmark=benchmark,
        v1_selection_histogram=v1_hist,
        d_set_size=d_size,
        d_set_fraction=d_frac,
        delta_a=delta_a,
        pi_s=pi_s,
        pi_a=pi_a,
        delta_d_subset=delta_d_subset,
        rho_at_tau_star_meets_target=rho_meets,
        rho_summary_at_alpha2=rho_summary,
        corr_pearson_overall=corr_pearson_overall,
        corr_spearman_overall=corr_spearman_overall,
        corr_pearson_dbar=corr_pearson_dbar,
        corr_pearson_d=corr_pearson_d,
        corr_pearson_gap=corr_gap,
        classification=classification,
    )


# ===========================================================================
# Component 8: §15.6 sampling-noise hypothesis test.
# Per §15.7 Chunk 7e. KS two-sample test + summary distance metrics.
# Three pinned outcomes: HYPOTHESIS_SUPPORTED / REFUTED / PARTIAL.
# ===========================================================================


def _numpy_ks_2samp(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Numpy-only two-sample KS (Smirnov-Cramér-von Mises asymptotic).

    Used as fallback when scipy.stats.ks_2samp is unavailable.

    Returns (KS_statistic, two-sided asymptotic p-value).

    The KS statistic is exact: D = max_x |F_a(x) - F_b(x)|. The
    p-value uses the Smirnov asymptotic series, identical functional
    form to scipy's old non-exact branch.
    """
    a = np.sort(a.astype(np.float64))
    b = np.sort(b.astype(np.float64))
    n_a = len(a)
    n_b = len(b)
    if n_a == 0 or n_b == 0:
        return 0.0, 1.0

    # Empirical CDFs evaluated at the union of points.
    all_pts = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, all_pts, side="right") / n_a
    cdf_b = np.searchsorted(b, all_pts, side="right") / n_b
    d_stat = float(np.max(np.abs(cdf_a - cdf_b)))

    # Smirnov two-sided asymptotic p-value:
    # p = 2 * sum_{j=1..inf} (-1)^(j-1) exp(-2 j^2 lambda^2)
    # where lambda = (sqrt(n_eff) + 0.12 + 0.11/sqrt(n_eff)) * D
    # and n_eff = n_a*n_b / (n_a+n_b).
    n_eff = (n_a * n_b) / (n_a + n_b)
    if n_eff <= 0.0:
        return d_stat, 1.0
    sqrt_n_eff = math.sqrt(n_eff)
    lam = (sqrt_n_eff + 0.12 + 0.11 / sqrt_n_eff) * d_stat
    if lam <= 0.0:
        return d_stat, 1.0
    j = 1
    p = 0.0
    sign = 1.0
    for _ in range(101):
        term = sign * math.exp(-2.0 * j * j * lam * lam)
        p += term
        if abs(term) < 1e-12:
            break
        j += 1
        sign = -sign
    p_value = max(0.0, min(1.0, 2.0 * p))
    return d_stat, p_value


def _ks_two_sample(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Wrapper that uses scipy.stats.ks_2samp if available, else falls
    back to the numpy implementation. Both produce identical KS
    statistics; p-value formulas differ only in higher-order terms
    that don't matter at the §15.7 alpha=0.05 threshold."""
    if _HAS_SCIPY:
        result = _scipy_ks_2samp(a, b)
        return float(result.statistic), float(result.pvalue)
    return _numpy_ks_2samp(a, b)


def classify_sampling_noise(
    ks_pvalue: float, mean_diff: float, stdev_diff: float
) -> tuple[str, str]:
    """Component 8 — pinned three-outcome classifier per §15.7 Chunk 7e.

    Pinned thresholds:
      - SUPPORTED: p > 0.05 AND |mean_diff| < 0.10 AND |stdev_diff| < 0.10
      - REFUTED: p <= 0.05 OR |mean_diff| > 0.20 OR |stdev_diff| > 0.20
      - PARTIAL: p > 0.05 AND any distance in (0.10, 0.20]

    Returns (label, rationale).
    """
    abs_mean_diff = abs(mean_diff)
    abs_stdev_diff = abs(stdev_diff)
    p_clears = ks_pvalue > KS_PVALUE_THRESHOLD

    if not p_clears:
        return (
            "HYPOTHESIS_REFUTED",
            f"KS p={ks_pvalue:.4f} <= {KS_PVALUE_THRESHOLD} "
            f"rejects distributional equivalence at the pinned alpha.",
        )
    if (
        abs_mean_diff > DISTANCE_THRESHOLD_PARTIAL_UPPER
        or abs_stdev_diff > DISTANCE_THRESHOLD_PARTIAL_UPPER
    ):
        return (
            "HYPOTHESIS_REFUTED",
            f"distance metric exceeds PARTIAL upper bound "
            f"({DISTANCE_THRESHOLD_PARTIAL_UPPER} nats); substantive "
            f"distributional drift even with non-rejecting KS p-value.",
        )
    if (
        abs_mean_diff < DISTANCE_THRESHOLD_NATS
        and abs_stdev_diff < DISTANCE_THRESHOLD_NATS
    ):
        return (
            "HYPOTHESIS_SUPPORTED",
            f"KS p={ks_pvalue:.4f} > {KS_PVALUE_THRESHOLD} AND both "
            f"distance metrics < {DISTANCE_THRESHOLD_NATS} nats; "
            f"distributions statistically and practically equivalent.",
        )
    return (
        "HYPOTHESIS_PARTIAL",
        f"KS p={ks_pvalue:.4f} > {KS_PVALUE_THRESHOLD} but at least "
        f"one distance metric in [{DISTANCE_THRESHOLD_NATS}, "
        f"{DISTANCE_THRESHOLD_PARTIAL_UPPER}] nats; ambiguous.",
    )


def compute_sampling_noise_test(
    s15_5_records: list[HybridDumpRecord],
    s13_10_records: list[S13_10DumpRecord],
) -> SamplingNoiseTestResult:
    """Component 8 orchestrator — sampling-noise hypothesis test on
    TruthfulQA-MC.

    Compares §15.5 Phase 1 R_S distribution (winning-source entropy)
    against §13.10 TruthfulQA-MC Qwen-K=10 entropy distribution.
    Per §15.7 Chunk 7b §0.8 caveat, the §13.10 dump is now N=200; the
    test is about distributional shape.
    """
    s15_5_risk = np.array(
        [r.risk_score for r in s15_5_records], dtype=np.float64
    )
    s13_10_entropy = np.array(
        [r.semantic_entropy for r in s13_10_records], dtype=np.float64
    )

    ks_stat, ks_p = _ks_two_sample(s15_5_risk, s13_10_entropy)
    mean_diff = float(np.mean(s15_5_risk) - np.mean(s13_10_entropy))
    stdev_diff = float(np.std(s15_5_risk) - np.std(s13_10_entropy))

    classification, rationale = classify_sampling_noise(
        ks_p, mean_diff, stdev_diff
    )

    return SamplingNoiseTestResult(
        benchmark="truthfulqa_mc",
        n_15_5_phase_1=len(s15_5_records),
        n_13_10_reference=len(s13_10_records),
        n_13_10_overwritten=detect_n200_status(s13_10_records),
        ks_statistic=ks_stat,
        ks_pvalue=ks_p,
        mean_diff_nats=mean_diff,
        stdev_diff_nats=stdev_diff,
        classification=classification,
        classification_rationale=rationale,
    )


# ===========================================================================
# Component 9: interpretation firewall + narrative template renderer.
# Per §15.7 Chunk 7f. Three statement classes; four pinned templates;
# Class-3 forbidden-statement detection at write time.
# ===========================================================================


# Per-benchmark verdict-of-record (binding under §0.8). Used by the
# template renderer to populate the "verdict band remains [X]" caveat.
S15_VERDICT_PER_BENCHMARK: dict[str, dict[str, str]] = {
    "halueval_qa": {
        "section": "§15.4",
        "verdict": "USEFUL_INTERNAL",
    },
    "truthfulqa_mc": {
        "section": "§15.6",
        "verdict": "REGRESSION",
    },
}


def render_narrative(
    benchmark: str,
    decomp: StageABCDecomposition,
    sampling_noise: Optional[SamplingNoiseTestResult],
) -> str:
    """Render the pinned narrative template for one benchmark per
    §15.7 Chunk 7f.

    Selects exactly one of four pinned templates based on
    decomp.classification, parameterizes with numeric evidence,
    and includes the mandatory "verdict band remains [X]" caveat.

    Returns the markdown-formatted paragraph; caller embeds it in
    the §15.7 result section.
    """
    binding = S15_VERDICT_PER_BENCHMARK[benchmark]
    section_ref = binding["section"]
    verdict_band = binding["verdict"]
    bench_label = benchmark.replace("_", "-")
    cls = decomp.classification

    # Per-benchmark numerics relevant to all templates.
    delta_a = decomp.delta_a
    pi_s = decomp.pi_s
    pi_a = decomp.pi_a
    rho_at_tau = decomp.rho_summary_at_alpha2.get(
        "rho_at_tau_star", float("nan")
    )
    rho_star = decomp.rho_summary_at_alpha2.get("rho_star", float("nan"))
    corr_dbar = decomp.corr_pearson_dbar
    corr_d = decomp.corr_pearson_d

    if cls == "A-DEGENERATE":
        v1_hist = decomp.v1_selection_histogram
        dominant_source = (
            max(v1_hist.items(), key=lambda kv: kv[1])
            if v1_hist
            else ("(none)", 0)
        )
        n_total = sum(v1_hist.values()) if v1_hist else 0
        sn_text = ""
        if sampling_noise is not None and benchmark == "truthfulqa_mc":
            sn_text = (
                f" The sampling-noise hypothesis test on this benchmark "
                f"returned `{sampling_noise.classification}` "
                f"(KS p={sampling_noise.ks_pvalue:.4f}; mean drift = "
                f"{sampling_noise.mean_diff_nats:+.4f} nats; stdev drift = "
                f"{sampling_noise.stdev_diff_nats:+.4f} nats), classification "
                f"rationale: {sampling_noise.classification_rationale}"
            )
        return (
            f"**{bench_label} — A-DEGENERATE classification.** "
            f"On {bench_label}, {section_ref}'s `{verdict_band}` verdict-"
            f"of-record (binding under §0.8) is consistent with Stage A "
            f"degeneration. V1 selected `{dominant_source[0]}` on "
            f"{dominant_source[1]}/{n_total} questions; the V1-divergent "
            f"set has size {decomp.d_set_size}/{n_total} "
            f"({decomp.d_set_fraction:.2%} of N). Stage A net lift "
            f"$\\Delta_A = \\pi_S - \\pi_A = {delta_a:+.4f}$ "
            f"($\\pi_S = {pi_s:.4f}$, $\\pi_A = {pi_a:.4f}$). "
            f"The hybrid effectively reduces to single-source plus "
            f"stochastic sampling on this benchmark.{sn_text} The "
            f"verdict band remains `{verdict_band}` regardless of this "
            f"diagnostic mechanism."
        )

    if cls == "B-INSUFFICIENT":
        return (
            f"**{bench_label} — B-INSUFFICIENT classification.** "
            f"On {bench_label}, {section_ref}'s `{verdict_band}` verdict-"
            f"of-record (binding under §0.8) is anchored by Stage B's "
            f"score-separability failure. The risk score's local "
            f"likelihood-ratio at the operating point "
            f"$\\rho(\\tau^*) = {rho_at_tau:.4f}$ falls below the "
            f"base-rate-adjusted threshold "
            f"$\\rho^*(\\alpha_2={ALPHA_PRIMARY}, \\pi={pi_s:.4f}) = "
            f"{rho_star:.4f}$ near the pinned operating point. The "
            f"verdict band remains `{verdict_band}` regardless of this "
            f"diagnostic mechanism; the failure is local discriminability "
            f"of the score, not Stage A answer-stream degeneration."
        )

    if cls == "C-MISMATCHED":
        return (
            f"**{bench_label} — C-MISMATCHED classification.** "
            f"On {bench_label}, {section_ref}'s `{verdict_band}` verdict-"
            f"of-record (binding under §0.8) is anchored by composition "
            f"failure. The per-source winning-source entropy $R_S$ "
            f"correlates with $1 - Y_S$ at Pearson "
            f"$r_{{\\bar{{D}}}} = {corr_dbar:+.4f}$ on the Qwen-picked "
            f"subset $\\bar{{D}}$ but only $r_{{D}} = {corr_d:+.4f}$ on "
            f"the V1-divergent subset $D$ "
            f"(size {decomp.d_set_size}/{decomp.d_set_size + (decomp.v1_selection_histogram.get('Qwen/Qwen2.5-7B-Instruct', 0) if decomp.v1_selection_histogram else 0)}). "
            f"The hybrid's risk-to-correctness mapping breaks on exactly "
            f"the questions where Stage A's selector matters — a "
            f"hybrid-specific pathology that does not exist in the "
            f"single-source scenario. The verdict band remains "
            f"`{verdict_band}` regardless of this diagnostic mechanism."
        )

    # MIXED template (and fallback).
    return (
        f"**{bench_label} — MIXED / OTHER classification.** "
        f"On {bench_label}, the §15.7 decomposition does not cleanly "
        f"resolve to a single failure mode. Stage A net lift "
        f"$\\Delta_A = {delta_a:+.4f}$; V1-divergent set size "
        f"{decomp.d_set_size} ({decomp.d_set_fraction:.2%}); "
        f"$\\rho(\\tau^*) = {rho_at_tau:.4f}$ vs $\\rho^* = "
        f"{rho_star:.4f}$ at $\\alpha_2 = {ALPHA_PRIMARY}$; "
        f"composition Pearson correlation gap "
        f"$r_{{\\bar{{D}}}} - r_{{D}} = {decomp.corr_pearson_gap:+.4f}$. "
        f"Multiple criteria fire or the data does not match any of the "
        f"three pinned single-mode signatures cleanly. The verdict band "
        f"remains `{verdict_band}` regardless of this diagnostic "
        f"mechanism; the §15.7 decomposition flags this for inspection "
        f"rather than asserting a single mechanism."
    )


def check_class3_forbidden(text: str) -> list[str]:
    """Component 9 — interpretation firewall scanner.

    Searches `text` (case-insensitive substring match) for any of the
    pinned Class-3 forbidden-statement patterns from §15.7 Chunk 7f.
    Returns a list of matched patterns; empty list means no
    violations.

    The orchestrator (Chunk I-9) calls this on the rendered markdown
    BEFORE writing artifacts; non-empty result triggers
    INTERPRETATION_VIOLATION abort.
    """
    text_lower = text.lower()
    violations: list[str] = []
    for pattern in CLASS_3_FORBIDDEN_PATTERNS:
        if pattern.lower() in text_lower:
            violations.append(pattern)
    return violations


def abort_interpretation_violation(violations: list[str]) -> None:
    """Print INTERPRETATION_VIOLATION and exit 4."""
    print(
        "INTERPRETATION_VIOLATION: §15.7 markdown output contains "
        "Class-3 forbidden statements (per §15.7 Chunk 7f firewall).",
        file=sys.stderr,
    )
    print("  Matched forbidden patterns:", file=sys.stderr)
    for v in violations:
        print(f"    - {v!r}", file=sys.stderr)
    print(
        "  Refusing to write artifacts. Either correct the rendering "
        "logic to use a pinned narrative template (see §15.7 Chunk 7f) "
        "or land a fresh §0.8 amendment to §15.7.",
        file=sys.stderr,
    )
    raise SystemExit(4)


# ===========================================================================
# Component 10: self-test gate.
# Required pre-execution gate per §15.7 Chunks 7d / 7e / 7g.
# Verifies both classifiers on synthetic boundary cases.
# ===========================================================================


def self_test() -> int:
    """Run pinned self-test boundary cases for both classifiers.

    Returns 0 on success, nonzero on failure. Aborts real-data
    execution when invoked as a gate (see main()).
    """
    failures: list[str] = []

    # Decision-tree classifier self-test (Chunk 7d boundary cases).
    print("Decision-tree classifier (Chunk 7d):")
    for inputs, expected in SELF_TEST_DECISION_TREE_CASES:
        observed = _classify_decision_tree(inputs)
        ok = observed == expected
        marker = "PASS" if ok else "FAIL"
        # Compact input summary for the log line.
        summary = (
            f"delta_a={inputs['delta_a']:+.3f}, "
            f"d_frac={inputs['d_set_fraction']:.2f}, "
            f"rho_meets={inputs['rho_at_tau_star_meets_target']!s:5}, "
            f"corr_dbar={inputs['corr_dbar']:+.2f}, "
            f"corr_d={inputs['corr_d']:+.2f}"
        )
        print(f"  [{marker}] classify({summary}) = {observed} "
              f"(expected {expected})")
        if not ok:
            failures.append(
                f"decision-tree({summary}) = {observed} != expected "
                f"{expected}"
            )

    # Sampling-noise classifier self-test (Chunk 7e boundary cases).
    print("Sampling-noise classifier (Chunk 7e):")
    for ks_p, mean_diff, stdev_diff, expected in (
        SELF_TEST_SAMPLING_NOISE_CASES
    ):
        observed, _rationale = classify_sampling_noise(
            ks_p, mean_diff, stdev_diff
        )
        ok = observed == expected
        marker = "PASS" if ok else "FAIL"
        print(
            f"  [{marker}] classify_sampling_noise(p={ks_p:.4f}, "
            f"mean_diff={mean_diff:+.3f}, stdev_diff={stdev_diff:+.3f}) "
            f"= {observed} (expected {expected})"
        )
        if not ok:
            failures.append(
                f"sampling-noise(p={ks_p:.4f}, mean={mean_diff:+.3f}, "
                f"stdev={stdev_diff:+.3f}) = {observed} != expected "
                f"{expected}"
            )

    # Interpretation-firewall self-test: verify the scanner detects
    # known Class-3 forbidden patterns.
    print("Interpretation firewall (Chunk 7f):")
    test_violations = [
        ("the §15.6 verdict was wrong", "verdict was wrong"),
        ("Δκ should be re-classified as SATURATION", "should be re-classified"),
        ("§15.4's USEFUL_INTERNAL is invalid because composition", "is invalid because"),
        ("§13.9 hold should be relaxed in light of §15.7", "§13.9 hold should be"),
        ("§15.8 is authorized by these findings", "§15.8 is authorized"),
        ("§6.1 autonomy result is strengthened by this", "autonomy result is strengthened"),
    ]
    for sample_text, expected_match in test_violations:
        violations = check_class3_forbidden(sample_text)
        # Match-detection check: at least one violation pattern should
        # match (case-insensitive substring of sample_text).
        ok = any(expected_match.lower() in v.lower() for v in violations)
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] firewall detects {sample_text!r}")
        if not ok:
            failures.append(
                f"firewall did not detect expected match {expected_match!r} "
                f"in sample {sample_text!r}"
            )

    # Negative-control: clean text should produce no violations.
    clean_text = (
        "The §15.6 REGRESSION verdict-of-record (binding under §0.8) "
        "is consistent with Stage A degeneration. The verdict band "
        "remains REGRESSION regardless of this diagnostic mechanism."
    )
    clean_violations = check_class3_forbidden(clean_text)
    ok = len(clean_violations) == 0
    marker = "PASS" if ok else "FAIL"
    print(f"  [{marker}] firewall passes clean narrative text")
    if not ok:
        failures.append(
            f"firewall false-positive on clean text; matched: "
            f"{clean_violations}"
        )

    if failures:
        print(
            f"\nSELF_TEST FAILED: {len(failures)} mismatch(es).",
            file=sys.stderr,
        )
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print(
        f"\nSELF_TEST PASSED: "
        f"{len(SELF_TEST_DECISION_TREE_CASES)} decision-tree cases + "
        f"{len(SELF_TEST_SAMPLING_NOISE_CASES)} sampling-noise cases + "
        f"{len(test_violations) + 1} firewall cases."
    )
    return 0


# ===========================================================================
# Component 11: output writers — JSON + markdown with firewall enforcement.
# Per §15.7 Chunk 7g. Markdown is rendered first, scanned for Class-3
# forbidden statements, and written only if the firewall passes.
# ===========================================================================


def _curve_audit_to_dict(c: CurveAuditResult) -> dict:
    return {
        "benchmark": c.benchmark,
        "n_questions": c.n_questions,
        "n_correct": c.n_correct,
        "n_wrong": c.n_wrong,
        "pi_observed": c.pi_observed,
        "n_distinct_r": c.n_distinct_r,
        "rho_star_per_alpha": {
            f"{a:.2f}": v for a, v in c.rho_star_per_alpha.items()
        },
        "operating_points": c.operating_points,
        "operating_point_collapse": [
            {"alpha_low": a1, "alpha_high": a2, "same_tau_star": same}
            for (a1, a2, same) in c.operating_point_collapse
        ],
        # Curves emitted as parallel arrays to keep the JSON readable.
        "grid": c.grid,
        "f1_curve": c.f1_curve,
        "f0_curve": c.f0_curve,
        "delta_curve": c.delta_curve,
        "rho_curve": c.rho_curve,
        "p_curve": c.p_curve,
        "c_curve": c.c_curve,
        "jump_sizes": c.jump_sizes,
    }


def _decomposition_to_dict(d: StageABCDecomposition) -> dict:
    return {
        "benchmark": d.benchmark,
        "v1_selection_histogram": d.v1_selection_histogram,
        "d_set_size": d.d_set_size,
        "d_set_fraction": d.d_set_fraction,
        "delta_a": d.delta_a,
        "pi_s": d.pi_s,
        "pi_a": d.pi_a,
        "delta_d_subset": d.delta_d_subset,
        "rho_at_tau_star_meets_target": d.rho_at_tau_star_meets_target,
        "rho_summary_at_alpha2": d.rho_summary_at_alpha2,
        "corr_pearson_overall": d.corr_pearson_overall,
        "corr_spearman_overall": d.corr_spearman_overall,
        "corr_pearson_dbar": d.corr_pearson_dbar,
        "corr_pearson_d": d.corr_pearson_d,
        "corr_pearson_gap": d.corr_pearson_gap,
        "classification": d.classification,
    }


def _sampling_noise_to_dict(s: SamplingNoiseTestResult) -> dict:
    return {
        "benchmark": s.benchmark,
        "n_15_5_phase_1": s.n_15_5_phase_1,
        "n_13_10_reference": s.n_13_10_reference,
        "n_13_10_overwritten": s.n_13_10_overwritten,
        "ks_statistic": s.ks_statistic,
        "ks_pvalue": s.ks_pvalue,
        "mean_diff_nats": s.mean_diff_nats,
        "stdev_diff_nats": s.stdev_diff_nats,
        "classification": s.classification,
        "classification_rationale": s.classification_rationale,
    }


def write_json_artifact(out_path: Path, outputs: AuditOutputs) -> None:
    """Component 11 — emit the §15.7 machine-readable artifact.

    schema_version pinned to "15.7-diagnostic" per Chunk 7g; top-level
    field flags this as diagnostic-only content (NOT a new verdict-of-
    record).
    """
    payload = {
        "schema_version": outputs.schema_version,
        "kind": "DIAGNOSTIC, not a verdict-of-record",
        "scipy_available": _HAS_SCIPY,
        "s15_2_baselines": outputs.s15_2_baselines,
        "s13_10_n200_status": outputs.s13_10_n200_status,
        "benchmarks": {
            "halueval_qa": {
                "binding_verdict_section": (
                    S15_VERDICT_PER_BENCHMARK["halueval_qa"]["section"]
                ),
                "binding_verdict_band": (
                    S15_VERDICT_PER_BENCHMARK["halueval_qa"]["verdict"]
                ),
                "curves": _curve_audit_to_dict(outputs.halueval_curves),
                "decomposition": _decomposition_to_dict(
                    outputs.halueval_decomposition
                ),
            },
            "truthfulqa_mc": {
                "binding_verdict_section": (
                    S15_VERDICT_PER_BENCHMARK["truthfulqa_mc"]["section"]
                ),
                "binding_verdict_band": (
                    S15_VERDICT_PER_BENCHMARK["truthfulqa_mc"]["verdict"]
                ),
                "curves": _curve_audit_to_dict(outputs.truthfulqa_curves),
                "decomposition": _decomposition_to_dict(
                    outputs.truthfulqa_decomposition
                ),
            },
        },
        "sampling_noise_test": _sampling_noise_to_dict(
            outputs.sampling_noise_test
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, allow_nan=True)


def _fmt_float(x: float, ndigits: int = 4) -> str:
    if x != x:
        return "NaN"
    if x == float("inf"):
        return "+inf"
    if x == float("-inf"):
        return "-inf"
    return f"{x:.{ndigits}f}"


def render_markdown_report(outputs: AuditOutputs) -> str:
    """Render the human-readable §15.7 diagnostic report.

    Output is scanned by `check_class3_forbidden` BEFORE writing.
    Detection triggers INTERPRETATION_VIOLATION abort.
    """
    lines: list[str] = []
    lines.append("# §15.7 — Diagnostic post-processing audit (no new compute)")
    lines.append("")
    lines.append(
        "**Status:** §15.7 diagnostic content. This report does NOT "
        "constitute a new verdict-of-record. All §13/§14/§15.x verdicts "
        "remain binding under §0.8 regardless of §15.7 outputs."
    )
    lines.append("")
    lines.append(f"- schema_version: `{outputs.schema_version}`")
    lines.append(
        f"- scipy.stats available at runtime: "
        f"`{'yes' if _HAS_SCIPY else 'no, used numpy fallback'}`"
    )
    lines.append("")

    # §15.2 pinned baselines (per Chunk 7b).
    lines.append("## §15.2 verdict-of-record pinned baselines (read-only)")
    lines.append("| benchmark | $\\kappa_{\\S15.1}$ baseline |")
    lines.append("|---|---|")
    for b in ("halueval_qa", "truthfulqa_mc"):
        lines.append(
            f"| {b.replace('_', '-')} | {outputs.s15_2_baselines[b]:.4f} |"
        )
    lines.append("")

    # §13.10 N=200 caveat (per Chunk 7b).
    n200_truthful = outputs.s13_10_n200_status.get("truthfulqa_mc", False)
    n200_halueval = outputs.s13_10_n200_status.get("halueval_qa", False)
    if n200_truthful or n200_halueval:
        lines.append("**§13.10 dump status caveat (per §15.7 Chunk 7b).**")
        lines.append("")
        if n200_truthful:
            lines.append(
                "- TruthfulQA-MC §13.10 dump on disk is the post-§13.20 "
                "N=200 overwrite; §15.7's sampling-noise test uses it as "
                "a distributional reference, NOT as a re-derivation of "
                "§15.2's pinned baseline."
            )
        if n200_halueval:
            lines.append(
                "- HaluEval-QA §13.10 dump on disk is the post-§13.20 "
                "N=200 overwrite; not consumed by §15.7's sampling-noise "
                "test (single-benchmark on TruthfulQA-MC) but flagged "
                "for completeness."
            )
        lines.append("")

    # Per-benchmark sections.
    for benchmark in ("halueval_qa", "truthfulqa_mc"):
        binding = S15_VERDICT_PER_BENCHMARK[benchmark]
        if benchmark == "halueval_qa":
            curves = outputs.halueval_curves
            decomp = outputs.halueval_decomposition
            sn = None
        else:
            curves = outputs.truthfulqa_curves
            decomp = outputs.truthfulqa_decomposition
            sn = outputs.sampling_noise_test
        bench_label = benchmark.replace("_", "-")

        lines.append(f"## {bench_label} — diagnostic curves")
        lines.append(
            f"Binding verdict: {binding['section']} `{binding['verdict']}` "
            f"(unchanged by §15.7)."
        )
        lines.append("")
        lines.append(
            f"- N: {curves.n_questions}; correct: {curves.n_correct}; "
            f"wrong: {curves.n_wrong}; observed $\\pi$: "
            f"{curves.pi_observed:.4f}"
        )
        lines.append(
            f"- distinct $r(q)$ values: {curves.n_distinct_r}"
        )
        lines.append("")
        lines.append("### Operating points (with base-rate-adjusted $\\rho^*$)")
        lines.append(
            "| $\\alpha$ | cov@α | $\\tau^*$ | $\\rho(\\tau^*)$ | "
            "$\\rho^*$ | meets $\\rho^*$? |"
        )
        lines.append("|---|---|---|---|---|---|")
        for op in curves.operating_points:
            lines.append(
                f"| {op['alpha']:.2f} | "
                f"{_fmt_float(op['cov_at_alpha'])} | "
                f"{_fmt_float(op['tau_star'])} | "
                f"{_fmt_float(op['rho_at_tau_star'])} | "
                f"{_fmt_float(op['rho_star'])} | "
                f"{'**yes**' if op['meets_rho_star'] else 'no'} |"
            )
        lines.append("")
        lines.append("### Operating-point collapse audit")
        lines.append(
            "| $\\alpha$ pair | same $\\tau^*$? |"
        )
        lines.append("|---|---|")
        for a1, a2, same in curves.operating_point_collapse:
            lines.append(
                f"| ({a1:.2f}, {a2:.2f}) | "
                f"{'**collapsed**' if same else 'distinct'} |"
            )
        lines.append("")

        lines.append(f"### {bench_label} — Stage A / B / Composition decomposition")
        lines.append(
            f"- Decision-tree classification: **`{decomp.classification}`**"
        )
        lines.append(
            f"- $\\pi_S = {decomp.pi_s:.4f}$, "
            f"$\\pi_A = {decomp.pi_a:.4f}$, "
            f"$\\Delta_A = {decomp.delta_a:+.4f}$"
        )
        lines.append(
            f"- V1-divergent set: $|D| = {decomp.d_set_size}$ "
            f"({decomp.d_set_fraction:.2%} of N)"
        )
        lines.append(
            f"- $\\rho(\\tau^*) = "
            f"{_fmt_float(decomp.rho_summary_at_alpha2.get('rho_at_tau_star', float('nan')))}$ "
            f"vs $\\rho^* = "
            f"{_fmt_float(decomp.rho_summary_at_alpha2.get('rho_star', float('nan')))}$ "
            f"at $\\alpha_2 = {ALPHA_PRIMARY}$ "
            f"(meets: {decomp.rho_at_tau_star_meets_target})"
        )
        lines.append(
            f"- Composition correlations: overall Pearson "
            f"{_fmt_float(decomp.corr_pearson_overall)}, "
            f"Spearman {_fmt_float(decomp.corr_spearman_overall)}; "
            f"$\\bar{{D}}$ Pearson {_fmt_float(decomp.corr_pearson_dbar)}, "
            f"$D$ Pearson {_fmt_float(decomp.corr_pearson_d)}, "
            f"gap {_fmt_float(decomp.corr_pearson_gap)}"
        )
        lines.append("")
        lines.append("**V1 selection histogram:**")
        for src_name, count in sorted(
            decomp.v1_selection_histogram.items(),
            key=lambda kv: -kv[1],
        ):
            lines.append(f"- `{src_name}`: {count}")
        lines.append("")

        lines.append(f"### {bench_label} — narrative")
        lines.append("")
        lines.append(render_narrative(benchmark, decomp, sn))
        lines.append("")

    # Sampling-noise test section (TruthfulQA-MC only).
    sn = outputs.sampling_noise_test
    lines.append("## §15.6 sampling-noise hypothesis test (TruthfulQA-MC)")
    lines.append("")
    lines.append(
        f"- KS statistic: {_fmt_float(sn.ks_statistic)}"
    )
    lines.append(
        f"- KS p-value: {_fmt_float(sn.ks_pvalue)}"
    )
    lines.append(
        f"- mean drift: {_fmt_float(sn.mean_diff_nats)} nats"
    )
    lines.append(
        f"- stdev drift: {_fmt_float(sn.stdev_diff_nats)} nats"
    )
    lines.append(
        f"- N (§15.5 Phase 1): {sn.n_15_5_phase_1}"
    )
    lines.append(
        f"- N (§13.10 reference, on-disk): {sn.n_13_10_reference} "
        f"({'N=200 post-§13.20 overwrite' if sn.n_13_10_overwritten else 'N≤150'})"
    )
    lines.append(
        f"- **Classification: `{sn.classification}`**"
    )
    lines.append(f"- Rationale: {sn.classification_rationale}")
    lines.append("")
    lines.append(
        "Per §15.7 Chunk 7e, this test does NOT change §15.6's "
        "REGRESSION verdict-of-record (binding under §0.8). The "
        "classification informs the interpretation of the verdict, "
        "not the verdict band itself."
    )
    lines.append("")

    # Closing §0.8 boundary statement.
    lines.append("## §0.8 boundary")
    lines.append("")
    lines.append(
        "All §15.7 outputs are diagnostic-only. §15.4 USEFUL_INTERNAL "
        "and §15.6 REGRESSION verdict-of-records remain binding under "
        "§0.8. §13.9 VC-brief hold remains in force. Autonomy-domain "
        "BCVF claim (§6.1) is unaffected. No §15.8+ follow-up is "
        "authorized by §15.7; any further LLM-track work requires a "
        "fresh top-level §0.8 commitment."
    )
    lines.append("")

    return "\n".join(lines) + "\n"


def write_markdown_artifact(out_path: Path, outputs: AuditOutputs) -> None:
    """Render markdown, scan for Class-3 forbidden statements, and
    write only if firewall passes (§15.7 Chunks 7f / 7g)."""
    report = render_markdown_report(outputs)
    violations = check_class3_forbidden(report)
    if violations:
        abort_interpretation_violation(violations)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")


# ===========================================================================
# Orchestration + CLI.
# ===========================================================================


def run_real_data(repo_root: Path) -> int:
    """Load all four input artifacts, run the full §15.7 audit, write
    the two output artifacts. Aborts on any schema mismatch or
    interpretation violation (per Chunks 7b / 7f)."""
    # Component 2 — load §14a.2 dumps (both benchmarks).
    halueval_records = load_hybrid_dump(
        repo_root / INPUT_HALUEVAL_DUMP, "halueval_qa"
    )
    truthfulqa_records = load_hybrid_dump(
        repo_root / INPUT_TRUTHFULQA_DUMP, "truthfulqa_mc"
    )

    # Component 4 — §15.2 verdict-of-record baselines.
    s15_2_baselines = load_s15_2_baselines(repo_root / INPUT_S15_2_ARTIFACT)

    # Component 3 — §13.10 dump (TruthfulQA-MC only is required for
    # the sampling-noise test; HaluEval loaded if present for the
    # N=200 status flag).
    s13_10_truthfulqa = load_s13_10_dump(
        repo_root / INPUT_S13_10_TRUTHFULQA
    )
    halueval_path = repo_root / INPUT_S13_10_HALUEVAL
    if halueval_path.exists():
        s13_10_halueval = load_s13_10_dump(halueval_path)
        halueval_n200 = detect_n200_status(s13_10_halueval)
    else:
        halueval_n200 = False

    # Component 5 — diagnostic curves per benchmark.
    halueval_risk = np.array(
        [r.risk_score for r in halueval_records], dtype=np.float64
    )
    halueval_correct = np.array(
        [r.selected_answer_correct for r in halueval_records], dtype=bool
    )
    halueval_pi = float(np.mean(halueval_correct))
    halueval_curves = compute_curve_audit(
        "halueval_qa", halueval_risk, halueval_correct, halueval_pi
    )

    truthfulqa_risk = np.array(
        [r.risk_score for r in truthfulqa_records], dtype=np.float64
    )
    truthfulqa_correct = np.array(
        [r.selected_answer_correct for r in truthfulqa_records], dtype=bool
    )
    truthfulqa_pi = float(np.mean(truthfulqa_correct))
    truthfulqa_curves = compute_curve_audit(
        "truthfulqa_mc", truthfulqa_risk, truthfulqa_correct, truthfulqa_pi
    )

    # Component 6 — Stage A / B / Composition decomposition per benchmark.
    halueval_decomp = compute_decomposition(
        "halueval_qa", halueval_records, halueval_curves
    )
    truthfulqa_decomp = compute_decomposition(
        "truthfulqa_mc", truthfulqa_records, truthfulqa_curves
    )

    # Component 8 — sampling-noise hypothesis test on TruthfulQA-MC.
    sampling_noise_test = compute_sampling_noise_test(
        truthfulqa_records, s13_10_truthfulqa
    )

    outputs = AuditOutputs(
        schema_version=SCHEMA_VERSION,
        halueval_curves=halueval_curves,
        truthfulqa_curves=truthfulqa_curves,
        halueval_decomposition=halueval_decomp,
        truthfulqa_decomposition=truthfulqa_decomp,
        sampling_noise_test=sampling_noise_test,
        s15_2_baselines=s15_2_baselines,
        s13_10_n200_status={
            "truthfulqa_mc": detect_n200_status(s13_10_truthfulqa),
            "halueval_qa": halueval_n200,
        },
    )

    out_json = repo_root / OUTPUT_JSON_PATH
    out_md = repo_root / OUTPUT_MD_PATH
    write_json_artifact(out_json, outputs)
    write_markdown_artifact(out_md, outputs)

    print(f"\nWrote: {out_json}")
    print(f"Wrote: {out_md}")
    print(
        f"\n§15.7 diagnostic classifications:"
        f"\n  halueval_qa decomposition: "
        f"{halueval_decomp.classification}"
        f"\n  truthfulqa_mc decomposition: "
        f"{truthfulqa_decomp.classification}"
        f"\n  truthfulqa_mc sampling-noise: "
        f"{sampling_noise_test.classification}"
    )
    print(
        "\nAll §13/§14/§15.x verdicts-of-record remain binding under §0.8 "
        "regardless of these diagnostic outputs (per §15.7 Chunk 7f)."
    )
    return 0


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "§15.7 diagnostic post-processing audit on existing dumps "
            "(no new compute). Pure CPU; numpy + stdlib + (optional) "
            "scipy.stats."
        )
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Run the §15.7 classifier + firewall self-test only and "
            "exit. Required pre-execution gate per §15.7 Chunks 7d / "
            "7e / 7g."
        ),
    )
    p.add_argument(
        "--no-self-test",
        action="store_true",
        help=(
            "Skip the self-test gate before real-data execution "
            "(debug only; the result section MUST flag this as a §0.8 "
            "deviation)."
        ),
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help=(
            "Repository root (defaults to the parent directory of "
            "scripts/). Pinned input and output paths are resolved "
            "relative to this directory."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)

    if args.self_test and args.no_self_test:
        print(
            "ERROR: --self-test and --no-self-test are mutually exclusive.",
            file=sys.stderr,
        )
        return 2

    if args.self_test:
        return self_test()

    if not args.no_self_test:
        rc = self_test()
        if rc != 0:
            print(
                "\nABORT: self-test failed; refusing to proceed with "
                "real-data execution per §15.7 Chunks 7d / 7e / 7g.",
                file=sys.stderr,
            )
            return rc
    else:
        print(
            "WARNING: --no-self-test set; classifier gate skipped.",
            file=sys.stderr,
        )

    return run_real_data(args.repo_root)


if __name__ == "__main__":
    raise SystemExit(main())

