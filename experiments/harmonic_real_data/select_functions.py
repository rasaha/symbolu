"""Train-only eligibility and cohort freeze (PREREGISTRATION.md).

Reads ONLY d01-d08 invocation files, applies the frozen eligibility rule,
freezes the 200-function cohort, and writes frozen_functions.json. Run and
committed before the development or held-out periods are used for anything.

Usage: python -m experiments.harmonic_real_data.select_functions <data_dir>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

TRAIN_DAYS = range(1, 9)
BINS_PER_DAY = 96
MIN_ACTIVE_DAYS = 7
MIN_NONZERO_BIN_FRAC = 0.40
MIN_MEAN_PER_BIN = 2.0
MIN_LOG1P_VAR = 0.05
MIN_CV = 0.10
N_COHORT, N_QUINTILES, PER_QUINTILE = 200, 5, 40


def main(data_dir: str):
    t0 = time.time()
    idx: dict[tuple, int] = {}
    bins_list: list[np.ndarray] = []
    active_list: list[np.ndarray] = []
    for d in TRAIN_DAYS:
        f = Path(data_dir) / f"invocations_per_function_md.anon.d{d:02d}.csv"
        df = pd.read_csv(f)
        minutes = df[[str(m) for m in range(1, 1441)]].to_numpy(np.int64)
        day_bins = minutes.reshape(len(df), BINS_PER_DAY, 15).sum(axis=2)
        keys = list(zip(df["HashOwner"], df["HashApp"], df["HashFunction"]))
        for k, row in zip(keys, day_bins):
            if k not in idx:
                idx[k] = len(bins_list)
                bins_list.append(np.zeros(8 * BINS_PER_DAY, np.int64))
                active_list.append(np.zeros(8, bool))
            bins_list[idx[k]][(d - 1) * BINS_PER_DAY: d * BINS_PER_DAY] = row
            active_list[idx[k]][d - 1] = row.sum() > 0
        print(f"d{d:02d}: {len(df)} rows, union {len(idx)} functions "
              f"({time.time() - t0:.0f}s)", flush=True)

    keys = list(idx.keys())
    bins = np.stack(bins_list)
    active = np.stack(active_list)
    mean = bins.mean(axis=1)
    std = bins.std(axis=1)
    elig = ((active.sum(axis=1) >= MIN_ACTIVE_DAYS)
            & ((bins > 0).mean(axis=1) >= MIN_NONZERO_BIN_FRAC)
            & (mean >= MIN_MEAN_PER_BIN)
            & (np.log1p(bins).var(axis=1) >= MIN_LOG1P_VAR)
            & (std / np.maximum(mean, 1e-9) >= MIN_CV))
    elig_i = np.flatnonzero(elig)
    print(f"eligible: {len(elig_i)} of {len(keys)}", flush=True)

    total = bins[elig_i].sum(axis=1)
    order = np.argsort(total, kind="stable")
    cohort = []
    qs = np.array_split(order, N_QUINTILES)
    for q in qs:
        cand = sorted(q, key=lambda j: keys[elig_i[j]][2])[:PER_QUINTILE]
        cohort.extend(elig_i[j] for j in cand)
    assert len(cohort) == N_COHORT
    out = {
        "eligibility": {"n_seen": len(keys), "n_eligible": int(len(elig_i))},
        "functions": [{"HashOwner": keys[i][0], "HashApp": keys[i][1],
                       "HashFunction": keys[i][2],
                       "train_total": int(bins[i].sum())} for i in cohort],
    }
    p = Path(__file__).parent / "frozen_functions.json"
    p.write_text(json.dumps(out, indent=1))
    print(f"wrote {p} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
