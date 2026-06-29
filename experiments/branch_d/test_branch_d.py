"""Control tests for Branch D loaders + incremental test (inline fixtures; no network).

    python3 experiments/branch_d/test_branch_d.py
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import stats                              # noqa: E402
from data import build_dataset, parse_cmudict        # noqa: E402
from run_branch_d import incremental                 # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _fixtures(d: Path):
    (d / "cmudict.dict").write_text(
        "bat B AE1 T\ntab T AE1 B\ntabby T AE1 B IY0\nbat(2) B AE2 T\n")
    # PanPhon-like: ipa, two features
    (d / "ipa_all.csv").write_text(
        "ipa,son,cons\nb,-1,1\næ,1,-1\nt,-1,1\ni,1,-1\n")
    (d / "warriner.csv").write_text(
        "X,Word,V.Mean.Sum,V.SD.Sum,V.Rat.Sum,A.Mean.Sum,A.SD.Sum,A.Rat.Sum,D.Mean.Sum\n"
        "1,bat,5.0,1,1,4.0,1,1,5.0\n2,tab,3.0,1,1,4.0,1,1,5.0\n3,tabby,6.0,1,1,4.0,1,1,5.0\n")


def test_parse_cmudict():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t); _fixtures(d)
        pron = parse_cmudict(d / "cmudict.dict")
        _check("cmudict: bat parsed stress-stripped", pron["bat"] == ["B", "AE", "T"])
        _check("cmudict: variant bat(2) skipped", list(pron["bat"]) == ["B", "AE", "T"])
        _check("cmudict: tab present", pron["tab"] == ["T", "AE", "B"])


def test_build_dataset_join():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t); _fixtures(d)
        ds = build_dataset(d / "cmudict.dict", d / "ipa_all.csv", d / "warriner.csv")
        _check("join: 3 words", ds["n"] == 3)
        _check("E_max width = 39 ARPABET", ds["E_max"].shape[1] == 39)
        _check("PHON width = 2 feats + 2 length", ds["PHON"].shape[1] == 4)
        # bat vs tab share identical phoneme multiset {B,AE,T} -> identical E_max rows
        wi = {w: i for i, w in enumerate(ds["words"])}
        _check("bat & tab have identical phoneme counts (order-blind E_max)",
               np.array_equal(ds["E_max"][wi["bat"]], ds["E_max"][wi["tab"]]))


def test_incremental_detects_planted_signal():
    rng = stats.rng(0)
    n, p = 1000, 6
    BASE = rng.standard_normal((n, 3))
    EXTRA = rng.integers(0, 4, size=(n, p)).astype(float)
    beta = rng.standard_normal(p)
    y = EXTRA @ beta + 0.3 * rng.standard_normal(n)     # signal lives in EXTRA, not BASE
    r = incremental(BASE, EXTRA, y, K=80, seed=1)
    _check("planted: ΔR² > null p95", r["delta"] > r["null_p95"])
    _check("planted: partial r large", r["partial_r"] > 0.3)
    _check("planted: perm p small", r["p"] < 0.05)


def test_incremental_null_on_noise():
    rng = stats.rng(2)
    n, p = 1000, 6
    BASE = rng.standard_normal((n, 3))
    EXTRA = rng.integers(0, 4, size=(n, p)).astype(float)
    y = rng.standard_normal(n)                          # no relation to EXTRA
    r = incremental(BASE, EXTRA, y, K=80, seed=2)
    _check("noise: ΔR² not above null p95", r["delta"] <= r["null_p95"] + 1e-9)
    _check("noise: perm p not significant", r["p"] >= 0.05)


def test_determinism():
    rng = stats.rng(5); BASE = rng.standard_normal((400, 3))
    EXTRA = rng.integers(0, 3, size=(400, 5)).astype(float)
    y = EXTRA @ rng.standard_normal(5) + rng.standard_normal(400)
    a = incremental(BASE, EXTRA, y, K=40, seed=7)
    b = incremental(BASE, EXTRA, y, K=40, seed=7)
    _check("determinism: identical delta", a["delta"] == b["delta"])


def main():
    print("Branch D control tests (inline fixtures; no network)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Branch D control tests passed.")


if __name__ == "__main__":
    main()
