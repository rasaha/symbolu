"""Stage A structural gate G1-G4 (pre-registered thresholds).

A PASS means ONLY: a structural signal exists (feature-grounded operator product
produces inventory-specific, factorizable order-structure beyond bag / random /
relabel). It does NOT mean meaning, Sanskrit privilege, or LLM usefulness.

All thresholds below are FROZEN before any run (see STRUCTURAL_V1_GATE_THRESHOLDS.md
and STRUCTURAL_V1_FACTORIZATION_METRIC.md). No post-hoc tuning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .features import feature_matrix
from .metrics import (
    commuting_vs_coupling_coeffs,
    effective_rank,
    mean_standardized_order_effect,
    order_effect_matrix,
    structure_score,
)
from .operators import feature_operators, random_orthogonal_operators

# ---- FROZEN constants -------------------------------------------------------
SEED = 20240601                 # master seed
G1_MIN_ORDER = 0.10             # mean standardized order-effect floor
PCTILE = 95.0                   # null exceedance percentile
N_RANDOM_ORTHO = 200            # G2 random-orthogonal draws
N_RELABEL = 200                 # G3 relabel permutations
N_RANDOM_FACTOR = 200           # G4 random-factorization (column-shuffle) draws
EFFECTIVE_RANK_MAX = 6.0        # G4 low-dim bar (= C(4,2) generator pairs)
N_STABILITY_SEEDS = 5           # score-stability resamples
STABILITY_STD_MAX = 0.15        # max score std across seeds before INCONCLUSIVE
MIN_PAIRS = 45                  # underpowered floor (n>=10)
N_BOOTSTRAP = 200               # gap-reliability bootstrap


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: Dict[str, float] = field(default_factory=dict)
    note: str = ""


@dataclass
class StageAResult:
    verdict: str                       # PASS | FAIL | INCONCLUSIVE
    gates: List[GateResult]
    warnings: List[str]
    diagnostics: Dict[str, float]


def _pctile_pass(value: float, null: np.ndarray, pct: float = PCTILE) -> bool:
    return float(value) > float(np.percentile(null, pct))


def run_stage_a() -> StageAResult:
    warnings: List[str] = []
    rng = np.random.default_rng(SEED)
    F = feature_matrix()
    n = F.shape[0]
    n_pairs = n * (n - 1) // 2

    ops = feature_operators(F)
    B, _ = order_effect_matrix(ops)
    real_score = structure_score(B, F, seed=SEED)

    # ---- power / stability pre-checks ----
    inconclusive = False
    if n_pairs < MIN_PAIRS:
        warnings.append(f"underpowered: {n_pairs} pairs < {MIN_PAIRS}")
        inconclusive = True
    stab = [structure_score(B, F, seed=SEED + s) for s in range(N_STABILITY_SEEDS)]
    if float(np.std(stab)) > STABILITY_STD_MAX:
        warnings.append(
            f"unstable structure_score across seeds (std={np.std(stab):.3f} > {STABILITY_STD_MAX})"
        )
        inconclusive = True

    # ---- G1: order-sensitivity exists and >> bag (bag == 0 by construction) ----
    mean_oe = mean_standardized_order_effect(B)
    bag_oe = 0.0  # additive aggregation is order-blind by construction
    g1 = GateResult(
        "G1_order_sensitivity",
        passed=(mean_oe >= G1_MIN_ORDER and mean_oe > bag_oe),
        detail={"mean_standardized_order_effect": mean_oe, "bag_order_effect": bag_oe,
                "threshold": G1_MIN_ORDER},
        note="bag order-effect is identically 0 (additive aggregation).",
    )

    # ---- G2: beats random-orthogonal on STRUCTURE (not magnitude) ----
    g2_null = np.array([
        structure_score(order_effect_matrix(
            random_orthogonal_operators(n, rng))[0], F, seed=SEED)
        for _ in range(N_RANDOM_ORTHO)
    ])
    g2 = GateResult(
        "G2_beats_random_orthogonal",
        passed=_pctile_pass(real_score, g2_null),
        detail={"real_structure_score": real_score,
                "null_p95": float(np.percentile(g2_null, PCTILE)),
                "null_mean": float(np.mean(g2_null))},
        note="discriminator is STRUCTURE; random operators may have larger magnitude.",
    )

    # ---- G3: beats relabel (permute feature->unit binding vs real B) ----
    g3_null = np.array([
        structure_score(B, F[rng.permutation(n)], seed=SEED)
        for _ in range(N_RELABEL)
    ])
    g3 = GateResult(
        "G3_beats_relabel",
        passed=_pctile_pass(real_score, g3_null),
        detail={"real_structure_score": real_score,
                "null_p95": float(np.percentile(g3_null, PCTILE)),
                "null_mean": float(np.mean(g3_null))},
        note="tests that the SPECIFIC feature->unit binding matters.",
    )

    # ---- G4: factorization precondition ----
    # (a) low effective dimension
    eff_rank = effective_rank(B)
    low_dim = eff_rank <= EFFECTIVE_RANK_MAX
    # (b) disjoint(commuting) < shared(coupling): coupling coef > commuting coef, reliably
    coeffs = commuting_vs_coupling_coeffs(B, F)
    # bootstrap the gap over unit-pairs for reliability
    from .metrics import wedge_features
    X, pairs, gp = wedge_features(F)
    y = np.array([B[i, j] for (i, j) in pairs])
    from .operators import commuting_generator_pairs
    commuting = set(commuting_generator_pairs())
    comm_idx = [c for c, p in enumerate(gp) if p in commuting]
    coup_idx = [c for c, p in enumerate(gp) if p not in commuting]
    gaps = []
    m = X.shape[0]
    for _ in range(N_BOOTSTRAP):
        bi = rng.integers(0, m, m)
        A = np.hstack([np.ones((m, 1)), X[bi]])
        beta, *_ = np.linalg.lstsq(A, y[bi], rcond=None)
        cf = beta[1:]
        cm = np.mean([abs(cf[c]) for c in comm_idx]) if comm_idx else 0.0
        cp = np.mean([abs(cf[c]) for c in coup_idx]) if coup_idx else 0.0
        gaps.append(cp - cm)
    gap_lo = float(np.percentile(gaps, 2.5))
    gap_reliable = gap_lo > 0.0
    # (c) random-factorization null: predict real B from column-shuffled F
    def _colshuffle(Fm: np.ndarray) -> np.ndarray:
        out = Fm.copy()
        for c in range(out.shape[1]):
            out[:, c] = out[rng.permutation(n), c]
        return out
    g4_null = np.array([
        structure_score(B, _colshuffle(F), seed=SEED)
        for _ in range(N_RANDOM_FACTOR)
    ])
    beats_randfactor = _pctile_pass(real_score, g4_null)
    g4 = GateResult(
        "G4_factorization",
        passed=(low_dim and gap_reliable and beats_randfactor),
        detail={"sub_low_dim": float(low_dim),
                "sub_gap_reliable": float(gap_reliable),
                "sub_beats_randfactor": float(beats_randfactor),
                "effective_rank": eff_rank, "effective_rank_max": EFFECTIVE_RANK_MAX,
                "commuting_coef_mean_abs": coeffs["commuting_coef_mean_abs"],
                "coupling_coef_mean_abs": coeffs["coupling_coef_mean_abs"],
                "gap_ci_low": gap_lo,
                "randfactor_null_p95": float(np.percentile(g4_null, PCTILE)),
                "real_structure_score": real_score},
        note=("partly circular by construction (operators built from features); "
              "informative parts are the relabel/random-factorization nulls."),
    )

    gates = [g1, g2, g3, g4]
    if inconclusive:
        verdict = "INCONCLUSIVE"
    elif all(g.passed for g in gates):
        verdict = "PASS"
    else:
        verdict = "FAIL"

    diagnostics = {
        "n_units": float(n),
        "n_pairs": float(n_pairs),
        "real_structure_score": real_score,
        "structure_score_std_over_seeds": float(np.std(stab)),
        "mean_order_effect": mean_oe,
        "effective_rank": eff_rank,
    }
    return StageAResult(verdict=verdict, gates=gates, warnings=warnings,
                        diagnostics=diagnostics)
