#!/usr/bin/env python
"""§15.1 — Selective abstention scout on existing §13.10 dumps.

Pure post-processing analysis: reads pre-existing §13.10
semantic-entropy JSON dumps, computes selective-prediction
operational metrics (residual accuracy, coverage at target
accuracy, error capture rate, AURC, false abstention rate)
across an exhaustive threshold sweep, runs paired bootstrap
CIs, and emits a verdict per the §15.1-pinned ordered cascade.

Reference design: Project_documentation/repository/docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md
§15.1 Chunks 1–7 plus §15.1 Amendment 1.

Discipline: all numerical bands, metric definitions, baselines,
and acceptance/rejection rules are pinned in §15.1 and MUST
NOT be changed during implementation. Any deviation discovered
at run time MUST be flagged as a §0.8 deviation in the §15
result section, not absorbed silently. The required pre-
execution gate is `--self-test`, which verifies the verdict
cascade against §15.1 Chunk 4b's boundary-case audit table
and against Chunk 4c's STRONG-only demotion rule.

Inputs (per §15.1 Chunk 2b as amended by §15.1 Amendment 1):
    docs/experiments/probe_semantic_entropy_truthfulqa_mc.json
    docs/experiments/probe_semantic_entropy_halueval_qa.json

Outputs (per §15.1 Chunk 7):
    docs/experiments/probe_selective_abstention.json
    docs/experiments/probe_selective_abstention.md

Usage:
    # Required pre-execution gate.
    python scripts/probe_selective_abstention.py --self-test

    # Real-data run (auto-runs --self-test first; aborts on failure).
    python scripts/probe_selective_abstention.py

    # Real-data run skipping the self-test gate (debug only; the
    # result section MUST flag this as a §0.8 deviation).
    python scripts/probe_selective_abstention.py --no-self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# ===========================================================================
# §15.1 PINNED CONSTANTS — DO NOT CHANGE during implementation.
# Any change requires a fresh §0.8 amendment to §15.1 with explicit
# rationale, mirroring §15.1 Amendment 1.
# ===========================================================================

SCHEMA_VERSION = "15.1"

# Chunk 2b (as amended by Amendment 1, then partially reverted by
# Amendment 2 for the TruthfulQA-MC path) — input paths.
PINNED_INPUT_PATHS: dict[str, str] = {
    "truthfulqa_mc": "docs/experiments/probe_semantic_entropy.json",
    "halueval_qa": "docs/experiments/probe_semantic_entropy_halueval_qa.json",
}
BENCHMARKS: tuple[str, ...] = ("truthfulqa_mc", "halueval_qa")

# Chunk 2b (as amended by Amendment 1) — per-question JSON field names
# in the §13.10 dumps.
FIELD_QUESTION_ID = "q_idx"
FIELD_ENTROPY = "semantic_entropy"
FIELD_CORRECT = "greedy_matches_correct"

# Chunk 2b — pinned size of each §13.10 run.
PINNED_N = 100

# Chunk 3a — pinned greedy total-wrong per benchmark, derived from
# §13.10's documented greedy accuracies (0.250 on TruthfulQA-MC,
# 0.300 on HaluEval-QA). Parity check aborts the run if the loaded
# dump does not match.
PINNED_GREEDY_ACC: dict[str, float] = {
    "truthfulqa_mc": 0.250,
    "halueval_qa": 0.300,
}
PINNED_W: dict[str, int] = {
    "truthfulqa_mc": 75,
    "halueval_qa": 70,
}

# Chunk 3a — three pinned target-accuracy operating points per benchmark.
# alpha_1 = greedy baseline + 10pp; alpha_2 = 0.50; alpha_3 = 0.75.
PINNED_ALPHA_TARGETS: dict[str, tuple[float, float, float]] = {
    "truthfulqa_mc": (0.35, 0.50, 0.75),
    "halueval_qa": (0.40, 0.50, 0.75),
}

# Chunk 3a — minimum-answered floor for cov@alpha (prevents trivial
# high-accuracy-at-tiny-coverage degeneracy).
N_MIN = 10

# Chunk 4c — paired bootstrap parameters.
BOOTSTRAP_B = 1000
BOOTSTRAP_SEED_ENTROPY = 15
CI_LOW_PCT = 2.5
CI_HIGH_PCT = 97.5

# Chunks 4a / 4b — verdict cascade thresholds.
DELTA_REGRESSION = -0.02
DELTA_STRONG = +0.10
DELTA_USEFUL = +0.05
DELTA_MARGINAL = +0.02
KAPPA_STRONG = 0.30
KAPPA_USEFUL = 0.20
KAPPA_MARGINAL = 0.10

# Chunk 7 — output paths.
OUTPUT_JSON_PATH = "docs/experiments/probe_selective_abstention.json"
OUTPUT_MD_PATH = "docs/experiments/probe_selective_abstention.md"

# Chunk 4b boundary-case audit table — pinned --self-test inputs.
# Each entry: (delta, kappa, expected_verdict).
SELF_TEST_CASCADE_CASES: list[tuple[float, float, str]] = [
    (+0.10, 0.29, "USEFUL_INTERNAL"),
    (+0.049, 0.25, "MARGINAL"),
    (-0.019, 0.40, "SATURATION"),
    (+0.10, 0.30, "STRONG"),
    (+0.15, 0.10, "MARGINAL"),
    (-0.025, 0.50, "REGRESSION"),
]

# Chunk 4c STRONG-only demotion-rule self-test cases.
# Each entry: (point-estimate verdict, per-benchmark CI lower bounds on delta,
#              expected demoted verdict, expected annotations).
SELF_TEST_DEMOTION_CASES: list[
    tuple[str, tuple[float, float], str, list[str]]
] = [
    # Both CI lower bounds strictly positive — STRONG stands.
    ("STRONG", (0.01, 0.01), "STRONG", []),
    # One benchmark's CI lower bound is exactly 0 — STRONG demotes.
    ("STRONG", (0.00, 0.05), "USEFUL_INTERNAL", ["STRONG_BUT_CI_DEMOTION"]),
    # Both CI lower bounds negative — STRONG demotes.
    ("STRONG", (-0.01, -0.02), "USEFUL_INTERNAL", ["STRONG_BUT_CI_DEMOTION"]),
    # USEFUL_INTERNAL not subject to demotion.
    ("USEFUL_INTERNAL", (-0.05, -0.05), "USEFUL_INTERNAL", []),
    # MARGINAL not subject to demotion.
    ("MARGINAL", (-0.05, -0.05), "MARGINAL", []),
    # SATURATION not subject to demotion.
    ("SATURATION", (-0.05, -0.05), "SATURATION", []),
    # REGRESSION not subject to demotion.
    ("REGRESSION", (-0.10, -0.10), "REGRESSION", []),
]


# ===========================================================================
# Dataclasses — immutable record types for clarity.
# ===========================================================================


@dataclass(frozen=True)
class BenchmarkInputs:
    """Per-question arrays loaded from a §13.10 dump (one benchmark)."""

    benchmark: str
    q_ids: np.ndarray  # int, shape (N,)
    entropies: np.ndarray  # float, shape (N,)
    correctness: np.ndarray  # bool, shape (N,)


@dataclass(frozen=True)
class OperatingPoint:
    """Headline operating point at one target-accuracy alpha."""

    alpha: float
    cov: float
    tau_star: float
    ecr: float
    far: float


@dataclass(frozen=True)
class BenchmarkMetrics:
    """Per-benchmark §15 metrics + bootstrap CIs."""

    benchmark: str
    n_questions: int
    greedy_accuracy: float
    total_wrong_W: int
    auc_random: float
    auc_policy: float
    delta_auc: float
    delta_auc_ci: tuple[float, float]
    kappa: float
    kappa_ci: tuple[float, float]
    operating_points: list[OperatingPoint]
    threshold_sweep: list[dict]
    parity_gates: dict[str, bool]


@dataclass(frozen=True)
class CombinedVerdict:
    """Combined classification across both benchmarks."""

    delta: float
    kappa: float
    verdict: str
    verdict_annotations: list[str]


# ===========================================================================
# Core numerical primitives (pure, deterministic).
# Per §15.1 Chunks 2c, 3a, 3b. No I/O, no RNG, no logging.
# ===========================================================================


def analytic_random_aurc(W: int, N: int) -> float:
    """Random-matched AURC baseline (Chunk 3b / Chunk 5).

    By linearity of expectation, a uniformly random selection at any
    coverage has expected wrong rate W / N at every coverage level,
    so the integrated AURC of B_random equals W / N exactly.
    """
    if N <= 0:
        raise ValueError(f"N must be positive (got {N})")
    return float(W) / float(N)


def compute_threshold_grid(entropies: np.ndarray) -> np.ndarray:
    """Threshold sweep grid per §15.1 Chunk 2c.

    The grid is the sorted unique values of r(q) plus -inf and +inf.
    At -inf the policy abstains every question (empty answered set).
    At +inf the policy answers every question (full answered set).
    """
    uniques = np.unique(entropies.astype(float))
    return np.concatenate(([-np.inf], uniques, [np.inf]))


def policy_at_threshold(
    entropies: np.ndarray, tau: float
) -> np.ndarray:
    """Boolean mask of the answered set A_tau.

    Per §15.1 Chunk 2c: ANSWER iff r(q) < tau, ABSTAIN otherwise.
    Ties at r(q) == tau resolve to ABSTAIN (deterministic,
    conservative).
    """
    return entropies < tau


def metrics_at_threshold(
    entropies: np.ndarray,
    correctness: np.ndarray,
    tau: float,
    W: int,
    N: int,
) -> tuple[float, float, float, float]:
    """Compute (cov, acc, ecr, far) at one threshold.

    Per §15.1 Chunks 3a / 3b:
        cov(tau) = |A_tau| / N                                 (Chunk 3a)
        acc(tau) = (1/|A_tau|) sum_{q in A_tau} c(q)           (Chunk 3a, Metric 1)
                   NaN when |A_tau| == 0
        ecr(tau) = (1/W) sum_{q not in A_tau} (1 - c(q))       (Chunk 3a, Metric 3)
                   NaN when W == 0
        far(tau) = (1/C) sum_{q not in A_tau} c(q)             (Chunk 3b, Metric 5)
                   NaN when C == 0   (C = N - W)
    """
    answered_mask = policy_at_threshold(entropies, tau)
    n_answered = int(answered_mask.sum())
    cov = n_answered / float(N)

    if n_answered > 0:
        acc = float(correctness[answered_mask].sum()) / float(n_answered)
    else:
        acc = float("nan")

    abstained_mask = ~answered_mask
    if W > 0:
        n_wrong_abstained = int((~correctness[abstained_mask]).sum())
        ecr = float(n_wrong_abstained) / float(W)
    else:
        ecr = float("nan")

    C = N - W
    if C > 0:
        n_correct_abstained = int(correctness[abstained_mask].sum())
        far = float(n_correct_abstained) / float(C)
    else:
        far = float("nan")

    return cov, acc, ecr, far


def aurc_discrete(
    entropies: np.ndarray,
    correctness: np.ndarray,
    q_ids: np.ndarray,
) -> float:
    """Discrete Geifman–El-Yaniv 2017 AURC per §15.1 Chunk 3b, Metric 4.

    Sort questions by ascending r(q), breaking ties by ascending q_id.
    Cumulative selective error at coverage k/N:
        e_k = (1/k) * sum_{i=1..k} (1 - c_(i))
    AURC = (1/N) * sum_{k=1..N} e_k.
    Range [0, 1], lower is better.
    """
    n = entropies.shape[0]
    if n == 0:
        raise ValueError("Cannot compute AURC on empty input")

    # np.lexsort: last key is primary. Primary = entropies (ascending),
    # secondary = q_ids (ascending tiebreak).
    order = np.lexsort((q_ids, entropies))
    sorted_correct = correctness[order].astype(np.float64)
    cumulative_wrong = np.cumsum(1.0 - sorted_correct)
    ks = np.arange(1, n + 1, dtype=np.float64)
    e_k = cumulative_wrong / ks
    return float(e_k.mean())


# ===========================================================================
# Operating-point + verdict cascade (pure, deterministic).
# Per §15.1 Chunks 3a, 4a, 4b, 4c.
# ===========================================================================


def cov_at_target_accuracy(
    entropies: np.ndarray,
    correctness: np.ndarray,
    grid: np.ndarray,
    alpha: float,
    n_min: int,
    W: int,
    N: int,
) -> tuple[float, float, float, float]:
    """Coverage at target accuracy alpha (Chunk 3a, Metric 2).

    cov@alpha = max{ cov(tau) : acc(tau) >= alpha AND |A_tau| >= n_min }

    Returns (cov, tau_star, ecr_at_tau_star, far_at_tau_star).
    If no tau in the grid satisfies both conditions, returns
    (0.0, +inf, NaN, NaN). The +inf tau_star indicates "always-
    abstain" — the policy yields no operating point at this alpha.
    """
    best_cov = 0.0
    best_tau = float("inf")
    best_ecr = float("nan")
    best_far = float("nan")

    for tau in grid:
        cov, acc, ecr, far = metrics_at_threshold(
            entropies, correctness, float(tau), W, N
        )
        n_answered = int(round(cov * N))
        if n_answered < n_min:
            continue
        if not (acc >= alpha):  # NaN-safe: NaN >= alpha is False.
            continue
        if cov > best_cov:
            best_cov = cov
            best_tau = float(tau)
            best_ecr = ecr
            best_far = far

    return best_cov, best_tau, best_ecr, best_far


def verdict_cascade(delta: float, kappa: float) -> str:
    """Apply the §15.1 ordered verdict cascade (Chunks 4a / 4b).

    Rules evaluated in order; the first match wins. Rule 5 has no
    positive condition and explicitly catches every (delta, kappa)
    not matching rules 1–4 — making the partition exhaustive over
    R^2 by construction.

        1. REGRESSION       — delta < -0.02
        2. STRONG           — delta >= +0.10  AND kappa >= 0.30
        3. USEFUL_INTERNAL  — delta >= +0.05  AND kappa >= 0.20
        4. MARGINAL         — delta >= +0.02  AND kappa >= 0.10
        5. SATURATION       — explicit residual catch-all
    """
    # Rule 1: REGRESSION first so a delta < -0.02 outcome classifies as
    # regression regardless of kappa (per Chunk 4a explicit ordering note).
    if delta < DELTA_REGRESSION:
        return "REGRESSION"
    if delta >= DELTA_STRONG and kappa >= KAPPA_STRONG:
        return "STRONG"
    if delta >= DELTA_USEFUL and kappa >= KAPPA_USEFUL:
        return "USEFUL_INTERNAL"
    if delta >= DELTA_MARGINAL and kappa >= KAPPA_MARGINAL:
        return "MARGINAL"
    return "SATURATION"


def apply_demotion_rule(
    point_verdict: str, delta_ci_lowers: tuple[float, float]
) -> tuple[str, list[str]]:
    """STRONG-only bootstrap-CI demotion rule (Chunk 4c).

    If the point-estimate verdict is STRONG and the bootstrap CI
    lower bound on delta is <= 0 on either benchmark, demote to
    USEFUL_INTERNAL with explicit STRONG_BUT_CI_DEMOTION annotation.
    USEFUL_INTERNAL / MARGINAL / SATURATION / REGRESSION are not
    subject to demotion — their operational scope does not require
    external statistical confirmation.
    """
    if point_verdict != "STRONG":
        return point_verdict, []
    lo_a, lo_b = delta_ci_lowers
    if lo_a > 0.0 and lo_b > 0.0:
        return "STRONG", []
    return "USEFUL_INTERNAL", ["STRONG_BUT_CI_DEMOTION"]


# ===========================================================================
# Bootstrap CIs + per-benchmark pipeline.
# Per §15.1 Chunks 4c, 5.
# ===========================================================================


def _benchmark_rng(benchmark: str) -> np.random.Generator:
    """Deterministic per-benchmark RNG (Chunk 4c).

    Spawns a child SeedSequence from the pinned root entropy=15,
    ordered by the BENCHMARKS tuple. Two benchmarks therefore use
    independent, reproducible PCG64 streams.
    """
    root = np.random.SeedSequence(entropy=BOOTSTRAP_SEED_ENTROPY)
    children = root.spawn(len(BENCHMARKS))
    idx = BENCHMARKS.index(benchmark)
    return np.random.Generator(np.random.PCG64(children[idx]))


def bootstrap_delta_and_kappa(
    inputs: BenchmarkInputs,
    alpha2: float,
    n_min: int,
    B: int,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Paired bootstrap CIs on (delta, kappa) per §15.1 Chunk 4c.

    For each of B resamples:
      * draw N indices uniformly with replacement,
      * recompute AURC_policy on the resample,
      * recompute W_resample = N - sum(c_resample),
      * delta_resample = W_resample / N - AURC_policy_resample,
      * kappa_resample = cov_at_target_accuracy at alpha=alpha2.

    Returns ((delta_lo, delta_hi), (kappa_lo, kappa_hi)) at the
    pinned 2.5 / 97.5 percentiles (two-sided 95% CI).

    Rationale for jointly resampling delta and kappa from the same
    bootstrap draws: Chunk 4c pins paired bootstrap over question
    indices — both statistics derive from the same per-question
    arrays, so a single resample produces both samples and
    preserves the joint sampling-variance structure.
    """
    rng = _benchmark_rng(inputs.benchmark)
    n = inputs.q_ids.shape[0]

    delta_samples = np.empty(B, dtype=np.float64)
    kappa_samples = np.empty(B, dtype=np.float64)

    for b in range(B):
        idx = rng.integers(0, n, size=n)
        q_ids_r = inputs.q_ids[idx]
        ent_r = inputs.entropies[idx]
        cor_r = inputs.correctness[idx]

        w_r = int((~cor_r).sum())
        aurc_random_r = analytic_random_aurc(w_r, n)
        aurc_policy_r = aurc_discrete(ent_r, cor_r, q_ids_r)
        delta_samples[b] = aurc_random_r - aurc_policy_r

        # Kappa = cov@alpha_2 on the resample (n_min applies as on
        # the real run; pinned in Chunk 3a).
        grid_r = compute_threshold_grid(ent_r)
        kappa_r, _, _, _ = cov_at_target_accuracy(
            ent_r, cor_r, grid_r, alpha2, n_min, w_r, n
        )
        kappa_samples[b] = kappa_r

    delta_ci = (
        float(np.percentile(delta_samples, CI_LOW_PCT)),
        float(np.percentile(delta_samples, CI_HIGH_PCT)),
    )
    kappa_ci = (
        float(np.percentile(kappa_samples, CI_LOW_PCT)),
        float(np.percentile(kappa_samples, CI_HIGH_PCT)),
    )
    return delta_ci, kappa_ci


def compute_benchmark_results(inputs: BenchmarkInputs) -> BenchmarkMetrics:
    """End-to-end metric computation for one benchmark.

    Runs (in this order):
      * AURC_policy and AURC_random.
      * Operating points at the three pinned alpha targets.
      * Full threshold sweep table.
      * Bootstrap CIs on (delta, kappa).
    """
    benchmark = inputs.benchmark
    n = int(inputs.q_ids.shape[0])
    w = int((~inputs.correctness).sum())
    greedy_acc = float(inputs.correctness.mean())

    grid = compute_threshold_grid(inputs.entropies)
    aurc_random = analytic_random_aurc(w, n)
    aurc_policy = aurc_discrete(inputs.entropies, inputs.correctness, inputs.q_ids)
    delta = aurc_random - aurc_policy

    alpha1, alpha2, alpha3 = PINNED_ALPHA_TARGETS[benchmark]

    operating_points: list[OperatingPoint] = []
    for alpha in (alpha1, alpha2, alpha3):
        cov, tau_star, ecr, far = cov_at_target_accuracy(
            inputs.entropies, inputs.correctness, grid, alpha, N_MIN, w, n
        )
        operating_points.append(
            OperatingPoint(
                alpha=alpha, cov=cov, tau_star=tau_star, ecr=ecr, far=far
            )
        )

    kappa = operating_points[1].cov  # cov@alpha_2 (Chunk 4a headline).

    threshold_sweep: list[dict] = []
    for tau in grid:
        cov, acc, ecr, far = metrics_at_threshold(
            inputs.entropies, inputs.correctness, float(tau), w, n
        )
        threshold_sweep.append(
            {
                "tau": float(tau),
                "cov": cov,
                "acc": acc,
                "ecr": ecr,
                "far": far,
            }
        )

    delta_ci, kappa_ci = bootstrap_delta_and_kappa(
        inputs, alpha2, N_MIN, BOOTSTRAP_B
    )

    parity_gates = run_parity_gates(benchmark, n, w, aurc_random)

    return BenchmarkMetrics(
        benchmark=benchmark,
        n_questions=n,
        greedy_accuracy=greedy_acc,
        total_wrong_W=w,
        auc_random=aurc_random,
        auc_policy=aurc_policy,
        delta_auc=delta,
        delta_auc_ci=delta_ci,
        kappa=kappa,
        kappa_ci=kappa_ci,
        operating_points=operating_points,
        threshold_sweep=threshold_sweep,
        parity_gates=parity_gates,
    )


def compute_combined_verdict(
    metrics_a: BenchmarkMetrics, metrics_b: BenchmarkMetrics
) -> CombinedVerdict:
    """Combined classification under the worst-benchmark rule (Chunk 4a)."""
    delta = min(metrics_a.delta_auc, metrics_b.delta_auc)
    kappa = min(metrics_a.kappa, metrics_b.kappa)

    point_verdict = verdict_cascade(delta, kappa)
    final_verdict, annotations = apply_demotion_rule(
        point_verdict,
        (metrics_a.delta_auc_ci[0], metrics_b.delta_auc_ci[0]),
    )
    return CombinedVerdict(
        delta=delta,
        kappa=kappa,
        verdict=final_verdict,
        verdict_annotations=annotations,
    )


# ===========================================================================
# Self-test (required pre-execution gate per §15.1 Chunks 4b / 4c).
# Verifies the verdict cascade against the boundary-case audit table
# and the STRONG-only demotion rule against pinned demotion cases.
# ===========================================================================


def self_test() -> int:
    """Run the §15.1 cascade + demotion self-tests.

    Returns 0 on success, nonzero on failure. Aborts real-data
    execution when invoked as a gate (see main()).
    """
    failures: list[str] = []

    # Cascade boundary-case audit (Chunk 4b).
    for delta, kappa, expected in SELF_TEST_CASCADE_CASES:
        observed = verdict_cascade(delta, kappa)
        ok = observed == expected
        marker = "PASS" if ok else "FAIL"
        print(
            f"  [{marker}] cascade(delta={delta:+.3f}, kappa={kappa:.3f}) "
            f"= {observed}  (expected {expected})"
        )
        if not ok:
            failures.append(
                f"cascade({delta:+.3f}, {kappa:.3f}) = {observed} "
                f"!= expected {expected}"
            )

    # STRONG-only demotion rule (Chunk 4c).
    for point_verdict, ci_lowers, expected, expected_anns in (
        SELF_TEST_DEMOTION_CASES
    ):
        verdict, anns = apply_demotion_rule(point_verdict, ci_lowers)
        ok = verdict == expected and anns == expected_anns
        marker = "PASS" if ok else "FAIL"
        print(
            f"  [{marker}] demote({point_verdict}, "
            f"ci_lowers={ci_lowers}) "
            f"= ({verdict}, {anns})  "
            f"(expected ({expected}, {expected_anns}))"
        )
        if not ok:
            failures.append(
                f"demote({point_verdict}, {ci_lowers}) = "
                f"({verdict}, {anns}) != expected ({expected}, "
                f"{expected_anns})"
            )

    if failures:
        print(f"\nSELF_TEST FAILED: {len(failures)} mismatch(es).", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print(
        f"\nSELF_TEST PASSED: "
        f"{len(SELF_TEST_CASCADE_CASES)} cascade cases + "
        f"{len(SELF_TEST_DEMOTION_CASES)} demotion cases."
    )
    return 0


# ===========================================================================
# Dump loading + parity gates.
# Per §15.1 Chunk 2b (as amended) and Chunk 6 §(2) load-bearing
# assumptions. Fail-fast on schema mismatch and on parity-gate failure.
# ===========================================================================


def load_dump(path: Path, benchmark: str) -> BenchmarkInputs:
    """Load one §13.10 JSON dump per the §15.1-pinned schema.

    Reads ONLY the three pinned fields (q_idx, semantic_entropy,
    greedy_matches_correct). Aborts with SCHEMA_MISMATCH on any
    missing field, file not found, or malformed structure rather
    than substituting a derived quantity (per Chunk 2b).
    """
    if not path.exists():
        print(
            f"SCHEMA_MISMATCH: input dump not found: {path}",
            file=sys.stderr,
        )
        print(
            f"  (per §15.1 Chunk 2b as amended by Amendment 1, "
            f"the {benchmark} dump is pinned at this exact path; "
            f"no fallback path is consulted)",
            file=sys.stderr,
        )
        raise SystemExit(2)

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        print(f"SCHEMA_MISMATCH: {path} is not valid JSON: {e}", file=sys.stderr)
        raise SystemExit(2) from None

    if not isinstance(raw, list):
        print(
            f"SCHEMA_MISMATCH: {path} top-level must be a JSON list "
            f"of per-question records; got {type(raw).__name__}",
            file=sys.stderr,
        )
        raise SystemExit(2)

    required_fields = (FIELD_QUESTION_ID, FIELD_ENTROPY, FIELD_CORRECT)
    q_ids: list[int] = []
    entropies: list[float] = []
    correctness: list[bool] = []

    for i, rec in enumerate(raw):
        if not isinstance(rec, dict):
            print(
                f"SCHEMA_MISMATCH: {path}[{i}] is not a JSON object",
                file=sys.stderr,
            )
            raise SystemExit(2)
        for fname in required_fields:
            if fname not in rec:
                print(
                    f"SCHEMA_MISMATCH: {path}[{i}] missing required "
                    f"field '{fname}' (per §15.1 Chunk 2b as amended)",
                    file=sys.stderr,
                )
                raise SystemExit(2)
        q_ids.append(int(rec[FIELD_QUESTION_ID]))
        entropies.append(float(rec[FIELD_ENTROPY]))
        correctness.append(bool(rec[FIELD_CORRECT]))

    q_id_arr = np.asarray(q_ids, dtype=np.int64)
    if len(set(q_ids)) != len(q_ids):
        print(
            f"SCHEMA_MISMATCH: {path} contains duplicate {FIELD_QUESTION_ID} "
            f"values; ascending-risk tiebreak would be non-deterministic",
            file=sys.stderr,
        )
        raise SystemExit(2)

    return BenchmarkInputs(
        benchmark=benchmark,
        q_ids=q_id_arr,
        entropies=np.asarray(entropies, dtype=np.float64),
        correctness=np.asarray(correctness, dtype=bool),
    )


def run_parity_gates(
    benchmark: str, n: int, w: int, aurc_random: float
) -> dict[str, bool]:
    """Pre-run parity gates per §15.1 (Chunks 2b, 3a, 5).

    Verifies:
      * N matches PINNED_N = 100.
      * W matches PINNED_W[benchmark] (75 / 70).
      * AURC_random matches W / N exactly (analytic baseline).

    On mismatch, aborts with explicit message — does NOT recompute
    pinned floors from the dump (per the user's pinned guidance:
    "If W does not match the pinned §13.10 assumption, do not
    recompute a new floor from the dump. Abort explicitly and say
    the §15.1 assumptions no longer hold.").
    """
    n_ok = n == PINNED_N
    w_ok = w == PINNED_W[benchmark]
    expected_random = PINNED_W[benchmark] / PINNED_N
    auc_random_ok = abs(aurc_random - expected_random) < 1e-12

    if not (n_ok and w_ok and auc_random_ok):
        msg = [
            f"PARITY_GATE_FAILED on benchmark '{benchmark}':",
            f"  observed: N={n}, W={w}, AURC_random={aurc_random:.6f}",
            f"  pinned:   N={PINNED_N}, W={PINNED_W[benchmark]}, "
            f"AURC_random={expected_random:.6f}",
            "",
            "§15.1's pinned assumptions about the §13.10 dump no longer",
            "hold. Per Chunk 6 §(2), §15.1 cannot proceed under modified",
            "assumptions. Abort. A fresh §0.8 amendment to §15.1 would",
            "be required before any §15 verdict can be reported on this",
            "configuration.",
        ]
        print("\n".join(msg), file=sys.stderr)
        raise SystemExit(3)

    return {"N_ok": n_ok, "W_ok": w_ok, "auc_random_ok": auc_random_ok}


# ===========================================================================
# Output writers — JSON and markdown artifacts per §15.1 Chunk 7.
# ===========================================================================


def _operating_point_to_dict(op: OperatingPoint) -> dict:
    return {
        "alpha": op.alpha,
        "cov": op.cov,
        "tau_star": op.tau_star,
        "ecr": op.ecr,
        "far": op.far,
    }


def _benchmark_to_dict(m: BenchmarkMetrics) -> dict:
    return {
        "n_questions": m.n_questions,
        "greedy_accuracy": m.greedy_accuracy,
        "total_wrong_W": m.total_wrong_W,
        "auc_random": m.auc_random,
        "auc_policy": m.auc_policy,
        "delta_auc": m.delta_auc,
        "delta_auc_ci": list(m.delta_auc_ci),
        "kappa": m.kappa,
        "kappa_ci": list(m.kappa_ci),
        "operating_points": [_operating_point_to_dict(op) for op in m.operating_points],
        "threshold_sweep": m.threshold_sweep,
        "parity_gates": m.parity_gates,
    }


def write_json_artifact(
    out_path: Path,
    metrics_a: BenchmarkMetrics,
    metrics_b: BenchmarkMetrics,
    combined: CombinedVerdict,
) -> None:
    """Write the §15.1 Chunk 7 machine-readable artifact."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "n_questions": PINNED_N,
        "bootstrap_B": BOOTSTRAP_B,
        "bootstrap_seed": f"SeedSequence(entropy={BOOTSTRAP_SEED_ENTROPY})",
        "benchmarks": {
            metrics_a.benchmark: _benchmark_to_dict(metrics_a),
            metrics_b.benchmark: _benchmark_to_dict(metrics_b),
        },
        "combined": {
            "delta": combined.delta,
            "kappa": combined.kappa,
            "verdict": combined.verdict,
            "verdict_annotations": list(combined.verdict_annotations),
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, allow_nan=True)


def _fmt_float(x: float, ndigits: int = 4) -> str:
    if x != x:  # NaN
        return "NaN"
    if x == float("inf"):
        return "+inf"
    if x == float("-inf"):
        return "-inf"
    return f"{x:.{ndigits}f}"


def _cascade_trace(delta: float, kappa: float) -> list[str]:
    """Walk-through of the cascade for the markdown report."""
    trace = []
    if delta < DELTA_REGRESSION:
        trace.append(
            f"  rule 1 REGRESSION: delta={_fmt_float(delta)} < "
            f"{DELTA_REGRESSION:+.2f}  -> YES"
        )
        return trace
    trace.append(
        f"  rule 1 REGRESSION: delta={_fmt_float(delta)} < "
        f"{DELTA_REGRESSION:+.2f}  -> NO"
    )
    if delta >= DELTA_STRONG and kappa >= KAPPA_STRONG:
        trace.append(
            f"  rule 2 STRONG: delta>={DELTA_STRONG:+.2f} AND "
            f"kappa>={KAPPA_STRONG:.2f}  -> YES"
        )
        return trace
    trace.append(
        f"  rule 2 STRONG: delta>={DELTA_STRONG:+.2f} AND "
        f"kappa>={KAPPA_STRONG:.2f}  -> NO"
    )
    if delta >= DELTA_USEFUL and kappa >= KAPPA_USEFUL:
        trace.append(
            f"  rule 3 USEFUL_INTERNAL: delta>={DELTA_USEFUL:+.2f} AND "
            f"kappa>={KAPPA_USEFUL:.2f}  -> YES"
        )
        return trace
    trace.append(
        f"  rule 3 USEFUL_INTERNAL: delta>={DELTA_USEFUL:+.2f} AND "
        f"kappa>={KAPPA_USEFUL:.2f}  -> NO"
    )
    if delta >= DELTA_MARGINAL and kappa >= KAPPA_MARGINAL:
        trace.append(
            f"  rule 4 MARGINAL: delta>={DELTA_MARGINAL:+.2f} AND "
            f"kappa>={KAPPA_MARGINAL:.2f}  -> YES"
        )
        return trace
    trace.append(
        f"  rule 4 MARGINAL: delta>={DELTA_MARGINAL:+.2f} AND "
        f"kappa>={KAPPA_MARGINAL:.2f}  -> NO"
    )
    trace.append("  rule 5 SATURATION: residual catch-all  -> YES")
    return trace


def format_markdown_report(
    metrics_a: BenchmarkMetrics,
    metrics_b: BenchmarkMetrics,
    combined: CombinedVerdict,
    self_test_ran: bool,
) -> str:
    """Render the §15.1 Chunk 7 human-readable summary report."""
    lines: list[str] = []
    lines.append("# §15.1 — Selective abstention scout result\n")
    lines.append(f"- schema_version: `{SCHEMA_VERSION}`")
    lines.append(f"- bootstrap_B: {BOOTSTRAP_B}")
    lines.append(
        f"- bootstrap_seed: `SeedSequence(entropy={BOOTSTRAP_SEED_ENTROPY})`"
    )
    lines.append(f"- n_min (cov@alpha floor): {N_MIN}")
    lines.append("")

    lines.append("## Self-test gate")
    if self_test_ran:
        lines.append(
            "- `--self-test` ran in this invocation and PASSED "
            "(else the script would have aborted before reaching this point)."
        )
    else:
        lines.append(
            "- **§0.8 deviation:** `--no-self-test` was passed; the cascade "
            "self-test gate did not run in this invocation. Result must be "
            "audited externally."
        )
    lines.append("")

    lines.append("## Parity gates")
    lines.append("| benchmark | N_ok | W_ok | auc_random_ok |")
    lines.append("|---|---|---|---|")
    for m in (metrics_a, metrics_b):
        g = m.parity_gates
        lines.append(
            f"| {m.benchmark} | {g['N_ok']} | {g['W_ok']} | "
            f"{g['auc_random_ok']} |"
        )
    lines.append("")

    lines.append("## Per-benchmark headline")
    lines.append(
        "| benchmark | N | W | greedy_acc | AURC_random | AURC_policy | "
        "delta_auc | delta_auc_CI | kappa | kappa_CI |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for m in (metrics_a, metrics_b):
        lines.append(
            f"| {m.benchmark} | {m.n_questions} | {m.total_wrong_W} | "
            f"{_fmt_float(m.greedy_accuracy, 3)} | "
            f"{_fmt_float(m.auc_random, 4)} | "
            f"{_fmt_float(m.auc_policy, 4)} | "
            f"{_fmt_float(m.delta_auc, 4)} | "
            f"[{_fmt_float(m.delta_auc_ci[0], 4)}, "
            f"{_fmt_float(m.delta_auc_ci[1], 4)}] | "
            f"{_fmt_float(m.kappa, 4)} | "
            f"[{_fmt_float(m.kappa_ci[0], 4)}, "
            f"{_fmt_float(m.kappa_ci[1], 4)}] |"
        )
    lines.append("")

    for m in (metrics_a, metrics_b):
        lines.append(f"## Operating points — {m.benchmark}")
        lines.append("| alpha | cov | tau_star | ecr | far |")
        lines.append("|---|---|---|---|---|")
        for op in m.operating_points:
            lines.append(
                f"| {_fmt_float(op.alpha, 2)} | {_fmt_float(op.cov, 4)} | "
                f"{_fmt_float(op.tau_star, 4)} | {_fmt_float(op.ecr, 4)} | "
                f"{_fmt_float(op.far, 4)} |"
            )
        lines.append("")

    lines.append("## Combined classification (worst-benchmark rule)")
    lines.append(f"- delta = min over benchmarks = {_fmt_float(combined.delta, 4)}")
    lines.append(f"- kappa = min over benchmarks = {_fmt_float(combined.kappa, 4)}")
    lines.append("")
    lines.append("Cascade trace:")
    lines.append("```")
    for tline in _cascade_trace(combined.delta, combined.kappa):
        lines.append(tline)
    lines.append("```")
    lines.append("")
    lines.append(f"**Verdict:** `{combined.verdict}`")
    if combined.verdict_annotations:
        lines.append(
            f"**Annotations:** {', '.join('`' + a + '`' for a in combined.verdict_annotations)}"
        )
    else:
        lines.append("**Annotations:** (none)")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_markdown_artifact(out_path: Path, report: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")


# ===========================================================================
# Orchestration + CLI.
# ===========================================================================


def run_real_data(repo_root: Path, self_test_ran: bool) -> int:
    """Real-data execution: load both dumps, compute, write artifacts."""
    inputs: dict[str, BenchmarkInputs] = {}
    for benchmark in BENCHMARKS:
        path = repo_root / PINNED_INPUT_PATHS[benchmark]
        inputs[benchmark] = load_dump(path, benchmark)

    metrics: dict[str, BenchmarkMetrics] = {}
    for benchmark in BENCHMARKS:
        metrics[benchmark] = compute_benchmark_results(inputs[benchmark])

    combined = compute_combined_verdict(
        metrics[BENCHMARKS[0]], metrics[BENCHMARKS[1]]
    )

    out_json = repo_root / OUTPUT_JSON_PATH
    out_md = repo_root / OUTPUT_MD_PATH
    write_json_artifact(
        out_json, metrics[BENCHMARKS[0]], metrics[BENCHMARKS[1]], combined
    )
    report = format_markdown_report(
        metrics[BENCHMARKS[0]],
        metrics[BENCHMARKS[1]],
        combined,
        self_test_ran=self_test_ran,
    )
    write_markdown_artifact(out_md, report)

    print(f"\nWrote: {out_json}")
    print(f"Wrote: {out_md}")
    print(
        f"\nVerdict: {combined.verdict}"
        + (
            f"  (annotations: {combined.verdict_annotations})"
            if combined.verdict_annotations
            else ""
        )
    )
    return 0


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "§15.1 selective abstention scout — pure post-processing of "
            "existing §13.10 dumps."
        )
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Run the §15.1 cascade + demotion self-test only and exit. "
            "Required pre-execution gate per §15.1 Chunks 4b / 4c."
        ),
    )
    p.add_argument(
        "--no-self-test",
        action="store_true",
        help=(
            "Skip the cascade self-test gate before real-data execution "
            "(debug only; the result section will flag this as a §0.8 "
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

    # Pure self-test invocation.
    if args.self_test:
        return self_test()

    # Real-data invocation: gate self-test first unless explicitly skipped.
    self_test_ran = False
    if not args.no_self_test:
        rc = self_test()
        if rc != 0:
            print(
                "\nABORT: self-test failed; refusing to proceed with "
                "real-data execution per §15.1 Chunks 4b / 4c.",
                file=sys.stderr,
            )
            return rc
        self_test_ran = True
    else:
        print(
            "WARNING: --no-self-test set; cascade gate skipped. The result "
            "markdown will flag this as a §0.8 deviation.",
            file=sys.stderr,
        )

    return run_real_data(args.repo_root, self_test_ran=self_test_ran)


if __name__ == "__main__":
    raise SystemExit(main())

