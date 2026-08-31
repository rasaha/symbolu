#!/usr/bin/env python3
"""Frozen configuration for the frozen-representation readout DIAGNOSTIC.

The base encoder is the merged temporal E1 checkpoint (deterministically reconstructed at temporal final
seed 6140; its param hash matches the committed PR #1354 evidence). Every base parameter is frozen; only the
new readout-head parameters are trained. Gate numbers are the GIVEN a-priori numbers (grounded in the R0
baseline + a meaningful effect size, NOT tuned on any readout result); they are frozen here before dev.
"""
from __future__ import annotations

import pathlib
import sys

TEMPORAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_temporal"
FACTOR_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_3factor"
for p in (str(TEMPORAL_DIR), str(FACTOR_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)
import temporal_config as TC        # noqa: E402  (frozen C1 recipe + temporal gates + prior seeds)

# ---- frozen C1 recipe (inherited, unchanged; base is FROZEN — used only for the readout optimizer) ----
STEPS = TC.STEPS                    # 1200 readout-only steps
TAU = TC.TAU                        # 0.07 (frozen)
BATCH = TC.BATCH                    # 48
LR = TC.LR                          # 1e-3
D = TC.D                            # 64
TRAIN_EPISODES = TC.TRAIN_EPISODES  # 1500
TRAIN_NO_MATCH_FRAC = TC.TRAIN_NO_MATCH_FRAC   # 0.30
POOL_SALT = TC.POOL_SALT

# ---- frozen base checkpoint (provenance: committed temporal PR #1354 evidence) ----
FROZEN_ENCODER_SEED = 6140         # temporal final seed; reconstructs byte-identically to committed hash
FROZEN_ENCODER_COMMITTED_SHA256 = "f81e72c8e41c78d7"   # prefix cross-check (full verified at build time)

# ---- arms ----
ARMS = ["R0", "R1", "R2", "R3"]
LEARNED_ARMS = ["R1", "R2"]        # only these can emit SIGNAL_PRESENT
REFERENCE_ARM = "R0"
STRUCTURAL_ARM = "R3"              # diagnostic upper bound; never selectable as primary

# ---- readout hidden sizes (fixed BEFORE any development execution) ----
R1_HIDDEN = 32
R2_HIDDEN = 32                     # per head
R3_HIDDEN = 32                     # per head

# ---- fresh approved seeds (mechanically verified disjoint; see seed check) ----
TRAIN_SEED = 75
DEV_SEEDS = [750, 751, 752]
FINAL_SEEDS = [7150, 7151, 7152, 7153, 7154]
EVAL_N_PER_SPLIT = 150
REQUIRED_TO_PASS = 4               # of 5

PRIOR_SEEDS = dict(TC.PRIOR_SEEDS)
PRIOR_SEEDS["temporal_train"] = [TC.TRAIN_SEED]          # 73
PRIOR_SEEDS["temporal_dev"] = list(TC.DEV_SEEDS)         # 720-722
PRIOR_SEEDS["temporal_final"] = list(TC.FINAL_SEEDS)     # 6140-6144
PRIOR_SEEDS["factorial_train"] = [74]
PRIOR_SEEDS["factorial_dev"] = [740, 741, 742]
PRIOR_SEEDS["factorial_final"] = [7140, 7141, 7142, 7143, 7144]


def all_prior_seeds():
    s = set()
    for v in PRIOR_SEEDS.values():
        s |= set(v)
    return s


def proposed_seeds():
    return {TRAIN_SEED} | set(DEV_SEEDS) | set(FINAL_SEEDS)


# ---- GIVEN gates (a-priori; frozen before dev; NOT derived from any readout result) ----
# All gates apply to null-inclusive T4 (P(argmax over K+1 == target)) unless stated otherwise.
# Inherited T1/T2/T3/T6/T7/T9 gate on null-excluded addressing_top1 (regression guards), as in the factorial.
GATES = {
    "present_min_seeds": REQUIRED_TO_PASS,          # >=4/5
    "present_mean_T4_min": 0.75,
    "present_mean_improvement_over_R0_min": 0.10,
    "partial_min_seeds": REQUIRED_TO_PASS,
    "partial_mean_T4_min": 0.68,
    "partial_mean_improvement_over_R0_min": 0.05,
    # inherited (from the temporal/factorial GIVEN gates)
    "T1_min": TC.GATES["T1_min"], "T2_min": TC.GATES["T2_min"], "T3_min": TC.GATES["T3_min"],
    "T6_min": TC.GATES["T6_min"], "T7_min": TC.GATES["T7_min"],
    "T9_min_no_material_regression": TC.GATES["T9_min_no_material_regression"],
    "nomatch_max_false_accept": TC.GATES["nomatch_max_false_accept"],   # 0.30
    "nomatch_max_false_reject": TC.GATES["nomatch_max_false_reject"],   # 0.15
    # shortcut-baseline ceiling (both lexical + global-latest must be <= this on the final cohort)
    "shortcut_baseline_max": 0.15,
}

PRESERVE = ["E1_TEMPORAL_TRANSFER_PARTIAL",
            "ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED",
            "KDA_VALIDATION_BLOCKED"]
NEVER_EMIT = ["E1_TEMPORAL_TRANSFER_VALIDATED", "E1_STRUCTURAL_TRANSFER_CONFIRMED",
              "E1_FOLLOW_ON_RESEARCH_ELIGIBLE"]
CONCLUSIONS = ["FROZEN_REPRESENTATION_READOUT_SIGNAL_PRESENT",
               "FROZEN_REPRESENTATION_READOUT_SIGNAL_PARTIAL",
               "FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND",
               "FROZEN_REPRESENTATION_READOUT_PROTOCOL_VIOLATED",
               "FROZEN_REPRESENTATION_READOUT_RESOURCE_BLOCKED"]


def build_train_episodes():
    import temporal_task as T
    return T.build_train_episodes(T.identity_pools(POOL_SALT)["train"], TRAIN_EPISODES,
                                  seed=TRAIN_SEED, no_match_frac=TRAIN_NO_MATCH_FRAC)
