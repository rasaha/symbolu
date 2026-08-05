#!/usr/bin/env python3
"""FINAL/RESERVED phase: the full 8-cell x 5-seed factorial on the fresh reserved seeds 7140-7144. Runs
ONLY after the protocol lock. Trains every cell on identical task instances / batches per seed, evaluates
on one shared reserved cohort per seed, records every required metric + param hash + factor activity, and
verifies determinism (byte-identical replay) + leakage on a reserved cohort. Writes final_per_seed.json.
No gate is applied here (that is analysis); this file only produces the reserved evidence."""
from __future__ import annotations

import json
import pathlib
import time

import factor_config as C
import factor_leakage as LK
import run_lib as R

RES = pathlib.Path(__file__).resolve().parent / "results"


def main():
    # guard: protocol lock must exist and sources must be unchanged since the lock
    lock = json.loads((RES / "protocol_lock.json").read_text())
    import hashlib
    here = pathlib.Path(__file__).resolve().parent
    for n, h in lock["frozen_source_sha256"].items():
        cur = hashlib.sha256((here / n).read_bytes()).hexdigest()
        assert cur == h, f"source {n} changed since protocol lock (tuning forbidden): {cur} != {h}"

    t0 = time.time()
    train_eps = C.build_train_episodes()
    per_seed = {}
    cohort_last = None
    for seed in C.FINAL_SEEDS:
        res, cohort = R.run_seed(train_eps, seed)
        per_seed[str(seed)] = res
        cohort_last = cohort

    det = R.determinism_replay(train_eps, C.FINAL_SEEDS[0], "111")
    equiv = R.oracle_equivariance_check(C.FINAL_SEEDS[0], "111")
    leak = LK.run_all(cohort_last)

    out = {
        "schema": "bindingslots_e1_3factor/final/v1",
        "final_seeds": C.FINAL_SEEDS, "cells": list(C.CELLS.keys()),
        "added_params_per_cell": {c: R.added_params_for(c) for c in C.CELLS},
        "per_seed": per_seed,
        "determinism": det, "oracle_equivariance": equiv,
        "leakage": leak, "leakage_all_pass": leak["all_pass"],
        "source_hashes_match_lock": True,
        "wall_clock_sec": round(time.time() - t0, 1),
    }
    R.write_json("final_per_seed.json", out)
    print(f"FINAL done in {out['wall_clock_sec']}s | det={det['byte_identical']} equiv={equiv['pass']} "
          f"leak={leak['all_pass']}")
    for c in C.CELLS:
        t4 = [per_seed[str(s)][c]["metrics"]["T4_latest"]["correct_latest"] for s in C.FINAL_SEEDS]
        print(f"  {c}: T4(null-incl) mean={sum(t4)/len(t4):.3f} worst={min(t4):.3f} "
              f"per-seed={[round(x,3) for x in t4]}")


if __name__ == "__main__":
    main()
