"""Tests for the shared experiments infrastructure (deterministic + property).

    python3 experiments/common/test_common.py
"""
from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import config, repro, stats          # noqa: E402
from common.report import ReportBuilder          # noqa: E402


def _check(name: str, ok: bool) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# ---- stats ----
def test_rng_deterministic() -> None:
    a = stats.rng(7).standard_normal(5)
    b = stats.rng(7).standard_normal(5)
    _check("rng deterministic under fixed seed", np.array_equal(a, b))


def test_numerical_rank() -> None:
    _check("rank(I4)=4", stats.numerical_rank(np.eye(4)) == 4)
    _check("rank(0)=0", stats.numerical_rank(np.zeros((3, 3))) == 0)


def test_random_orthogonal_is_orthogonal_and_deterministic() -> None:
    a = stats.random_orthogonal_family(4, 3, seed=1)
    b = stats.random_orthogonal_family(4, 3, seed=1)
    _check("random orthogonal deterministic", all(np.array_equal(x, y) for x, y in zip(a, b)))
    _check("random orthogonal: QᵀQ=I",
           all(np.allclose(Q.T @ Q, np.eye(3), atol=1e-10) for Q in a))


def test_ridge_recovers_linear_signal() -> None:
    g = stats.rng(0)
    X = g.standard_normal((200, 4)); beta = g.standard_normal(4)
    y = X @ beta + 0.01 * g.standard_normal(200)
    _check("ridge OOF R^2 high on clean linear signal",
           stats.ridge_oof_r2(X, y, seed=0) > 0.95)
    yn = g.standard_normal(200)
    _check("ridge OOF R^2 ~0 on pure noise", stats.ridge_oof_r2(X, yn, seed=0) < 0.2)


def test_shuffle_preserves_multiset() -> None:
    seqs = [[1, 2, 2, 3], [0, 0, 1]]
    out = stats.shuffle_within(seqs, stats.rng(3))
    _check("shuffle preserves per-sequence counts",
           all(sorted(a) == sorted(b) for a, b in zip(seqs, out)))


def test_percentile_gate_and_pvalue() -> None:
    null = list(range(100))
    g = stats.percentile_gate(98, null, 95)
    _check("percentile gate exceeds", g["exceeds"])
    _check("percentile gate not-exceeds", not stats.percentile_gate(50, null, 95)["exceeds"])
    _check("perm p-value small for large observed",
           stats.permutation_pvalue(1e9, null) < 0.05)


def test_bootstrap_ci_excludes_zero() -> None:
    vals = list(np.full(50, 0.5) + 0.01 * stats.rng(1).standard_normal(50))
    ci = stats.bootstrap_ci(vals, n_boot=500, seed=1)
    _check("bootstrap CI excludes zero for positive mean", ci["excludes_zero"])


def test_bh_fdr_monotone() -> None:
    rej = stats.benjamini_hochberg([0.001, 0.04, 0.5, 0.9], q=0.05)
    _check("BH rejects smallest p", bool(rej[0]))
    _check("BH does not reject largest p", not bool(rej[-1]))


# ---- repro ----
def test_metadata_fields() -> None:
    m = repro.collect_metadata(config={"a": 1}, seed=5, runtime_s=1.23)
    for key in ("git_hash", "python", "numpy", "seed", "runtime_s", "config"):
        _check(f"metadata has {key}", key in m)
    _check("metadata seed preserved", m["seed"] == 5)


def test_sha256_stable() -> None:
    _check("sha256_text deterministic",
           repro.sha256_text("abc") == repro.sha256_text("abc"))


# ---- report ----
def test_report_builder() -> None:
    rb = ReportBuilder("T", "caveat")
    rb.section("S").table(["a", "b"], [(1, 2)]).decision("X")
    md = rb.build()
    _check("report has title", md.startswith("# T"))
    _check("report has decision", "DECISION: X" in md)
    _check("report has table", "| a | b |" in md)


# ---- config ----
def test_config_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "cfg.json"
        cfg = config.HarnessConfig(repeats=7, n_ref=123)
        config.save_config(cfg, p)
        loaded = config.load_config(config.HarnessConfig, p)
        _check("config roundtrip repeats", loaded.repeats == 7)
        _check("config roundtrip n_ref", loaded.n_ref == 123)
        _check("config version recorded", loaded.version == config.CONFIG_VERSION)
    _check("config defaults when file absent",
           config.load_config(config.D0Config, Path(d) / "missing.json").rank_tol == 1e-9)


def main() -> None:
    print("common infrastructure tests\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll common-infrastructure tests passed.")


if __name__ == "__main__":
    main()
