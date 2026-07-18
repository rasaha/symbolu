"""Synthetic tests for the B0 machinery (no real data, no network, no B0 result).

Covers (PREREG step 6):
  - constructed T aligns with P when designed to,
  - scrambled-table null behaves correctly (centered ~0; signal beats it),
  - partial Mantel REMOVES alignment when T only tracks the control C,
  - partial Mantel PRESERVES alignment when T carries signal beyond C,
  - permutation p-value sanity (signal → small p; noise → large p),
  - deterministic seeds,
  - no real B0 result emitted (runner NOT_RUN; real T-vs-P alignment never computed).
Plus shape/symmetry smoke tests for the real-inventory P/C/T scaffolds (build only).

    python3 experiments/varna_phonetic_alignment/test_varna_phonetic_alignment.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import matrices as MX            # noqa: E402
import phonetics as PH           # noqa: E402
import control as CTL            # noqa: E402
import table_structure as TS     # noqa: E402
import run_b0 as RUN             # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _sym(g, n):
    """Symmetric, zero-diagonal distance-like matrix from gaussian noise."""
    A = g.standard_normal((n, n))
    A = (A + A.T) / 2.0
    np.fill_diagonal(A, 0.0)
    return A


# ---- shared synthetic latent construction (C-structure + beyond-C detail) ----
def _components(seed=0, n=20):
    g = MX.stats.rng(seed)
    base = _sym(g, n)         # the control (class) structure → C
    extra = _sym(g, n)        # phonetic detail beyond the class grid
    na = _sym(g, n); nb = _sym(g, n)
    C = base.copy()
    P = 1.0 * base + 1.0 * extra
    T_onlyC = base + 0.05 * na               # tracks ONLY C
    T_signal = base + extra + 0.05 * nb       # tracks C AND the beyond-C part of P
    return C, P, T_onlyC, T_signal


# ----------------------------------------------------------------- tests -------
def test_constructed_T_aligns_with_P():
    g = MX.stats.rng(1)
    X = g.standard_normal((18, 6))
    T0 = TS.table_dissimilarity(X, metric="cosine")
    P = T0 + 0.02 * _sym(g, 18)               # phonetics ≈ aligned with the table
    r = MX.mantel_r(T0, P)
    _check("aligned: mantel_r high when T designed to track P", r > 0.7)
    # an unrelated P gives near-zero alignment
    P_un = MX.np.abs(_sym(g, 18))
    _check("aligned: mantel_r ~0 for unrelated P", abs(MX.mantel_r(T0, P_un)) < 0.3)


def test_scrambled_null_behaves():
    g = MX.stats.rng(2)
    X = g.standard_normal((16, 5))
    T0 = TS.table_dissimilarity(X, metric="cosine")
    P = T0 + 0.02 * _sym(g, 16)
    build_T = TS.scramble_builder(X, metric="cosine")
    null = MX.scrambled_null(build_T, P, n=300, seed=7)
    observed = MX.mantel_r(T0, P)
    gate = MX.percentile_gate(observed, null, pctl=95)
    _check("scramble: null centered near 0", abs(float(np.mean(null))) < 0.15)
    _check("scramble: observed beats 95th pct", gate["exceeds"])
    # negative control: unrelated P does NOT beat its scramble null
    P_un = MX.np.abs(_sym(g, 16))
    null_un = MX.scrambled_null(build_T, P_un, n=300, seed=7)
    obs_un = MX.mantel_r(T0, P_un)
    p_un = MX.permutation_pvalue(obs_un, null_un)
    _check("scramble: unrelated P → not significant", p_un > 0.05)


def test_partial_mantel_removes_C_only_alignment():
    C, P, T_onlyC, _ = _components(seed=3)
    raw = MX.mantel_r(T_onlyC, P)
    part = MX.partial_mantel_r(T_onlyC, P, C)
    _check("C-only: raw Mantel inflated by shared C", raw > 0.3)
    _check("C-only: partial Mantel collapses to ~0", abs(part) < 0.15)


def test_partial_mantel_preserves_signal_beyond_C():
    C, P, _, T_signal = _components(seed=4)
    raw = MX.mantel_r(T_signal, P)
    part = MX.partial_mantel_r(T_signal, P, C)
    _check("signal: raw Mantel positive", raw > 0.3)
    _check("signal: partial Mantel stays positive beyond C", part > 0.2)


def test_permutation_pvalue_sanity():
    g = MX.stats.rng(5)
    X = g.standard_normal((16, 5))
    T0 = TS.table_dissimilarity(X, metric="cosine")
    P = T0 + 0.02 * _sym(g, 16)
    null = MX.mantel_permutation(T0, P, n=500, seed=9)
    p_sig = MX.permutation_pvalue(MX.mantel_r(T0, P), null)
    _check("perm: signal → small p", p_sig < 0.05)
    P_un = MX.np.abs(_sym(g, 16))
    null_un = MX.mantel_permutation(T0, P_un, n=500, seed=9)
    p_noise = MX.permutation_pvalue(MX.mantel_r(T0, P_un), null_un)
    _check("perm: noise → large p", p_noise > 0.05)


def test_partial_permutation_and_bootstrap():
    C, P, _, T_signal = _components(seed=6)
    null = MX.mantel_permutation(T_signal, P, C=C, n=400, seed=11)
    p = MX.permutation_pvalue(MX.partial_mantel_r(T_signal, P, C), null)
    _check("partial-perm: beyond-C signal → small p", p < 0.05)
    boot = MX.bootstrap_partial(T_signal, P, C, n_boot=400, seed=12)
    _check("bootstrap: partial Mantel CI excludes zero for real signal", boot["excludes_zero"])
    _check("bootstrap: CI lower > 0 for positive signal", boot["lo"] > 0)


def test_deterministic_seeds():
    C, P, _, T_signal = _components(seed=7)
    a = MX.mantel_permutation(T_signal, P, C=C, n=50, seed=3)
    b = MX.mantel_permutation(T_signal, P, C=C, n=50, seed=3)
    _check("determinism: same seed → identical permutation null", np.allclose(a, b))
    c1 = MX.bootstrap_partial(T_signal, P, C, n_boot=100, seed=4)
    c2 = MX.bootstrap_partial(T_signal, P, C, n_boot=100, seed=4)
    _check("determinism: same seed → identical bootstrap CI",
           c1["lo"] == c2["lo"] and c1["hi"] == c2["hi"])
    d1 = MX.mantel_permutation(T_signal, P, C=C, n=50, seed=99)
    _check("determinism: different seed → different null", not np.allclose(a, d1))


def test_real_inventory_scaffolds_build_only():
    # build the real-inventory P / C / T matrices (shapes only) — NO alignment computed.
    keys, entries = TS.load_table()
    _check("real: 34 consonant varṇas loaded", len(keys) == 34)
    C = CTL.control_matrix(keys)
    _check("real: C is 34×34", C.shape == (34, 34))
    _check("real: C symmetric, zero diag", np.allclose(C, C.T) and np.allclose(np.diag(C), 0))
    _check("real: C values in {0,1,2}", set(np.unique(C)).issubset({0.0, 1.0, 2.0}))
    feats, names, source = PH.load_feature_matrix(keys)
    _check("real: feature source is mock (panphon absent)", source == "mock")
    _check("real: feature matrix is 34×F", feats.shape[0] == 34 and feats.shape[1] == len(names))
    P = PH.dissimilarity(feats, metric="hamming")
    _check("real: P is 34×34 symmetric zero-diag",
           P.shape == (34, 34) and np.allclose(P, P.T) and np.allclose(np.diag(P), 0))
    Xcat = TS.categorical_encoder(keys, entries)
    Tcat = TS.table_dissimilarity(Xcat, metric="cosine")
    _check("real: categorical T is 34×34", Tcat.shape == (34, 34))
    # primary embedding encoder must NOT fabricate vectors without a frozen model
    raised = False
    try:
        TS.embedding_encoder(keys, entries, model=None)
    except NotImplementedError:
        raised = True
    _check("real: embedding encoder refuses without frozen model", raised)


def test_no_real_b0_result_emitted():
    # manifest-driven runner: NOT_RUN on the default frozen manifest (T_embed deferred)
    res = RUN.run()
    _check("runner: NOT_RUN on default manifest", res["status"] == "NOT_RUN")
    _check("runner: NOT_RUN computes no alignment", res["computed_alignment"] is False)
    _check("runner: NOT_RUN emits no verdict", res["verdict"] is None)
    # a missing manifest path also yields NOT_RUN, never a result
    miss = RUN.run(manifest_path="/nonexistent/b0_frozen_artifacts.json")
    _check("runner: missing manifest → NOT_RUN", miss["status"] == "NOT_RUN")
    _check("runner: missing manifest computes no alignment", miss["computed_alignment"] is False)


def main():
    print("varna_phonetic_alignment B0 — synthetic machinery tests (no real result, no fit)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll B0 scaffolding tests passed.")


if __name__ == "__main__":
    main()
