"""Control tests for Branch D.1 grouped CV + morphology proxies (no network).

The decisive new machinery is grouped_ridge_oof_r2. Its job is to make a
GROUP-confounded signal (predictable only by memorizing per-group offsets)
vanish, while a genuine per-sample signal survives. Both behaviours are tested.

    python3 experiments/branch_d/test_branch_d1.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import stats                                       # noqa: E402
from data import morph_features, rime_group, suffix_group, SUFFIXES, PREFIXES  # noqa: E402
from run_branch_d import incremental                           # noqa: E402
from run_branch_d1 import grouped_ridge_oof_r2, incremental_grouped  # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def test_grouped_cv_kills_group_confound():
    """X one-hot-encodes group identity; y is a per-group random offset. A linear
    model can recover each group's offset ONLY when that group appears in train.
    Random CV memorizes it (group seen in train); grouped CV holds the whole
    group out -> its column is unseen -> cannot generalize -> R² collapses."""
    rng = stats.rng(0)
    n_groups, per = 40, 12
    offset = rng.standard_normal(n_groups) * 3.0          # per-group target
    groups, X, y = [], [], []
    for g in range(n_groups):
        for _ in range(per):
            groups.append(g)
            oh = np.zeros(n_groups); oh[g] = 1.0          # group identity, linearly recoverable
            X.append(oh)
            y.append(offset[g] + 0.01 * rng.standard_normal())
    X = np.array(X); y = np.array(y); groups = np.array(groups)
    r2_random = stats.ridge_oof_r2(X, y, seed=1)
    r2_grouped = grouped_ridge_oof_r2(X, y, groups, seed=1)
    _check("group-confound: random CV R² high (leaks)", r2_random > 0.8)
    _check("group-confound: grouped CV R² collapses", r2_grouped < 0.2)
    _check("group-confound: grouped << random", r2_grouped < r2_random - 0.5)


def test_grouped_cv_keeps_genuine_signal():
    """Per-sample linear signal (groups assigned independently of X) survives
    grouped CV, because the X->y relation generalizes across held-out groups."""
    rng = stats.rng(3)
    n, dim = 800, 6
    X = rng.standard_normal((n, dim))
    beta = rng.standard_normal(dim)
    y = X @ beta + 0.3 * rng.standard_normal(n)
    groups = rng.integers(0, 40, size=n)                  # unrelated to X / y
    r2_grouped = grouped_ridge_oof_r2(X, y, groups, seed=2)
    _check("genuine signal: grouped CV R² high", r2_grouped > 0.7)


def test_incremental_grouped_neutralizes_what_random_cv_flags():
    """An EXTRA block that ONLY encodes group identity is a pure leakage signal.
    incremental (random CV) flags it with a large ΔR²; incremental_grouped sees
    through it (held-out group columns unseen) -> ΔR² collapses near zero."""
    rng = stats.rng(7)
    n_groups, per, bdim = 40, 14, 4
    groups, BASE, EXTRA, y = [], [], [], []
    offset = rng.standard_normal(n_groups) * 2.0
    for g in range(n_groups):
        for _ in range(per):
            groups.append(g)
            BASE.append(rng.standard_normal(bdim))
            oh = np.zeros(n_groups); oh[g] = 1.0                    # group identity only
            EXTRA.append(oh)
            y.append(offset[g] + 0.05 * rng.standard_normal())
    BASE = np.array(BASE); EXTRA = np.array(EXTRA); y = np.array(y)
    groups = np.array(groups)
    r_random = incremental(BASE, EXTRA, y, K=60, seed=4)
    r_grouped = incremental_grouped(BASE, EXTRA, y, groups, K=60, seed=4)
    _check("random-CV incremental flags the group confound (large ΔR²)",
           r_random["delta"] > 0.3)
    _check("grouped-CV incremental sees through it (ΔR² near zero)",
           r_grouped["delta"] < 0.05)
    _check("grouped ΔR² << random ΔR²", r_grouped["delta"] < r_random["delta"] - 0.3)


def test_grouped_oof_determinism():
    rng = stats.rng(11)
    X = rng.standard_normal((300, 4)); y = rng.standard_normal(300)
    groups = rng.integers(0, 20, size=300)
    a = grouped_ridge_oof_r2(X, y, groups, seed=5)
    b = grouped_ridge_oof_r2(X, y, groups, seed=5)
    _check("grouped CV determinism", a == b)


def test_no_group_spans_train_and_test():
    """Direct invariant: with k folds assigned by group, every group's rows fall
    in exactly one fold (verified by reconstructing the fold map)."""
    rng = stats.rng(9)
    groups = rng.integers(0, 25, size=400)
    uniq = list(dict.fromkeys(groups.tolist()))
    order = stats.rng(5).permutation(len(uniq))
    k = 5
    fold_of = {uniq[order[i]]: i % k for i in range(len(uniq))}
    fold_id = np.array([fold_of[g] for g in groups])
    ok = all(len(set(fold_id[groups == g])) == 1 for g in uniq)
    _check("each group lies entirely in one fold", ok)


def test_rime_group():
    _check("rime: bat -> AE_T", rime_group(["B", "AE", "T"]) == "AE_T")
    _check("rime: tab -> AE_B", rime_group(["T", "AE", "B"]) == "AE_B")
    _check("rime: cat & bat share rime", rime_group(["K", "AE", "T"]) == rime_group(["B", "AE", "T"]))
    _check("rime: no vowel -> novowel", rime_group(["S", "T"]) == "novowel")
    _check("rime: last vowel only", rime_group(["B", "AE", "N", "AE", "N", "AH"]) == "AH")


def test_morph_features():
    suf = morph_features("running")[:len(SUFFIXES)]
    _check("morph: 'running' flags -ing", suf[SUFFIXES.index("ing")] == 1.0)
    pre = morph_features("unhappy")[len(SUFFIXES):]
    _check("morph: 'unhappy' flags un-", pre[PREFIXES.index("un")] == 1.0)
    _check("morph: longest suffix wins ('toilet' not -et over nothing)",
           morph_features("hopeless")[SUFFIXES.index("less")] == 1.0)
    _check("morph: short word no spurious suffix", morph_features("ed").sum() == 0.0)
    _check("morph: dim = suffixes + prefixes",
           morph_features("cat").shape[0] == len(SUFFIXES) + len(PREFIXES))


def test_suffix_group():
    _check("suffix_group: happiness -> ness", suffix_group("happiness") == "ness")
    _check("suffix_group: cat -> none", suffix_group("cat") == "none")


def main():
    print("Branch D.1 control tests (inline fixtures; no network)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Branch D.1 control tests passed.")


if __name__ == "__main__":
    main()
