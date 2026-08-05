#!/usr/bin/env python3
"""Confirmation config: the EXACT frozen C1 recipe + gates from the merged PR #1351, applied to the
independent task with FRESH seeds. Nothing is retuned."""
from __future__ import annotations

import pathlib
import sys

# frozen recipe + gates from the merged validated experiment (single source of truth)
E1_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1"
if str(E1_DIR) not in sys.path:
    sys.path.insert(0, str(E1_DIR))
import config as FROZEN   # noqa: E402

# ---- frozen C1 recipe (exact; not retuned) ---------------------------------------------
assert FROZEN.SELECTED == "C1", "confirmation requires the frozen C1 recipe"
STEPS = FROZEN.STEPS                 # 1200
TAU = FROZEN.TAU                     # 0.07
TRAIN_NO_MATCH_FRAC = FROZEN.TRAIN_NO_MATCH_FRAC   # 0.30
BATCH = FROZEN.BATCH                 # 48
LR = FROZEN.LR                       # 1e-3
D = FROZEN.D                         # 64
TRAIN_EPISODES = FROZEN.TRAIN_EPISODES   # 1500

# ---- same primary gate structure as PR #1351 (unchanged) -------------------------------
GATES = dict(FROZEN.GATES)
RESERVED_SEEDS_REQUIRED_TO_PASS = FROZEN.RESERVED_SEEDS_REQUIRED_TO_PASS   # 4 of 5

# ---- FRESH seeds (never used anywhere in the program) ----------------------------------
POOL_SALT = "e1_conf_pool_v1"
TRAIN_SEED_FOR_EPISODES = 71
DEV_SEEDS = [700, 701, 702]
DEV_SEED_BASE = 700
EVAL_N_PER_SPLIT = 150
FINAL_SEEDS = [5140, 5141, 5142, 5143, 5144]

# provenance: all previously-used seeds anywhere in the program (for the disjointness assertion)
PRIOR_SEEDS = {
    "v100_final": [28, 29, 30, 31, 32],
    "e1_dev": [500, 501, 502],
    "e1_burned": [2028, 2029, 2030, 2031, 2032],
    "e1_final": [3140, 3141, 3142, 3143, 3144],
    "e1_train_episode_seed": [7],
}


def all_prior_seeds():
    s = set()
    for v in PRIOR_SEEDS.values():
        s |= set(v)
    return s


def build_train_episodes():
    import conf_task as T
    return T.build_split(T.identity_pools(POOL_SALT)["train"], TRAIN_EPISODES,
                         seed=TRAIN_SEED_FOR_EPISODES, no_match_frac=TRAIN_NO_MATCH_FRAC)
