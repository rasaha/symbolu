"""D0'.1 — adversarial structural-specificity test (STRUCTURAL ONLY).

Is the frozen Stage A operator algebra (D0' result) genuinely SPECIFIC to the
Symbol-U feature chart, or does comparable structure appear under alternative
feature assignments? Operators are built read-only through the frozen
constructor ``feature_operators(F) = {expm(sum_j f_{sigma,j} G_j)}``; only the
feature matrix ``F`` is replaced by null ensembles. The SAME D0' statistics are
computed (no new metrics invented).

Burden of proof is on Symbol-U. No semantics, no Stage A modification, no new
theory. Stage A code is loaded read-only by file path (package init / torch
bypassed).
"""
from __future__ import annotations

import numpy as np

from operator_algebra import analyze_family


# ---- read-only frozen Stage A constructor ---------------------------------
def load_frozen():
    """Return (units, F_real, feature_operators_fn, s0). Read-only."""
    import importlib.util
    from pathlib import Path
    sv1 = Path(__file__).resolve().parents[2] / "symbolu_neural" / "structural_v1"

    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    features = _load("sv1_features", sv1 / "features.py")
    operators = _load("sv1_operators", sv1 / "operators.py")
    F = features.feature_matrix()
    s0 = np.array([1.0, 0.0, 0.0, 0.0]); s0 /= np.linalg.norm(s0)
    return list(features.UNITS), F, operators.feature_operators, s0


def _clip(F):
    return np.clip(F, -1.0, 1.0)


# ---- null feature-matrix ensembles ----------------------------------------
def null_A_permute_rows(F, rng):
    """Permute unit->feature-vector assignment (rows). Preserves the multiset of
    feature vectors exactly. NOTE: the operator SET is invariant under this, so
    set-level statistics are degenerate (reported plainly)."""
    return F[rng.permutation(F.shape[0])]


def null_B_independent_global(F, rng):
    """Each entry i.i.d. from the pooled global distribution of F's values."""
    pool = F.ravel()
    return _clip(rng.choice(pool, size=F.shape, replace=True))


def null_C_preserve_norms(F, rng):
    """Preserve each unit's feature-vector norm; randomize orientation."""
    out = np.zeros_like(F)
    for i, row in enumerate(F):
        nrm = np.linalg.norm(row)
        v = rng.standard_normal(F.shape[1])
        v = v / (np.linalg.norm(v) + 1e-12) * nrm
        out[i] = v
    return _clip(out)


def null_D_preserve_cosines(F, rng):
    """Preserve ALL pairwise cosine similarities + norms by a random rotation of
    the feature configuration (F @ R^T, R orthogonal)."""
    d = F.shape[1]
    Q, R = np.linalg.qr(rng.standard_normal((d, d)))
    Q = Q @ np.diag(np.sign(np.diag(R)) + (np.diag(R) == 0))
    return _clip(F @ Q.T)


def null_E_maxent_first_order(F, rng):
    """Per-column resample with replacement: preserves each column's marginal
    (first-order) statistics, independent across columns."""
    out = np.zeros_like(F)
    for j in range(F.shape[1]):
        out[:, j] = rng.choice(F[:, j], size=F.shape[0], replace=True)
    return _clip(out)


NULLS = {
    "A_permute_rows": null_A_permute_rows,
    "B_independent_global": null_B_independent_global,
    "C_preserve_norms": null_C_preserve_norms,
    "D_preserve_cosines": null_D_preserve_cosines,
    "E_maxent_first_order": null_E_maxent_first_order,
}


# ---- exact D0' statistic vector (no new metrics) --------------------------
STAT_KEYS = [
    "algebra_dim", "commutator_max", "commutator_median", "commutator_min",
    "n_near_commuting", "abelian_defect_max", "abelian_defect_mean",
    "trace_order_frac", "order_separation_frac", "reachability_rank",
]


def stat_vector(ops, s0) -> dict:
    rep = analyze_family("x", ops, s0=s0)
    c = rep.noncommutativity; a = rep.abelianity
    return {
        "algebra_dim": float(rep.algebra["final_dim"]),
        "commutator_max": c["normalized_commutator_norm"]["max"],
        "commutator_median": c["normalized_commutator_norm"]["median"],
        "commutator_min": c["normalized_commutator_norm"]["min"],
        "n_near_commuting": float(c["n_near_commuting_pairs"]),
        "abelian_defect_max": a["offdiag_defect"]["max"],
        "abelian_defect_mean": a["offdiag_defect"]["mean"],
        "trace_order_frac": rep.trace_order["frac_order_sensitive"],
        "order_separation_frac": rep.reachability["order_separation_frac"],
        "reachability_rank": float(rep.reachability["reachability_rank"]),
    }


# ---- null sampling + comparison -------------------------------------------
def sample_null(name, F_real, feature_operators, s0, n_samples, seed) -> dict:
    rng = np.random.default_rng(seed)
    gen = NULLS[name]
    rows = {k: [] for k in STAT_KEYS}
    for _ in range(n_samples):
        F_null = gen(F_real, rng)
        ops = feature_operators(F_null)
        sv = stat_vector(ops, s0)
        for k in STAT_KEYS:
            rows[k].append(sv[k])
    return {k: np.array(v) for k, v in rows.items()}


def compare(stage_vec: dict, null_arrays: dict) -> dict:
    """Per-statistic: mean/std of null, percentile of Stage A, two-sided p."""
    out = {}
    for k in STAT_KEYS:
        null = null_arrays[k]; x = stage_vec[k]
        n = null.size
        frac_ge = float(np.mean(null >= x)); frac_le = float(np.mean(null <= x))
        p_two = float(min(1.0, 2.0 * min(frac_ge, frac_le)))
        pctl = float(np.mean(null < x) * 100.0)
        out[k] = {"stage": float(x), "null_mean": float(null.mean()),
                  "null_std": float(null.std()), "percentile": pctl,
                  "p_two_sided": p_two,
                  "spread_zero": bool(null.std() < 1e-12)}
    return out
