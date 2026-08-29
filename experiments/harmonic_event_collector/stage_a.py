"""Stage A: fit detector thresholds on training streams, freeze, evaluate once
on the held-out set, and check the E-GATE.

Usage: python -m experiments.harmonic_event_collector.stage_a
Writes results/frozen_thresholds.json (at freeze time) and results/stage_a.json.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .detectors import (HEC_GRID, STAT_GRID, emit, grid_configs, hec_channels,
                        score_events, stat_channels)
from .streams import EVENT_FAMILIES, T_A, TOLERANCE, gen_stage_a

RESULTS = Path(__file__).parent / "results"
TRAIN_SEED, TRAIN_N = 60_000, 64
HELD_SEED, HELD_N = 61_000, 128
FIT_MIN_REDUCTION = 110.0   # fit margin above the 100x E-GATE requirement
E_GATE = {"rare_recall": 0.95, "macro_recall": 0.90, "min_recall": 0.85,
          "reduction": 100.0}


def make_streams(seed: int, n: int):
    rng = np.random.default_rng(seed)
    return [gen_stage_a(rng) for _ in range(n)]


def eval_config(channel_list, label_list, config):
    fam_tot = {f: [0, 0] for f in EVENT_FAMILIES}
    n_emit = n_matched = 0
    for ch, labels in zip(channel_list, label_list):
        emitted = emit(ch, config)
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


def fit(channel_list, label_list, grid) -> tuple[dict, dict]:
    """Gate-aware selection on TRAINING streams only: maximize the worst
    E-GATE margin, then macro recall, then reduction."""
    best_cfg, best, best_key = None, None, None
    for cfg in grid_configs(grid):
        m = eval_config(channel_list, label_list, cfg)
        if m["reduction"] < FIT_MIN_REDUCTION:
            continue
        worst_margin = min(m["rare_recall"] - E_GATE["rare_recall"],
                           m["min_recall"] - E_GATE["min_recall"],
                           m["macro_recall"] - E_GATE["macro_recall"])
        key = (worst_margin, m["macro_recall"], m["reduction"])
        if best_key is None or key > best_key:
            best_cfg, best, best_key = cfg, m, key
    return best_cfg, best


def main():
    t0 = time.time()
    RESULTS.mkdir(exist_ok=True)
    train = make_streams(TRAIN_SEED, TRAIN_N)
    print(f"train streams: {TRAIN_N}, "
          f"gt events/stream: {np.mean([len(l) for _, l in train]):.1f}", flush=True)

    tr_hec = [hec_channels(x) for x, _ in train]
    tr_stat = [stat_channels(x) for x, _ in train]
    tr_labels = [l for _, l in train]
    hec_cfg, hec_train = fit(tr_hec, tr_labels, HEC_GRID)
    stat_cfg, stat_train = fit(tr_stat, tr_labels, STAT_GRID)
    frozen = {"hec": hec_cfg, "stat": stat_cfg,
              "train_metrics": {"hec": hec_train, "stat": stat_train}}
    (RESULTS / "frozen_thresholds.json").write_text(json.dumps(frozen, indent=2))
    print("FROZEN hec:", hec_cfg, "\n  train:", {k: round(v, 3) for k, v in
          hec_train.items() if not isinstance(v, dict)}, flush=True)
    print("FROZEN stat:", stat_cfg, flush=True)

    # Single held-out evaluation with frozen thresholds.
    held = make_streams(HELD_SEED, HELD_N)
    hd_labels = [l for _, l in held]
    hec_held = eval_config([hec_channels(x) for x, _ in held], hd_labels, hec_cfg)
    stat_held = eval_config([stat_channels(x) for x, _ in held], hd_labels, stat_cfg)

    gate = {
        "rare_recall": hec_held["rare_recall"] >= E_GATE["rare_recall"],
        "macro_recall": hec_held["macro_recall"] >= E_GATE["macro_recall"],
        "min_recall": hec_held["min_recall"] >= E_GATE["min_recall"],
        "reduction": hec_held["reduction"] >= E_GATE["reduction"],
    }
    gate["pass"] = all(gate.values())
    res = {"frozen": frozen, "held_out": {"hec": hec_held, "stat": stat_held},
           "e_gate": gate, "wall_seconds": round(time.time() - t0, 1)}
    (RESULTS / "stage_a.json").write_text(json.dumps(res, indent=2))
    print("\nheld-out HEC:", json.dumps(hec_held, indent=2))
    print("held-out stat baseline:", json.dumps(stat_held, indent=2))
    print("E-GATE:", json.dumps(gate, indent=2), flush=True)


if __name__ == "__main__":
    main()
