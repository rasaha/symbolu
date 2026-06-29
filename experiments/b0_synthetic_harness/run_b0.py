"""Run the B.0 synthetic harness calibration sweep; write a measured report.

Synthetic calibration ONLY: no semantics, no real-world data, no Symbol-U
PASS/FAIL/bottom. A' remains halted; D0' remains structural-only.

    python3 experiments/b0_synthetic_harness/run_b0.py [out.md]
"""
from __future__ import annotations

import pathlib
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import config as _cfgmod, report as _report, repro as _repro  # noqa: E402
from generators import GenParams, generate  # noqa: E402
from harness import (MIN_DELTA_R2, SHUFFLE_PCTL, decision_label, detect_order)  # noqa: E402

_CFG = _cfgmod.load_config(_cfgmod.HarnessConfig,
                           pathlib.Path(__file__).parent / "config.json")
REPEATS, K_SHUFFLE, N_REF = _CFG.repeats, _CFG.k_shuffle, _CFG.n_ref
BASE = _CFG.base_seed


def run_cell(repeats=REPEATS, K=K_SHUFFLE, N=N_REF, base_seed=BASE, **paramkw):
    p = GenParams(**paramkw)
    labels, deltas, det = Counter(), [], 0
    op_present = None
    for r in range(repeats):
        seed = base_seed + r
        seqs, y, meta = generate(N, p, seed)
        op_present = meta["order_present"]
        res = detect_order(seqs, y, p.n_units, K=K, seed=seed)
        labels[decision_label(res, op_present)] += 1
        deltas.append(res["delta"])
        det += int(res["detected"])
    return {"detect_rate": det / repeats, "labels": dict(labels),
            "median_delta": float(np.median(deltas)), "order_present": op_present}


def fmt_labels(d: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(d.items()))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else (Path(__file__).resolve().parent / "B0_RESULT.md")
    t0 = time.perf_counter()
    L = []
    L.append("# B0_RESULT — Synthetic Harness Calibration (measured)")
    L.append("")
    L.append("> **SYNTHETIC CALIBRATION ONLY.** Generated from actual execution of "
             "`experiments/b0_synthetic_harness/run_b0.py`. **No semantics · no real-world data · "
             "no L2 `F` · no decoder · no PASS/FAIL/⊥ for Symbol-U.** A′ remains canonically "
             "halted; D₀′ remains structural-only. This measures whether the probe/baseline/⊥ "
             "machinery detects PLANTED synthetic order signal and returns null on planted-null "
             "data — instrument readiness, not a finding about Symbol-U.")
    L.append("")
    L.append(f"Probe: ridge OOF R²; order statistic = ΔR²(bag+bigram over bag) vs a "
             f"within-sequence shuffle null (p{SHUFFLE_PCTL}); detect iff ΔR²>null-p{SHUFFLE_PCTL} "
             f"and ΔR²>{MIN_DELTA_R2}. REPEATS={REPEATS}, K_shuffle={K_SHUFFLE}, N_ref={N_REF}.")
    L.append("")

    # 1. confusion across named regimes ---------------------------------------
    print("[1/6] confusion across regimes ...")
    L.append("## 1. Decision confusion across regimes")
    L.append("| regime | order present | detect rate | label counts |")
    L.append("|---|---|---|---|")
    regimes = {
        "null_bag (confound=1, effect=0)": dict(confound=1.0, effect=0.0),
        "order (effect=1)":                dict(confound=0.0, effect=1.0),
        "weak (effect=0.2)":               dict(confound=0.0, effect=0.2),
        "confounded (confound=1.5,eff=0.4)": dict(confound=1.5, effect=0.4),
        "pure_noise (effect=0)":           dict(confound=0.0, effect=0.0),
    }
    for name, kw in regimes.items():
        c = run_cell(**kw)
        L.append(f"| {name} | {c['order_present']} | {c['detect_rate']:.2f} | {fmt_labels(c['labels'])} |")

    # 2. TPR / FPR / FNR -------------------------------------------------------
    print("[2/6] TPR/FPR/FNR ...")
    tp = run_cell(confound=0.0, effect=0.5)            # order present, moderate
    fp1 = run_cell(confound=1.0, effect=0.0)           # bag-only null
    fp2 = run_cell(confound=0.0, effect=0.0)           # pure noise
    tpr = tp["detect_rate"]
    fpr = (fp1["detect_rate"] + fp2["detect_rate"]) / 2
    L.append("")
    L.append("## 2. Operating point (effect=0.5 for TPR; effect=0 for FPR)")
    L.append(f"- **TPR** (order present, effect=0.5): **{tpr:.2f}**")
    L.append(f"- **FNR**: **{1 - tpr:.2f}**")
    L.append(f"- **FPR** (mean of bag-null and pure-noise): **{fpr:.2f}** "
             f"(bag-null {fp1['detect_rate']:.2f}, pure-noise {fp2['detect_rate']:.2f})")
    L.append(f"  - target FPR by construction ≈ {(100 - SHUFFLE_PCTL)/100:.2f} (1 - p{SHUFFLE_PCTL})")

    # 3. calibration curve over effect size -> MDE ----------------------------
    print("[3/6] calibration curve over effect size ...")
    effects = _CFG.effect_grid
    L.append("")
    L.append("## 3. Calibration curve (detection rate vs effect size)")
    L.append("| effect | detect rate | median ΔR² |")
    L.append("|---|---|---|")
    mde = None
    for e in effects:
        c = run_cell(confound=0.0, effect=e)
        L.append(f"| {e:.2f} | {c['detect_rate']:.2f} | {c['median_delta']:.4f} |")
        if mde is None and e > 0 and c["detect_rate"] >= 0.80:
            mde = e
    L.append("")
    L.append(f"- **Minimum detectable effect (detection rate ≥ 0.80): "
             f"{('%.2f' % mde) if mde is not None else '> %.2f (not reached in grid)' % effects[-1]}**")

    # 4. sample-size sweep -----------------------------------------------------
    print("[4/6] sample-size sweep ...")
    L.append("")
    L.append("## 4. Sample-size sweep (effect=0.3)")
    L.append("| N | detect rate | median ΔR² |")
    L.append("|---|---|---|")
    for N in _CFG.sample_grid:
        c = run_cell(N=N, confound=0.0, effect=0.3)
        L.append(f"| {N} | {c['detect_rate']:.2f} | {c['median_delta']:.4f} |")

    # 5. noise sweep -----------------------------------------------------------
    print("[5/6] noise sweep ...")
    L.append("")
    L.append("## 5. Noise sweep (effect=0.5)")
    L.append("| noise | detect rate | median ΔR² |")
    L.append("|---|---|---|")
    for nz in _CFG.noise_grid:
        c = run_cell(confound=0.0, effect=0.5, noise=nz)
        L.append(f"| {nz:.1f} | {c['detect_rate']:.2f} | {c['median_delta']:.4f} |")

    # 6. confound sweep + hard (operator-product) case ------------------------
    print("[6/6] confound sweep + hard product case ...")
    L.append("")
    L.append("## 6. Confounding sweep (effect=0.4)")
    L.append("| confound (bag weight) | detect rate | median ΔR² |")
    L.append("|---|---|---|")
    for cf in _CFG.confound_grid:
        c = run_cell(confound=cf, effect=0.4)
        L.append(f"| {cf:.1f} | {c['detect_rate']:.2f} | {c['median_delta']:.4f} |")

    hard = run_cell(confound=0.0, effect=1.0, order_kind="product")
    L.append("")
    L.append("## 7. Probe power limit — HARD case (full non-commutative product)")
    L.append(f"- order_kind='product' (effect=1): detect rate **{hard['detect_rate']:.2f}**, "
             f"median ΔR² {hard['median_delta']:.4f}")
    L.append("- The linear bigram probe under-detects a pure non-commutative operator-product "
             "signal (it cannot linearly represent the full ordered product). Calibration of "
             "matched (bigram) order signal above does NOT extend to arbitrary non-commutative "
             "structure — a documented power limit for any future linear order probe.")

    L.append("")
    L.append("## Interpretation (binding)")
    L.append("- Synthetic instrument calibration only; **no semantic validation, no real-world "
             "result, no PASS/FAIL/⊥ for Symbol-U**. A′ remains canonically halted; D₀′ remains "
             "structural-only.")
    L.append("- The harness detects matched planted order signal above an effect/sample/noise-"
             "dependent threshold and returns null on planted-null/noise data at the designed "
             "false-positive rate; it under-detects non-commutative-product signal a linear probe "
             "cannot represent.")
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
