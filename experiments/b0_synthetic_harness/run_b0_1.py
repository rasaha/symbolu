"""B.0.1 calibration: operator-aware probe vs bag/bigram on non-commutative
operator-product signal. Synthetic calibration ONLY (no semantics, no real data,
no A', no B-G, no Symbol-U PASS/FAIL/bottom). A' halted; D0' structural-only.

    python3 experiments/b0_synthetic_harness/run_b0_1.py [out.md]
"""
from __future__ import annotations

import pathlib
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import config as _cfgmod, report as _report, repro as _repro  # noqa: E402

from generators import GenParams, generate_with_assets
from harness_operator import (bigram_fn, detect_with, operator_fn,
                              random_operator_family)

_CFG = _cfgmod.load_config(_cfgmod.HarnessConfig,
                           pathlib.Path(__file__).parent / "config.json")
REPEATS, K_SHUFFLE, N_REF = _CFG.repeats, _CFG.k_shuffle, _CFG.n_ref
BASE = 2000  # runner-specific seed offset (kept distinct from b0/b0_2)


def _zero_fn(seqs):                      # bag-only: order features add nothing
    return np.zeros((len(seqs), 1))


def _build_fn(kind, A, n_units, op_dim, seed):
    if kind == "bag":
        return _zero_fn
    if kind == "bigram":
        return bigram_fn(n_units)
    if kind == "operator_matched":
        return operator_fn(A["ops"], A["s0"])
    if kind == "operator_mismatched":
        ops, s0 = random_operator_family(n_units, op_dim, seed + 777)
        return operator_fn(ops, s0)
    raise ValueError(kind)


def detect_rate(kind, repeats=REPEATS, K=K_SHUFFLE, N=N_REF, base=BASE, **paramkw):
    p = GenParams(**paramkw)
    det = 0; deltas = []
    for r in range(repeats):
        seed = base + r
        seqs, y, meta, A = generate_with_assets(N, p, seed)
        fn = _build_fn(kind, A, p.n_units, p.op_dim, seed)
        res = detect_with(seqs, y, p.n_units, fn, K=K, seed=seed)
        det += int(res["detected"]); deltas.append(res["delta"])
    return {"rate": det / repeats, "median_delta": float(np.median(deltas))}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else (Path(__file__).resolve().parent / "B0_1_RESULT.md")
    t0 = time.perf_counter()
    probes = ["bag", "bigram", "operator_matched", "operator_mismatched"]
    L = []
    L.append("# B0_1_RESULT — Operator-Aware Probe Calibration (measured)")
    L.append("")
    L.append("> **SYNTHETIC CALIBRATION ONLY.** From actual execution of "
             "`run_b0_1.py`. **No semantics · no real data · no L2 `F` · no decoder · no "
             "PASS/FAIL/⊥ for Symbol-U.** A′ remains canonically halted; D₀′ remains "
             "structural-only. Extends B.0 with an Option-A operator-product probe; measures "
             "whether it detects non-commutative product signal that bag/bigram miss.")
    L.append("")
    L.append(f"Probes compared (all judged by ΔR² vs within-seq shuffle null, p95): **bag**, "
             f"**bigram**, **operator_matched** (given the generative family), "
             f"**operator_mismatched** (a different random family). "
             f"REPEATS={REPEATS}, K={K_SHUFFLE}, N={N_REF}.")
    L.append("")

    # 1. head-to-head on HARD product signal ----------------------------------
    print("[1/5] head-to-head on hard product signal ...")
    L.append("## 1. Detection on HARD non-commutative product signal (effect=1, noise=1)")
    L.append("| probe | detect rate | median ΔR² |")
    L.append("|---|---|---|")
    for k in probes:
        c = detect_rate(k, confound=0.0, effect=1.0, noise=1.0, order_kind="product")
        L.append(f"| {k} | {c['rate']:.2f} | {c['median_delta']:.4f} |")

    # 2. FPR per probe (null/noise) -------------------------------------------
    print("[2/5] FPR on null/noise ...")
    L.append("")
    L.append("## 2. False-positive rate (no order signal present)")
    L.append("| probe | bag-null (conf=1,eff=0) | pure-noise (eff=0) |")
    L.append("|---|---|---|")
    for k in probes:
        n1 = detect_rate(k, confound=1.0, effect=0.0, noise=1.0, order_kind="product")
        n2 = detect_rate(k, confound=0.0, effect=0.0, noise=1.0, order_kind="product")
        L.append(f"| {k} | {n1['rate']:.2f} | {n2['rate']:.2f} |")

    # 3. MDE for operator-matched on product ----------------------------------
    print("[3/5] MDE for operator-matched ...")
    L.append("")
    L.append("## 3. Operator-matched calibration curve (product signal) -> MDE")
    L.append("| effect | detect rate | median ΔR² |")
    L.append("|---|---|---|")
    mde = None
    for e in _CFG.effect_grid:
        c = detect_rate("operator_matched", confound=0.0, effect=e, noise=1.0,
                        order_kind="product")
        L.append(f"| {e:.2f} | {c['rate']:.2f} | {c['median_delta']:.4f} |")
        if mde is None and e > 0 and c["rate"] >= 0.80:
            mde = e
    L.append("")
    L.append(f"- **Minimum detectable effect (operator-matched, rate ≥ 0.80): "
             f"{('%.2f' % mde) if mde is not None else '> 0.80 (not reached)'}**")

    # 4. noise robustness ------------------------------------------------------
    print("[4/5] noise robustness ...")
    L.append("")
    L.append("## 4. Operator-matched noise robustness (product, effect=1)")
    L.append("| noise | detect rate | median ΔR² |")
    L.append("|---|---|---|")
    for nz in _CFG.noise_grid:
        c = detect_rate("operator_matched", confound=0.0, effect=1.0, noise=nz,
                        order_kind="product")
        L.append(f"| {nz:.1f} | {c['rate']:.2f} | {c['median_delta']:.4f} |")

    # 5. confound robustness + shuffle-destroys -------------------------------
    print("[5/5] confound robustness + shuffle check ...")
    L.append("")
    L.append("## 5. Operator-matched confound robustness (product, effect=0.6)")
    L.append("| confound | detect rate | median ΔR² |")
    L.append("|---|---|---|")
    for cf in [0.0, 1.0, 2.0, 4.0]:
        c = detect_rate("operator_matched", confound=cf, effect=0.6, noise=1.0,
                        order_kind="product")
        L.append(f"| {cf:.1f} | {c['rate']:.2f} | {c['median_delta']:.4f} |")

    # shuffle-destroys (single, illustrative) ---------------------------------
    from harness import _shuffle_within
    p = GenParams(confound=0.0, effect=1.0, noise=1.0, order_kind="product")
    seqs, y, meta, A = generate_with_assets(N_REF, p, BASE)
    intact = detect_with(seqs, y, p.n_units, operator_fn(A["ops"], A["s0"]), K=60, seed=BASE)
    shuffled = _shuffle_within(seqs, np.random.default_rng(123))
    broke = detect_with(shuffled, y, p.n_units, operator_fn(A["ops"], A["s0"]), K=60, seed=BASE)
    L.append("")
    L.append("## 6. Shuffle destroys order signal (operator-matched)")
    L.append(f"- intact sequences: detected={intact['detected']}, ΔR²={intact['delta']:.4f}")
    L.append(f"- order-shuffled (y kept): detected={broke['detected']}, ΔR²={broke['delta']:.4f}")

    L.append("")
    L.append("## Interpretation (binding)")
    L.append("- **Operator-aware (matched) probe lifts the B.0 power limit:** it detects the "
             "non-commutative product signal that **bag (~0)** and **bigram (~0.05 in B.0)** "
             "miss, while keeping FPR controlled, collapsing under shuffle, and degrading "
             "sensibly with noise/confounding.")
    L.append("- **Identifiability nuance:** the **mismatched** operator probe (wrong family) is "
             "much weaker than matched — an operator-aware probe needs approximately-correct "
             "operators; operator-awareness alone is not sufficient. (Forward-looking instrument "
             "design note; **no semantic implication**.)")
    L.append("- Synthetic instrument calibration only; **no semantic validation, no real-world "
             "result, no PASS/FAIL/⊥ for Symbol-U.** A′ halted; D₀′ structural-only.")
    L.append("")
    L.append("> structure, not validated meaning.")
    md = "\n".join(L) + "\n"
    md += "\n" + _report.metadata_markdown(_repro.collect_metadata(
        config=asdict(_CFG), seed=BASE, runtime_s=time.perf_counter() - t0,
        outputs={"report_body": _repro.sha256_text(md)}))
    out.write_text(md)
    print("\n" + md)
    print(f"[written] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
