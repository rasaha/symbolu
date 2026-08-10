#!/usr/bin/env python
"""§15.3 — Hybrid §14-selector + §15-abstention scout.

Pure post-processing analysis: reads the §14a.2 on-disk dump
(probe_system_level_scout_v2_halueval_qa.json), extracts the
V1-selected answer's per-question correctness and the
winning-source's semantic-entropy scalar, runs a §15-style
abstention sweep + bootstrap, and emits a §15.3 verdict per
the 1D Delta_kappa cascade pinned in §15.3 Chunk 3g.

Reference design: Project_documentation/repository/docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md
§15.3 Chunks 3a-3i.

Discipline: all pinned constants, the cascade, the demotion
rule, and the operational metrics are pinned in §15.3 and
MUST NOT be changed during implementation. Any deviation at
run time MUST be flagged as a §0.8 deviation in the §15.3
result section, not absorbed silently. The required pre-
execution gate is `--self-test`, which verifies the 1D
cascade against §15.3 Chunk 3g's boundary-case audit table
and the STRONG-only demotion rule.

Stage A is FIXED to the §14a.2 NLI-clustered selector + V1
softmin tau=0.5 consumer, with M=3 cross-family sources
(Qwen + Llama + Mistral). Stage A is NOT re-run; the §14a.2
dump is the pinned input.

Stage B is the §15-style abstention gate: ANSWER if r(q) <
tau else ABSTAIN; ties to ABSTAIN. The risk signal r(q) is
the V1-winning-source's per-source semantic entropy.

Inputs (per §15.3 Chunk 3h):
    docs/experiments/probe_system_level_scout_v2_halueval_qa.json

Outputs (per §15.3 Chunk 3h):
    docs/experiments/probe_hybrid_selective_abstention.json
    docs/experiments/probe_hybrid_selective_abstention.md

Usage:
    # Required pre-execution gate.
    python scripts/probe_hybrid_selective_abstention.py --self-test

    # Real-data run (auto-runs --self-test first; aborts on failure).
    python scripts/probe_hybrid_selective_abstention.py

    # Real-data run skipping the self-test gate (debug only;
    # the result section MUST flag this as a §0.8 deviation).
    python scripts/probe_hybrid_selective_abstention.py --no-self-test

§15.1 metric primitives are COPIED, not imported, to preserve
§15.1's reproducibility chain (per §15.3 Chunk 3h).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# ===========================================================================
# §15.3 PINNED CONSTANTS — DO NOT CHANGE during implementation.
# Any change requires a fresh §0.8 amendment to §15.3.
# ===========================================================================

SCHEMA_VERSION = "15.3"

# Chunk 3e — single benchmark.
BENCHMARK = "halueval_qa"

# Chunk 3h — pinned input path; fail-fast on file-not-found.
INPUT_PATH = "docs/experiments/probe_system_level_scout_v2_halueval_qa.json"

# Chunk 3b / 3e — pinned size.
PINNED_N = 100
PINNED_M = 3  # cross-family source count

# Chunk 3f — three pinned target accuracies on HaluEval-QA.
# (alpha_1 = greedy baseline + 10pp; alpha_2 = 0.50; alpha_3 = 0.75.)
ALPHA_TARGETS: tuple[float, ...] = (0.40, 0.50, 0.75)
ALPHA_PRIMARY = 0.50  # alpha_2 — drives kappa_hybrid and Delta_kappa

# Chunk 3a (inherited from §15.1) — minimum-answered floor.
N_MIN = 10

# Chunk 3f — pinned §15.1 HaluEval kappa@alpha_2 baseline (§15.2
# verdict-of-record). Drives the primary decision metric Delta_kappa.
KAPPA_BASELINE_S15_1 = 0.26

# Chunk 3f — bootstrap convention (matches §15.1 for audit consistency).
BOOTSTRAP_B = 1000
BOOTSTRAP_SEED_ENTROPY = 15
CI_LOW_PCT = 2.5
CI_HIGH_PCT = 97.5

# Chunk 3g — verdict cascade thresholds (1D, on Delta_kappa).
DELTA_KAPPA_REGRESSION = -0.02
DELTA_KAPPA_STRONG = +0.10
DELTA_KAPPA_USEFUL = +0.05
DELTA_KAPPA_MARGINAL = +0.02

# Chunk 3h — pinned output paths.
OUTPUT_JSON_PATH = "docs/experiments/probe_hybrid_selective_abstention.json"
OUTPUT_MD_PATH = "docs/experiments/probe_hybrid_selective_abstention.md"

# Chunk 3h — §14a.2 dump field names (validated against
# scripts/probe_system_level_scout_v2.py's JSON writer).
FIELD_QUESTIONS = "questions"
FIELD_QUESTION_ID = "q_idx"
FIELD_SOURCES = "sources"
FIELD_SOURCE_ENTROPY = "semantic_entropy"
FIELD_ANSWER_CLUSTER_IDS = "answer_cluster_ids"
FIELD_V1_WEIGHTS = "v1_weights"
FIELD_V1_WINNING_CLUSTER = "v1_winning_cluster"
FIELD_V1_CORRECT = "v1_correct"

# Chunk 3g boundary-case audit table — 4 rows from §15.3 Chunk 3g
# plus 3 boundary-inclusivity anchors.
SELF_TEST_CASCADE_CASES: list[tuple[float, str]] = [
    (+0.099, "USEFUL_INTERNAL"),
    (+0.019, "SATURATION"),
    (-0.020, "SATURATION"),
    (-0.021, "REGRESSION"),
    (+0.100, "STRONG"),  # boundary inclusive
    (+0.050, "USEFUL_INTERNAL"),  # boundary inclusive
    (+0.020, "MARGINAL"),  # boundary inclusive
]

# Chunk 3g STRONG-only demotion rule self-test cases.
# Single-benchmark, so only one CI lower bound (not pair like §15.1).
SELF_TEST_DEMOTION_CASES: list[
    tuple[str, float, str, list[str]]
] = [
    # Strictly positive CI lower bound — STRONG stands.
    ("STRONG", 0.01, "STRONG", []),
    # CI lower bound exactly 0 — STRONG demotes.
    ("STRONG", 0.00, "USEFUL_INTERNAL", ["STRONG_BUT_CI_DEMOTION"]),
    # CI lower bound negative — STRONG demotes.
    ("STRONG", -0.01, "USEFUL_INTERNAL", ["STRONG_BUT_CI_DEMOTION"]),
    # USEFUL_INTERNAL not subject to demotion.
    ("USEFUL_INTERNAL", -0.05, "USEFUL_INTERNAL", []),
    # MARGINAL not subject to demotion.
    ("MARGINAL", -0.05, "MARGINAL", []),
    # SATURATION not subject to demotion.
    ("SATURATION", -0.05, "SATURATION", []),
    # REGRESSION not subject to demotion.
    ("REGRESSION", -0.10, "REGRESSION", []),
]


# ===========================================================================
# Dataclasses.
# ===========================================================================


@dataclass(frozen=True)
class StageAHandoff:
    """Per-question Stage A output the hybrid evaluator consumes."""

    q_ids: np.ndarray  # int, shape (N,)
    risk_scores: np.ndarray  # float, shape (N,) — H_src of V1's winning source
    correctness: np.ndarray  # bool, shape (N,) — c(q) = V1's selected answer correctness
    winning_source_idx: np.ndarray  # int, shape (N,) — the i* per question


@dataclass(frozen=True)
class OperatingPoint:
    alpha: float
    cov: float
    tau_star: float
    ecr: float
    far: float


@dataclass(frozen=True)
class HybridResult:
    benchmark: str
    n_questions: int
    n_questions_v1_correct: int  # = sum(c(q))
    w_hybrid: int  # = N - n_questions_v1_correct
    auc_random: float
    auc_policy: float
    delta_auc: float
    kappa_hybrid: float
    kappa_baseline: float
    delta_kappa: float
    delta_kappa_ci: tuple[float, float]
    operating_points: list[OperatingPoint]
    threshold_sweep: list[dict]
    parity_gates: dict[str, bool]


@dataclass(frozen=True)
class Verdict:
    verdict: str
    verdict_annotations: list[str]


# ===========================================================================
# Glue layer (components 1-3 per §15.3 Chunk 3h).
# ===========================================================================


def load_dump(path: Path) -> list[dict]:
    """Component 1 — load and validate the §14a.2 dump.

    Returns the per-question records list. Aborts with
    SCHEMA_MISMATCH on file-not-found, malformed JSON, missing
    top-level `questions` field, or any per-question record
    missing the §15.3-pinned fields. No fallback.
    """
    if not path.exists():
        print(
            f"SCHEMA_MISMATCH: §14a.2 dump not found: {path}",
            file=sys.stderr,
        )
        print(
            f"  (per §15.3 Chunk 3h, the §14a.2 dump is pinned at this "
            f"exact path; no fallback path is consulted.)",
            file=sys.stderr,
        )
        raise SystemExit(2)

    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        print(f"SCHEMA_MISMATCH: {path} is not valid JSON: {e}", file=sys.stderr)
        raise SystemExit(2) from None

    if not isinstance(payload, dict) or FIELD_QUESTIONS not in payload:
        print(
            f"SCHEMA_MISMATCH: {path} top-level missing '{FIELD_QUESTIONS}' "
            f"field (§14a.2 schema)",
            file=sys.stderr,
        )
        raise SystemExit(2)

    records = payload[FIELD_QUESTIONS]
    if not isinstance(records, list):
        print(
            f"SCHEMA_MISMATCH: {path}.{FIELD_QUESTIONS} must be a list",
            file=sys.stderr,
        )
        raise SystemExit(2)

    required_per_question = (
        FIELD_QUESTION_ID,
        FIELD_SOURCES,
        FIELD_ANSWER_CLUSTER_IDS,
        FIELD_V1_WEIGHTS,
        FIELD_V1_WINNING_CLUSTER,
        FIELD_V1_CORRECT,
    )
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            print(
                f"SCHEMA_MISMATCH: {path}.questions[{i}] is not a JSON object",
                file=sys.stderr,
            )
            raise SystemExit(2)
        for fname in required_per_question:
            if fname not in rec:
                print(
                    f"SCHEMA_MISMATCH: {path}.questions[{i}] missing "
                    f"required field '{fname}' (§14a.2 schema; pinned by "
                    f"§15.3 Chunk 3h)",
                    file=sys.stderr,
                )
                raise SystemExit(2)
        sources = rec[FIELD_SOURCES]
        if not isinstance(sources, list) or len(sources) != PINNED_M:
            print(
                f"SCHEMA_MISMATCH: {path}.questions[{i}].sources must be a "
                f"list of length M={PINNED_M} (got {len(sources) if isinstance(sources, list) else type(sources).__name__})",
                file=sys.stderr,
            )
            raise SystemExit(2)
        for j, src in enumerate(sources):
            if not isinstance(src, dict) or FIELD_SOURCE_ENTROPY not in src:
                print(
                    f"SCHEMA_MISMATCH: {path}.questions[{i}].sources[{j}] "
                    f"missing required field '{FIELD_SOURCE_ENTROPY}'",
                    file=sys.stderr,
                )
                raise SystemExit(2)

    return records


def run_parity_gates(records: list[dict]) -> dict[str, bool]:
    """Component 2 — verify N=PINNED_N on HaluEval-QA.

    Aborts on mismatch with explicit "§15.3 assumptions no longer
    hold" message; does NOT recompute pinned values from the
    dump (per §15.3's discipline mirroring §15.1 Chunk 5).
    """
    n = len(records)
    n_ok = n == PINNED_N

    if not n_ok:
        msg = [
            f"PARITY_GATE_FAILED on §15.3 hybrid scout:",
            f"  observed: N={n}",
            f"  pinned:   N={PINNED_N}",
            "",
            "§15.3's pinned assumptions about the §14a.2 dump no longer",
            "hold. Per §15.3 Chunk 3h, §15.3 cannot proceed under modified",
            "assumptions. Abort. A fresh §0.8 amendment to §15.3 would",
            "be required before any §15.3 verdict can be reported on this",
            "configuration.",
        ]
        print("\n".join(msg), file=sys.stderr)
        raise SystemExit(3)

    return {"N_ok": n_ok}


def extract_stage_a_handoff(records: list[dict]) -> StageAHandoff:
    """Component 3 — derive (r(q), c(q), q_idx, winning_source_idx).

    For each question:
      * winning_source_idx i* = argmax_{i in winning_cluster} v1_weights[i],
        ties broken by lowest source index (matches §14a.2's
        within-cluster representative-source rule).
      * r(q) = sources[i*].semantic_entropy.
      * c(q) = v1_correct.
      * q_idx = q_idx.
    """
    q_ids: list[int] = []
    risk_scores: list[float] = []
    correctness: list[bool] = []
    winning_source_idx: list[int] = []

    for i, rec in enumerate(records):
        sources = rec[FIELD_SOURCES]
        v1_weights = rec[FIELD_V1_WEIGHTS]
        cluster_ids = rec[FIELD_ANSWER_CLUSTER_IDS]
        winning_cluster = rec[FIELD_V1_WINNING_CLUSTER]

        if len(v1_weights) != PINNED_M or len(cluster_ids) != PINNED_M:
            print(
                f"SCHEMA_MISMATCH: questions[{i}] v1_weights or "
                f"answer_cluster_ids length != M={PINNED_M}",
                file=sys.stderr,
            )
            raise SystemExit(2)

        # Candidates = sources in the winning cluster.
        candidates = [
            j for j in range(PINNED_M) if cluster_ids[j] == winning_cluster
        ]
        if not candidates:
            print(
                f"SCHEMA_MISMATCH: questions[{i}] winning_cluster "
                f"{winning_cluster} has no member sources",
                file=sys.stderr,
            )
            raise SystemExit(2)
        # argmax v1_weights[j], ties broken by lowest j.
        winner = max(candidates, key=lambda j: (v1_weights[j], -j))

        q_ids.append(int(rec[FIELD_QUESTION_ID]))
        risk_scores.append(float(sources[winner][FIELD_SOURCE_ENTROPY]))
        correctness.append(bool(rec[FIELD_V1_CORRECT]))
        winning_source_idx.append(winner)

    q_id_arr = np.asarray(q_ids, dtype=np.int64)
    if len(set(q_ids)) != len(q_ids):
        print(
            f"SCHEMA_MISMATCH: duplicate {FIELD_QUESTION_ID} values; "
            f"ascending-risk tiebreak would be non-deterministic",
            file=sys.stderr,
        )
        raise SystemExit(2)

    return StageAHandoff(
        q_ids=q_id_arr,
        risk_scores=np.asarray(risk_scores, dtype=np.float64),
        correctness=np.asarray(correctness, dtype=bool),
        winning_source_idx=np.asarray(winning_source_idx, dtype=np.int64),
    )


# ===========================================================================
# §15.1 metric primitives — COPIED verbatim from
# scripts/probe_selective_abstention.py per §15.3 Chunk 3h's "copy not
# import" rule. Importing would couple §15.3 to any future drift in the
# §15.1 codepath, compromising §15.1's reproducibility chain (§15.2
# Postscript).
#
# Components 4-7 per §15.3 Chunk 3h.
# ===========================================================================


def compute_threshold_grid(entropies: np.ndarray) -> np.ndarray:
    """Component 4 (copied from §15.1) — threshold sweep grid.

    Sorted unique values of r(q) plus -inf and +inf.
    """
    uniques = np.unique(entropies.astype(float))
    return np.concatenate(([-np.inf], uniques, [np.inf]))


def policy_at_threshold(entropies: np.ndarray, tau: float) -> np.ndarray:
    """Boolean mask of the answered set A_tau (copied from §15.1).

    ANSWER iff r(q) < tau, ABSTAIN otherwise. Ties to ABSTAIN.
    """
    return entropies < tau


def metrics_at_threshold(
    entropies: np.ndarray,
    correctness: np.ndarray,
    tau: float,
    W: int,
    N: int,
) -> tuple[float, float, float, float]:
    """Component 5 (copied from §15.1) — (cov, acc, ecr, far) at one tau.

    NaN handling identical to §15.1: acc=NaN when |A_tau|=0;
    ecr=NaN when W=0; far=NaN when C=N-W=0.
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
    """Component 7 (copied from §15.1) — Geifman-El-Yaniv 2017 AURC.

    Sort by ascending r(q), q_id tiebreak. Cumulative selective
    error e_k = (1/k) sum_{i<=k} (1 - c_(i)). AURC = (1/N) sum_k e_k.
    Range [0, 1], lower is better.
    """
    n = entropies.shape[0]
    if n == 0:
        raise ValueError("Cannot compute AURC on empty input")
    order = np.lexsort((q_ids, entropies))
    sorted_correct = correctness[order].astype(np.float64)
    cumulative_wrong = np.cumsum(1.0 - sorted_correct)
    ks = np.arange(1, n + 1, dtype=np.float64)
    e_k = cumulative_wrong / ks
    return float(e_k.mean())


def cov_at_target_accuracy(
    entropies: np.ndarray,
    correctness: np.ndarray,
    grid: np.ndarray,
    alpha: float,
    n_min: int,
    W: int,
    N: int,
) -> tuple[float, float, float, float]:
    """Component 6 (copied from §15.1) — cov@alpha with n_min floor.

    cov@alpha = max{ cov(tau) : acc(tau) >= alpha AND |A_tau| >= n_min }.
    Returns (cov, tau_star, ecr_at_tau_star, far_at_tau_star).
    Defaults to (0.0, +inf, NaN, NaN) if no tau qualifies.
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
        if not (acc >= alpha):  # NaN-safe.
            continue
        if cov > best_cov:
            best_cov = cov
            best_tau = float(tau)
            best_ecr = ecr
            best_far = far

    return best_cov, best_tau, best_ecr, best_far


def analytic_random_aurc(W: int, N: int) -> float:
    """Random-matched AURC baseline = W/N (copied from §15.1)."""
    if N <= 0:
        raise ValueError(f"N must be positive (got {N})")
    return float(W) / float(N)


# ===========================================================================
# Hybrid evaluator (components 8-10 per §15.3 Chunk 3h).
# Single-benchmark; 1D cascade on Delta_kappa; STRONG-only demotion.
# These are §15.3-specific, NOT copied from §15.1.
# ===========================================================================


def _benchmark_rng() -> np.random.Generator:
    """Deterministic RNG for the single-benchmark §15.3 bootstrap.

    Per §15.3 Chunk 3f, the bootstrap seed convention matches §15.1
    exactly (SeedSequence(entropy=15)). Single benchmark means a
    single child seed (no spawn over a benchmark tuple).
    """
    seed_seq = np.random.SeedSequence(entropy=BOOTSTRAP_SEED_ENTROPY)
    return np.random.Generator(np.random.PCG64(seed_seq))


def bootstrap_delta_kappa(
    handoff: StageAHandoff, B: int = BOOTSTRAP_B
) -> tuple[float, float]:
    """Component 8 — paired bootstrap CI on Delta_kappa.

    For each of B resamples:
      * draw N indices uniformly with replacement,
      * recompute kappa_hybrid_resample = cov@alpha_2 on the resample
        with the same n_min floor,
      * Delta_kappa_resample = kappa_hybrid_resample - KAPPA_BASELINE_S15_1.

    Returns (lo, hi) at the pinned 2.5/97.5 percentiles (two-sided
    95% CI). The §15.1 HaluEval kappa@alpha_2 baseline is treated
    as a fixed constant (its sampling variance was already captured
    in §15.2's verdict-of-record CI; re-bootstrapping the §15.1
    baseline against §15.3 resamples would conflate two
    different sampling distributions).
    """
    rng = _benchmark_rng()
    n = int(handoff.q_ids.shape[0])
    delta_samples = np.empty(B, dtype=np.float64)

    for b in range(B):
        idx = rng.integers(0, n, size=n)
        ent_r = handoff.risk_scores[idx]
        cor_r = handoff.correctness[idx]
        w_r = int((~cor_r).sum())
        grid_r = compute_threshold_grid(ent_r)
        kappa_r, _, _, _ = cov_at_target_accuracy(
            ent_r, cor_r, grid_r, ALPHA_PRIMARY, N_MIN, w_r, n
        )
        delta_samples[b] = kappa_r - KAPPA_BASELINE_S15_1

    return (
        float(np.percentile(delta_samples, CI_LOW_PCT)),
        float(np.percentile(delta_samples, CI_HIGH_PCT)),
    )


def verdict_cascade_15_3(delta_kappa: float) -> str:
    """Component 9 — 1D cascade on Delta_kappa per §15.3 Chunk 3g.

    Ordered, mutually exclusive, exhaustive over R via the
    SATURATION residual catch-all:

        1. REGRESSION       — Delta_kappa < -0.02
        2. STRONG           — Delta_kappa >= +0.10
        3. USEFUL_INTERNAL  — Delta_kappa >= +0.05
        4. MARGINAL         — Delta_kappa >= +0.02
        5. SATURATION       — explicit residual

    REGRESSION first so a Delta_kappa < -0.02 outcome classifies as
    regression regardless of any secondary diagnostic; secondary
    metrics do NOT participate in the cascade per Chunk 3g.
    """
    if delta_kappa < DELTA_KAPPA_REGRESSION:
        return "REGRESSION"
    if delta_kappa >= DELTA_KAPPA_STRONG:
        return "STRONG"
    if delta_kappa >= DELTA_KAPPA_USEFUL:
        return "USEFUL_INTERNAL"
    if delta_kappa >= DELTA_KAPPA_MARGINAL:
        return "MARGINAL"
    return "SATURATION"


def apply_demotion_rule_15_3(
    point_verdict: str, delta_kappa_ci_lower: float
) -> tuple[str, list[str]]:
    """Component 10 — STRONG-only demotion rule per §15.3 Chunk 3g.

    If point-estimate verdict is STRONG and the bootstrap CI lower
    bound on Delta_kappa is <= 0, demote to USEFUL_INTERNAL with
    explicit STRONG_BUT_CI_DEMOTION annotation. Other verdicts are
    NOT subject to demotion. Mirrors §15.1 Chunk 4c's narrow rule.
    """
    if point_verdict != "STRONG":
        return point_verdict, []
    if delta_kappa_ci_lower > 0.0:
        return "STRONG", []
    return "USEFUL_INTERNAL", ["STRONG_BUT_CI_DEMOTION"]


def compute_hybrid_result(handoff: StageAHandoff) -> HybridResult:
    """Orchestrates the full §15.3 evaluator pipeline."""
    n = int(handoff.q_ids.shape[0])
    n_correct = int(handoff.correctness.sum())
    w_hybrid = n - n_correct

    grid = compute_threshold_grid(handoff.risk_scores)
    auc_random = analytic_random_aurc(w_hybrid, n)
    auc_policy = aurc_discrete(
        handoff.risk_scores, handoff.correctness, handoff.q_ids
    )
    delta_auc = auc_random - auc_policy

    operating_points: list[OperatingPoint] = []
    kappa_at_primary = 0.0
    for alpha in ALPHA_TARGETS:
        cov, tau_star, ecr, far = cov_at_target_accuracy(
            handoff.risk_scores,
            handoff.correctness,
            grid,
            alpha,
            N_MIN,
            w_hybrid,
            n,
        )
        operating_points.append(
            OperatingPoint(alpha=alpha, cov=cov, tau_star=tau_star, ecr=ecr, far=far)
        )
        if alpha == ALPHA_PRIMARY:
            kappa_at_primary = cov

    delta_kappa = kappa_at_primary - KAPPA_BASELINE_S15_1

    threshold_sweep: list[dict] = []
    for tau in grid:
        cov, acc, ecr, far = metrics_at_threshold(
            handoff.risk_scores, handoff.correctness, float(tau), w_hybrid, n
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

    delta_kappa_ci = bootstrap_delta_kappa(handoff)
    parity_gates = {"N_ok": n == PINNED_N}

    return HybridResult(
        benchmark=BENCHMARK,
        n_questions=n,
        n_questions_v1_correct=n_correct,
        w_hybrid=w_hybrid,
        auc_random=auc_random,
        auc_policy=auc_policy,
        delta_auc=delta_auc,
        kappa_hybrid=kappa_at_primary,
        kappa_baseline=KAPPA_BASELINE_S15_1,
        delta_kappa=delta_kappa,
        delta_kappa_ci=delta_kappa_ci,
        operating_points=operating_points,
        threshold_sweep=threshold_sweep,
        parity_gates=parity_gates,
    )


def compute_verdict(result: HybridResult) -> Verdict:
    """Apply cascade + demotion rule to produce the final verdict."""
    point_verdict = verdict_cascade_15_3(result.delta_kappa)
    final_verdict, annotations = apply_demotion_rule_15_3(
        point_verdict, result.delta_kappa_ci[0]
    )
    return Verdict(verdict=final_verdict, verdict_annotations=annotations)


# ===========================================================================
# Self-test (component 11 per §15.3 Chunk 3h).
# Required pre-execution gate per §15.3 Chunk 3g. Verifies the 1D
# cascade against Chunk 3g's boundary-case audit table and the
# STRONG-only demotion rule against Chunk 3g's demotion cases.
# ===========================================================================


def self_test() -> int:
    """Run the §15.3 cascade + demotion self-tests.

    Returns 0 on success, nonzero on failure. Aborts real-data
    execution when invoked as a gate (see main()).
    """
    failures: list[str] = []

    # 1D cascade boundary cases (Chunk 3g audit table + boundary-
    # inclusivity anchors).
    for delta_kappa, expected in SELF_TEST_CASCADE_CASES:
        observed = verdict_cascade_15_3(delta_kappa)
        ok = observed == expected
        marker = "PASS" if ok else "FAIL"
        print(
            f"  [{marker}] cascade(delta_kappa={delta_kappa:+.3f}) "
            f"= {observed}  (expected {expected})"
        )
        if not ok:
            failures.append(
                f"cascade({delta_kappa:+.3f}) = {observed} "
                f"!= expected {expected}"
            )

    # STRONG-only demotion rule (Chunk 3g).
    for point_verdict, ci_lower, expected, expected_anns in (
        SELF_TEST_DEMOTION_CASES
    ):
        verdict, anns = apply_demotion_rule_15_3(point_verdict, ci_lower)
        ok = verdict == expected and anns == expected_anns
        marker = "PASS" if ok else "FAIL"
        print(
            f"  [{marker}] demote({point_verdict}, "
            f"ci_lower={ci_lower:+.3f}) "
            f"= ({verdict}, {anns})  "
            f"(expected ({expected}, {expected_anns}))"
        )
        if not ok:
            failures.append(
                f"demote({point_verdict}, {ci_lower:+.3f}) = "
                f"({verdict}, {anns}) != expected "
                f"({expected}, {expected_anns})"
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
        f"{len(SELF_TEST_CASCADE_CASES)} cascade cases + "
        f"{len(SELF_TEST_DEMOTION_CASES)} demotion cases."
    )
    return 0


# ===========================================================================
# Output writers (component 12 per §15.3 Chunk 3h).
# JSON: machine-readable, schema_version "15.3", single-benchmark block
# under `benchmark`, `combined` block with verdict + delta_kappa fields.
# Markdown: parity gates, headline, operating points, cascade trace,
# verdict + annotations.
# ===========================================================================


def _operating_point_to_dict(op: OperatingPoint) -> dict:
    return {
        "alpha": op.alpha,
        "cov": op.cov,
        "tau_star": op.tau_star,
        "ecr": op.ecr,
        "far": op.far,
    }


def write_json_artifact(
    out_path: Path, result: HybridResult, verdict: Verdict
) -> None:
    """Write the §15.3 Chunk 3h machine-readable artifact."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_name": result.benchmark,
        "n_questions": result.n_questions,
        "bootstrap_B": BOOTSTRAP_B,
        "bootstrap_seed": f"SeedSequence(entropy={BOOTSTRAP_SEED_ENTROPY})",
        "stage_a": {
            "selector": "NLI-clustered weighted majority vote (§14a.2)",
            "consumer": "V1 softmin tau=0.5 (§14a.2)",
            "M_sources": PINNED_M,
            "input_dump": INPUT_PATH,
        },
        "stage_b": {
            "risk_signal": "H_src_winning (§13.10/§14a.2 semantic entropy of V1's winning source)",
            "policy": "ANSWER if r(q) < tau else ABSTAIN; ties to ABSTAIN",
            "alpha_targets": list(ALPHA_TARGETS),
            "alpha_primary": ALPHA_PRIMARY,
            "n_min": N_MIN,
        },
        "benchmark": {
            "n_questions": result.n_questions,
            "n_v1_correct": result.n_questions_v1_correct,
            "w_hybrid": result.w_hybrid,
            "auc_random": result.auc_random,
            "auc_policy": result.auc_policy,
            "delta_auc": result.delta_auc,
            "kappa_hybrid": result.kappa_hybrid,
            "kappa_baseline_§15.1": result.kappa_baseline,
            "delta_kappa": result.delta_kappa,
            "delta_kappa_ci": list(result.delta_kappa_ci),
            "operating_points": [
                _operating_point_to_dict(op) for op in result.operating_points
            ],
            "threshold_sweep": result.threshold_sweep,
            "parity_gates": result.parity_gates,
        },
        "combined": {
            "delta_kappa": result.delta_kappa,
            "kappa_hybrid": result.kappa_hybrid,
            "kappa_baseline_§15.1": result.kappa_baseline,
            "verdict": verdict.verdict,
            "verdict_annotations": list(verdict.verdict_annotations),
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


def _cascade_trace_15_3(delta_kappa: float) -> list[str]:
    """Walk the §15.3 1D cascade for the markdown report."""
    trace = []
    if delta_kappa < DELTA_KAPPA_REGRESSION:
        trace.append(
            f"  rule 1 REGRESSION: delta_kappa={_fmt_float(delta_kappa)} "
            f"< {DELTA_KAPPA_REGRESSION:+.2f}  -> YES"
        )
        return trace
    trace.append(
        f"  rule 1 REGRESSION: delta_kappa={_fmt_float(delta_kappa)} "
        f"< {DELTA_KAPPA_REGRESSION:+.2f}  -> NO"
    )
    if delta_kappa >= DELTA_KAPPA_STRONG:
        trace.append(
            f"  rule 2 STRONG: delta_kappa>={DELTA_KAPPA_STRONG:+.2f}  -> YES"
        )
        return trace
    trace.append(
        f"  rule 2 STRONG: delta_kappa>={DELTA_KAPPA_STRONG:+.2f}  -> NO"
    )
    if delta_kappa >= DELTA_KAPPA_USEFUL:
        trace.append(
            f"  rule 3 USEFUL_INTERNAL: delta_kappa>={DELTA_KAPPA_USEFUL:+.2f}  -> YES"
        )
        return trace
    trace.append(
        f"  rule 3 USEFUL_INTERNAL: delta_kappa>={DELTA_KAPPA_USEFUL:+.2f}  -> NO"
    )
    if delta_kappa >= DELTA_KAPPA_MARGINAL:
        trace.append(
            f"  rule 4 MARGINAL: delta_kappa>={DELTA_KAPPA_MARGINAL:+.2f}  -> YES"
        )
        return trace
    trace.append(
        f"  rule 4 MARGINAL: delta_kappa>={DELTA_KAPPA_MARGINAL:+.2f}  -> NO"
    )
    trace.append("  rule 5 SATURATION: residual catch-all  -> YES")
    return trace


def format_markdown_report(
    result: HybridResult, verdict: Verdict, self_test_ran: bool
) -> str:
    """Render the §15.3 Chunk 3h human-readable summary report."""
    lines: list[str] = []
    lines.append("# §15.3 — Hybrid §14-selector + §15-abstention scout result\n")
    lines.append(f"- schema_version: `{SCHEMA_VERSION}`")
    lines.append(f"- benchmark: `{result.benchmark}` (single-benchmark scout)")
    lines.append(f"- n_questions: {result.n_questions}")
    lines.append(f"- bootstrap_B: {BOOTSTRAP_B}")
    lines.append(
        f"- bootstrap_seed: `SeedSequence(entropy={BOOTSTRAP_SEED_ENTROPY})`"
    )
    lines.append(f"- alpha_primary (cov@α target): {ALPHA_PRIMARY}")
    lines.append(f"- n_min (cov@α floor): {N_MIN}")
    lines.append(f"- kappa_baseline (§15.1 HaluEval κ@α₂): {result.kappa_baseline}")
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
    lines.append("| benchmark | N_ok |")
    lines.append("|---|---|")
    lines.append(f"| {result.benchmark} | {result.parity_gates['N_ok']} |")
    lines.append("")

    lines.append("## Stage A configuration (§14a.2 pinned)")
    lines.append(f"- selector: NLI-clustered weighted majority vote (§14a.2)")
    lines.append(f"- consumer: V1 softmin tau=0.5 (§14a.2)")
    lines.append(f"- M sources: {PINNED_M} (Qwen + Llama + Mistral)")
    lines.append(f"- input dump: `{INPUT_PATH}`")
    lines.append("")

    lines.append("## Headline")
    lines.append(
        "| metric | value |"
    )
    lines.append("|---|---|")
    lines.append(f"| W_hybrid | {result.w_hybrid} |")
    lines.append(f"| AURC_random (= W/N) | {_fmt_float(result.auc_random)} |")
    lines.append(f"| AURC_policy | {_fmt_float(result.auc_policy)} |")
    lines.append(f"| δ_AURC (diagnostic) | {_fmt_float(result.delta_auc)} |")
    lines.append(f"| κ_hybrid | {_fmt_float(result.kappa_hybrid)} |")
    lines.append(f"| κ_§15.1 baseline | {_fmt_float(result.kappa_baseline)} |")
    lines.append(
        f"| **Δκ (primary)** | "
        f"**{_fmt_float(result.delta_kappa)}** |"
    )
    lines.append(
        f"| Δκ 95% CI | "
        f"[{_fmt_float(result.delta_kappa_ci[0])}, "
        f"{_fmt_float(result.delta_kappa_ci[1])}] |"
    )
    lines.append("")

    lines.append("## Operating points")
    lines.append("| α | cov | τ* | ecr | far |")
    lines.append("|---|---|---|---|---|")
    for op in result.operating_points:
        lines.append(
            f"| {_fmt_float(op.alpha, 2)} | {_fmt_float(op.cov)} | "
            f"{_fmt_float(op.tau_star)} | {_fmt_float(op.ecr)} | "
            f"{_fmt_float(op.far)} |"
        )
    lines.append("")

    lines.append("## Verdict cascade trace")
    lines.append("```")
    for tline in _cascade_trace_15_3(result.delta_kappa):
        lines.append(tline)
    lines.append("```")
    lines.append("")
    lines.append(f"**Verdict:** `{verdict.verdict}`")
    if verdict.verdict_annotations:
        lines.append(
            f"**Annotations:** "
            f"{', '.join('`' + a + '`' for a in verdict.verdict_annotations)}"
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
    """Real-data execution: load §14a.2 dump, parity gates, evaluate, write."""
    input_path = repo_root / INPUT_PATH
    records = load_dump(input_path)
    run_parity_gates(records)

    handoff = extract_stage_a_handoff(records)
    result = compute_hybrid_result(handoff)
    verdict = compute_verdict(result)

    out_json = repo_root / OUTPUT_JSON_PATH
    out_md = repo_root / OUTPUT_MD_PATH
    write_json_artifact(out_json, result, verdict)
    report = format_markdown_report(result, verdict, self_test_ran=self_test_ran)
    write_markdown_artifact(out_md, report)

    print(f"\nWrote: {out_json}")
    print(f"Wrote: {out_md}")
    print(
        f"\nVerdict: {verdict.verdict}"
        + (
            f"  (annotations: {verdict.verdict_annotations})"
            if verdict.verdict_annotations
            else ""
        )
    )
    return 0


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "§15.3 hybrid §14-selector + §15-abstention scout — pure "
            "post-processing of the §14a.2 HaluEval-QA dump."
        )
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Run the §15.3 cascade + demotion self-test only and exit. "
            "Required pre-execution gate per §15.3 Chunks 3g."
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

    if args.self_test:
        return self_test()

    self_test_ran = False
    if not args.no_self_test:
        rc = self_test()
        if rc != 0:
            print(
                "\nABORT: self-test failed; refusing to proceed with "
                "real-data execution per §15.3 Chunks 3g / 3h.",
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
