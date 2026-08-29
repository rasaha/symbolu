"""ONE-SHOT held-out evaluation and gate check (run only after the freeze
commit; the held-out period d11-d14 is inspected here for the first time).

Usage: python -m experiments.harmonic_real_data.evaluate_heldout <npz> <model_dir>
Writes results/heldout.json and results/gates.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

from .arms import READER_ARMS, build_matched
from .data_assembly import Assembled
from .features import BINS_PER_DAY, HORIZONS

HELD_T = np.arange(960, 1333, 4)          # 94 queries/function
SEEDS = (0, 1, 2)
VAR_FLOOR = 0.01
MIN_SPIKE_QUERIES = 5                      # per-function floor for spike aggregation
WIN_MIN, RI_MIN = 0.55, 0.03
RESULTS = Path(__file__).parent / "results"
BASELINES = ("persistence", "seasonal_naive")


def reader_preds(data, model_dir, arm, seed):
    model = build_matched(arm)
    model.load_state_dict(torch.load(Path(model_dir) / f"{arm}_seed{seed}.pt",
                                     weights_only=True))
    model.eval()
    preds = np.zeros((data.n_func, len(HELD_T), 3), np.float32)
    with torch.no_grad():
        for f0 in range(0, data.n_func, 50):
            fs = np.arange(f0, min(f0 + 50, data.n_func))
            f_idx = np.repeat(fs, len(HELD_T))
            t_idx = np.tile(HELD_T, len(fs))
            toks, q, _ = data.tokens(arm, f_idx, t_idx)
            preds[fs] = model(toks, q).numpy().reshape(len(fs), len(HELD_T), 3)
    return preds


def per_function_nmse(preds, targets, include_mask, sel=None):
    """preds/targets [F, Q, 3]; sel optional [F, Q, 3] bool query filter.
    Returns nmse [F, 3] (nan where excluded)."""
    F, Q, H = targets.shape
    out = np.full((F, H), np.nan)
    for h in range(H):
        for f in range(F):
            if not include_mask[f, h]:
                continue
            m = np.ones(Q, bool) if sel is None else sel[f, :, h]
            if sel is not None and m.sum() < MIN_SPIKE_QUERIES:
                continue
            err = np.mean((preds[f, m, h] - targets[f, m, h]) ** 2)
            out[f, h] = err / max(targets[f, :, h].var(), VAR_FLOOR)
    return out


def compare(nmse_a, nmse_b, h):
    """a vs b at horizon h -> (win_fraction, RI of median)."""
    m = ~np.isnan(nmse_a[:, h]) & ~np.isnan(nmse_b[:, h])
    win = float((nmse_a[m, h] < nmse_b[m, h]).mean())
    med_a, med_b = np.median(nmse_a[m, h]), np.median(nmse_b[m, h])
    return win, float((med_b - med_a) / med_b), int(m.sum())


def main(npz_path, model_dir):
    data = Assembled(npz_path)
    targets = data.targets[:, HELD_T]                     # [F, 94, 3]
    include = np.stack([data.targets[:, HELD_T, h].var(axis=1) >= VAR_FLOOR
                        for h in range(3)], axis=1)      # [F, 3]

    # Spike selector: target window contains a bin >= 3x train seasonal median
    # for its bin-of-day AND >= 10 invocations.
    med_count = np.expm1(data.seas_med)                  # [F, 96]
    spike_bin = np.zeros_like(data.bins, bool)
    bod = np.arange(data.bins.shape[1]) % BINS_PER_DAY
    spike_bin = (data.bins >= np.maximum(3 * med_count[:, bod], 10))
    sel = np.zeros((data.n_func, len(HELD_T), 3), bool)
    for qi, t in enumerate(HELD_T):
        for h, H in enumerate(HORIZONS):
            sel[:, qi, h] = spike_bin[:, t:t + H].any(axis=1)

    all_nmse, spike_nmse = {}, {}
    for b in BASELINES:
        preds = data.baselines[b][:, HELD_T]
        all_nmse[b] = per_function_nmse(preds, targets, include)
        spike_nmse[b] = per_function_nmse(preds, targets, include, sel)
    for arm in READER_ARMS:
        for seed in SEEDS:
            preds = reader_preds(data, model_dir, arm, seed)
            all_nmse[(arm, seed)] = per_function_nmse(preds, targets, include)
            spike_nmse[(arm, seed)] = per_function_nmse(preds, targets, include, sel)
            print(f"evaluated {arm} seed {seed}", flush=True)

    def seedwise(arm_a, other, h, table):
        rows = []
        for s in SEEDS:
            a = table[(arm_a, s)]
            b = table[other] if isinstance(other, str) else table[(other, s)]
            rows.append(compare(a, b, h))
        return rows

    def gate_all(rows):
        return all(w >= WIN_MIN and ri >= RI_MIN for w, ri, _ in rows)

    gates = {"summary": {}}
    # V-GATE: stats_reader beats persistence at H=180 (h index 2).
    v_rows = seedwise("stats_reader", "persistence", 2, all_nmse)
    gates["V"] = {"rows": v_rows, "pass": gate_all(v_rows)}
    # H-GATE: harmonic_reader beats each of stats_reader/persistence/seasonal
    # at H=60 and H=180 (h index 1, 2).
    h_detail, h_pass = {}, True
    for other in ("stats_reader", "persistence", "seasonal_naive"):
        for h in (1, 2):
            rows = seedwise("harmonic_reader", other, h, all_nmse)
            h_detail[f"vs_{other}_h{HORIZONS[h]}"] = rows
            h_pass &= gate_all(rows)
    gates["H"] = {"detail": h_detail, "pass": h_pass}
    # S-GATE: harmonic_retrieval beats harmonic_reader on spike queries at
    # H=15 and H=60 (h index 0, 1).
    s_detail, s_pass = {}, True
    for h in (0, 1):
        rows = seedwise("harmonic_retrieval", "harmonic_reader", h, spike_nmse)
        s_detail[f"h{HORIZONS[h]}"] = rows
        s_pass &= gate_all(rows)
    sr_info = {f"h{HORIZONS[h]}": seedwise("stats_retrieval", "stats_reader",
                                           h, spike_nmse) for h in (0, 1)}
    gates["S"] = {"detail": s_detail, "pass": s_pass,
                  "stats_retrieval_informational": sr_info}

    # Median nMSE tables (seed-averaged for readers).
    table = {}
    for name in list(BASELINES):
        table[name] = [float(np.nanmedian(all_nmse[name][:, h])) for h in range(3)]
    for arm in READER_ARMS:
        meds = np.array([[np.nanmedian(all_nmse[(arm, s)][:, h])
                          for h in range(3)] for s in SEEDS])
        table[arm] = meds.mean(axis=0).tolist()
    coverage = {"functions_included_per_horizon": include.sum(axis=0).tolist(),
                "spike_functions_per_horizon":
                    [int(np.sum([~np.isnan(spike_nmse[("harmonic_reader", 0)][:, h])
                                 for h in (h,)])) for h in range(3)]}

    out = {"median_nmse": table, "gates": gates, "coverage": coverage,
           "n_queries_per_function": int(len(HELD_T))}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "heldout.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(table, indent=1))
    print("V:", gates["V"]["pass"], "H:", gates["H"]["pass"], "S:", gates["S"]["pass"])
    print("V rows:", v_rows)
    print("H detail:", json.dumps(h_detail, indent=1))
    print("S detail:", json.dumps(s_detail, indent=1))


if __name__ == "__main__":
    torch.set_num_threads(4)
    main(sys.argv[1], sys.argv[2])
