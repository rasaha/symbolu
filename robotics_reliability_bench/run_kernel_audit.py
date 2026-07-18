#!/usr/bin/env python3
"""Part 2 — predictor-trust kernel audit against the real implementation.

Exercises ``symbolu_robotics.bcvf_autonomous`` directly on:
  (a) the two central invariance claims, noiseless AND with realistic noise;
  (b) every fault family, recording kernel margin + attribution + whether the
      fault is harm-bearing yet invariance-hidden.

    python -m robotics_reliability_bench.run_kernel_audit

Writes ``results/kernel_audit.json``.
"""
from __future__ import annotations

import json
import os
from typing import Dict

import numpy as np

from symbolu_robotics.bcvf_autonomous.core import (BCVFConfig, CostOrder,
                                                   compute_bcvf_cost,
                                                   compute_bcvf_cost_batch)
from robotics_reliability_bench import fault_corpus as fc

RESULTS = os.path.join(os.path.dirname(__file__), "results")
CFG = BCVFConfig(use_anchor_pairing=False, cost_order=CostOrder.SECOND)
SEEDS = list(range(100, 150))


def _line(H, dt, v, off_y=0.0, drift=0.0, accel=0.0):
    t = np.arange(H) * dt
    tr = np.zeros((H, 3))
    tr[:, 0] = v * t
    tr[:, 1] = off_y + drift * t + 0.5 * accel * t * t
    return tr


def invariance_tests() -> Dict:
    H, dt, v = 50, 0.1, 5.0
    base = _line(H, dt, v)
    third = _line(H, dt, v)
    results = {}
    for name, p1 in [("constant_offset", _line(H, dt, v, off_y=0.7)),
                     ("linear_drift", _line(H, dt, v, drift=0.3)),
                     ("accelerating", _line(H, dt, v, accel=0.3))]:
        r = compute_bcvf_cost([base, p1, third], CFG)
        results[name] = {"noiseless_total_cost": float(r.total_cost),
                         "noiseless_max_accel_norm": float(r.max_acceleration_norm)}
    # with noise: does the gate leak produce an attribution signal?
    rng = np.random.default_rng(0)
    for name, p1 in [("constant_offset", _line(H, dt, v, off_y=0.7)),
                     ("linear_drift", _line(H, dt, v, drift=0.3))]:
        trajs = np.stack([base + rng.normal(0, 0.01, (H, 3)),
                          p1 + rng.normal(0, 0.01, (H, 3)),
                          third + rng.normal(0, 0.01, (H, 3))])
        _, per = compute_bcvf_cost_batch(trajs[None], CFG, return_per_predictor=True)
        per = per[0]
        results[name]["noisy_per_predictor_cost"] = [round(x, 3) for x in per.tolist()]
        results[name]["noisy_argmax_is_biased_predictor"] = int(np.argmax(per)) == 1
    return results


def per_family() -> Dict:
    out = {}
    for fam in fc.FAMILIES:
        margins, amaxes, hits = [], [], []
        for s in SEEDS:
            b = fc.generate(fam, seed=s)
            _, per = compute_bcvf_cost_batch(b.trajectories[None], CFG,
                                             return_per_predictor=True)
            per = per[0]
            amax = int(np.argmax(per))
            others = np.delete(per, amax)
            margins.append(float(per[amax] / (np.mean(others) + 1e-12)))
            amaxes.append(amax)
            if b.truth_label is not None:
                hits.append(int(amax == b.truth_label))
        b0 = fc.generate(fam, seed=SEEDS[0])
        out[fam] = {
            "harm_class": b0.harm_class,
            "fault_active": b0.fault_active,
            "bcvf_visible_by_design": b0.bcvf_visible,
            "truth_label": b0.truth_label,
            "median_margin": round(float(np.median(margins)), 3),
            "attribution_hit_rate": (round(float(np.mean(hits)), 3) if hits else None),
        }
    return out


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    audit = {"config": {"use_anchor_pairing": False, "cost_order": "SECOND"},
             "invariance": invariance_tests(),
             "per_family": per_family()}
    path = os.path.join(RESULTS, "kernel_audit.json")
    with open(path, "w") as f:
        json.dump(audit, f, indent=2)

    inv = audit["invariance"]
    print("=== Invariance (noiseless) ===")
    for k in ("constant_offset", "linear_drift", "accelerating"):
        print(f"  {k:16s} total_cost={inv[k]['noiseless_total_cost']:.3e}")
    print("=== Invariance with noise (gate leak) ===")
    for k in ("constant_offset", "linear_drift"):
        print(f"  {k:16s} per_pred={inv[k]['noisy_per_predictor_cost']} "
              f"argmax_is_biased={inv[k]['noisy_argmax_is_biased_predictor']}")
    print("=== Per-family kernel behaviour ===")
    print(f"{'family':20s} {'harm':18s} {'margin':>7s} {'attr_hit':>9s} bcvf_visible")
    for fam, d in audit["per_family"].items():
        hr = "-" if d["attribution_hit_rate"] is None else f"{d['attribution_hit_rate']:.2f}"
        print(f"{fam:20s} {d['harm_class']:18s} {d['median_margin']:7.2f} {hr:>9s} "
              f"{int(d['bcvf_visible_by_design'])}")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
