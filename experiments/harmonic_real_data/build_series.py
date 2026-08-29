"""Extract the frozen cohort's minute-level series for all 14 days into a
compact npz OUTSIDE Git (scratchpad). Deterministic; reads only rows matching
frozen_functions.json.

Usage: python -m experiments.harmonic_real_data.build_series <data_dir> <out_npz>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

MIN_PER_DAY = 1440


def main(data_dir: str, out_npz: str, frozen_name="frozen_functions.json"):
    t0 = time.time()
    frozen = json.loads((Path(__file__).parent / frozen_name).read_text())
    keys = [(f["HashOwner"], f["HashApp"], f["HashFunction"])
            for f in frozen["functions"]]
    pos = {k: i for i, k in enumerate(keys)}
    minutes = np.zeros((len(keys), 14 * MIN_PER_DAY), np.int64)
    for d in range(1, 15):
        f = Path(data_dir) / f"invocations_per_function_md.anon.d{d:02d}.csv"
        df = pd.read_csv(f)
        mask = [
            (o, a, fn) in pos
            for o, a, fn in zip(df["HashOwner"], df["HashApp"], df["HashFunction"])
        ]
        sub = df[np.array(mask)]
        vals = sub[[str(m) for m in range(1, 1441)]].to_numpy(np.int64)
        for (o, a, fn), row in zip(
                zip(sub["HashOwner"], sub["HashApp"], sub["HashFunction"]), vals):
            minutes[pos[(o, a, fn)], (d - 1) * MIN_PER_DAY: d * MIN_PER_DAY] = row
        print(f"d{d:02d}: matched {len(sub)}/200 ({time.time() - t0:.0f}s)", flush=True)
    np.savez_compressed(out_npz, minutes=minutes)
    print(f"wrote {out_npz} shape={minutes.shape}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(sys.argv[3:4]))
