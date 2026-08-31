#!/usr/bin/env python3
"""Frozen configuration for the E1 latest-state three-factor 2^3 factorial.

Exact frozen C1 recipe (no retuning) + the GIVEN gate numbers + fresh, disjoint, approved seeds. The
eight cells differ ONLY in which minimal factor side-heads are enabled; every cell shares identical task
instances, seeds, training budget, base C1 configuration, and evaluation logic.
"""
from __future__ import annotations

import pathlib
import sys

TEMPORAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_temporal"
if str(TEMPORAL_DIR) not in sys.path:
    sys.path.insert(0, str(TEMPORAL_DIR))
import temporal_config as TC          # noqa: E402  (frozen C1 recipe + temporal gates + prior seeds)

# ---- exact frozen C1 recipe (inherited, unchanged) -------------------------------------
STEPS = TC.STEPS                      # 1200
TAU = TC.TAU                          # 0.07
TRAIN_NO_MATCH_FRAC = TC.TRAIN_NO_MATCH_FRAC   # 0.30
BATCH = TC.BATCH                      # 48
LR = TC.LR                            # 1e-3
D = TC.D                              # 64
TRAIN_EPISODES = TC.TRAIN_EPISODES    # 1500
POOL_SALT = TC.POOL_SALT              # same temporal identity partition

# ---- 2^3 factorial cells (code "abc": a=F1, b=F2, c=F3) --------------------------------
CELLS = {
    "000": (),
    "100": ("F1",),
    "010": ("F2",),
    "001": ("F3",),
    "110": ("F1", "F2"),
    "101": ("F1", "F3"),
    "011": ("F2", "F3"),
    "111": ("F1", "F2", "F3"),
}
REFERENCE_CELL = "000"

# ---- fresh approved seeds (mechanically verified disjoint; see seed_registry) ----------
TRAIN_SEED = 74
DEV_SEEDS = [740, 741, 742]
DEV_SEED_BASE = 740
FINAL_SEEDS = [7140, 7141, 7142, 7143, 7144]
EVAL_N_PER_SPLIT = 150
REQUIRED_TO_PASS = 4                  # of 5 final seeds

# every seed used anywhere earlier in the program, including the temporal phase
PRIOR_SEEDS = dict(TC.PRIOR_SEEDS)
PRIOR_SEEDS["temporal_train"] = [TC.TRAIN_SEED]        # 73
PRIOR_SEEDS["temporal_dev"] = list(TC.DEV_SEEDS)       # 720-722
PRIOR_SEEDS["temporal_final"] = list(TC.FINAL_SEEDS)   # 6140-6144


def all_prior_seeds():
    s = set()
    for v in PRIOR_SEEDS.values():
        s |= set(v)
    return s


def proposed_seeds():
    return set([TRAIN_SEED]) | set(DEV_SEEDS) | set(FINAL_SEEDS)


# ---- GIVEN gates (frozen before the first final seed; not derived from dev) ------------
# Metric conventions (documented, applied uniformly):
#   * T4 latest-state accuracy = NULL-INCLUSIVE correct-latest = P(argmax over K+1 == target index).
#     This is the honest end-to-end addressing decision (abstention counts as a miss) and is the metric
#     the three factors are designed to move (F1 abstention, F2 wrong-entity, F3 right-entity-wrong-older).
#   * Inherited T1/T2/T3/T6/T7/T9 gate on the inherited NULL-EXCLUDED addressing_top1 (argmax over real
#     keys), preserving the exact inherited gate metric; these are the regression guards.
GATES = {
    "T4_min": 0.85,                                   # null-inclusive correct-latest
    "T4_improvement_over_000_min": 0.05,              # mean, absolute, for a selected intervention
    "T1_min": TC.GATES["T1_min"], "T2_min": TC.GATES["T2_min"], "T3_min": TC.GATES["T3_min"],
    "T6_min": TC.GATES["T6_min"], "T7_min": TC.GATES["T7_min"],
    "T9_min_no_material_regression": TC.GATES["T9_min_no_material_regression"],   # 0.90
    "nomatch_max_false_accept": TC.GATES["nomatch_max_false_accept"],   # 0.30
    "nomatch_max_false_reject": TC.GATES["nomatch_max_false_reject"],   # 0.15
    "required_seeds_pass": REQUIRED_TO_PASS,
}
INHERITED_SPLIT_MINS = {"T1": GATES["T1_min"], "T2": GATES["T2_min"], "T3": GATES["T3_min"],
                        "T6": GATES["T6_min"], "T7": GATES["T7_min"],
                        "T9": GATES["T9_min_no_material_regression"]}
# T5 predecessor/successor is a REPORTED DIAGNOSTIC ONLY — never a gate, never in selection or verdict.

PRESERVE = ["E1_TEMPORAL_TRANSFER_PARTIAL",
            "ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED",
            "KDA_VALIDATION_BLOCKED"]


def build_train_episodes(seed=None):
    import temporal_task as T
    return T.build_train_episodes(T.identity_pools(POOL_SALT)["train"], TRAIN_EPISODES,
                                  seed=TRAIN_SEED if seed is None else seed,
                                  no_match_frac=TRAIN_NO_MATCH_FRAC)
