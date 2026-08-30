"""2021 trace preparation: arrival-minute binning, train-only eligibility
(identical rule to 2019), cohort freeze, and the cohort minute matrix.

Usage: python -m experiments.harmonic_real_data_2021.prepare_2021 <txt> <out_npz>
Writes frozen_functions_2021.json (commit before dev/held-out use) and the
npz OUTSIDE Git.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

MIN_PER_DAY = 1440
DAYS = 14
TOTAL_MIN = DAYS * MIN_PER_DAY
TRAIN_BINS = 8 * 96
# Identical eligibility thresholds to experiments/harmonic_real_data.
MIN_ACTIVE_DAYS = 7
MIN_NONZERO_BIN_FRAC = 0.40
MIN_MEAN_PER_BIN = 2.0
MIN_LOG1P_VAR = 0.05
MIN_CV = 0.10
COHORT_FLOOR = 40


def main(txt_path: str, out_npz: str):
    t0 = time.time()
    df = pd.read_csv(txt_path)
    arrival = (df["end_timestamp"] - df["duration"]).clip(0, DAYS * 86400 - 1e-6)
    minute = (arrival // 60).astype(np.int64)
    key = df["app"] + "|" + df["func"]
    codes, uniques = pd.factorize(key)
    F = len(uniques)
    minutes = np.zeros((F, TOTAL_MIN), np.int64)
    np.add.at(minutes, (codes, minute.to_numpy()), 1)
    print(f"parsed {len(df):,} invocations, {F} (app,func) pairs "
          f"({time.time() - t0:.0f}s)", flush=True)

    # Train-only eligibility (bins 0..767), identical rule to 2019.
    bins = minutes.reshape(F, 14 * 96, 15).sum(axis=2)
    tb = bins[:, :TRAIN_BINS]
    day_active = minutes[:, :8 * MIN_PER_DAY].reshape(F, 8, MIN_PER_DAY).sum(2) > 0
    mean = tb.mean(axis=1)
    std = tb.std(axis=1)
    elig = ((day_active.sum(axis=1) >= MIN_ACTIVE_DAYS)
            & ((tb > 0).mean(axis=1) >= MIN_NONZERO_BIN_FRAC)
            & (mean >= MIN_MEAN_PER_BIN)
            & (np.log1p(tb).var(axis=1) >= MIN_LOG1P_VAR)
            & (std / np.maximum(mean, 1e-9) >= MIN_CV))
    elig_i = np.flatnonzero(elig)
    # Cohort = ALL eligible (preregistered adaptation), lexicographic order.
    elig_i = sorted(elig_i, key=lambda i: uniques[i])
    print(f"eligible: {len(elig_i)} of {F} (floor {COHORT_FLOOR})", flush=True)

    out = {"eligibility": {"n_seen": int(F), "n_eligible": len(elig_i),
                           "cohort_floor": COHORT_FLOOR,
                           "floor_met": len(elig_i) >= COHORT_FLOOR},
           "functions": [{"app_func": uniques[i],
                          "train_total": int(tb[i].sum())} for i in elig_i]}
    p = Path(__file__).parent / "frozen_functions_2021.json"
    p.write_text(json.dumps(out, indent=1))
    print(f"wrote {p}", flush=True)
    if len(elig_i) >= COHORT_FLOOR:
        np.savez_compressed(out_npz, minutes=minutes[np.array(elig_i)])
        print(f"wrote {out_npz} shape=({len(elig_i)}, {TOTAL_MIN})", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
