#!/usr/bin/env python3
"""TUNE-only threshold sweep for the LLT-Kalman variant.

Sweeps ``LLTKalmanConfig`` over the TUNE families ONLY (``fault_corpus
.TUNE_FAMILIES``) on seeds 0..19 — the same tuning protocol the frozen
baseline used. Nothing here touches TEST families or the evaluation seeds
100..149.

Selection rule (fixed before running):
  1. zero false alarms on the TUNE benign families (gaussian_noise,
     noisy_unbiased);
  2. recall 1.0 on the TUNE harm families (constant_bias, linear_drift,
     accelerating) with attribution 1.0;
  3. among survivors, minimise mean detection delay under the STRICT tick
     policy (bias confirmation only), so the accelerated tick cannot buy a
     looser bias test;
  4. ties -> the more conservative config (larger cusum_h, larger bias_z).

    python -m robotics_reliability_bench.tune_llt_kalman

Writes ``results/llt_kalman_tune.json``; the chosen config is then frozen as
``LLTKalmanConfig`` defaults by hand (recorded in the results note).
"""
from __future__ import annotations

import itertools
import json
import os
from dataclasses import asdict
from typing import Dict, List

from robotics_reliability_bench import fault_corpus as fc
from robotics_reliability_bench.detectors import LLTKalmanDetector
from robotics_reliability_bench.llt_kalman_trust import LLTKalmanConfig
from robotics_reliability_bench.metrics import score_family

RESULTS = os.path.join(os.path.dirname(__file__), "results")
TUNE_SEEDS = list(range(0, 20))

GRID = {
    "q_level_ratio": [0.003, 0.01, 0.03],
    "q_slope_ratio": [0.0003, 0.001, 0.003],
    "cusum_k": [2.0, 2.5],
    "cusum_h": [6.0, 8.0, 12.0],
    "bias_z": [3.0, 4.0, 6.0],
    "bias_sustain": [4, 6, 8],
}


def _corpus() -> Dict[str, List[fc.FaultBundle]]:
    return {fam: [fc.generate(fam, seed=s) for s in TUNE_SEEDS]
            for fam in fc.TUNE_FAMILIES}


def evaluate(cfg: LLTKalmanConfig, corpus) -> Dict:
    det = LLTKalmanDetector(cfg)
    rows = {}
    for fam, bundles in corpus.items():
        fs = score_family(det, bundles)
        rows[fam] = {"detected_rate": fs.detected_rate,
                     "attribution_acc": fs.attribution_acc,
                     "mean_delay": fs.mean_delay,
                     "fault_active": fs.fault_active}
    benign_fa = max(r["detected_rate"] for r in rows.values() if not r["fault_active"])
    harm = [r for r in rows.values() if r["fault_active"]]
    recall = min(r["detected_rate"] for r in harm)
    attr = min(r["attribution_acc"] for r in harm)
    delays = [r["mean_delay"] for r in harm if r["mean_delay"] is not None]
    mean_delay = sum(delays) / len(delays) if delays else None
    return {"benign_fa": benign_fa, "recall": recall, "attr": attr,
            "mean_delay": mean_delay, "per_family": rows}


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    corpus = _corpus()
    keys = list(GRID)
    records = []
    for values in itertools.product(*(GRID[k] for k in keys)):
        params = dict(zip(keys, values))
        cfg = LLTKalmanConfig(cusum_accelerates_tick=False, **params)  # STRICT tick
        res = evaluate(cfg, corpus)
        res["params"] = params
        records.append(res)

    survivors = [r for r in records
                 if r["benign_fa"] == 0.0 and r["recall"] == 1.0 and r["attr"] == 1.0]
    survivors.sort(key=lambda r: (r["mean_delay"],
                                  -r["params"]["cusum_h"], -r["params"]["bias_z"]))
    chosen = survivors[0] if survivors else None

    out = {"tune_families": fc.TUNE_FAMILIES, "tune_seeds": TUNE_SEEDS,
           "grid": GRID, "n_configs": len(records), "n_survivors": len(survivors),
           "selection_rule": ("benign_fa==0 and recall==1 and attr==1; "
                              "then min strict-tick mean delay; then larger "
                              "cusum_h, bias_z"),
           "chosen": chosen,
           "top10": survivors[:10],
           "frozen_config": (asdict(LLTKalmanConfig(**chosen["params"]))
                             if chosen else None)}
    path = os.path.join(RESULTS, "llt_kalman_tune.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"configs={len(records)} survivors={len(survivors)}")
    for r in survivors[:10]:
        print(f"  delay={r['mean_delay']:.2f}  {r['params']}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
