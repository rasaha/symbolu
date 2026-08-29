"""Train-days-only spike-predictability diagnostic (owner-ratified).

For every spike in the TRAIN period (bins 0-767; frozen spike rule: bin count
>= 3x the train seasonal median for its bin-of-day AND >= 10), ask whether it
was preceded within the prior 72 h (288 bins, truncated at the series start)
by (a) a spike at the same bin-of-day (+/-1 bin, mod 96), or (b) a spike at a
repeating interval: the gap to the most recent prior spike matches some gap
between consecutive prior spikes in the window to within +/-10%.

Touches train days only. Usage:
  python -m experiments.harmonic_real_data.diagnostic_spikes <c1_npz> <c2_npz>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from .data_assembly import Assembled
from .features import BINS_PER_DAY, TRAIN_END

LOOKBACK = 288  # 72 h in 15-min bins


def cohort_stats(npz_path: str) -> dict:
    data = Assembled(npz_path)
    med_count = np.expm1(data.seas_med)
    bod = np.arange(data.bins.shape[1]) % BINS_PER_DAY
    spike = data.bins >= np.maximum(3 * med_count[:, bod], 10)
    spike = spike[:, :TRAIN_END]  # train days only
    n = n_bod = n_gap = n_either = 0
    for f in range(spike.shape[0]):
        times = np.flatnonzero(spike[f])
        for i, t in enumerate(times):
            prior = times[(times >= t - LOOKBACK) & (times < t)]
            hit_bod = any((abs(int(p % 96) - int(t % 96)) % 96) in (0, 1, 95)
                          for p in prior)
            hit_gap = False
            if len(prior) >= 2:
                gaps = np.diff(prior)
                cur = t - prior[-1]
                hit_gap = bool(np.any(np.abs(cur - gaps) <= 0.1 * gaps))
            n += 1
            n_bod += hit_bod
            n_gap += hit_gap
            n_either += (hit_bod or hit_gap)
    return {"n_train_spikes": n,
            "frac_same_bin_of_day": round(n_bod / max(n, 1), 4),
            "frac_repeating_interval": round(n_gap / max(n, 1), 4),
            "frac_either": round(n_either / max(n, 1), 4)}


def main(c1, c2):
    out = {"cohort1": cohort_stats(c1), "cohort2": cohort_stats(c2)}
    p = Path(__file__).parent / "results" / "spike_predictability.json"
    p.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
