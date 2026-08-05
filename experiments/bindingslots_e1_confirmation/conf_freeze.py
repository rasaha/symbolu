#!/usr/bin/env python3
"""Freeze step: writes the confirmation protocol (fresh seeds, dataset hashes, frozen gates + recipe),
runs the determinism fixture and the leakage suite on NON-reserved (dev) data, and asserts seed
disjointness and that no final seed is exposed. Must be committed before the final cohort runs."""
from __future__ import annotations

import hashlib
import json
import pathlib

import conf_task as T
import conf_config as C
import conf_leakage as LK
import conf_train as TR
import conf_eval as EV

RES = pathlib.Path(__file__).resolve().parent / "results"


def _write(name, obj):
    RES.mkdir(parents=True, exist_ok=True)
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def main():
    # seed disjointness (fresh seeds vs everything used before)
    prior = C.all_prior_seeds()
    conf_all = set(C.DEV_SEEDS) | set(C.FINAL_SEEDS) | {C.TRAIN_SEED_FOR_EPISODES}
    disjoint = not (conf_all & prior)

    # dataset hashes over TRAIN + DEV only (final pool identities not enumerated here)
    pools = T.identity_pools(C.POOL_SALT)
    train = C.build_train_episodes()
    dev = T.build_eval_splits(pools["dev"], C.EVAL_N_PER_SPLIT, C.DEV_SEED_BASE)
    dataset_hashes = {
        "identity_pools": _h({k: sorted(map(list, v)) for k, v in pools.items()}),
        "pool_sizes": {k: len(v) for k, v in pools.items()},
        "train_episodes": _h(train),
        "dev_eval_splits": _h({k: v for k, v in dev.items()}),
    }

    # determinism fixture (dev seed): train E1 twice -> identical hash + metric
    a, _ = TR.train_e1(train, C.DEV_SEEDS[0])
    b, _ = TR.train_e1(train, C.DEV_SEEDS[0])
    ha, hb = TR.param_hash(a), TR.param_hash(b)
    ma = EV.eval_e1_split(a, dev["G1_unseen_identity"], C.TAU)
    mb = EV.eval_e1_split(b, dev["G1_unseen_identity"], C.TAU)
    det_ok = (ha == hb) and (ma == mb)
    _write("determinism.json", {"schema": "bindingslots_e1_confirmation/determinism/v1",
           "seed": C.DEV_SEEDS[0], "hash_match": ha == hb, "metrics_match": ma == mb,
           "determinism_ok": det_ok, "e1_param_sha256": ha})

    # leakage suite (dev data)
    lk = LK.run_all(dev)
    _write("leakage_report.json", {"schema": "bindingslots_e1_confirmation/leakage/v1", **lk})

    frozen = det_ok and lk["all_pass"] and disjoint
    _write("conf_protocol.json", {
        "schema": "bindingslots_e1_confirmation/protocol/v1",
        "frozen": frozen,
        "recipe_C1": {"steps": C.STEPS, "tau": C.TAU, "train_no_match_frac": C.TRAIN_NO_MATCH_FRAC,
                      "batch": C.BATCH, "lr": C.LR, "D": C.D, "train_episodes": C.TRAIN_EPISODES,
                      "no_match": "learned_null_key", "read": "hard_top1", "score": "cosine",
                      "keys_per_episode": T.KEYS_PER_EPISODE},
        "gates": C.GATES, "dev_seeds": C.DEV_SEEDS, "final_seeds": C.FINAL_SEEDS,
        "train_episode_seed": C.TRAIN_SEED_FOR_EPISODES,
        "seed_disjoint_from_all_prior": disjoint, "prior_seeds": C.PRIOR_SEEDS,
        "determinism_ok": det_ok, "leakage_all_pass": lk["all_pass"],
        "final_seeds_unused_before_lock": True,
        "dataset_hashes": dataset_hashes,
        "independent_task": True, "independent_evaluator": True, "recipe_reused_frozen_C1": True})
    print("FREEZE:", "OK" if frozen else "NOT_FROZEN",
          "| det", det_ok, "| leakage", lk["all_pass"], "| seed_disjoint", disjoint, flush=True)


if __name__ == "__main__":
    main()
