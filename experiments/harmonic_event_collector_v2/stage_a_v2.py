"""V2 Stage A: fit on fresh training streams (seed 70000), freeze, evaluate the
fresh held-out set (seed 71000) exactly once, check the unchanged E-GATE.

Usage: python -m experiments.harmonic_event_collector_v2.stage_a_v2
Writes results/frozen_thresholds.json (at freeze time) and results/stage_a.json.
The StatChangeDetector baseline is imported unchanged from V1.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from experiments.harmonic_event_collector.detectors import (STAT_GRID, emit,
                                                            grid_configs,
                                                            score_events,
                                                            stat_channels)
from experiments.harmonic_event_collector.streams import (EVENT_FAMILIES, T_A,
                                                          TOLERANCE,
                                                          gen_stage_a)
from .detectors_v2 import HEC_V2_GRID, PROTECT_GRID, emit_v2, hec_channels_v2

RESULTS = Path(__file__).parent / "results"
TRAIN_SEED, TRAIN_N = 70_000, 64
HELD_SEED, HELD_N = 71_000, 128
FIT_MIN_REDUCTION = 110.0
E_GATE = {"rare_recall": 0.95, "macro_recall": 0.90, "min_recall": 0.85,
          "reduction": 100.0}


def make_streams(seed: int, n: int):
    rng = np.random.default_rng(seed)
    return [gen_stage_a(rng) for _ in range(n)]


def eval_config(channel_list, label_list, config, emit_fn):
    fam_tot = {f: [0, 0] for f in EVENT_FAMILIES}
    n_emit = n_matched = 0
    for ch, labels in zip(channel_list, label_list):
        emitted = emit_fn(ch, config)
        n_emit += len(emitted)
        fams, matched = score_events(emitted, labels, TOLERANCE)
        n_matched += matched
        for f, (h, n) in fams.items():
            fam_tot[f][0] += h
            fam_tot[f][1] += n
    recalls = {f: (h / n if n else float("nan")) for f, (h, n) in fam_tot.items()}
    valid = [r for r in recalls.values() if not np.isnan(r)]
    return {
        "recalls": recalls,
        "macro_recall": float(np.mean(valid)),
        "min_recall": float(np.min(valid)),
        "rare_recall": recalls["rare_aperiodic"],
        "reduction": (len(channel_list) * T_A) / max(n_emit, 1),
        "precision": n_matched / max(n_emit, 1),
        "events_per_stream": n_emit / len(channel_list),
    }


def gate_key(m):
    worst = min(m["rare_recall"] - E_GATE["rare_recall"],
                m["min_recall"] - E_GATE["min_recall"],
                m["macro_recall"] - E_GATE["macro_recall"])
    return (worst, m["macro_recall"], m["reduction"])


def main():
    t0 = time.time()
    RESULTS.mkdir(exist_ok=True)
    train = make_streams(TRAIN_SEED, TRAIN_N)
    tr_labels = [l for _, l in train]
    print(f"train streams: {TRAIN_N}, "
          f"gt events/stream: {np.mean([len(l) for l in tr_labels]):.1f}", flush=True)

    # HEC V2: channels per protect value, gate-aware fit over the frozen grids.
    best_cfg, best, best_key = None, None, None
    for p in PROTECT_GRID:
        chans = [hec_channels_v2(x, p) for x, _ in train]
        for cfg in grid_configs(HEC_V2_GRID):
            m = eval_config(chans, tr_labels, cfg, emit_v2)
            if m["reduction"] < FIT_MIN_REDUCTION:
                continue
            key = gate_key(m)
            if best_key is None or key > best_key:
                best_cfg, best, best_key = {**cfg, "protect": p}, m, key
        print(f"  protect={p} searched ({time.time() - t0:.0f}s)", flush=True)

    tr_stat = [stat_channels(x) for x, _ in train]
    stat_cfg, stat_best, stat_key = None, None, None
    for cfg in grid_configs(STAT_GRID):
        m = eval_config(tr_stat, tr_labels, cfg, emit)
        if m["reduction"] < FIT_MIN_REDUCTION:
            continue
        key = gate_key(m)
        if stat_key is None or key > stat_key:
            stat_cfg, stat_best, stat_key = cfg, m, key

    frozen = {"hec_v2": best_cfg, "stat": stat_cfg,
              "train_metrics": {"hec_v2": best, "stat": stat_best}}
    (RESULTS / "frozen_thresholds.json").write_text(json.dumps(frozen, indent=2))
    print("FROZEN hec_v2:", best_cfg, flush=True)
    print("  train:", json.dumps({k: v for k, v in best.items()}, indent=2), flush=True)

    # Single held-out evaluation with frozen parameters.
    held = make_streams(HELD_SEED, HELD_N)
    hd_labels = [l for _, l in held]
    hec_held = eval_config([hec_channels_v2(x, best_cfg["protect"]) for x, _ in held],
                           hd_labels, best_cfg, emit_v2)
    stat_held = eval_config([stat_channels(x) for x, _ in held], hd_labels,
                            stat_cfg, emit)

    gate = {k: hec_held[k] >= v for k, v in
            [("rare_recall", E_GATE["rare_recall"]),
             ("macro_recall", E_GATE["macro_recall"]),
             ("min_recall", E_GATE["min_recall"]),
             ("reduction", E_GATE["reduction"])]}
    gate["pass"] = all(gate.values())
    res = {"frozen": frozen, "held_out": {"hec_v2": hec_held, "stat": stat_held},
           "e_gate": gate, "wall_seconds": round(time.time() - t0, 1)}
    (RESULTS / "stage_a.json").write_text(json.dumps(res, indent=2))
    print("\nheld-out HEC v2:", json.dumps(hec_held, indent=2))
    print("held-out stat baseline:", json.dumps(stat_held, indent=2))
    print("E-GATE:", json.dumps(gate, indent=2), flush=True)


if __name__ == "__main__":
    main()
