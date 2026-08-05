#!/usr/bin/env python3
"""Frozen config for the Temporal Event Memory transfer test: the EXACT C1 recipe + the GIVEN gates +
fresh approved seeds. Nothing is retuned; gates are fixed by the task prompt, not by dev results."""
from __future__ import annotations

import pathlib
import sys

E1_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1"
if str(E1_DIR) not in sys.path:
    sys.path.insert(0, str(E1_DIR))
import config as FROZEN   # noqa: E402

# ---- exact frozen C1 recipe (no change) ------------------------------------------------
assert FROZEN.SELECTED == "C1"
STEPS = FROZEN.STEPS            # 1200
TAU = FROZEN.TAU               # 0.07
TRAIN_NO_MATCH_FRAC = FROZEN.TRAIN_NO_MATCH_FRAC   # 0.30
BATCH = FROZEN.BATCH           # 48
LR = FROZEN.LR                 # 1e-3
D = FROZEN.D                   # 64
TRAIN_EPISODES = FROZEN.TRAIN_EPISODES   # 1500

# ---- approved seeds (fresh) ------------------------------------------------------------
POOL_SALT = "e1_temporal_pool_v1"
TRAIN_SEED = 73
DEV_SEEDS = [720, 721, 722]
DEV_SEED_BASE = 720
EVAL_N_PER_SPLIT = 150
FINAL_SEEDS = [6140, 6141, 6142, 6143, 6144]
REQUIRED_TO_PASS = 4           # of 5

PRIOR_SEEDS = {
    "v100_final": [28, 29, 30, 31, 32], "e1_dev": [500, 501, 502],
    "e1_burned": [2028, 2029, 2030, 2031, 2032], "e1_final": [3140, 3141, 3142, 3143, 3144],
    "e1_train_seed": [7], "conf_train": [71], "conf_dev": [700, 701, 702],
    "conf_final": [5140, 5141, 5142, 5143, 5144],
}


def all_prior_seeds():
    s = set()
    for v in PRIOR_SEEDS.values():
        s |= set(v)
    return s


# ---- GIVEN gates (frozen before the first final seed; not derived from dev) -------------
GATES = {
    "improvement_over_b0_min": 0.50,       # on the primary structural score (macro-avg T3,T4)
    "T1_min": 0.80, "T2_min": 0.80, "T3_min": 0.80, "T4_min": 0.85, "T6_min": 0.80, "T7_min": 0.80,
    "T9_min_no_material_regression": 0.90,  # inherited G7 stable bar (0.90) as "no material regression"
    # no-match ceilings inherited from PR #1352
    "nomatch_max_false_accept": FROZEN.GATES["nomatch_max_false_accept"],   # 0.30
    "nomatch_max_false_reject": FROZEN.GATES["valid_max_false_reject"],     # 0.15
    "nomatch_min_recall": FROZEN.GATES["nomatch_min_recall"],               # 0.70
    "nomatch_min_precision": FROZEN.GATES["nomatch_min_precision"],         # 0.70
    "worst_seed_min_T3T4_floor": FROZEN.GATES["worst_seed_min_G1_addr"],    # 0.70
    "required_seeds_pass": REQUIRED_TO_PASS,
}
# T5 predecessor/successor is a REPORTED DIAGNOSTIC — never a gate.


def build_train_episodes():
    import temporal_task as T
    return T.build_train_episodes(T.identity_pools(POOL_SALT)["train"], TRAIN_EPISODES,
                                  seed=TRAIN_SEED, no_match_frac=TRAIN_NO_MATCH_FRAC)
