#!/usr/bin/env python3
"""Part 4 — incremental-value study. Baseline vs BCVF vs Fusion.

Evaluated on HELD-OUT seeds (100..119); all threshold tuning used seeds
0..19, so nothing is tested on a tuning trajectory. Thresholds are frozen in
``PREDICTOR_TRUST_V2_PREREGISTRATION.md`` (committed before this runs).

    python -m robotics_reliability_bench.run_incremental_value

Writes ``results/incremental_value.json`` and prints the comparison table.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from robotics_reliability_bench import fault_corpus as fc
from robotics_reliability_bench.detectors import (BaselineDetector, BCVFDetector,
                                                  FusionDetector, LLTKalmanDetector)
from robotics_reliability_bench.llt_kalman_trust import A1_CONFIG, LLTKalmanConfig
from robotics_reliability_bench.metrics import aggregate, score_family

RESULTS = os.path.join(os.path.dirname(__file__), "results")

# ---- FROZEN evaluation config (see preregistration) ----------------------
EVAL_SEEDS = list(range(100, 150))          # 50 seeds, held out from tuning (0..19)
BCVF_MARGIN_THRESHOLD = 1.5                  # frozen; separates benign gauss (~1.07)
                                             # from faults (~2.0) on TUNE
DETECTOR_WINDOW = 12


def build_corpus() -> Dict[str, List[fc.FaultBundle]]:
    return {fam: [fc.generate(fam, seed=s) for s in EVAL_SEEDS]
            for fam in fc.FAMILIES}


def run() -> Dict:
    corpus = build_corpus()
    baseline = BaselineDetector()
    bcvf = BCVFDetector(margin_threshold=BCVF_MARGIN_THRESHOLD, window=DETECTOR_WINDOW)
    fusion = FusionDetector(baseline, bcvf)
    # LLT-Kalman cross-domain variant (added after the original prereg; its
    # thresholds were tuned on TUNE families / seeds 0..19 only — see
    # results/llt_kalman_tune.json). Two tick policies are reported: the
    # default lets a same-predictor CUSUM crossing set the detection tick
    # (FusionDetector semantics); "strict" counts bias confirmation only.
    llt = LLTKalmanDetector()
    llt_strict = LLTKalmanDetector(LLTKalmanConfig(cusum_accelerates_tick=False),
                                   name="LLTKalman(strict-tick)")
    llt_fusion = FusionDetector(llt, bcvf)
    llt_fusion.name = "Fusion(LLT+BCVF)"
    # Amendment A1 (preregistration §7 A1): forgetting noise estimate, frozen
    # A1_CONFIG from results/llt_kalman_tune_A1.json.
    llt_a1 = LLTKalmanDetector(A1_CONFIG, name="LLTKalman-A1")
    llt_a1_fusion = FusionDetector(llt_a1, bcvf)
    llt_a1_fusion.name = "Fusion(LLT-A1+BCVF)"
    detectors = [baseline, bcvf, fusion, llt, llt_strict, llt_fusion,
                 llt_a1, llt_a1_fusion]

    out: Dict = {"eval_seeds": EVAL_SEEDS,
                 "bcvf_margin_threshold": BCVF_MARGIN_THRESHOLD,
                 "llt_kalman_config": {k: v for k, v in vars(llt.det.cfg).items()},
                 "llt_kalman_a1_config": {k: v for k, v in vars(A1_CONFIG).items()},
                 "tune_families": fc.TUNE_FAMILIES,
                 "test_families": fc.TEST_FAMILIES,
                 "per_detector": {}}

    for det in detectors:
        fam_scores = []
        per_family = {}
        for fam, bundles in corpus.items():
            fs = score_family(det, bundles)
            fam_scores.append(fs)
            per_family[fam] = {
                "harm_class": fs.harm_class, "fault_active": fs.fault_active,
                "detected_rate": round(fs.detected_rate, 3),
                "attribution_acc": (None if fs.attribution_acc is None
                                    else round(fs.attribution_acc, 3)),
                "mean_delay": (None if fs.mean_delay is None else round(fs.mean_delay, 1)),
                "abstain_rate": round(fs.abstain_rate, 3),
                "false_alarm": fs.false_alarm,
                "runtime_us": round(fs.mean_runtime_us, 1),
            }
        agg = aggregate(fam_scores)
        # split aggregates by TUNE vs held-out TEST families
        test_scores = [s for s in fam_scores if s.family in fc.TEST_FAMILIES]
        agg_test = aggregate(test_scores)
        out["per_detector"][det.name] = {
            "aggregate_all": _round(agg),
            "aggregate_test_only": _round(agg_test),
            "per_family": per_family,
        }
    return out


def _round(d: Dict) -> Dict:
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def _print(out: Dict) -> None:
    print("\n=== Per-family detected_rate / attribution_acc / delay ===")
    dets = list(out["per_detector"].keys())
    hdr = f"{'family':20s} {'harm':10s} " + " ".join(f"{d[:10]:>22s}" for d in dets)
    print(hdr)
    fams = out["per_detector"][dets[0]]["per_family"].keys()
    for fam in fams:
        row = f"{fam:20s} {out['per_detector'][dets[0]]['per_family'][fam]['harm_class'][:10]:10s} "
        for d in dets:
            pf = out["per_detector"][d]["per_family"][fam]
            aa = "-" if pf["attribution_acc"] is None else f"{pf['attribution_acc']:.2f}"
            dl = "-" if pf["mean_delay"] is None else f"{pf['mean_delay']:.0f}"
            row += f"  det={pf['detected_rate']:.2f} at={aa:>4} d={dl:>3}"
        print(row)

    print("\n=== Aggregate (ALL families) ===")
    for d in dets:
        a = out["per_detector"][d]["aggregate_all"]
        print(f"{d:22s} recall={a['fault_detection_recall']} "
              f"FA={a['false_alarm_rate']} nFA={a['n_benign_families_with_false_alarm']} "
              f"cm_false_det={a['common_mode_false_detection_rate']} "
              f"delay={a['detection_delay_ticks']} attr={a['attribution_accuracy']} "
              f"abst_ok={a['abstention_correctness']} us={a['runtime_us_per_episode']}")

    print("\n=== Aggregate (HELD-OUT TEST families only) ===")
    for d in dets:
        a = out["per_detector"][d]["aggregate_test_only"]
        print(f"{d:22s} recall={a['fault_detection_recall']} "
              f"FA={a['false_alarm_rate']} nFA={a['n_benign_families_with_false_alarm']} "
              f"delay={a['detection_delay_ticks']} attr={a['attribution_accuracy']}")


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = run()
    path = os.path.join(RESULTS, "incremental_value.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    _print(out)
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
