#!/usr/bin/env python3
"""FINAL/RESERVED phase: R0-R3 on the fresh reserved seeds 7150-7154. Runs ONLY after the protocol lock;
verifies frozen source + frozen-base hashes match the lock before executing, and re-verifies frozen-base
unchanged per arm/seed. Writes final_per_seed.json (reserved evidence only; no gate applied here)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import time

import readout_config as C
import readout_leakage as LK
import readout_run_lib as R
from readout_model import build_frozen_encoder, Readout
from readout_train import base_hash

HERE = pathlib.Path(__file__).resolve().parent
RES = HERE / "results"


def main():
    lock = json.loads((RES / "protocol_lock.json").read_text())
    for n, h in lock["frozen_source_sha256"].items():
        cur = hashlib.sha256((HERE / n).read_bytes()).hexdigest()
        assert cur == h, f"source {n} changed since lock (tuning forbidden)"

    t0 = time.time()
    enc = build_frozen_encoder(verify=True)
    assert base_hash(Readout(enc, "R0")) == lock["frozen_base_param_hash"], "frozen-base hash != lock"
    train_eps = C.build_train_episodes()

    per_seed = {}
    cohort_last = None
    for seed in C.FINAL_SEEDS:
        res, cohort = R.run_seed(enc, train_eps, seed)
        per_seed[str(seed)] = res
        cohort_last = cohort

    det = R.determinism_replay(enc, train_eps, C.FINAL_SEEDS[0], "R2")
    equiv = R.oracle_equivariance_check(enc, C.FINAL_SEEDS[0], "R2")
    leak = LK.run_all(cohort_last)
    frozen_ok = all(per_seed[str(s)][a]["frozen_base_unchanged"] for s in C.FINAL_SEEDS for a in C.ARMS)
    base_after = base_hash(Readout(enc, "R0"))

    out = {
        "schema": "bindingslots_e1_readout/final/v1",
        "final_seeds": C.FINAL_SEEDS, "arms": C.ARMS,
        "added_params_per_arm": {a: R.added_params(enc, a) for a in C.ARMS},
        "per_seed": per_seed,
        "determinism": det, "oracle_equivariance": equiv,
        "leakage": leak, "leakage_all_pass": leak["all_pass"],
        "frozen_base_unchanged_all": frozen_ok,
        "frozen_base_param_hash_after": base_after,
        "frozen_base_matches_lock": base_after == lock["frozen_base_param_hash"],
        "source_hashes_match_lock": True,
        "wall_clock_sec": round(time.time() - t0, 1),
    }
    R.write_json("final_per_seed.json", out)
    print(f"FINAL done in {out['wall_clock_sec']}s | det={det['byte_identical']} equiv={equiv['pass']} "
          f"leak={leak['all_pass']} frozen_base_unchanged={frozen_ok} matches_lock={out['frozen_base_matches_lock']}")
    for a in C.ARMS:
        t4 = [per_seed[str(s)][a]["metrics"]["T4_latest"]["correct_latest"] for s in C.FINAL_SEEDS]
        r0 = [per_seed[str(s)]["R0"]["metrics"]["T4_latest"]["correct_latest"] for s in C.FINAL_SEEDS]
        impr = [t4[i] - r0[i] for i in range(len(t4))]
        print(f"  {a}: T4 mean={sum(t4)/len(t4):.3f} worst={min(t4):.3f} impr_mean={sum(impr)/len(impr):+.3f} "
              f"per-seed={[round(x,3) for x in t4]}")


if __name__ == "__main__":
    main()
